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

    def execute(self, query, params, execution_context=None):
        cr = self.env.cr
        with cr.savepoint():
            cr.execute(query, params)
            cols = [d[0] for d in cr.description] if cr.description else []
            rows = cr.fetchall()
            return cols, rows

    def execute_bounded(self, query, params, *, max_rows=None, timeout_s=None,
                        order_by=None, execution_context=None):
        """Bounded execution on the request cursor (see BaseQueryExecutor).

        Timeout: ``SET LOCAL statement_timeout`` inside a savepoint. SET LOCAL
        survives RELEASE SAVEPOINT (it lasts until the transaction ends), so
        the previous value is captured first and restored in ``finally`` —
        OUTSIDE the savepoint, so a failed statement (savepoint rolled back,
        which already undoes the SET) never runs the restore inside an
        aborted transaction.
        """
        from .bounded import (BoundedResult, is_unknown_column_error,
                              split_bounded_rows, wrap_bounded)
        cr = self.env.cr
        params = params if params is not None else {}

        def _run(sort):
            sql = wrap_bounded(query, max_rows=max_rows, order_by=sort,
                               dialect='postgres')
            previous = None
            if timeout_s:
                cr.execute('SHOW statement_timeout')
                previous = cr.fetchone()[0]
            try:
                with cr.savepoint():
                    if timeout_s:
                        ms = max(1, int(float(timeout_s) * 1000))
                        cr.execute('SET LOCAL statement_timeout = %s', (f'{ms}ms',))
                    cr.execute(sql, params)
                    cols = [d[0] for d in cr.description] if cr.description else []
                    rows = cr.fetchall()
            finally:
                if previous is not None:
                    cr.execute('SET LOCAL statement_timeout = %s', (previous,))
            return cols, rows

        sort_applied = bool(order_by)
        try:
            cols, rows = _run(order_by)
        except Exception as exc:
            if not order_by or not is_unknown_column_error(exc):
                raise
            _logger.info('Bounded query: configured sort column not in the '
                         'result; retrying without the sort.')
            cols, rows = _run(None)
            sort_applied = False
        shown, more = split_bounded_rows(rows, max_rows)
        return BoundedResult(cols, shown, more, sort_applied)

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
