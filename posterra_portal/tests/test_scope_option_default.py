# -*- coding: utf-8 -*-
"""Default scope option for data requests without ``_scope_option_id``.

``dashboard.widget._default_query_scope_option()`` is the single rule the
widget data API uses when a "Different SQL Per Option" widget is fetched
without an option id (deferred-tab lazy load on first render, downloads,
projection refreshes). It mirrors the page's first-paint rule and returns
an EMPTY recordset whenever the pre-existing widget-level fallback must
keep applying, so widgets without scope options are untouched.

Run:
    odoo-bin --test-enable -i posterra_portal \\
             --test-tags posterra_scope_default --stop-after-init -d <test_db>
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'posterra_scope_default')
class TestDefaultQueryScopeOption(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = cls.env['saas.app'].create({
            'name': 'SD App', 'app_key': 'sdapp', 'access_mode': 'group',
        })
        cls.nav = cls.env['dashboard.nav.section'].create(
            {'name': 'SD Nav', 'key': 'sd_nav'})
        cls.page = cls.env['dashboard.page'].create({
            'name': 'SD Page', 'key': 'sd_page', 'app_id': cls.app.id,
            'nav_section_id': cls.nav.id, 'portal_type': 'all', 'is_active': True,
        })
        cls.Option = cls.env['dashboard.widget.scope.option']

    def _widget(self, **vals):
        base = {
            'page_id': self.page.id, 'name': 'SD Table', 'chart_type': 'table',
            'query_type': 'sql', 'query_sql': 'SELECT 1 AS a',
            'scope_mode': 'independent', 'scope_ui': 'toggle',
            'scope_query_mode': 'query',
        }
        base.update(vals)
        return self.env['dashboard.widget'].create(base)

    def _opt(self, widget, value, sequence, sql='SELECT 2 AS a', **vals):
        base = {'widget_id': widget.id, 'label': value, 'value': value,
                'sequence': sequence, 'query_sql': sql}
        base.update(vals)
        return self.Option.create(base)

    # ── Positive cases ────────────────────────────────────────────────────

    def test_first_active_option_by_sequence(self):
        w = self._widget()
        later = self._opt(w, 'all', 20)
        first = self._opt(w, 'with_eid', 10)
        self.assertEqual(w._default_query_scope_option(), first)
        self.assertNotEqual(w._default_query_scope_option(), later)

    def test_scope_default_value_wins(self):
        w = self._widget(scope_default_value='all')
        self._opt(w, 'with_eid', 10)
        all_opt = self._opt(w, 'all', 20)
        self.assertEqual(w._default_query_scope_option(), all_opt)

    def test_unknown_default_value_falls_back_to_first(self):
        w = self._widget(scope_default_value='nope')
        first = self._opt(w, 'with_eid', 10)
        self._opt(w, 'all', 20)
        self.assertEqual(w._default_query_scope_option(), first)

    def test_inactive_option_skipped(self):
        w = self._widget()
        self._opt(w, 'with_eid', 10, is_active=False)
        second = self._opt(w, 'all', 20)
        self.assertEqual(w._default_query_scope_option(), second)

    # ── Empty recordset → caller keeps the widget-level fallback ──────────

    def test_no_options_is_empty(self):
        w = self._widget()
        self.assertFalse(w._default_query_scope_option())

    def test_parameter_mode_is_empty(self):
        w = self._widget(scope_query_mode='parameter')
        self._opt(w, 'with_eid', 10)
        self.assertFalse(w._default_query_scope_option())

    def test_no_scope_is_empty(self):
        w = self._widget(scope_mode='none')
        self.assertFalse(w._default_query_scope_option())

    def test_option_without_sql_is_empty(self):
        w = self._widget()
        self._opt(w, 'with_eid', 10, sql='')
        self.assertFalse(w._default_query_scope_option())
