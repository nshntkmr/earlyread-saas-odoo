# -*- coding: utf-8 -*-
"""Live integration tests for the ClickHouse executor.

These tests exercise the real ``clickhouse-connect`` driver against a
reachable ClickHouse cluster — no mocks. They verify that the
executor's logic matches the actual server's behaviour for placeholder
translation, parameter binding, type inference, and the per-query
``SQL_tenant_id`` setting that gates row policies.

## How to run

The tests skip cleanly unless these env vars are populated:

    CH_TEST_HOST       # e.g. ch-dev.internal.posterra.com
    CH_TEST_PORT       # 8443 — HTTPS, what clickhouse-connect uses.
                       # NOT 9440 (that's native TCP TLS for the
                       # clickhouse-driver / clickhouse-client CLI).
    CH_TEST_USER       # e.g. app_user
    CH_TEST_PASSWORD   # bootstrap-rotated password
    CH_TEST_DATABASE   # e.g. default
    CH_TEST_TENANT_ID  # e.g. '1' — tenant the test will set + verify
                       # (only used in the tenant-isolation test;
                       # safe to omit if you haven't seeded a tenant
                       # row policy yet)
    CH_TEST_USE_TLS    # '1' for TLS, '0' to disable; default '1'

Then:

    cd C:/Users/nisha/Odoo_Dev/Tests/clickhouse_integration
    POSTERRA_ADDONS_ROOT=<worktree-path> \
    CH_TEST_HOST=... CH_TEST_PASSWORD=... \
    pytest integration/test_clickhouse_live.py -v

## Prerequisites on the cluster

Run ``dashboard_builder/sql/clickhouse_bootstrap.sql`` against the
cluster ONCE before these tests. Without it:

  - ``app_user`` may not exist (auth failure)
  - ``app_profile`` is missing → setting ``SQL_tenant_id`` is rejected
    as an unknown setting → all queries fail

The tenant-isolation test additionally needs at least one tenant-scoped
table populated with a ``tenant_id`` matching ``CH_TEST_TENANT_ID``.
That's a Phase 3+ concern; the test is marked optional and skips if
no ``CH_TEST_FACT_TABLE`` is provided.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_package, load_source  # noqa: E402


# ── Connect (or skip) ──────────────────────────────────────────────────────


def _env(name, default=None):
    val = os.environ.get(name, default)
    return val if val not in (None, '') else default


CH_HOST = _env('CH_TEST_HOST')
CH_PORT = int(_env('CH_TEST_PORT', '8443'))
CH_USER = _env('CH_TEST_USER', 'app_user')
CH_PASSWORD = _env('CH_TEST_PASSWORD')
CH_DATABASE = _env('CH_TEST_DATABASE', 'default')
CH_USE_TLS = _env('CH_TEST_USE_TLS', '1') != '0'
CH_TENANT_ID = _env('CH_TEST_TENANT_ID')
CH_FACT_TABLE = _env('CH_TEST_FACT_TABLE')

_skip_no_creds = pytest.mark.skipif(
    not (CH_HOST and CH_PASSWORD),
    reason=(
        'CH_TEST_HOST + CH_TEST_PASSWORD not set — '
        'live ClickHouse tests skipped. See module docstring.'
    ),
)


def _try_import_driver():
    try:
        import clickhouse_connect  # noqa: F401
        return True
    except ImportError:
        return False


_skip_no_driver = pytest.mark.skipif(
    not _try_import_driver(),
    reason='clickhouse-connect not installed',
)


# ── Load the executor ──────────────────────────────────────────────────────

_pkg = load_package(
    os.path.join('posterra_portal', 'utils', 'query_executors'),
    package_name='qe_pkg_live',
)
load_source(
    os.path.join('posterra_portal', 'utils', 'query_executors', 'base.py'),
    package='qe_pkg_live',
)
_clickhouse = load_source(
    os.path.join('posterra_portal', 'utils', 'query_executors', 'clickhouse.py'),
    package='qe_pkg_live',
)
ClickHouseExecutor = _clickhouse.ClickHouseExecutor


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def conn():
    """A ``dashboard.connection``-shaped namespace pointing at the test
    cluster. Each test gets a unique id so the executor's per-process
    client cache treats them independently."""
    if not (CH_HOST and CH_PASSWORD):
        pytest.skip('live CH not configured')

    # Stash the password in a fake ir.config_parameter the executor
    # can read via env['ir.config_parameter'].sudo().get_param(...).
    fake_env = _FakeEnv(password=CH_PASSWORD)

    # Unique connection id per test so cache entries don't bleed.
    cid = id(object())
    return _LiveConn(
        env=fake_env,
        id=cid,
        name=f'live-test-{cid}',
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password_param_key='ch.test.password',
        database=CH_DATABASE,
        use_tls=CH_USE_TLS,
        is_active=True,
        engine='clickhouse',
        requires_tenant_filter=False,  # off by default; opt in per test
        query_timeout_seconds=10,
    )


@pytest.fixture(autouse=True)
def _clean_cache_between_tests():
    """Drop cached clients between tests so a connection-config tweak
    doesn't leak into the next test's cached state."""
    yield
    _clickhouse._clients.clear()


class _LiveConn(SimpleNamespace):
    pass


class _FakeConfigParam:
    def __init__(self, password):
        self._password = password

    def sudo(self):
        return self

    def get_param(self, key, default=''):
        if key == 'ch.test.password':
            return self._password
        return default


class _FakeEnv:
    def __init__(self, password):
        self._cp = _FakeConfigParam(password)
        self.user = None

    def __getitem__(self, model_name):
        if model_name == 'ir.config_parameter':
            return self._cp
        raise KeyError(model_name)


# ── Tests ──────────────────────────────────────────────────────────────────


@_skip_no_creds
@_skip_no_driver
class TestClickHouseLivePing:

    def test_ping_returns_true(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        assert ex.ping() is True

    def test_ping_after_invalidate(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        ex.ping()
        _clickhouse._invalidate_client(conn.id)
        # Should reconnect cleanly.
        assert ex.ping() is True


@_skip_no_creds
@_skip_no_driver
class TestClickHouseLiveExecute:

    def test_select_one(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        cols, rows = ex.execute('SELECT 1', {})
        assert rows == [(1,)]

    def test_named_string_param(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        cols, rows = ex.execute(
            'SELECT %(s)s AS v', {'s': 'hello'},
        )
        assert rows == [('hello',)]

    def test_named_int_param(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        cols, rows = ex.execute(
            'SELECT %(n)s AS v', {'n': 42},
        )
        assert rows[0][0] == 42

    def test_in_clause_array(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        cols, rows = ex.execute(
            "SELECT v FROM (SELECT arrayJoin([1,2,3,4]) AS v) "
            "WHERE v IN %(items)s ORDER BY v",
            {'items': [1, 3]},
        )
        assert [r[0] for r in rows] == [1, 3]

    def test_null_value(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        cols, rows = ex.execute(
            "SELECT %(maybe)s AS v", {'maybe': None},
        )
        assert rows[0][0] is None

    def test_select_only_validation(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        with pytest.raises(ValueError, match='Only SELECT or WITH'):
            ex.execute('INSERT INTO system.tables SELECT 1', {})

    def test_blocked_keyword(self, conn):
        ex = ClickHouseExecutor(conn.env, conn)
        with pytest.raises(ValueError, match='disallowed'):
            ex.execute('SELECT 1; DROP TABLE foo', {})


@_skip_no_creds
@_skip_no_driver
class TestClickHouseLiveDiscoverColumns:

    def test_discover_system_columns(self, conn):
        """``system.columns`` is always present on every CH cluster —
        an ideal smoke target for column discovery."""
        ex = ClickHouseExecutor(conn.env, conn)
        cols = ex.discover_columns('system.columns')
        names = {c[0] for c in cols}
        # Standard columns on every CH version.
        assert {'database', 'table', 'name', 'type'}.issubset(names)

    def test_discover_with_default_database(self, conn):
        """Bare table name (no dot) should use the connection's database."""
        ex = ClickHouseExecutor(conn.env, conn)
        # We can only assert this doesn't blow up — we don't know
        # what tables exist in the configured database. An empty
        # result is perfectly valid.
        cols = ex.discover_columns('numbers')
        assert isinstance(cols, list)


@_skip_no_creds
@_skip_no_driver
class TestClickHouseLiveTenantSetting:
    """Verify the per-query ``SQL_tenant_id`` setting is honoured by
    the cluster (i.e. the bootstrap DDL has been applied).

    Doesn't need a fact table — just confirms ``getSetting()`` reads
    back what the executor sent."""

    def test_SQL_tenant_id_setting_round_trips(self, conn):
        # Flip on the tenant filter so the executor SETs the value.
        conn.requires_tenant_filter = True
        ex = ClickHouseExecutor(conn.env, conn)
        # Stub the tenant resolver — no Odoo request context here.
        ex.get_tenant_id = lambda: '42'

        cols, rows = ex.execute(
            "SELECT getSetting('SQL_tenant_id') AS tid", {},
        )
        assert rows[0][0] == '42', (
            'Cluster did not echo back the tenant_id sent via per-query '
            'settings. Three equally likely causes:\n'
            "  1. Server config — ``<custom_settings_prefixes>SQL_</...>`` "
            "is not set in users.xml / config.d (managed providers may "
            "have it pre-configured; verify, don't assume). Check with "
            "``SELECT value FROM system.server_settings "
            "WHERE name='custom_settings_prefixes'`` and run "
            "``SYSTEM RELOAD CONFIG`` after editing.\n"
            '  2. ``app_profile`` was not created — re-run '
            'dashboard_builder/sql/clickhouse_bootstrap.sql.\n'
            "  3. ``app_user`` was created without "
            "``SETTINGS PROFILE 'app_profile'`` — recreate it per "
            'phase2_verification.md section C, or attach the profile '
            "via ``ALTER USER app_user SETTINGS PROFILE 'app_profile'``."
        )

    def test_concurrent_tenant_isolation(self, conn):
        """Regression test for the per-query setting binding (the race
        Codex flagged: a session-state SET on a shared cached client
        could be overwritten by another thread before its query ran).

        This test is **sequential** — both executors share the cached
        client but run one at a time. It proves that each query carries
        its own ``SQL_tenant_id`` in the request, independent of any
        previous query's setting. That's sufficient to catch a
        regression where someone reintroduces ``client.command(SET)``,
        because that pattern would leak the last-set value into the
        next query.

        It is NOT a true thread-parallel test. A real concurrency
        check (multiple threads issuing queries against the same
        cached client at the same instant, with row policies actively
        filtering) belongs in Phase 4 once tenant-tagged tables exist
        and row policies are applied. Add it to
        ``test_clickhouse_live.py`` then; it should spin up N threads
        each doing ``ex.execute(...)`` with a different tenant_id and
        assert each thread sees only its own tenant's rows."""
        conn.requires_tenant_filter = True
        ex_a = ClickHouseExecutor(conn.env, conn)
        ex_b = ClickHouseExecutor(conn.env, conn)
        ex_a.get_tenant_id = lambda: '111'
        ex_b.get_tenant_id = lambda: '222'

        _, rows_a = ex_a.execute(
            "SELECT getSetting('SQL_tenant_id')", {},
        )
        _, rows_b = ex_b.execute(
            "SELECT getSetting('SQL_tenant_id')", {},
        )

        assert rows_a[0][0] == '111'
        assert rows_b[0][0] == '222'


# Validate the optional fact-table env var the same way the addon
# validates ``dashboard.schema.source.table_name`` — admins can pass
# ``gold.fact_referrals`` (db.table) but not arbitrary SQL fragments.
# Loaded lazily so the import doesn't fail when the addon worktree
# can't be added to sys.path (e.g. CI without POSTERRA_ADDONS_ROOT).

def _validated_fact_table():
    if not CH_FACT_TABLE:
        return None
    sql_idents = load_source(
        os.path.join('posterra_portal', 'utils', 'sql_idents.py'),
        module_name='sql_idents_for_live_test',
    )
    if not sql_idents.is_valid_table(CH_FACT_TABLE):
        pytest.fail(
            f'CH_TEST_FACT_TABLE={CH_FACT_TABLE!r} is not a valid '
            f'ClickHouse table reference. Expected ``table`` or '
            f'``db.table`` with alphanumeric segments. Refusing to '
            f'interpolate it into SQL.'
        )
    return sql_idents.quote_table(CH_FACT_TABLE)


@_skip_no_creds
@_skip_no_driver
@pytest.mark.skipif(
    not (CH_FACT_TABLE and CH_TENANT_ID),
    reason='CH_TEST_FACT_TABLE and CH_TEST_TENANT_ID not set — '
           'tenant-row-policy smoke test requires a tenant-tagged '
           'fact table to be seeded (Phase 3+).',
)
class TestClickHouseLiveRowPolicy:
    """Optional: verify that a tenant-scoped fact table actually filters
    rows when ``SQL_tenant_id`` is set. Requires a seeded table with at
    least one row matching ``CH_TEST_TENANT_ID`` and at least one row
    that doesn't."""

    def test_row_policy_filters_for_tenant(self, conn):
        conn.requires_tenant_filter = True
        ex = ClickHouseExecutor(conn.env, conn)
        ex.get_tenant_id = lambda: CH_TENANT_ID

        # Quote the env-var-supplied table with the same helper the
        # addon uses everywhere else — refuses dotted-with-junk and
        # quotes ``db.table`` as ``"db"."table"``.
        quoted = _validated_fact_table()

        sql = (
            f"SELECT count() AS n, "
            f"sum(if(tenant_id = %(tid)s, 1, 0)) AS matching "
            f"FROM {quoted}"
        )
        cols, rows = ex.execute(sql, {'tid': CH_TENANT_ID})
        n, matching = rows[0]
        assert n > 0, 'fact table is empty'
        assert n == matching, (
            f'Row policy did not filter: saw {n} rows but only '
            f'{matching} match tenant_id={CH_TENANT_ID!r}. The '
            f'policy on {CH_FACT_TABLE} may be missing or referencing '
            f'a different setting name.'
        )
