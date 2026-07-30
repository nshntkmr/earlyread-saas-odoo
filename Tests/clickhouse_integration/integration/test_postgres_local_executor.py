# -*- coding: utf-8 -*-
"""Integration tests for ``PostgresLocalExecutor``.

The executor wraps ``self.env.cr`` — the goal is parity with the
pre-executor cursor path. If anything diverges (different savepoint
semantics, different column-name extraction), every existing widget
breaks.
"""

from odoo.tests.common import TransactionCase, tagged

from posterra_portal.utils.query_executors import PostgresLocalExecutor


@tagged("post_install", "-at_install", "clickhouse_integration")
class TestPostgresLocalExecutor(TransactionCase):

    def setUp(self):
        super().setUp()
        self.executor = PostgresLocalExecutor(self.env)

    def test_select_one(self):
        cols, rows = self.executor.execute("SELECT 1 AS x", {})
        self.assertEqual(cols, ["x"])
        self.assertEqual(rows, [(1,)])

    def test_select_with_named_param(self):
        cols, rows = self.executor.execute(
            "SELECT %(n)s::int AS n", {"n": 42},
        )
        self.assertEqual(cols, ["n"])
        self.assertEqual(rows, [(42,)])

    def test_select_in_clause(self):
        cols, rows = self.executor.execute(
            "SELECT v FROM (VALUES ('a'), ('b'), ('c')) t(v) WHERE v IN %(items)s ORDER BY v",
            {"items": ("a", "c")},
        )
        self.assertEqual(cols, ["v"])
        self.assertEqual([r[0] for r in rows], ["a", "c"])

    def test_savepoint_isolates_failure(self):
        # A failed query inside the executor's savepoint should not poison
        # the outer transaction. We can confirm by running another query
        # successfully after the failure.
        with self.assertRaises(Exception):
            self.executor.execute("SELECT 1/0", {})
        cols, rows = self.executor.execute("SELECT 1", {})
        self.assertEqual(rows, [(1,)])

    def test_discover_columns_known_table(self):
        # res_users always exists in any Odoo database — easy fixture.
        cols = self.executor.discover_columns("res_users")
        names = {c[0] for c in cols}
        self.assertIn("id", names)
        self.assertIn("login", names)

    def test_ping(self):
        self.assertTrue(self.executor.ping())

    def test_get_tenant_id_returns_none(self):
        # Postgres-local executor doesn't need tenant_id at the SQL
        # layer — return None so callers know there's nothing to set.
        self.assertIsNone(self.executor.get_tenant_id())
