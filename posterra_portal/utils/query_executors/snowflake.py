# -*- coding: utf-8 -*-
"""Snowflake executor — hospital-scoped PHI connector.

Talks to Snowflake via ``snowflake-connector-python`` (lazy-imported so this
module loads cleanly on hosts without the driver — the driver is only needed
when an admin actually creates a Snowflake connection).

Isolation model (NOT a ClickHouse-style per-query session variable):
  Snowflake has no atomic per-query custom setting like CH's ``SQL_tenant_id``;
  ``QUERY_TAG`` / session variables are session state and race on the shared
  cached connection. So isolation does NOT depend on Snowflake receiving
  dynamic Odoo context. Instead:
    1. The executor's four-condition PHI guard verifies, before any SQL, that
       the request app's immutable ``org_id`` == the connection's scoped app
       ``org_id`` (plus connection active + configuration_verified + source
       source_verified).
    2. The connection authenticates as a dedicated hospital service role that
       can read ONLY that hospital's approved secure views (no base-table /
       cross-hospital grants) — the grants ARE the boundary.
  ``QUERY_TAG=org_id`` is set once at connect for audit correlation only.

Credentials are Snowflake-only: the ``sf_*`` fields, resolved env-first. This
module NEVER reads the shared ``password``/``password_param_key`` fields (those
belong to ClickHouse) and never logs secret values or SQL params.

Connection caching: one client per (worker, connection.id), like the CH
executor. ``dashboard.connection.write()``/``unlink()`` call
``_invalidate_client`` so credential/host changes take effect without a
restart.
"""

import logging
import os
import re
import threading

from .base import BaseQueryExecutor

_logger = logging.getLogger(__name__)


# ── Per-worker connection cache ─────────────────────────────────────────────
_connections = {}
_connection_query_locks = {}
_connections_lock = threading.Lock()


def _invalidate_client(connection_id):
    """Drop the cached Snowflake connection for ``connection_id``.

    Named identically to the CH module's symbol so
    ``dashboard.connection._invalidate_one`` calls both uniformly. No-op when
    nothing is cached, so it's always safe to call.
    """
    with _connections_lock:
        conn = _connections.pop(connection_id, None)
        _connection_query_locks.pop(connection_id, None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


# ── Credential resolution — Snowflake-only, env-first, never logged ─────────
def _resolve_secret(env, direct_value, param_key):
    """env[param_key] → direct field → ir.config_parameter[param_key] → ''."""
    if param_key:
        env_secret = os.environ.get(param_key)
        if env_secret:
            return env_secret
    if direct_value:
        return direct_value
    if param_key:
        return env['ir.config_parameter'].sudo().get_param(param_key, '')
    return ''


def _get_sf_password(env, connection):
    return _resolve_secret(
        env, connection.sf_password, connection.sf_password_param_key)


def _get_sf_private_key(env, connection):
    return _resolve_secret(
        env, connection.sf_private_key, connection.sf_private_key_param_key)


def _get_sf_passphrase(env, connection):
    return _resolve_secret(
        env, connection.sf_private_key_passphrase,
        connection.sf_passphrase_param_key)


def _pem_to_der(pem_text, passphrase):
    """Load a PEM RSA private key (encrypted PKCS#8 supported) and return
    unencrypted PKCS#8 DER bytes for ``snowflake.connector.connect(
    private_key=...)``."""
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import serialization
    except ImportError as exc:
        raise RuntimeError(
            "The 'cryptography' package is required for Snowflake key-pair "
            "auth. It ships with snowflake-connector-python; ensure both are "
            "installed on the Odoo host."
        ) from exc

    pem_bytes = pem_text.encode() if isinstance(pem_text, str) else pem_text
    pw = None
    if passphrase:
        pw = passphrase.encode() if isinstance(passphrase, str) else passphrase

    key = serialization.load_pem_private_key(
        pem_bytes, password=pw, backend=default_backend())
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _build_connect_kwargs(env, connection):
    """host/port/use_tls are intentionally ignored — Snowflake derives the
    endpoint from the account identifier."""
    timeout = connection.query_timeout_seconds or 30
    kwargs = {
        'account': connection.sf_account or '',
        'user': connection.username or '',
        'warehouse': connection.sf_warehouse or None,
        'database': connection.database or None,
        'schema': connection.sf_db_schema or None,
        'role': connection.sf_role or None,
        'login_timeout': 10,
        'network_timeout': 60,
        # client_session_keep_alive deliberately OFF — we validate-on-reuse
        # and reconnect-once instead of holding background heartbeats.
        'client_session_keep_alive': False,
        'session_parameters': {
            'STATEMENT_TIMEOUT_IN_SECONDS': timeout,
        },
    }
    # QUERY_TAG = org_id for audit correlation only (constant per connection;
    # never mutated per request). Only meaningful for hospital_phi.
    if connection.security_profile == 'hospital_phi' and connection.org_id:
        kwargs['session_parameters']['QUERY_TAG'] = str(connection.org_id)

    if (connection.auth_method or 'key_pair') == 'key_pair':
        pem = _get_sf_private_key(env, connection)
        if not pem:
            raise RuntimeError(
                f"Connection {connection.name!r} uses key-pair auth but no "
                "private key was found (set the key or its Config Key).")
        kwargs['private_key'] = _pem_to_der(pem, _get_sf_passphrase(env, connection))
    else:
        kwargs['password'] = _get_sf_password(env, connection)

    return {k: v for k, v in kwargs.items() if v is not None}


def _connect(env, connection):
    try:
        import snowflake.connector  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "snowflake-connector-python is not installed. Run "
            "'pip install snowflake-connector-python' on the Odoo host before "
            "creating Snowflake connections."
        ) from exc
    import snowflake.connector as sf
    return sf.connect(**_build_connect_kwargs(env, connection))


def _connection_alive(conn):
    """Cheap liveness check before reusing a cached connection."""
    try:
        closed = conn.is_closed()
    except Exception:
        return False
    return not closed


def _get_connection(env, connection):
    """Lazy-create + cache a Snowflake connection (double-checked locking).
    Validates the cached connection before reuse; reconnects if dead."""
    with _connections_lock:
        conn = _connections.get(connection.id)
    if conn is not None and _connection_alive(conn):
        return conn
    if conn is not None:
        _invalidate_client(connection.id)

    new_conn = _connect(env, connection)
    with _connections_lock:
        existing = _connections.get(connection.id)
        if existing is not None and _connection_alive(existing):
            try:
                new_conn.close()
            except Exception:
                pass
            return existing
        _connections[connection.id] = new_conn
        _connection_query_locks.setdefault(connection.id, threading.Lock())
    return new_conn


def _get_query_lock(connection_id):
    """A cached connection's cursor isn't safe for concurrent queries across
    worker threads — serialize per connection (same reasoning as CH)."""
    with _connections_lock:
        return _connection_query_locks.setdefault(connection_id, threading.Lock())


# ── Safety: SELECT/WITH only, single statement, no DML/DDL ──────────────────
_BLOCKED_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|'
    r'EXECUTE|RENAME|REPLACE)\b',
    re.IGNORECASE,
)


def _strip_comments(query):
    cleaned = re.sub(r'/\*.*?\*/', ' ', query, flags=re.DOTALL)
    cleaned = re.sub(r'--[^\n]*', ' ', cleaned)
    return cleaned


def _validate_select_only(query):
    """Refuse anything that isn't a single SELECT/WITH statement.

    The real boundary is the read-only Snowflake role (SELECT grants only);
    this regex is defense-in-depth. We deliberately do NOT block high-false-
    positive verbs like GET/PUT/LIST that collide with column/alias names.
    """
    cleaned = _strip_comments(query)
    first = cleaned.strip().split()[0].upper() if cleaned.strip() else ''
    if first not in ('SELECT', 'WITH'):
        raise ValueError('Only SELECT or WITH queries are allowed against Snowflake.')
    # Reject multiple statements (more than one meaningful ;-separated stmt).
    if len([s for s in cleaned.split(';') if s.strip()]) > 1:
        raise ValueError('Multiple SQL statements are not allowed.')
    if _BLOCKED_KEYWORDS.search(cleaned):
        raise ValueError('SQL contains a disallowed keyword (DML/DDL not permitted).')


# ── Deterministic IN-expansion via a SQL-aware scanner ──────────────────────
#
# snowflake-connector-python (paramstyle=pyformat) binds scalar %(name)s
# natively, but does NOT reliably expand a single list/tuple into an IN list,
# and the singleton ('__all__',) sentinel renders as invalid SQL. So we
# rewrite each collection-valued placeholder used in an IN expression into
# individually-bound scalars, refusing collection params used outside IN.

_PLACEHOLDER_RE = re.compile(r'%\(([^)]+)\)s')


def _mask_literals(sql):
    """Return a copy of ``sql`` with string literals and comments replaced by
    same-length spaces, so placeholder scanning ignores them while character
    offsets stay aligned with the original."""
    out = list(sql)
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        # line comment
        if ch == '-' and i + 1 < n and sql[i + 1] == '-':
            while i < n and sql[i] != '\n':
                out[i] = ' '
                i += 1
            continue
        # block comment
        if ch == '/' and i + 1 < n and sql[i + 1] == '*':
            while i < n and not (sql[i] == '*' and i + 1 < n and sql[i + 1] == '/'):
                out[i] = ' '
                i += 1
            if i < n:
                out[i] = ' '
                if i + 1 < n:
                    out[i + 1] = ' '
                i += 2
            continue
        # single-quoted string (handles '' escape)
        if ch == "'":
            out[i] = ' '
            i += 1
            while i < n:
                if sql[i] == "'" and i + 1 < n and sql[i + 1] == "'":
                    out[i] = out[i + 1] = ' '
                    i += 2
                    continue
                done = sql[i] == "'"
                out[i] = ' '
                i += 1
                if done:
                    break
            continue
        i += 1
    return ''.join(out)


def _expand_in_params(sql, params):
    """Rewrite ``IN %(name)s`` / ``NOT IN %(name)s`` (and the parenthesised
    forms) for collection-valued params into ``IN (%(name__0)s, ...)`` with
    individually-bound scalars. Returns ``(new_sql, new_params)``.

    - Handles every occurrence of a collection placeholder.
    - Empty collection → a guaranteed-false predicate ``IN (NULL)``.
    - Rejects a collection param used outside an IN expression.
    - Ignores placeholders inside string literals / comments.
    - Generated names (``name__0``) are collision-checked against existing keys.
    """
    masked = _mask_literals(sql)
    collection_keys = {
        k for k, v in params.items() if isinstance(v, (list, tuple))
    }
    if not collection_keys:
        return sql, params

    # "<IN> %(name)s" (bare) vs "<IN> ( %(name)s )" (author already wrote the
    # parens). We must NOT double-wrap the latter into IN ((...)).
    in_bare_re = re.compile(r'\bIN\s*$', re.IGNORECASE)
    in_paren_re = re.compile(r'\bIN\s*\(\s*$', re.IGNORECASE)

    new_params = dict(params)

    # Render each collection key's INNER list ONCE (no parens) so repeated
    # occurrences of the same placeholder reuse the same scalar names/values.
    inner_for = {}
    for name in collection_keys:
        values = list(params[name])
        if not values:
            inner_for[name] = 'NULL'  # guaranteed-false predicate
            continue
        scalar_names = []
        for idx, val in enumerate(values):
            sn = f'{name}__{idx}'
            while sn in params:  # collision-safe against caller-supplied keys
                sn = f'{sn}_'
            new_params[sn] = val
            scalar_names.append(sn)
        inner_for[name] = ', '.join('%(' + s + ')s' for s in scalar_names)

    # Find every (in-IN) occurrence of a collection placeholder; reject any
    # collection placeholder used outside an IN expression.
    replacements = []
    for m in _PLACEHOLDER_RE.finditer(masked):
        name = m.group(1)
        if name not in collection_keys:
            continue
        preceding = masked[:m.start()]
        if in_paren_re.search(preceding):
            text = inner_for[name]            # author supplied the parens
        elif in_bare_re.search(preceding):
            text = '(' + inner_for[name] + ')'  # bare IN — add the parens
        else:
            raise ValueError(
                f"Collection parameter %({name})s is only supported inside an "
                "IN (...) expression.")
        replacements.append((m.start(), m.end(), text))

    # Apply right-to-left so indices stay valid.
    new_sql = sql
    for start, end, text in sorted(replacements, key=lambda r: r[0], reverse=True):
        new_sql = new_sql[:start] + text + new_sql[end:]

    # Drop the original collection keys (now expanded) so they don't bind.
    for k in collection_keys:
        new_params.pop(k, None)
    return new_sql, new_params


# ── Identifier safety for discover/validate FROM clauses ────────────────────
_SF_TABLE_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*){0,2}$')


def _safe_sf_table(table_name):
    """Validate a Snowflake object name (TABLE / SCHEMA.TABLE / DB.SCHEMA.TABLE)
    of unquoted identifiers. Used only for admin discover/validate probes where
    we build the FROM clause. Rejects anything that could carry injection."""
    name = (table_name or '').strip()
    if not _SF_TABLE_RE.match(name):
        raise ValueError(
            f"Unsupported Snowflake object name {table_name!r}; expected "
            "TABLE, SCHEMA.TABLE, or DATABASE.SCHEMA.TABLE of simple "
            "identifiers.")
    return name


class SnowflakeExecutor(BaseQueryExecutor):
    """Hospital-scoped Snowflake executor with a fail-closed four-condition PHI
    guard, two-event append-only audit, deterministic IN-expansion, and bounded
    result controls.

    Result limits (executor layer): bounded ``fetchmany`` (never ``fetchall``)
    with a raw row cap + raw-value size safety. Exceeding the cap cancels the
    cursor and raises — never a silently truncated table. The post-formatting
    payload byte cap is enforced separately at the controller layer.
    """

    # Executor-layer result safety caps (controller layer adds the
    # post-formatting payload-byte cap).
    _FETCH_BATCH = 5000
    _MAX_ROWS = 200_000
    _MAX_QUERY_CHARS = 100_000
    _MAX_PARAMS = 2_000

    # ── Org resolver — NEVER the shared get_tenant_id (CH contract) ────
    def get_org_id(self):
        from ..tenant_context import get_current_org_id
        try:
            from odoo.http import request
        except Exception:
            request = None
        return get_current_org_id(self.env, request)

    # ── Four-condition PHI guard ───────────────────────────────────────
    def _enforce_phi_guard(self, execution_context):
        from odoo.exceptions import AccessError
        conn = self.connection
        if conn.security_profile != 'hospital_phi':
            return  # standard Snowflake connection — no PHI guard
        if not conn.configuration_verified:
            raise AccessError("Snowflake connection is not verified.")
        if not self.schema_source or not self.schema_source.source_verified:
            raise AccessError("PHI schema source is not verified.")
        configured = conn.org_id
        current = self.get_org_id()
        if not configured or not current or current != configured:
            raise AccessError(
                "Snowflake connection is not authorized for this hospital.")
        # PHI execution must carry audit context.
        if not execution_context or not execution_context.get('origin_model'):
            raise AccessError(
                "PHI query is missing required audit context.")

    # ── Two-event append-only audit (delegated to the audit model) ─────
    def _is_phi(self):
        return self.connection.security_profile == 'hospital_phi'

    def _audit_started(self, ctx, query, params):
        Audit = self.env['portal.audit.log'].sudo()
        return Audit.log_phi_started(
            connection=self.connection,
            schema_source=self.schema_source,
            org_id=self.connection.org_id,
            execution_context=ctx or {},
            param_names=sorted(params.keys()),
        )

    def _audit_finished(self, started, outcome, query_id=None,
                        row_count=None, error=None):
        Audit = self.env['portal.audit.log'].sudo()
        Audit.log_phi_finished(
            started=started, outcome=outcome, query_id=query_id,
            row_count=row_count, error_code=error)

    # ── execute ────────────────────────────────────────────────────────
    def execute(self, query, params, execution_context=None):
        params = params or {}
        if len(query) > self._MAX_QUERY_CHARS:
            raise ValueError('Query text exceeds the maximum allowed length.')
        if len(params) > self._MAX_PARAMS:
            raise ValueError('Too many query parameters.')
        _validate_select_only(query)
        self._enforce_phi_guard(execution_context)

        sql, sf_params = _expand_in_params(query, params)

        is_phi = self._is_phi()
        started = self._audit_started(execution_context, sql, sf_params) if is_phi else None

        try:
            cols, rows, query_id = self._run_with_reconnect(sql, sf_params)
        except Exception as exc:
            if is_phi and started is not None:
                # Fail-closed: record the failure (a clean error code only).
                self._audit_finished(
                    started, 'failed', error=type(exc).__name__)
            _logger.warning(
                'Snowflake query failed (connection=%s): %s',
                self.connection.name, type(exc).__name__)
            raise

        if is_phi and started is not None:
            # If the completion event cannot be written, do NOT return data.
            self._audit_finished(
                started, 'completed', query_id=query_id, row_count=len(rows))
        return cols, rows

    @staticmethod
    def _is_session_error(exc):
        code = getattr(exc, 'errno', None)
        if code in (390114, 390104, 390111, 390195):
            return True
        sqlstate = getattr(exc, 'sqlstate', None)
        if sqlstate in ('08001', '08003', '08006'):
            return True
        msg = str(exc).lower()
        return any(s in msg for s in (
            'authentication token has expired', 'session token',
            'session no longer exists', 'connection is closed'))

    def _run_with_reconnect(self, sql, sf_params):
        for attempt in (0, 1):
            conn = _get_connection(self.env, self.connection)
            lock = _get_query_lock(self.connection.id)
            try:
                with lock:
                    cur = conn.cursor()
                    try:
                        cur.execute(sql, sf_params or None)
                        cols = [d[0] for d in cur.description] if cur.description else []
                        rows = self._fetch_bounded(cur)
                        query_id = getattr(cur, 'sfqid', None)
                    finally:
                        cur.close()
                return cols, rows, query_id
            except Exception as exc:
                if attempt == 0 and self._is_session_error(exc):
                    _logger.info(
                        'Snowflake session error on %s; reconnecting once.',
                        self.connection.name)
                    _invalidate_client(self.connection.id)
                    continue
                raise

    def _fetch_bounded(self, cur):
        """Bounded fetchmany — never fetchall. Exceeding the row cap cancels
        the query and raises (no silent truncation)."""
        rows = []
        while True:
            batch = cur.fetchmany(self._FETCH_BATCH)
            if not batch:
                break
            rows.extend(tuple(r) for r in batch)
            if len(rows) > self._MAX_ROWS:
                try:
                    cur.connection.cancel() if hasattr(cur, 'connection') else None
                except Exception:
                    pass
                raise ValueError(
                    'Result limit exceeded: this query returns more than '
                    f'{self._MAX_ROWS:,} rows. Narrow the filters or use a '
                    'paginated view.')
        return rows

    # ── Admin validation probe — no PHI guard, no rows ─────────────────
    def validate_phi_source(self, table_name):
        """Privilege + metadata check: ``SELECT * FROM <view> LIMIT 0`` proves
        the role can read the object and returns its column names (no patient
        rows). Admin path — bypasses the four-condition guard (it's what the
        "Validate PHI Source" action calls before source_verified is set)."""
        table = _safe_sf_table(table_name)
        conn = _get_connection(self.env, self.connection)
        lock = _get_query_lock(self.connection.id)
        with lock:
            cur = conn.cursor()
            try:
                cur.execute(f'SELECT * FROM {table} LIMIT 0')
                return [d[0] for d in cur.description] if cur.description else []
            finally:
                cur.close()

    # ── discover_columns ───────────────────────────────────────────────
    def discover_columns(self, table_name):
        """Return ``[(column_name, rich_native_type), ...]`` from
        INFORMATION_SCHEMA. Handles TABLE / SCHEMA.TABLE / DB.SCHEMA.TABLE and
        reconstructs ``NUMBER(p,s)`` / ``VARCHAR(n)`` so the normalizer can tell
        integer from decimal."""
        name = _safe_sf_table(table_name)
        parts = name.upper().split('.')
        if len(parts) == 3:
            db, schema, tbl = parts
        elif len(parts) == 2:
            db, schema, tbl = None, parts[0], parts[1]
        else:
            db, schema, tbl = None, None, parts[0]

        where = ['table_name = %(tbl)s']
        bind = {'tbl': tbl}
        if schema:
            where.append('table_schema = %(schema)s')
            bind['schema'] = schema
        info_table = f'{db}.INFORMATION_SCHEMA.COLUMNS' if db else 'INFORMATION_SCHEMA.COLUMNS'
        sql = (
            "SELECT column_name, data_type, numeric_precision, numeric_scale, "
            "character_maximum_length "
            f"FROM {info_table} WHERE " + ' AND '.join(where) +
            " ORDER BY ordinal_position"
        )
        conn = _get_connection(self.env, self.connection)
        lock = _get_query_lock(self.connection.id)
        with lock:
            cur = conn.cursor()
            try:
                cur.execute(sql, bind)
                raw = cur.fetchall()
            finally:
                cur.close()
        return [(col, _rich_sf_type(dtype, prec, scale, char_len))
                for (col, dtype, prec, scale, char_len) in raw]

    def ping(self):
        conn = _get_connection(self.env, self.connection)
        lock = _get_query_lock(self.connection.id)
        with lock:
            cur = conn.cursor()
            try:
                cur.execute("SELECT 1")
                return cur.fetchone() == (1,)
            finally:
                cur.close()

    def get_tenant_id(self):
        # The Snowflake executor never uses the shared tenant contract.
        return None


def _rich_sf_type(data_type, precision, scale, char_len):
    """Reconstruct a precision/scale-bearing type string from
    INFORMATION_SCHEMA so ``_normalise_type`` can distinguish NUMBER(38,0)
    (integer) from NUMBER(10,2) (float)."""
    dt = (data_type or '').upper()
    if dt in ('NUMBER', 'DECIMAL', 'NUMERIC') and precision is not None:
        return f'{dt}({int(precision)},{int(scale or 0)})'
    if dt in ('VARCHAR', 'CHAR', 'STRING', 'TEXT') and char_len is not None:
        return f'{dt}({int(char_len)})'
    return dt or 'TEXT'
