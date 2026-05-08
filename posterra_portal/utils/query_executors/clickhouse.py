# -*- coding: utf-8 -*-
"""ClickHouse executor.

Talks HTTPS to a ClickHouse cluster via ``clickhouse-connect``. The
driver is imported lazily so this module loads cleanly even on hosts
that haven't installed the dependency yet — the driver is only required
when an admin actually creates a CH-backed schema source.

Tenancy: every query ships ``SQL_tenant_id`` as a per-query setting
inside ``client.query(settings={'SQL_tenant_id': '<id>', ...})``. CH
row policies (defined cluster-side) read it via
``getSetting('SQL_tenant_id')`` and filter rows accordingly. The
setting and the query travel in the same HTTP request so the binding
is atomic — there is no cached session state for concurrent requests
to race on. ``connection.requires_tenant_filter`` must stay True for
any connection user-facing widgets touch; set False only for admin
tooling that legitimately reads cross-tenant aggregates.

Do NOT reintroduce ``client.command('SET SQL_tenant_id = ...')``
followed by ``client.query(...)`` "for performance" — the cached
clickhouse-connect client is shared across worker threads, and a
two-step pattern races (thread A's SET overwritten by thread B before
A's query reaches the server). The race silently leaks rows across
tenants, which is the failure mode this whole layer exists to prevent.

Connection caching: clients are cached per-process keyed by connection
id. ``dashboard.connection.write()`` and ``unlink()`` call
``_invalidate_client(connection.id)`` so password rotation / host change
takes effect without an Odoo restart. Rotating the password under
``password_param_key`` (an ``ir.config_parameter`` row) does NOT
trigger ``write()`` on the connection record — admins must click the
**Invalidate Cache** button (or **Test Connection**, which auto-
invalidates) to flush the cached client. Each Odoo worker has its own
cache, so peak open client count is ``workers × connections`` — keep
both numbers small in production sizing.
"""

import datetime
import logging
import os
import re
import threading

from .base import BaseQueryExecutor

_logger = logging.getLogger(__name__)


# ── Per-worker client cache ─────────────────────────────────────────────────
_clients = {}
_clients_lock = threading.Lock()


def _invalidate_client(connection_id):
    """Drop the cached client for ``connection_id``.

    Called from ``dashboard.connection.write()`` and ``unlink()`` so
    config changes (password, host, port) take effect immediately
    without an Odoo restart.
    """
    with _clients_lock:
        client = _clients.pop(connection_id, None)
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


def _get_password(env, connection):
    """Resolve the password for a connection.

    Priority:
      1. ``os.environ[connection.password_param_key]`` — production path.
         The admin sets ``password_param_key`` to a stable name (e.g.
         ``POSTERRA_CH_PASSWORD_PROD``); ESO syncs the secret from Azure
         Key Vault into a Kubernetes Secret with the same name, mounted
         as an env var on every pod. We deliberately key by the
         admin-supplied string, NOT ``connection.id`` — IDs shift across
         fresh-seed deploys, so id-keyed env vars would break on every
         redeploy.
      2. ``connection.password`` — admin-typed direct field. Common in
         dev / single-pod installs.
      3. ``connection.password_param_key`` → ``ir.config_parameter``
         lookup. Legacy indirection retained for installs already using
         it; takes effect when neither env nor direct field is set.
      4. Empty string — auth will fail, but cleanly.

    Cache invalidation: rotation requires a rolling pod restart
    (``kubectl rollout restart deploy/odoo-http``) — clickhouse-connect
    clients are cached per worker keyed by ``connection.id`` and don't
    notice env-var changes. Documented in the rotate-secrets runbook.
    """
    key = connection.password_param_key or ''
    if key:
        env_secret = os.environ.get(key)
        if env_secret:
            return env_secret
    direct = getattr(connection, 'password', '') or ''
    if direct:
        return direct
    if key:
        return env['ir.config_parameter'].sudo().get_param(key, '')
    return ''


def _coerce_port(value, default=8443):
    """Coerce a Char port field to int for clickhouse-connect.

    The connection record stores ``port`` as Char (so the admin form
    renders ``8443`` cleanly without a locale thousands separator).
    clickhouse-connect's ``get_client`` accepts int or str, but
    explicit int avoids any ambiguity.
    """
    if value in (None, '', False):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_client(env, connection):
    """Lazy-create + cache a clickhouse-connect client for this connection."""
    with _clients_lock:
        client = _clients.get(connection.id)
        if client is not None:
            return client

    try:
        import clickhouse_connect
    except ImportError as exc:
        raise RuntimeError(
            "clickhouse-connect is not installed. Run "
            "'pip install clickhouse-connect' on the Odoo host before "
            "creating ClickHouse connections."
        ) from exc

    client = clickhouse_connect.get_client(
        host=connection.host,
        port=_coerce_port(connection.port),
        username=connection.username or '',
        password=_get_password(env, connection),
        database=connection.database or 'default',
        secure=bool(connection.use_tls),
        connect_timeout=10,
        send_receive_timeout=60,
    )

    with _clients_lock:
        # Another thread may have created one while we were connecting —
        # keep theirs and close ours.
        existing = _clients.get(connection.id)
        if existing is not None:
            try:
                client.close()
            except Exception:
                pass
            return existing
        _clients[connection.id] = client
    return client


# ── Placeholder translation: %(name)s → {name:Type} ─────────────────────────
#
# Widget SQL is authored with psycopg2 named placeholders; clickhouse-connect
# expects ``{name:Type}`` style. We translate at execute-time so admins write
# one dialect of placeholder and it works for both backends.

_PG_PARAM_RE = re.compile(r'%\(([^)]+)\)s')


def _infer_ch_type(value):
    """Map a Python value to a ClickHouse type literal for placeholder
    translation.

    Order matters: bool is a subclass of int, so it must be checked first.
    Lists/tuples become ``Array(<inner>)`` for IN clauses; the inner type
    is inferred from the first non-None element, defaulting to String.
    None becomes ``Nullable(String)`` — works for any nullable column.
    """
    if value is None:
        return 'Nullable(String)'
    if isinstance(value, bool):
        return 'UInt8'
    if isinstance(value, int):
        return 'Int64'
    if isinstance(value, float):
        return 'Float64'
    if isinstance(value, datetime.datetime):
        return 'DateTime'
    if isinstance(value, datetime.date):
        return 'Date'
    if isinstance(value, (list, tuple)):
        inner = 'String'
        for item in value:
            if item is None:
                continue
            if isinstance(item, bool):
                inner = 'UInt8'
                break
            if isinstance(item, int):
                inner = 'Int64'
                break
            if isinstance(item, float):
                inner = 'Float64'
                break
            if isinstance(item, datetime.datetime):
                inner = 'DateTime'
                break
            if isinstance(item, datetime.date):
                inner = 'Date'
                break
            inner = 'String'
            break
        return f'Array({inner})'
    return 'String'


def translate_params(sql, params):
    """Rewrite ``%(name)s`` placeholders to ``{name:Type}`` for CH.

    Returns the rewritten SQL. Parameter values themselves are passed
    through to clickhouse-connect's ``parameters=`` kwarg, which handles
    the actual binding (escaping, array packing, etc.).
    """
    types = {k: _infer_ch_type(v) for k, v in params.items()}

    def _replace(match):
        name = match.group(1)
        # Unknown placeholder → keep as String; binding will set NULL.
        return '{%s:%s}' % (name, types.get(name, 'String'))

    return _PG_PARAM_RE.sub(_replace, sql)


# ── Safety: SELECT-only, no DML/DDL — extends the Postgres-side regex ──────
#
# Posterra's existing widget validator (dashboard_widget._BLOCKED_KEYWORDS)
# blocks INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/CREATE/GRANT/REVOKE/COPY/
# EXECUTE. ClickHouse adds a few engine-specific verbs we want to refuse
# from admin-authored SQL (OPTIMIZE rewrites parts; ATTACH/DETACH attaches
# foreign tables; SYSTEM runs cluster-level commands).

_BLOCKED_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|'
    r'EXECUTE|OPTIMIZE|ATTACH|DETACH|SYSTEM|RENAME|REPLACE)\b',
    re.IGNORECASE,
)


def _validate_select_only(query):
    """Refuse anything that isn't a SELECT or a WITH/CTE."""
    cleaned = re.sub(r'/\*.*?\*/', ' ', query, flags=re.DOTALL)
    cleaned = re.sub(r'--[^\n]*', ' ', cleaned)
    first = cleaned.strip().split()[0].upper() if cleaned.strip() else ''
    if first not in ('SELECT', 'WITH'):
        raise ValueError('Only SELECT or WITH queries are allowed against ClickHouse.')
    if _BLOCKED_KEYWORDS.search(cleaned):
        raise ValueError('SQL contains a disallowed keyword (DML/DDL not permitted).')


class ClickHouseExecutor(BaseQueryExecutor):
    """ClickHouse executor with per-query tenant context + safety
    validation.

    Tenant isolation strategy: ``SQL_tenant_id`` is sent as a per-query
    setting (``client.query(settings={'SQL_tenant_id': '<id>'})``), NOT
    as a session-level ``SET`` command. The cached client is shared
    across threads/requests, so any session-state approach
    (``client.command('SET ...')`` followed by ``client.query(...)``)
    races: thread A's SET could be overwritten by thread B before
    thread A's query runs. clickhouse-connect ships the per-query
    settings inside the same HTTP request, so the SET and the query
    are atomic from the server's perspective. The CH-side row policy
    reads ``getSetting('SQL_tenant_id')`` which sees the per-query
    value transparently.

    Prerequisite (CH-side DDL): a settings profile must declare
    ``SQL_tenant_id`` with ``READONLY = 0`` so the role can supply
    it per query — see Phase 4 DDL in the ClickHouse plan.
    """

    def execute(self, query, params):
        _validate_select_only(query)
        client = _get_client(self.env, self.connection)

        # Per-query resource limits — defence against runaway queries.
        timeout = self.connection.query_timeout_seconds or 30
        settings = {
            'max_execution_time': timeout,
            # Hard caps to prevent a single query exhausting the cluster.
            # 10 GiB and 1B rows are conservative; admins can override
            # by adding fields to the connection model later.
            'max_memory_usage': 10 * 1024 * 1024 * 1024,
            'max_rows_to_read': 1_000_000_000,
        }

        if self.connection.requires_tenant_filter:
            tenant_id = self.get_tenant_id()
            if tenant_id is None:
                raise ValueError(
                    "Connection requires tenant filter but no tenant_id "
                    "could be resolved from the request context"
                )
            # Per-query setting — atomic, no session state, thread-safe
            # across the shared client. CH row policies read this via
            # getSetting('SQL_tenant_id') and filter rows accordingly.
            settings['SQL_tenant_id'] = str(tenant_id)
        else:
            _logger.warning(
                'CH connection %s ran a query with requires_tenant_filter=False '
                '— admin tooling only, ensure this is intentional.',
                self.connection.name,
            )

        ch_query = translate_params(query, params)
        try:
            result = client.query(
                ch_query, parameters=params, settings=settings,
            )
        except Exception as exc:
            _logger.warning(
                'ClickHouse query failed (connection=%s): %s',
                self.connection.name, exc,
            )
            _logger.debug('Failed CH SQL: %s', ch_query)
            raise

        rows = [tuple(r) for r in result.result_rows]
        return list(result.column_names), rows

    def discover_columns(self, table_name):
        client = _get_client(self.env, self.connection)
        # Allow ``schema.table`` form too — split on the first dot.
        if '.' in table_name:
            db, tbl = table_name.split('.', 1)
        else:
            db = self.connection.database or 'default'
            tbl = table_name
        result = client.query(
            "SELECT name, type FROM system.columns "
            "WHERE database = {db:String} AND table = {tbl:String} "
            "ORDER BY position",
            parameters={'db': db, 'tbl': tbl},
        )
        return [(name, type_) for name, type_ in result.result_rows]

    def ping(self):
        client = _get_client(self.env, self.connection)
        result = client.query("SELECT 1")
        return list(result.result_rows) == [(1,)]
