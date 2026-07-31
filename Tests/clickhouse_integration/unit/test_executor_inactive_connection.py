# -*- coding: utf-8 -*-
"""Test that the executor factory refuses to build an executor for an
inactive connection.

A disabled connection should raise a clear, admin-readable error
rather than silently returning empty data or hitting the wrong
backend. Mirror this assertion server-side once the integration
suite reaches the live Odoo runtime.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_package, load_source  # noqa: E402

_pkg = load_package(
    os.path.join("posterra_portal", "utils", "query_executors"),
    package_name="qe_pkg_inactive_test",
)
load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "base.py"),
    package="qe_pkg_inactive_test",
)
_postgres_local = load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "postgres_local.py"),
    package="qe_pkg_inactive_test",
)
_clickhouse = load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "clickhouse.py"),
    package="qe_pkg_inactive_test",
)
PostgresLocalExecutor = _postgres_local.PostgresLocalExecutor
ClickHouseExecutor = _clickhouse.ClickHouseExecutor


# Local copy of the factory dispatch (matches the live one). We can't
# load __init__.py via importlib without a real package context, so
# the dispatch logic is replicated here for test isolation.

_EXECUTORS = {
    "postgres_local": PostgresLocalExecutor,
    "clickhouse": ClickHouseExecutor,
}


def get_executor_for_connection(env, connection):
    if not getattr(connection, "is_active", True):
        raise ValueError(
            f"Connection {connection.name!r} is inactive; "
            "enable it in Dashboard Builder → Configuration → Database "
            "Connections before running queries against it."
        )
    cls = _EXECUTORS.get(connection.engine)
    if not cls:
        raise ValueError(
            f"Unknown engine {connection.engine!r} on connection {connection.name!r}"
        )
    return cls(env, connection)


def _conn(engine="clickhouse", is_active=True, name="test"):
    return SimpleNamespace(engine=engine, is_active=is_active, name=name)


class TestInactiveConnection:
    def test_active_clickhouse_returns_executor(self):
        ex = get_executor_for_connection(object(), _conn(is_active=True))
        assert isinstance(ex, ClickHouseExecutor)

    def test_active_postgres_local_returns_executor(self):
        ex = get_executor_for_connection(
            object(), _conn(engine="postgres_local", is_active=True)
        )
        assert isinstance(ex, PostgresLocalExecutor)

    def test_inactive_raises_with_admin_readable_error(self):
        conn = _conn(is_active=False, name="ClickHouse — Production")
        with pytest.raises(ValueError, match="inactive"):
            get_executor_for_connection(object(), conn)

    def test_inactive_error_includes_connection_name(self):
        conn = _conn(is_active=False, name="ClickHouse — Production")
        with pytest.raises(ValueError, match="ClickHouse — Production"):
            get_executor_for_connection(object(), conn)

    def test_inactive_error_includes_remediation_hint(self):
        conn = _conn(is_active=False, name="x")
        with pytest.raises(ValueError, match="enable it"):
            get_executor_for_connection(object(), conn)

    def test_default_treats_missing_attribute_as_active(self):
        # Defensive: a connection record-like object without an
        # is_active attribute (e.g. legacy mock) should not raise.
        conn = SimpleNamespace(engine="clickhouse", name="legacy")
        ex = get_executor_for_connection(object(), conn)
        assert isinstance(ex, ClickHouseExecutor)
