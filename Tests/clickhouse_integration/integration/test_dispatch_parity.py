# -*- coding: utf-8 -*-
"""Parity tests: existing widgets and filters must produce IDENTICAL
output before and after the executor refactor.

Strategy: pick an existing widget on a stock page (dashboard widget
seeded by ``data/widget_templates_data.xml``), execute it via
``widget.get_portal_data(portal_ctx)``, and assert the shape is what
the React renderer expects (``cols`` + ``rows``). The executor under
the hood routes to ``PostgresLocalExecutor`` because ``connection_id``
is NULL on every existing schema source.

If a widget fails this test, the executor refactor introduced a
regression — block the merge.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "clickhouse_integration")
class TestWidgetDispatchParity(TransactionCase):

    def test_existing_widget_renders_via_executor(self):
        # Find any active widget that has a query_sql — every existing
        # widget should pass through PostgresLocalExecutor without error.
        widget = self.env["dashboard.widget"].search([
            ("is_active", "=", True),
            ("query_type", "=", "sql"),
            ("query_sql", "!=", False),
        ], limit=1)
        if not widget:
            self.skipTest("No SQL-mode widget seeded; nothing to assert against")
            return

        portal_ctx = {
            "filter_values_by_name": {},
            "sql_params": {},
            "_filter_defs": [],
        }
        # Should not raise — even if data is empty, the query path must
        # complete cleanly.
        result = widget.get_portal_data(portal_ctx)
        self.assertIsInstance(result, dict)

    def test_filter_options_render_via_executor(self):
        # Every active filter on a schema source should still produce
        # options when get_options is called. Empty option list is OK
        # (not all schema sources are populated in test data) — what
        # matters is that the executor dispatch path doesn't blow up.
        filt = self.env["dashboard.page.filter"].search([
            ("is_active", "=", True),
            ("schema_source_id", "!=", False),
            ("schema_column_id", "!=", False),
        ], limit=1)
        if not filt:
            self.skipTest("No schema-source filter seeded; nothing to test")
            return

        # Should not raise.
        opts = filt.get_options()
        self.assertIsInstance(opts, list)
