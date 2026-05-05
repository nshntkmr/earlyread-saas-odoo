# -*- coding: utf-8 -*-
"""Abstract query executor.

Subclasses bridge widget/filter SQL paths to a concrete database backend.
Two backends ship today: ``postgres_local`` (wraps Odoo's ``self.env.cr``)
and ``clickhouse`` (HTTPS via ``clickhouse-connect``).

Every executor returns ``(column_names, rows)`` so widget renderers and
filter option builders can stay backend-agnostic.
"""


class BaseQueryExecutor(object):
    """Contract every backend executor must satisfy.

    Args:
        env: an Odoo environment (used for ``ir.config_parameter`` lookups
             and the local cursor in PostgresLocalExecutor).
        connection: a ``dashboard.connection`` record, or None when running
             against the local Postgres (``connection_id IS NULL``).
    """

    def __init__(self, env, connection=None):
        self.env = env
        self.connection = connection

    def execute(self, query, params):
        """Execute a SELECT/WITH query and return ``(col_names, rows)``.

        ``params`` is a dict keyed by ``%(name)s`` placeholder names.
        Rows MUST be returned as a list of tuples so renderers behave
        identically across backends.
        """
        raise NotImplementedError

    def discover_columns(self, table_name):
        """Return ``[(column_name, native_type), ...]`` for ``table_name``.

        Used by ``dashboard.schema.source.action_discover_columns`` to
        populate ``dashboard.schema.column`` rows.
        """
        raise NotImplementedError

    def ping(self):
        """Return True if the backend is reachable. Used by the
        Test Connection button on ``dashboard.connection``."""
        raise NotImplementedError

    def get_tenant_id(self):
        """Resolve the tenant_id for the current request.

        Falls back to a ``ValueError`` if no request context is present
        and the connection requires a tenant filter — never silently
        picks an arbitrary tenant.
        """
        from ..tenant_context import get_current_tenant_id
        try:
            from odoo.http import request
        except Exception:
            request = None
        return get_current_tenant_id(self.env, request)
