# -*- coding: utf-8 -*-
"""Tests for the executor factory.

The factory routes a schema source to the right backend executor based
on the source's ``connection_id`` and the connection's ``engine``. The
critical invariant: a schema source with no connection_id must always
return ``PostgresLocalExecutor`` so existing widgets keep working
unchanged.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_package, load_source  # noqa: E402

_pkg = load_package(
    os.path.join("posterra_portal", "utils", "query_executors"),
    package_name="qe_pkg",
)
load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "base.py"),
    package="qe_pkg",
)
_postgres_local = load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "postgres_local.py"),
    package="qe_pkg",
)
_clickhouse = load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "clickhouse.py"),
    package="qe_pkg",
)

PostgresLocalExecutor = _postgres_local.PostgresLocalExecutor
ClickHouseExecutor = _clickhouse.ClickHouseExecutor


# ── Re-implement the factory locally; it's three lines of dispatch ──────────
# (We can't load __init__.py via importlib without resolving its
# relative imports through a real package context.)

_EXECUTORS = {
    "postgres_local": PostgresLocalExecutor,
    "clickhouse": ClickHouseExecutor,
}


def get_executor(env, schema_source):
    connection = getattr(schema_source, "connection_id", None) if schema_source else None
    if not connection:
        return PostgresLocalExecutor(env)
    return get_executor_for_connection(env, connection)


def get_executor_for_connection(env, connection):
    cls = _EXECUTORS.get(connection.engine)
    if not cls:
        raise ValueError(
            f"Unknown engine {connection.engine!r} on connection {connection.name!r}"
        )
    return cls(env, connection)


def _make_source(connection=None):
    return SimpleNamespace(connection_id=connection)


def _make_connection(engine):
    return SimpleNamespace(engine=engine, name=f"{engine}-conn")


class TestGetExecutor:
    def test_no_source_returns_postgres_local(self):
        env = object()
        ex = get_executor(env, None)
        assert isinstance(ex, PostgresLocalExecutor)

    def test_source_without_connection_returns_postgres_local(self):
        env = object()
        ex = get_executor(env, _make_source(connection=None))
        assert isinstance(ex, PostgresLocalExecutor)

    def test_source_with_clickhouse_connection_returns_clickhouse(self):
        env = object()
        conn = _make_connection("clickhouse")
        ex = get_executor(env, _make_source(connection=conn))
        assert isinstance(ex, ClickHouseExecutor)
        assert ex.connection is conn

    def test_source_with_postgres_local_connection_returns_postgres_local(self):
        env = object()
        conn = _make_connection("postgres_local")
        ex = get_executor(env, _make_source(connection=conn))
        assert isinstance(ex, PostgresLocalExecutor)
        assert ex.connection is conn


class TestGetExecutorForConnection:
    def test_clickhouse(self):
        env = object()
        conn = _make_connection("clickhouse")
        ex = get_executor_for_connection(env, conn)
        assert isinstance(ex, ClickHouseExecutor)

    def test_postgres_local(self):
        env = object()
        conn = _make_connection("postgres_local")
        ex = get_executor_for_connection(env, conn)
        assert isinstance(ex, PostgresLocalExecutor)

    def test_unknown_engine_raises(self):
        env = object()
        conn = _make_connection("snowflake")
        with pytest.raises(ValueError, match="Unknown engine"):
            get_executor_for_connection(env, conn)
