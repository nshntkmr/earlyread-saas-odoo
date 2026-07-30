# -*- coding: utf-8 -*-
"""Model tests for the remote_autocomplete filter (Part D).

Covers the constraint contract and the search_options_page / hydrate_options
behavior: page cap, min-chars, blank exclusion, SQL dedup, LIKE-wildcard
escaping, falsy-value rendering, scope fail-closed (config + runtime), and
error-vs-empty. The executor is mocked so no real Schema Source table is
required.
"""
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase

EXEC_PATH = 'odoo.addons.posterra_portal.utils.query_executors.get_executor'
WHERE_PATH = 'odoo.addons.posterra_portal.models.dashboard_page_filter.DashboardPageFilter._build_schema_where'


def _executor(rows, capture=None):
    """Fake get_executor() whose .execute(sql, params) returns (cols, rows)."""
    def factory(env, source):
        ex = MagicMock()

        def execute(sql, params):
            if capture is not None:
                capture['sql'] = sql
                capture['params'] = dict(params)
            return (['eid', 'patient_name'], rows)

        ex.execute.side_effect = execute
        return ex
    return factory


class TestRemoteAutocomplete(TransactionCase):

    def setUp(self):
        super().setUp()
        self.app = self.env['saas.app'].create({
            'name': 'RA Test', 'app_key': 'ratest', 'access_mode': 'group'})
        self.section = self.env['dashboard.nav.section'].create({
            'name': 'RA', 'key': 'ra_sec'})
        self.page = self.env['dashboard.page'].create({
            'name': 'RA Page', 'key': 'ra_page', 'nav_section_id': self.section.id,
            'app_id': self.app.id, 'portal_type': 'all'})
        self.source = self.env['dashboard.schema.source'].create({
            'name': 'ra_src', 'table_name': 'patient_dim'})
        self.col_eid = self.env['dashboard.schema.column'].create({
            'source_id': self.source.id, 'column_name': 'eid',
            'display_name': 'EID', 'data_type': 'text'})
        self.col_name = self.env['dashboard.schema.column'].create({
            'source_id': self.source.id, 'column_name': 'patient_name',
            'display_name': 'Name', 'data_type': 'text'})
        self.col_ccn = self.env['dashboard.schema.column'].create({
            'source_id': self.source.id, 'column_name': 'hha_ccn',
            'display_name': 'CCN', 'data_type': 'text'})

    def _mk(self, **kw):
        vals = {
            'page_id': self.page.id, 'name': 'Find patient', 'param_name': 'EID',
            'ui_type': 'remote_autocomplete', 'schema_source_id': self.source.id,
            'schema_column_id': self.col_eid.id, 'display_template_source': 'schema',
            'display_template': '{patient_name}',
            'search_column_ids': [(6, 0, [self.col_eid.id, self.col_name.id])],
            'search_page_size': 300, 'search_min_chars': 2, 'default_strategy': 'static',
        }
        vals.update(kw)
        return self.env['dashboard.page.filter'].create(vals)

    # ── Constraints ────────────────────────────────────────────────────────
    def test_valid_config_ok(self):
        self.assertTrue(self._mk())

    def test_requires_value_column(self):
        with self.assertRaises(ValidationError):
            self._mk(schema_column_id=False)

    def test_rejects_non_schema_template_source(self):
        with self.assertRaises(ValidationError):
            self._mk(display_template_source='table')

    def test_rejects_multiselect(self):
        with self.assertRaises(ValidationError):
            self._mk(is_multiselect=True)

    def test_rejects_all_values_default(self):
        with self.assertRaises(ValidationError):
            self._mk(default_strategy='all_values')

    def test_default_strategy_change_retriggers(self):
        f = self._mk()
        with self.assertRaises(ValidationError):
            f.default_strategy = 'first'   # changing only this must re-validate

    def test_requires_search_column(self):
        with self.assertRaises(ValidationError):
            self._mk(search_column_ids=[(5, 0, 0)])

    def test_page_size_range(self):
        with self.assertRaises(ValidationError):
            self._mk(search_page_size=5000)

    def test_control_width_range(self):
        with self.assertRaises(ValidationError):
            self._mk(control_width_px=99)

    def test_scoped_remote_requires_scope_column(self):
        # scope_to_user_hha without an HHA Scope Column would fail OPEN at
        # runtime — the constraint must reject the config.
        with self.assertRaises(ValidationError):
            self._mk(scope_to_user_hha=True)

    def test_scoped_remote_with_scope_column_ok(self):
        self.assertTrue(self._mk(scope_to_user_hha=True,
                                 hha_scope_column_id=self.col_ccn.id))

    def test_scope_column_change_retriggers(self):
        f = self._mk()
        with self.assertRaises(ValidationError):
            f.scope_to_user_hha = True   # flipping this alone must re-validate

    # ── Central no-preload guard ─────────────────────────────────────────────
    def test_get_options_empty_for_remote(self):
        self.assertEqual(self._mk().get_options(), [])

    # ── search_options_page ──────────────────────────────────────────────────
    def test_short_query_returns_empty_without_exec(self):
        f = self._mk(search_min_chars=2)
        with patch(EXEC_PATH) as ge:
            res = f.search_options_page(query='a', limit=300)
        ge.assert_not_called()
        self.assertEqual(res, {'options': [], 'has_more': False})

    def test_page_clamped_to_configured(self):
        f = self._mk(search_page_size=300)
        cap = {}
        with patch(EXEC_PATH, _executor([], cap)):
            f.search_options_page(query='ab', limit=1000)
        # +1 for has_more, clamped to the configured 300 (not the requested 1000).
        self.assertEqual(cap['params']['_limit'], 301)

    def test_has_more_and_formatting(self):
        # search_page_size floor is 10 (constraint + runtime max(10, ...)); need
        # page+1 = 11 rows to trip has_more.
        f = self._mk(search_page_size=10)
        rows = [('E%d' % i, 'P%d' % i) for i in range(11)]  # page + 1
        with patch(EXEC_PATH, _executor(rows)):
            res = f.search_options_page(query='ab')
        self.assertTrue(res['has_more'])
        self.assertEqual(len(res['options']), 10)
        self.assertEqual(res['options'][0], {'value': 'E0', 'label': 'P0'})

    def test_sql_normalizes_value_for_dedup_and_blank(self):
        f = self._mk()
        expr = f._remote_value_expr(f._remote_meta()['engine'], 'eid')
        cap = {}
        with patch(EXEC_PATH, _executor([], cap)):
            f.search_options_page(query='ab')
        self.assertIn('ROW_NUMBER()', cap['sql'])
        self.assertIn('IS NOT NULL', cap['sql'])
        # Dedup partitions on the TRIMMED value (not raw) so whitespace variants
        # collapse before LIMIT/OFFSET; blank rejection uses the same expression.
        self.assertIn('PARTITION BY %s' % expr, cap['sql'])
        self.assertIn("%s <> ''" % expr, cap['sql'])

    def test_search_escapes_wildcards_with_portable_escape(self):
        f = self._mk()
        cap = {}
        with patch(EXEC_PATH, _executor([], cap)):
            f.search_options_page(query='50%')
        # Wildcards escaped with '!' (portable across PG + Snowflake); NO
        # backslash ESCAPE (a syntax error on Snowflake).
        self.assertEqual(cap['params']['_q'], '%50!%%')
        self.assertIn("ESCAPE '!'", cap['sql'])
        self.assertNotIn("ESCAPE '\\'", cap['sql'])

    def test_dedup_by_emitted_value(self):
        # Whitespace-variant source keys ('E1' / ' E1 ') strip to the same
        # emitted value → exactly one option.
        f = self._mk()
        rows = [('E1', 'Alice'), (' E1 ', 'Alice')]
        with patch(EXEC_PATH, _executor(rows)):
            res = f.search_options_page(query='ab')
        self.assertEqual(len(res['options']), 1)
        self.assertEqual(res['options'][0]['value'], 'E1')

    def test_search_error_raises(self):
        f = self._mk()

        def boom(env, source):
            ex = MagicMock()
            ex.execute.side_effect = Exception('conn down')
            return ex

        with patch(EXEC_PATH, boom):
            with self.assertRaises(UserError):
                f.search_options_page(query='ab')

    def test_search_fail_closed_no_providers(self):
        f = self._mk(scope_to_user_hha=True, hha_scope_column_id=self.col_ccn.id)
        with patch(EXEC_PATH) as ge:
            res = f.search_options_page(query='ab', provider_ids=[])
        ge.assert_not_called()
        self.assertEqual(res['options'], [])

    def test_search_fail_closed_when_scope_predicate_absent(self):
        # provider_ids present (passes the empty guard) but scope clause not
        # emitted (e.g. providers resolve to no CCN) → runtime must fail closed.
        f = self._mk(scope_to_user_hha=True, hha_scope_column_id=self.col_ccn.id)
        with patch(EXEC_PATH) as ge, \
                patch(WHERE_PATH, new=lambda self, *a, **k: ([], {})):
            res = f.search_options_page(query='ab', provider_ids=[1])
        ge.assert_not_called()
        self.assertEqual(res['options'], [])

    def test_zero_value_column_renders(self):
        # Default template {value_col} over a numeric-0 value must render, not
        # be dropped by a falsy-substitution bug.
        f = self._mk(display_template=False,
                     search_column_ids=[(6, 0, [self.col_eid.id])])
        with patch(EXEC_PATH, _executor([(0,)])):
            out = f.hydrate_options(['0'])
        self.assertEqual(out, [{'value': '0', 'label': '0'}])

    # ── hydrate_options ──────────────────────────────────────────────────────
    def test_hydrate_fail_closed_no_providers(self):
        f = self._mk(scope_to_user_hha=True, hha_scope_column_id=self.col_ccn.id)
        with patch(EXEC_PATH) as ge:
            self.assertEqual(f.hydrate_options(['E1'], provider_ids=[]), [])
        ge.assert_not_called()

    def test_hydrate_fail_closed_when_scope_predicate_absent(self):
        f = self._mk(scope_to_user_hha=True, hha_scope_column_id=self.col_ccn.id)
        with patch(EXEC_PATH) as ge, \
                patch(WHERE_PATH, new=lambda self, *a, **k: ([], {})):
            self.assertEqual(f.hydrate_options(['E1'], provider_ids=[1]), [])
        ge.assert_not_called()

    def test_hydrate_uses_normalized_rownumber(self):
        f = self._mk()
        expr = f._remote_value_expr(f._remote_meta()['engine'], 'eid')
        cap = {}
        with patch(EXEC_PATH, _executor([('E1', 'Alice')], cap)):
            out = f.hydrate_options(['E1'])
        self.assertIn('ROW_NUMBER()', cap['sql'])
        self.assertNotIn('SELECT DISTINCT', cap['sql'])
        # Equality + dedup both on the normalized value so a padded stored key
        # (' E1 ') hydrates against the stripped selected value ('E1').
        self.assertIn('%s IN' % expr, cap['sql'])
        self.assertIn('PARTITION BY %s' % expr, cap['sql'])
        self.assertEqual(out, [{'value': 'E1', 'label': 'Alice'}])
