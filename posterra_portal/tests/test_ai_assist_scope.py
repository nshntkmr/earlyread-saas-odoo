# -*- coding: utf-8 -*-
"""AI Assist visibility + SQL-policy unit tests.

The chatbot's queryable-source set is resolved exclusively through
``dashboard.schema.source.get_ai_visible_sources(app)``. Visibility
requires EXPLICIT per-app AI assignment (``ai_app_ids``) — a source that
is globally available for dashboards (empty ``app_ids``) is still
invisible to the chatbot unless assigned. These tests pin the truth table
plus the AI SQL policy (table allowlist, engine gate, LIMIT cap).

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_ai_assist --stop-after-init -d <test_db>
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..utils.ai_query_policy import build_allowed_tables, check_ai_sql


@tagged('post_install', '-at_install', 'posterra_ai_assist')
class TestAiVisibleSources(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        App = cls.env['saas.app'].sudo()
        cls.app = App.create({
            'name': 'AI Test App', 'app_key': 'ai-test-app',
            'access_mode': 'group', 'ai_assist_enabled': True,
        })
        cls.other_app = App.create({
            'name': 'AI Other App', 'app_key': 'ai-other-app',
            'access_mode': 'group', 'ai_assist_enabled': True,
        })
        cls.Source = cls.env['dashboard.schema.source'].sudo()

    def _mk_source(self, table, assign=True, **vals):
        base = {
            'name': table, 'table_name': table,
            'is_active': True, 'data_classification': 'non_phi',
        }
        if assign:
            base['ai_app_ids'] = [(6, 0, [self.app.id])]
        base.update(vals)
        return self.Source.create(base)

    def _visible(self):
        return self.Source.get_ai_visible_sources(self.app)

    def test_assigned_source_visible(self):
        src = self._mk_source('t_ai_assigned')
        self.assertIn(src, self._visible())

    def test_unassigned_excluded_even_if_globally_available(self):
        # Empty app_ids = globally available for DASHBOARDS — but the
        # chatbot requires explicit AI assignment, so this stays invisible.
        src = self._mk_source('t_ai_unassigned', assign=False)
        self.assertNotIn(src, self._visible())

    def test_assignment_is_per_app(self):
        src = self._mk_source('t_ai_per_app')
        self.assertNotIn(
            src, self.Source.get_ai_visible_sources(self.other_app))
        src.ai_app_ids = [(4, self.other_app.id)]
        self.assertIn(
            src, self.Source.get_ai_visible_sources(self.other_app))

    def test_general_app_scoping_still_applies(self):
        # AI-assigned to self.app but generally scoped to other_app only →
        # invisible (both scoping layers must pass).
        src = self._mk_source('t_ai_general_scope',
                              app_ids=[(6, 0, [self.other_app.id])])
        self.assertNotIn(src, self._visible())

    def test_inactive_excludes(self):
        src = self._mk_source('t_ai_inactive', is_active=False)
        self.assertNotIn(src, self._visible())

    def test_app_toggle_off_yields_empty(self):
        self._mk_source('t_ai_toggle')
        self.app.ai_assist_enabled = False
        self.assertFalse(self._visible())

    def test_no_app_yields_empty(self):
        self._mk_source('t_ai_noapp')
        self.assertFalse(self.Source.get_ai_visible_sources(None))

    def test_phi_constraint_blocks_assignment(self):
        src = self._mk_source('t_ai_phi', assign=False)
        with self.assertRaises(ValidationError):
            src.write({'data_classification': 'phi_masked',
                       'ai_app_ids': [(6, 0, [self.app.id])]})

    def test_reclassify_clears_assignment(self):
        src = self._mk_source('t_ai_reclass')
        self.assertTrue(src.ai_app_ids)
        try:
            src.write({'data_classification': 'phi_masked'})
        except ValidationError as e:
            # PHI source-scoping constraint may fire (no hospital_phi
            # connection in this fixture) — but it must be THAT constraint,
            # not the AI one: the write() hook clears the AI assignment
            # before constraints evaluate.
            self.assertIn('Hospital-PHI', str(e))
        else:
            self.assertFalse(src.ai_app_ids)


@tagged('post_install', '-at_install', 'posterra_ai_assist')
class TestAiQueryPolicy(TransactionCase):
    """Pure-function policy tests — no DB rows needed."""

    ALLOWED = build_allowed_tables(
        ['mer_data', 'gold.utilization_snapshot'])

    def _check(self, sql, engine='clickhouse', allowed=None, cap=500):
        return check_ai_sql(sql, engine, allowed or self.ALLOWED, cap)

    def test_allowed_table_passes(self):
        self._check('SELECT market, SUM(x) FROM mer_data GROUP BY market')

    def test_qualified_and_bare_forms_pass(self):
        self._check('SELECT 1 FROM gold.utilization_snapshot')
        self._check('SELECT 1 FROM utilization_snapshot')

    def test_cross_table_rejected(self):
        # source_id says A; SQL reads B (not AI-visible) → reject.
        with self.assertRaises(ValueError):
            self._check('SELECT * FROM ul_humana_retention_data')

    def test_join_to_non_visible_rejected(self):
        with self.assertRaises(ValueError):
            self._check('SELECT 1 FROM mer_data m '
                        'JOIN secret_table s ON s.id = m.id')

    def test_cte_alias_not_flagged(self):
        self._check('WITH t AS (SELECT market FROM mer_data) '
                    'SELECT * FROM t')

    def test_system_tables_rejected(self):
        for tbl in ('system.tables', 'information_schema.tables',
                    'pg_catalog.pg_tables'):
            with self.assertRaises(ValueError):
                self._check(f'SELECT * FROM {tbl}')

    def test_table_functions_rejected(self):
        with self.assertRaises(ValueError):
            self._check("SELECT * FROM url('http://x', 'CSV')")
        with self.assertRaises(ValueError):
            self._check("SELECT * FROM s3('http://b/x.parquet')")

    def test_postgres_local_engine_rejected(self):
        with self.assertRaises(ValueError):
            self._check('SELECT 1 FROM mer_data', engine='postgres_local')

    def test_oversized_limit_rejected(self):
        with self.assertRaises(ValueError):
            self._check('SELECT * FROM mer_data LIMIT 1000000')
        self._check('SELECT * FROM mer_data LIMIT 100')


@tagged('post_install', '-at_install', 'posterra_ai_assist')
class TestAiQueryLog(TransactionCase):

    def test_log_model_creates(self):
        user = self.env.ref('base.user_admin')
        app = self.env['saas.app'].sudo().create({
            'name': 'AI Log App', 'app_key': 'ai-log-app',
            'access_mode': 'group',
        })
        log = self.env['ai.query.log'].sudo().create({
            'user_id': user.id, 'app_id': app.id, 'app_key': app.app_key,
            'channel': 'mcp', 'mode': 'sql', 'sql': 'SELECT 1',
            'row_count': 1, 'duration_ms': 5, 'status': 'ok',
        })
        self.assertTrue(log.create_date)
        self.assertEqual(log.app_key, 'ai-log-app')
