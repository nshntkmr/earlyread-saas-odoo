# -*- coding: utf-8 -*-
"""Phase T DB-bound tests: tab-scoped filter constraints, dependency tab
compatibility, runtime-key uniqueness, the ADDITIVE tab-deletion contract,
the filter unlink guard, and placement-change revalidation.

Runs under the Odoo test runner (odoo-bin --test-enable / --test-tags).
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTabScopedFilters(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = cls.env['saas.app'].create({
            'name': 'Tab Test App', 'app_key': 'tabtest',
            'access_mode': 'group',
        })
        cls.page = cls.env['dashboard.page'].create({
            'name': 'P360', 'key': 'p360_tabtest', 'app_id': cls.app.id,
        })
        cls.tab_a = cls.env['dashboard.page.tab'].create({
            'page_id': cls.page.id, 'name': 'Encounters', 'key': 'encounters',
        })
        cls.tab_b = cls.env['dashboard.page.tab'].create({
            'page_id': cls.page.id, 'name': 'Claims', 'key': 'claims',
        })
        cls.Filter = cls.env['dashboard.page.filter']

    def _mk_filter(self, param, tab=None, **vals):
        base = {
            'page_id': self.page.id,
            'param_name': param,
            'manual_options': 'a\nb',
        }
        if tab:
            base.update(display_region='tab_filter_bar', tab_id=tab.id)
        base.update(vals)
        return self.Filter.create(base)

    # ── Region <-> tab constraints ────────────────────────────────────────

    def test_tab_region_requires_tab(self):
        with self.assertRaises(ValidationError):
            self._mk_filter('x1', display_region='tab_filter_bar')

    def test_tab_forbidden_outside_tab_region(self):
        with self.assertRaises(ValidationError):
            self._mk_filter('x2', display_region='filter_bar',
                            tab_id=self.tab_a.id)

    def test_tab_must_match_page(self):
        other_page = self.env['dashboard.page'].create({
            'name': 'Other', 'key': 'other_tabtest', 'app_id': self.app.id,
        })
        with self.assertRaises(ValidationError):
            self.Filter.create({
                'page_id': other_page.id, 'param_name': 'x3',
                'manual_options': 'a', 'display_region': 'tab_filter_bar',
                'tab_id': self.tab_a.id,
            })

    # ── Dependency tab-compatibility matrix ───────────────────────────────

    def _edge(self, src, tgt):
        return self.env['dashboard.filter.dependency'].create({
            'page_id': self.page.id,
            'source_filter_id': src.id, 'target_filter_id': tgt.id,
        })

    def test_dependency_matrix(self):
        g = self._mk_filter('dep_global')
        a1 = self._mk_filter('dep_a1', tab=self.tab_a)
        a2 = self._mk_filter('dep_a2', tab=self.tab_a)
        b1 = self._mk_filter('dep_b1', tab=self.tab_b)
        # page-wide -> tab: OK
        self._edge(g, a1)
        # same tab (and the cycle back): OK
        self._edge(a1, a2)
        self._edge(a2, a1)
        # cross-tab: rejected
        with self.assertRaises(ValidationError):
            self._edge(a1, b1)
        # tab -> page-wide: rejected
        with self.assertRaises(ValidationError):
            self._edge(a1, g)

    def test_placement_change_revalidates_edges(self):
        src = self._mk_filter('reval_src')
        tgt = self._mk_filter('reval_tgt')
        self._edge(src, tgt)   # page-wide -> page-wide, fine
        # Moving the SOURCE into a tab makes the untouched edge tab->page-wide.
        with self.assertRaises(ValidationError):
            src.write({'display_region': 'tab_filter_bar',
                       'tab_id': self.tab_a.id})

    # ── Runtime-key uniqueness (active key = param_name or field_name) ────

    def test_runtime_key_unique_per_page(self):
        self._mk_filter('year')
        with self.assertRaises(ValidationError):
            self._mk_filter('year', tab=self.tab_a)

    def test_runtime_key_reactivation_validates(self):
        self._mk_filter('month')
        dormant = self._mk_filter('month_tmp')
        dormant.write({'is_active': False})
        dormant.write({'param_name': 'month'})   # inactive: no clash yet
        with self.assertRaises(ValidationError):
            dormant.write({'is_active': True})

    # ── Tab deletion: ADDITIVE contract ───────────────────────────────────

    def test_tab_without_tab_filters_deletes_as_today(self):
        tab = self.env['dashboard.page.tab'].create({
            'page_id': self.page.id, 'name': 'Doomed', 'key': 'doomed',
        })
        widget = self.env['dashboard.widget'].create({
            'page_id': self.page.id, 'tab_id': tab.id, 'name': 'W',
            'chart_type': 'kpi', 'query_type': 'sql',
            'query_sql': 'SELECT 1 AS value',
        })
        tab.unlink()   # must NOT raise — today's behavior preserved
        self.assertFalse(widget.tab_id, 'widget must survive as global')

    def test_tab_with_tab_filters_blocks_deletion(self):
        tab = self.env['dashboard.page.tab'].create({
            'page_id': self.page.id, 'name': 'Guarded', 'key': 'guarded',
        })
        self._mk_filter('guarded_year', tab=tab)
        with self.assertRaises(ValidationError):
            tab.unlink()

    # ── Filter unlink guard ───────────────────────────────────────────────

    def test_filter_unlink_blocked_while_referenced(self):
        flt = self._mk_filter('used_param')
        self.env['dashboard.widget'].create({
            'page_id': self.page.id, 'name': 'Uses param',
            'chart_type': 'kpi', 'query_type': 'sql',
            'query_sql': 'SELECT count(*) AS value FROM res_users '
                         'WHERE login != %(used_param)s',
        })
        with self.assertRaises(ValidationError):
            flt.unlink()

    def test_unreferenced_filter_deletes(self):
        flt = self._mk_filter('free_param')
        flt.unlink()   # must not raise

    # ── Widget SQL preflight vs tab filters ───────────────────────────────

    def test_global_widget_cannot_use_tab_param(self):
        self._mk_filter('enc_year', tab=self.tab_a)
        widget = self.env['dashboard.widget'].create({
            'page_id': self.page.id, 'name': 'Global W',
            'chart_type': 'kpi', 'query_type': 'sql',
            'query_sql': 'SELECT 1 AS value',
        })
        # Moving the FILTER is guarded; the reverse direction — the widget
        # gaining foreign-tab SQL — is checked via the inspector helper.
        from odoo.addons.posterra_portal.utils import filter_scope_inspector as insp
        widget.query_sql = ('SELECT count(*) AS value FROM res_users '
                            'WHERE create_date > %(enc_year)s')
        errors = insp.check_sql_surfaces(
            self.env, widget, self.page, None, 'widget %s' % widget.name)
        self.assertTrue(errors, 'foreign-tab placeholder must be flagged')
        errors_same_tab = insp.check_sql_surfaces(
            self.env, widget, self.page, self.tab_a, 'widget %s' % widget.name)
        self.assertFalse(errors_same_tab, 'same-tab consumer is legal')
