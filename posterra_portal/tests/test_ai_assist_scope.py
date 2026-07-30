# -*- coding: utf-8 -*-
"""AI Assist visibility + SQL-policy unit tests.

The chatbot's queryable-source set is resolved exclusively through
``dashboard.schema.source.get_ai_visible_sources(app)``. Visibility
requires EXPLICIT per-app AI assignment (``ai_app_ids``) AND the v1
tenancy contract (active ClickHouse connection with
``requires_tenant_filter=True``). The SQL policy is parser- and
scope-aware and REWRITES the outer LIMIT into the executed SQL.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_ai_assist --stop-after-init -d <test_db>
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..utils.ai_query_policy import (
    build_allowed_tables,
    validate_and_rewrite_ai_sql,
)


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
        Conn = cls.env['dashboard.connection'].sudo()
        # v1 tenancy contract: active CH + requires_tenant_filter=True.
        cls.ch_conn = Conn.create({
            'name': 'CH Test', 'engine': 'clickhouse',
            'requires_tenant_filter': True, 'is_active': True,
        })
        cls.ch_conn_unfiltered = Conn.create({
            'name': 'CH Unfiltered', 'engine': 'clickhouse',
            'requires_tenant_filter': False, 'is_active': True,
        })
        cls.Source = cls.env['dashboard.schema.source'].sudo()

    def _mk_source(self, table, assign=True, **vals):
        base = {
            'name': table, 'table_name': table,
            'is_active': True, 'data_classification': 'non_phi',
            'connection_id': self.ch_conn.id,
        }
        if assign:
            base['ai_app_ids'] = [(6, 0, [self.app.id])]
        base.update(vals)
        return self.Source.create(base)

    def _visible(self):
        return self.Source.get_ai_visible_sources(self.app)

    # ── assignment semantics ────────────────────────────────────────────

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

    def test_cross_app_assignment_rejected(self):
        # Generally scoped to other_app only → cannot be AI-assigned to
        # self.app (would be advertised nowhere / inconsistent).
        with self.assertRaises(ValidationError):
            self._mk_source('t_ai_cross_app',
                            app_ids=[(6, 0, [self.other_app.id])])

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

    # ── v1 tenancy contract (fail-closed) ───────────────────────────────

    def test_local_pg_source_cannot_be_assigned(self):
        with self.assertRaises(ValidationError):
            self._mk_source('t_ai_localpg', connection_id=False)

    def test_unfiltered_connection_cannot_be_assigned(self):
        with self.assertRaises(ValidationError):
            self._mk_source('t_ai_nofilter',
                            connection_id=self.ch_conn_unfiltered.id)

    def test_connection_deactivation_hides_source(self):
        src = self._mk_source('t_ai_conn_off')
        self.assertIn(src, self._visible())
        self.ch_conn.is_active = False
        try:
            self.assertNotIn(src, self._visible())
        finally:
            self.ch_conn.is_active = True

    def test_inverse_assignment_validated_on_app_side(self):
        # Writing through saas.app.ai_schema_source_ids must enforce the
        # same eligibility rules (source-side constraint may not fire on
        # inverse M2M writes).
        src = self.Source.create({
            'name': 't_ai_inverse', 'table_name': 't_ai_inverse',
            'is_active': True, 'data_classification': 'non_phi',
            'connection_id': self.ch_conn_unfiltered.id,
        })
        with self.assertRaises(ValidationError):
            self.app.write({'ai_schema_source_ids': [(4, src.id)]})

    def test_inverse_cross_app_assignment_rejected(self):
        src = self.Source.create({
            'name': 't_ai_inv_cross', 'table_name': 't_ai_inv_cross',
            'is_active': True, 'data_classification': 'non_phi',
            'connection_id': self.ch_conn.id,
            'app_ids': [(6, 0, [self.other_app.id])],
        })
        with self.assertRaises(ValidationError):
            self.app.write({'ai_schema_source_ids': [(4, src.id)]})

    # ── PHI interaction ─────────────────────────────────────────────────

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
            # The PHI source-scoping constraint may fire (no hospital_phi
            # connection in this fixture) — but it must be THAT constraint,
            # not the AI one: the write() hook clears the AI assignment
            # before constraints evaluate.
            self.assertIn('Hospital-PHI', str(e))
        else:
            self.assertFalse(src.ai_app_ids)


@tagged('post_install', '-at_install', 'posterra_ai_assist')
class TestAiQueryPolicy(TransactionCase):
    """Parser/scope-based policy — pure functions, no DB rows needed."""

    ALLOWED = build_allowed_tables(
        ['mer_data', 'gold.allowed', 'gold.utilization_snapshot'])

    def _run(self, sql, req=200, engine='clickhouse', cap=500):
        return validate_and_rewrite_ai_sql(
            sql, engine, self.ALLOWED, req, cap)

    def _rejects(self, sql, **kw):
        with self.assertRaises(ValueError):
            self._run(sql, **kw)

    # ── legitimate shapes pass, with the outer LIMIT rewritten in ───────

    def test_allowed_shapes_pass_with_outer_limit(self):
        out = self._run('SELECT market, SUM(x) FROM mer_data '
                        'GROUP BY market')
        self.assertTrue(out.endswith('LIMIT 200'), out)
        self._run('SELECT 1 FROM gold.allowed')
        self._run('WITH t AS (SELECT market FROM mer_data) '
                  'SELECT * FROM t')
        self._run('SELECT m.x FROM mer_data m '
                  'JOIN gold.utilization_snapshot u ON u.k = m.k')
        self._run('SELECT * FROM mer_data, gold.allowed')  # comma join OK
        self._run('SELECT * FROM (SELECT x FROM mer_data) s')

    def test_string_literal_limit_marker_still_capped(self):
        # 'LIMIT' as data would defeat substring-based cap appending —
        # the AST rewrite is immune.
        out = self._run("SELECT 'LIMIT' AS marker FROM mer_data")
        self.assertTrue(out.endswith('LIMIT 200'), out)

    def test_nested_only_limit_gets_outer_cap(self):
        out = self._run('SELECT * FROM (SELECT * FROM mer_data LIMIT 1) x '
                        'CROSS JOIN mer_data y')
        self.assertTrue(out.endswith('LIMIT 200'), out)

    def test_existing_smaller_outer_limit_wins(self):
        out = self._run('SELECT * FROM mer_data LIMIT 50', req=200)
        self.assertTrue(out.endswith('LIMIT 50'), out)

    def test_union_root_wrapped_with_outer_limit(self):
        out = self._run('SELECT a FROM mer_data '
                        'UNION ALL SELECT b FROM mer_data')
        self.assertIn('LIMIT 200', out)

    # ── round-3 probes ──────────────────────────────────────────────────

    def test_cte_scope_shadowing_outer_table_rejected(self):
        # Outer `secret` must NOT be hidden by an inner CTE of the same
        # name (global CTE-name collection was bypassable; scope-aware
        # resolution is not).
        self._rejects(
            'SELECT * FROM secret WHERE EXISTS ('
            'WITH secret AS (SELECT * FROM gold.allowed) '
            'SELECT * FROM secret)')

    def test_legit_cte_shadowing_allowed_outer_passes(self):
        self._run(
            'SELECT * FROM mer_data WHERE EXISTS ('
            'WITH mer_data AS (SELECT * FROM gold.allowed) '
            'SELECT * FROM mer_data)')

    def test_settings_clause_rejected(self):
        self._rejects(
            "SELECT * FROM mer_data SETTINGS SQL_tenant_id = 'other'")

    def test_nested_settings_rejected(self):
        self._rejects('SELECT * FROM ('
                      'SELECT * FROM mer_data SETTINGS max_threads = 8) x')

    def test_format_clause_rejected(self):
        self._rejects('SELECT * FROM mer_data FORMAT JSONEachRow')

    def test_dict_and_join_accessors_rejected(self):
        self._rejects("SELECT dictGet('hidden', 'secret', id) "
                      'FROM mer_data')
        self._rejects("SELECT joinGet('j', 'v', k) FROM mer_data")

    def test_bare_name_of_qualified_registration_rejected(self):
        # 'gold.allowed' is registered; bare 'allowed' could resolve to
        # default.allowed — a different object.
        self._rejects('SELECT 1 FROM allowed')

    def test_case_mismatch_rejected(self):
        # ClickHouse identifiers are case-sensitive; MER_DATA ≠ mer_data.
        self._rejects('SELECT 1 FROM MER_DATA')

    # ── rounds 1–2 stay closed ──────────────────────────────────────────

    def test_comma_join_bypass_rejected(self):
        self._rejects('SELECT * FROM gold.allowed, secret_table')

    def test_limit_null_rejected(self):
        self._rejects('SELECT * FROM gold.allowed LIMIT NULL')

    def test_subquery_hidden_table_rejected(self):
        self._rejects('SELECT * FROM (SELECT x FROM hidden_t) s')

    def test_system_tables_rejected(self):
        for tbl in ('system.tables', 'information_schema.tables',
                    'pg_catalog.pg_tables'):
            self._rejects(f'SELECT * FROM {tbl}')

    def test_table_functions_rejected(self):
        self._rejects("SELECT * FROM url('http://x', 'CSV')")
        self._rejects("SELECT * FROM s3('http://b/x.parquet')")
        self._rejects('SELECT * FROM numbers(10)')

    def test_limit_rules(self):
        self._rejects('SELECT * FROM mer_data LIMIT 1000000')
        self._rejects('SELECT * FROM mer_data LIMIT 1+1')

    # ── round-4 probes ──────────────────────────────────────────────────

    def test_bare_table_in_rejected(self):
        # ClickHouse: `x IN table` == `x IN (SELECT * FROM table)` — an
        # unauthorized-read path invisible to scope traversal.
        self._rejects('SELECT * FROM mer_data WHERE id IN hidden')
        self._rejects('SELECT * FROM mer_data WHERE id GLOBAL IN hidden')

    def test_in_subquery_forms(self):
        # Explicit subquery: allowed table passes, hidden table rejected
        # (its table goes through the normal scope-aware allowlist).
        self._run('SELECT * FROM mer_data WHERE id IN '
                  '(SELECT id FROM gold.allowed)')
        self._rejects('SELECT * FROM mer_data WHERE id IN '
                      '(SELECT id FROM hidden_t)')

    def test_tableless_queries_rejected(self):
        self._rejects('SELECT 1')
        self._rejects('SELECT hostName(), currentUser(), version()')
        self._rejects('SELECT arrayJoin(range(1000000000))')

    def test_infra_disclosure_functions_rejected(self):
        self._rejects('SELECT hostName() FROM mer_data')
        self._rejects("SELECT getSetting('SQL_tenant_id') FROM mer_data")
        self._rejects('SELECT currentUser() FROM mer_data')
        # These parse as TYPED sqlglot nodes (exp.CurrentDatabase /
        # exp.CurrentVersion) — an Anonymous-only scan misses them.
        self._rejects('SELECT currentDatabase() FROM mer_data')
        self._rejects('SELECT version() FROM mer_data')

    def test_normal_aggregates_not_over_blocked(self):
        # The generalized Func scan must not deny ordinary analytics
        # functions (typed nodes like Sum / TimestampTrunc included).
        self._run('SELECT toStartOfMonth(d) AS m, SUM(v), COUNT(*), '
                  'AVG(w), uniqExact(id) FROM mer_data GROUP BY m')

    def test_offset_rejected(self):
        self._rejects('SELECT * FROM mer_data LIMIT 1 OFFSET 1000000000')
        self._rejects('SELECT * FROM mer_data LIMIT 100, 1')  # comma form
        # OFFSET 0 is a no-op — allowed.
        self._run('SELECT * FROM mer_data LIMIT 10 OFFSET 0')

    def test_limit_by_and_with_ties_rejected(self):
        # A global-LIMIT rewrite would silently DROP these modifiers —
        # reject rather than mangle semantics.
        self._rejects('SELECT * FROM mer_data LIMIT 1 BY market')
        self._rejects('SELECT * FROM mer_data ORDER BY x '
                      'LIMIT 1 WITH TIES')

    def test_multi_statement_rejected(self):
        self._rejects('SELECT 1 FROM mer_data; SELECT 2 FROM mer_data')

    def test_unparseable_rejected(self):
        self._rejects('SELECT FROM WHERE (')

    def test_engine_gates(self):
        self._rejects('SELECT 1 FROM mer_data', engine='postgres_local')
        self._rejects('SELECT 1 FROM mer_data', engine='mysql')


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
