# -*- coding: utf-8 -*-
"""Postgres executor that wraps Odoo's local cursor.

This is the default executor when a schema source has no
``connection_id`` set — i.e. every Postgres-backed widget that exists
today. The behaviour MUST match the pre-executor codepath
(``self.env.cr.execute(...)`` inside a savepoint) so Phase 1 ships with
zero behavioral change.
"""

import logging

from .base import BaseQueryExecutor

_logger = logging.getLogger(__name__)


class PostgresLocalExecutor(BaseQueryExecutor):
    """Routes queries through ``self.env.cr`` — the same cursor that
    Odoo's ORM uses, sharing the request's transaction."""

    def execute(self, query, params):
        cr = self.env.cr
        with cr.savepoint():
            cr.execute(query, params)
            cols = [d[0] for d in cr.description] if cr.description else []
            rows = cr.fetchall()
            return cols, rows

    def discover_columns(self, table_name):
        cr = self.env.cr
        cr.execute("""
            SELECT a.attname,
                   format_type(a.atttypid, a.atttypmod)
              FROM pg_attribute a
              JOIN pg_class c ON c.oid = a.attrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relname = %s
               AND a.attnum > 0
               AND NOT a.attisdropped
             ORDER BY a.attnum
        """, (table_name,))
        return cr.fetchall()

    def ping(self):
        cr = self.env.cr
        cr.execute("SELECT 1")
        return cr.fetchone() == (1,)

    def get_tenant_id(self):
        """Local Postgres executor never needs tenant_id at the SQL layer
        — tenant separation is structural (per-app MVs, app-scoped
        filters). Return None so callers know there's nothing to set."""
        return None
