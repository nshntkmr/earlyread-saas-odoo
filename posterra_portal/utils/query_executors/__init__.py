# -*- coding: utf-8 -*-
"""Query executor factory.

Routes widget/filter SQL to the right backend based on the
schema source's ``connection_id``. Schema sources with a NULL
``connection_id`` use the local Postgres cursor (existing behaviour);
sources pointing at a ``dashboard.connection`` use that connection's
configured engine.

Public API:
    get_executor(env, schema_source)
        — returns the executor for a schema source
    get_executor_for_connection(env, connection)
        — returns the executor for a connection record (used by the
          Test Connection button)
"""

from .base import BaseQueryExecutor
from .postgres_local import PostgresLocalExecutor
from .clickhouse import ClickHouseExecutor
from .snowflake import SnowflakeExecutor


_EXECUTORS = {
    'postgres_local': PostgresLocalExecutor,
    'clickhouse': ClickHouseExecutor,
    'snowflake': SnowflakeExecutor,
}


def get_executor(env, schema_source):
    """Pick the executor for a schema source.

    Schema sources without ``connection_id`` fall back to the local
    Postgres executor — this is the path every existing widget/filter
    uses today, so behaviour is preserved. The ``schema_source`` is passed
    through so PHI-aware executors (Snowflake) can read its classification
    and verification state; non-PHI executors ignore it.
    """
    connection = getattr(schema_source, 'connection_id', None) if schema_source else None
    if not connection:
        return PostgresLocalExecutor(env, schema_source=schema_source)
    return get_executor_for_connection(env, connection, schema_source=schema_source)


def get_executor_for_connection(env, connection, schema_source=None, allow_inactive=False):
    """Pick the executor for a connection record.

    Refuses to build an executor for an inactive connection — a
    disabled connection should never run queries. Surfaces a clear
    error to the per-widget UI rather than silently returning empty
    data or hitting the wrong backend.

    ``allow_inactive=True`` is reserved for System-Admin
    validation/revalidation actions (e.g. "Validate PHI Source"), which
    must be able to test a connection that a sensitive-field change has
    just auto-deactivated. Normal widget/preview/API paths MUST NOT pass
    it — without it, an inactive connection still fails closed.
    """
    if not getattr(connection, 'is_active', True) and not allow_inactive:
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
    return cls(env, connection, schema_source=schema_source)


__all__ = [
    'BaseQueryExecutor',
    'PostgresLocalExecutor',
    'ClickHouseExecutor',
    'SnowflakeExecutor',
    'get_executor',
    'get_executor_for_connection',
]
