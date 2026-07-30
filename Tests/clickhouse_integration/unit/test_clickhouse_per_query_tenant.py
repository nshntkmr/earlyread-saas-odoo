# -*- coding: utf-8 -*-
"""Test that ``ClickHouseExecutor.execute`` ships the tenant_id as a
per-query setting (NOT via a separate ``client.command('SET ...')``).

The shared cached client is reused across threads. A two-step pattern
``client.command(SET ...)`` + ``client.query(...)`` races: thread A's
SET could be overwritten by thread B before thread A's query reaches
the server. The fix sends ``SQL_tenant_id`` inside the same HTTP
request as the query via ``settings={...}``, making it atomic.

This test asserts the behaviour by mocking the clickhouse-connect
client and verifying ``client.command`` is never called for the SET
and that ``settings`` includes ``SQL_tenant_id``.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_package, load_source  # noqa: E402

_pkg = load_package(
    os.path.join("posterra_portal", "utils", "query_executors"),
    package_name="qe_pkg_perquery_test",
)
load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "base.py"),
    package="qe_pkg_perquery_test",
)
_clickhouse = load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "clickhouse.py"),
    package="qe_pkg_perquery_test",
)
ClickHouseExecutor = _clickhouse.ClickHouseExecutor


# ── Fakes ───────────────────────────────────────────────────────────────────

class _FakeQueryResult:
    column_names = ["x"]
    result_rows = [(1,)]


class _FakeClient:
    """Records every call so the test can assert what was sent."""

    def __init__(self):
        self.command_calls = []  # list of (cmd, parameters)
        self.query_calls = []    # list of (query, parameters, settings)

    def command(self, cmd, parameters=None):
        self.command_calls.append((cmd, parameters or {}))

    def query(self, query, parameters=None, settings=None):
        self.query_calls.append(
            (query, parameters or {}, settings or {})
        )
        return _FakeQueryResult()

    def close(self):
        pass


class _FakeConnection(SimpleNamespace):
    pass


# Stable counter so each fixture call gets a unique cache key.
# id(object()) is unsafe — temporaries can be GC'd and their ids reused.
_next_id = [10_000]


def _make_executor_with_fake_client(tenant_id="42",
                                     requires_tenant_filter=True,
                                     query_timeout=30):
    """Wire a ClickHouseExecutor to a captured _FakeClient.

    Bypasses ``_get_client`` (which would try a real
    ``clickhouse_connect.get_client``) by injecting via the module's
    ``_clients`` cache.
    """
    _next_id[0] += 1
    conn_id = _next_id[0]
    conn = _FakeConnection(
        id=conn_id,
        name="fake-ch",
        host="x",
        port=8443,
        database="d",
        username="u",
        password_param_key="x",
        use_tls=True,
        is_active=True,
        engine="clickhouse",
        requires_tenant_filter=requires_tenant_filter,
        query_timeout_seconds=query_timeout,
    )

    fake = _FakeClient()
    _clickhouse._clients[conn_id] = fake

    env = SimpleNamespace(user=None)
    executor = ClickHouseExecutor(env, conn)

    # Stub the tenant resolver to return a known value without a
    # request context.
    executor.get_tenant_id = lambda: tenant_id

    return executor, fake


# ── Tests ───────────────────────────────────────────────────────────────────

class TestPerQueryTenantSetting:
    def test_tenant_id_is_in_settings_not_set_command(self):
        executor, client = _make_executor_with_fake_client(tenant_id="42")

        executor.execute("SELECT 1", {})

        # No ``SET SQL_tenant_id = ...`` command should have been
        # issued — it would race on the shared client.
        for cmd, _ in client.command_calls:
            assert "SQL_tenant_id" not in cmd, (
                "tenant_id must NOT travel via client.command(SET ...) — "
                "that races on the shared cached client"
            )

        # The single query call should carry SQL_tenant_id in settings.
        assert len(client.query_calls) == 1
        _, _, settings = client.query_calls[0]
        assert settings.get("SQL_tenant_id") == "42", (
            "tenant_id must travel as a per-query setting so it's "
            "atomic with the query in the same HTTP request"
        )

    def test_tenant_id_is_string_for_lowcardinality(self):
        # CH stores tenant_id as LowCardinality(String); the executor
        # must coerce numeric tenant ids to str.
        executor, client = _make_executor_with_fake_client(tenant_id=42)

        executor.execute("SELECT 1", {})

        _, _, settings = client.query_calls[0]
        assert settings.get("SQL_tenant_id") == "42"
        assert isinstance(settings["SQL_tenant_id"], str)

    def test_no_tenant_id_when_filter_disabled(self):
        executor, client = _make_executor_with_fake_client(
            requires_tenant_filter=False
        )

        executor.execute("SELECT 1", {})

        _, _, settings = client.query_calls[0]
        assert "SQL_tenant_id" not in settings, (
            "requires_tenant_filter=False means no tenant context is "
            "set — admin tooling only"
        )

    def test_resource_limits_present_on_every_query(self):
        executor, client = _make_executor_with_fake_client(
            query_timeout=15
        )
        executor.execute("SELECT 1", {})

        _, _, settings = client.query_calls[0]
        assert settings.get("max_execution_time") == 15
        assert "max_memory_usage" in settings
        assert "max_rows_to_read" in settings

    def test_concurrent_tenants_do_not_share_setting(self):
        """The whole point of the per-query setting: two executors
        sharing the same cached client can run with different
        tenant_ids without interfering."""
        executor_a, client_a = _make_executor_with_fake_client(tenant_id="1")
        executor_b, client_b = _make_executor_with_fake_client(tenant_id="2")

        executor_a.execute("SELECT 1", {})
        executor_b.execute("SELECT 1", {})

        _, _, settings_a = client_a.query_calls[0]
        _, _, settings_b = client_b.query_calls[0]

        assert settings_a["SQL_tenant_id"] == "1"
        assert settings_b["SQL_tenant_id"] == "2"
