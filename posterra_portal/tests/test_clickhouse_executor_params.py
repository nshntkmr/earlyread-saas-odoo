# -*- coding: utf-8 -*-
"""Lock the tuple → list normalization at the ClickHouse engine boundary.

Regression test for the CANNOT_READ_ARRAY_FROM_TEXT (code 130) class of
errors that hit every multi-select filter on a CH-backed widget. The
shared build_sql_params helper emits tuples for IN clauses (psycopg2's
contract on the PG path); the CH executor must coerce them to lists so
clickhouse-connect renders them as Array literals "[a,b]" rather than
Tuple literals "(a,b)".

Run:
    odoo-bin --test-enable -i posterra_portal --test-tags posterra_ch_executor \\
             --stop-after-init -d <test_db>
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase
from odoo.tests import tagged

# Use the odoo.addons.<addon> path — under Odoo's runtime, addons are loaded
# in that namespace and using the bare 'posterra_portal...' path can create
# a second module object, making patches no-ops against the production path.
from odoo.addons.posterra_portal.utils.query_executors.clickhouse import (
    ClickHouseExecutor,
)


@tagged('post_install', '-at_install', 'posterra_ch_executor')
class TestClickHouseExecutorParams(TransactionCase):
    """Smoke test for the tuple→list normalization at execute time."""

    def _build_executor(self):
        # Minimal stub — we only exercise the parameter normalization path.
        connection = MagicMock()
        connection.id = 1
        connection.name = 'test-ch'
        connection.query_timeout_seconds = 30
        connection.requires_tenant_filter = False
        connection.password_param_key = ''
        connection.password = ''
        return ClickHouseExecutor(self.env, connection)

    @patch('odoo.addons.posterra_portal.utils.query_executors.clickhouse._get_client')
    def test_tuple_params_are_passed_as_lists_to_clickhouse_connect(self, get_client):
        """A tuple param (multi-select IN clause) must reach client.query as a list."""
        fake_client = MagicMock()
        fake_result = MagicMock()
        fake_result.result_rows = []
        fake_result.column_names = []
        fake_client.query.return_value = fake_result
        get_client.return_value = fake_client

        executor = self._build_executor()
        executor.execute(
            "SELECT 1 FROM shared.t WHERE x IN %(x)s",
            {'x': ('2025',)},
        )

        kwargs = fake_client.query.call_args.kwargs
        self.assertIn('parameters', kwargs)
        self.assertEqual(
            kwargs['parameters'],
            {'x': ['2025']},
            "tuple param must be coerced to list at the CH boundary",
        )

    @patch('odoo.addons.posterra_portal.utils.query_executors.clickhouse._get_client')
    def test_scalar_params_pass_through_unchanged(self, get_client):
        """Non-tuple params (single-select strings, ints) must NOT be wrapped."""
        fake_client = MagicMock()
        fake_result = MagicMock()
        fake_result.result_rows = []
        fake_result.column_names = []
        fake_client.query.return_value = fake_result
        get_client.return_value = fake_client

        executor = self._build_executor()
        executor.execute(
            "SELECT 1 FROM shared.t WHERE x = %(x)s AND y = %(y)s",
            {'x': '2025', 'y': 42},
        )

        kwargs = fake_client.query.call_args.kwargs
        self.assertEqual(
            kwargs['parameters'],
            {'x': '2025', 'y': 42},
            "scalar params must not be coerced",
        )

    @patch('odoo.addons.posterra_portal.utils.query_executors.clickhouse._get_client')
    def test_list_params_pass_through_unchanged(self, get_client):
        """List params (already in CH-friendly shape) must NOT be re-wrapped."""
        fake_client = MagicMock()
        fake_result = MagicMock()
        fake_result.result_rows = []
        fake_result.column_names = []
        fake_client.query.return_value = fake_result
        get_client.return_value = fake_client

        executor = self._build_executor()
        executor.execute(
            "SELECT 1 FROM shared.t WHERE x IN %(x)s",
            {'x': ['a', 'b']},
        )

        kwargs = fake_client.query.call_args.kwargs
        self.assertEqual(kwargs['parameters'], {'x': ['a', 'b']})

    @patch('odoo.addons.posterra_portal.utils.query_executors.clickhouse._get_client')
    def test_placeholder_translation_sees_normalized_params(self, get_client):
        """The {param:Array(T)} placeholder must be derived from the same
        object that gets bound — guards against future _infer_ch_type
        changes that might treat tuple vs list differently."""
        fake_client = MagicMock()
        fake_result = MagicMock()
        fake_result.result_rows = []
        fake_result.column_names = []
        fake_client.query.return_value = fake_result
        get_client.return_value = fake_client

        executor = self._build_executor()
        executor.execute(
            "SELECT 1 FROM shared.t WHERE x IN %(x)s",
            {'x': ('a',)},
        )

        # client.query is called positionally with the rewritten SQL as args[0].
        args, kwargs = fake_client.query.call_args
        rewritten_sql = args[0] if args else kwargs.get('query', '')
        self.assertIn('{x:Array(String)}', rewritten_sql)
