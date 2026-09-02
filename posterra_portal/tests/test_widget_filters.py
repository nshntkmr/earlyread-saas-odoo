# -*- coding: utf-8 -*-
"""Widget-level filters (``dashboard.widget.filter``).

Covers the model constraints (param identifiers, mode requirements, the
page/widget runtime-key collision rules in both directions, the mirror
guard rails), option parsing, the runtime injector
(``utils.widget_filters``: declared-only parsing, static "All", mirror
inherit/override, multi-select tuples, ctx copy-not-mutate), the
Designer/template config round trip, and the page-template restore.

Run:
    odoo-bin --test-enable -i posterra_portal \\
             --test-tags posterra_widget_filters --stop-after-init -d <test_db>
"""

import json

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.posterra_portal.utils.widget_filters import (
    apply_widget_filter_values, default_values, parse_widget_filter_kw,
)


@tagged('post_install', '-at_install', 'posterra_widget_filters')
class TestWidgetFilters(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = cls.env['saas.app'].create({
            'name': 'WF App', 'app_key': 'wfapp', 'access_mode': 'group',
        })
        cls.nav = cls.env['dashboard.nav.section'].create(
            {'name': 'WF Nav', 'key': 'wf_nav'})
        cls.page = cls.env['dashboard.page'].create({
            'name': 'WF Page', 'key': 'wf_page', 'app_id': cls.app.id,
            'nav_section_id': cls.nav.id, 'portal_type': 'all', 'is_active': True,
        })
        Filter = cls.env['dashboard.page.filter']
        cls.pf_year = Filter.create({
            'page_id': cls.page.id, 'param_name': 'year',
            'manual_options': '2023\n2024', 'is_active': True,
        })
        cls.pf_state = Filter.create({
            'page_id': cls.page.id, 'param_name': 'state_cd',
            'manual_options': 'TX\nCA', 'is_multiselect': True, 'is_active': True,
        })
        cls.pf_hidden = Filter.create({
            'page_id': cls.page.id, 'param_name': 'hha_ccn',
            'manual_options': '1\n2', 'is_visible': False, 'is_active': True,
        })
        cls.widget = cls.env['dashboard.widget'].create({
            'page_id': cls.page.id, 'name': 'WF Pie', 'chart_type': 'pie',
            'query_type': 'sql',
            'query_sql': 'SELECT 1 AS a WHERE 1=1 [[ AND x = %(age_group)s ]]',
        })
        cls.WF = cls.env['dashboard.widget.filter']

    def _wf(self, **vals):
        base = {'widget_id': self.widget.id, 'label': 'Age Group',
                'param_name': 'age_group', 'options_mode': 'static',
                'manual_options': '0-17|Children\n18-64\n65+'}
        base.update(vals)
        return self.WF.create(base)

    # ── Options + declarations ────────────────────────────────────────────

    def test_static_options_and_payload(self):
        f = self._wf(default_value='18-64')
        self.assertEqual(f.get_options(), [
            {'value': '0-17', 'label': 'Children'},
            {'value': '18-64', 'label': '18-64'},
            {'value': '65+', 'label': '65+'},
        ])
        self.assertEqual(f.runtime_param, 'age_group')
        self.assertFalse(f.is_multiselect)
        decl = self.widget.get_widget_filter_declarations()
        self.assertEqual(decl, [{'param_name': 'age_group', 'mode': 'static',
                                 'is_multiselect': False, 'default_value': '18-64'}])
        payload = self.widget.get_widget_filters_payload()[0]
        self.assertEqual(payload['param_name'], 'age_group')
        self.assertEqual(payload['default_value'], '18-64')
        self.assertEqual(len(payload['options']), 3)
        self.assertEqual(payload['filter_param'], '')

    def test_multiselect_ui_sets_flag(self):
        f = self._wf(ui_type='multiselect')
        self.assertTrue(f.is_multiselect)

    def test_mirror_borrows_param_and_multiselect(self):
        f = self._wf(label='State', param_name='', options_mode='mirror',
                     manual_options='', page_filter_id=self.pf_state.id)
        self.assertEqual(f.runtime_param, 'state_cd')
        self.assertTrue(f.is_multiselect)          # from the page filter
        self.assertEqual(f.get_options(), [])       # React reads page options
        payload = f.to_portal_payload()
        self.assertEqual(payload['filter_param'], 'state_cd')
        self.assertEqual(payload['filter_id'], self.pf_state.id)

    # ── Constraints ───────────────────────────────────────────────────────

    def test_bad_identifier_rejected(self):
        with self.assertRaises(ValidationError):
            self._wf(param_name='age group')
        with self.assertRaises(ValidationError):
            self._wf(param_name='a.b')

    def test_static_needs_options(self):
        with self.assertRaises(ValidationError):
            self._wf(manual_options='')

    def test_schema_needs_source_and_identifier_column(self):
        with self.assertRaises(ValidationError):
            self._wf(options_mode='schema', manual_options='')
        src = self.env['dashboard.schema.source'].create(
            {'name': 'wf_src', 'table_name': 'wf_table'})
        with self.assertRaises(ValidationError):
            self._wf(options_mode='schema', manual_options='',
                     schema_source_id=src.id, value_column='bad col')
        ok = self._wf(options_mode='schema', manual_options='',
                      schema_source_id=src.id, value_column='age_group')
        self.assertEqual(ok.options_mode, 'schema')

    def test_static_cannot_shadow_page_filter(self):
        with self.assertRaises(ValidationError):
            self._wf(param_name='year')

    def test_page_filter_cannot_take_widget_key(self):
        self._wf()  # owns 'age_group'
        with self.assertRaises(ValidationError):
            self.env['dashboard.page.filter'].create({
                'page_id': self.page.id, 'param_name': 'age_group',
                'manual_options': 'x\ny',
            })

    def test_same_widget_duplicate_key_rejected(self):
        self._wf()
        with self.assertRaises(ValidationError):
            self._wf(label='Again')
        # A mirror of 'year' plus a static 'year' cannot coexist either.
        self._wf(label='Year', param_name='', options_mode='mirror',
                 manual_options='', page_filter_id=self.pf_year.id)
        with self.assertRaises(ValidationError):
            self._wf(label='Year 2', param_name='', options_mode='mirror',
                     manual_options='', page_filter_id=self.pf_year.id)

    def test_mirror_guard_rails(self):
        with self.assertRaises(ValidationError):   # needs a page filter
            self._wf(options_mode='mirror', manual_options='')
        with self.assertRaises(ValidationError):   # hidden filter
            self._wf(options_mode='mirror', manual_options='',
                     page_filter_id=self.pf_hidden.id)
        other_page = self.env['dashboard.page'].create({
            'name': 'Other', 'key': 'wf_other', 'app_id': self.app.id,
            'nav_section_id': self.nav.id, 'portal_type': 'all',
        })
        foreign = self.env['dashboard.page.filter'].create({
            'page_id': other_page.id, 'param_name': 'zip', 'manual_options': '1'})
        with self.assertRaises(ValidationError):   # other page
            self._wf(options_mode='mirror', manual_options='',
                     page_filter_id=foreign.id)
        prov = self.env['dashboard.page.filter'].create({
            'page_id': self.page.id, 'param_name': 'prov', 'manual_options': '1',
            'is_provider_selector': True})
        with self.assertRaises(ValidationError):   # provider selector
            self._wf(options_mode='mirror', manual_options='',
                     page_filter_id=prov.id)

    def test_widget_without_filters_is_noop(self):
        self.assertEqual(self.widget.get_widget_filter_declarations(), [])
        self.assertEqual(self.widget.get_widget_filters_payload(), [])

    # ── Runtime injector (pure helpers) ───────────────────────────────────

    def _ctx(self):
        return {
            'sql_params': {'year': '2024', 'state_cd': ('TX', 'CA'),
                           '_state_cd_single': None, 'selected_hha_ccn': None},
            'filter_values_by_name': {'year': '2024', 'state_cd': 'TX,CA'},
            'selected_hha': None,
        }

    def test_parse_reads_only_declared_params(self):
        declared = [{'param_name': 'age_group', 'mode': 'static',
                     'is_multiselect': False}]
        kw = {'_wf_age_group': ' 18-64 ', '_wf_year': '1999', 'year': '2024'}
        self.assertEqual(parse_widget_filter_kw(kw, declared),
                         {'age_group': '18-64'})
        self.assertEqual(parse_widget_filter_kw({}, declared), {})
        self.assertEqual(parse_widget_filter_kw(kw, []), {})

    def test_apply_static_value_and_blank_all(self):
        declared = [{'param_name': 'age_group', 'mode': 'static',
                     'is_multiselect': False}]
        ctx = self._ctx()
        out = apply_widget_filter_values(ctx, declared, {'age_group': '18-64'})
        self.assertEqual(out['sql_params']['age_group'], '18-64')
        self.assertEqual(out['filter_values_by_name']['age_group'], '18-64')
        # Input ctx untouched (portal.py shares one ctx per tab).
        self.assertNotIn('age_group', ctx['sql_params'])
        self.assertEqual(out['sql_params']['year'], '2024')   # page values kept
        # Blank = All: bound as '' so a placeholder outside [[ ]] never raises,
        # while [[ ]] clauses drop through the usual resolver.
        out2 = apply_widget_filter_values(ctx, declared, {})
        self.assertEqual(out2['sql_params']['age_group'], '')

    def test_apply_multiselect_becomes_tuple(self):
        declared = [{'param_name': 'age_group', 'mode': 'static',
                     'is_multiselect': True}]
        out = apply_widget_filter_values(self._ctx(), declared,
                                         {'age_group': '18-64,65+'})
        self.assertEqual(out['sql_params']['age_group'], ('18-64', '65+'))
        blank = apply_widget_filter_values(self._ctx(), declared, {})
        self.assertEqual(blank['sql_params']['age_group'], ('__all__',))

    def test_apply_mirror_inherits_when_blank_and_overrides_when_set(self):
        declared = [{'param_name': 'year', 'mode': 'mirror',
                     'is_multiselect': False},
                    {'param_name': 'state_cd', 'mode': 'mirror',
                     'is_multiselect': True}]
        ctx = self._ctx()
        inherit = apply_widget_filter_values(ctx, declared, {})
        self.assertEqual(inherit['sql_params']['year'], '2024')
        self.assertEqual(inherit['sql_params']['state_cd'], ('TX', 'CA'))
        override = apply_widget_filter_values(
            ctx, declared, {'year': '2023', 'state_cd': 'NY'})
        self.assertEqual(override['sql_params']['year'], '2023')
        self.assertEqual(override['sql_params']['state_cd'], ('NY',))
        self.assertEqual(override['filter_values_by_name']['year'], '2023')
        self.assertEqual(ctx['sql_params']['year'], '2024')   # not mutated

    def test_no_declarations_returns_same_object(self):
        ctx = self._ctx()
        self.assertIs(apply_widget_filter_values(ctx, [], {}), ctx)

    def test_default_values_helper(self):
        declared = [{'param_name': 'age_group', 'default_value': ' 65+ '},
                    {'param_name': 'year', 'default_value': ''}]
        self.assertEqual(default_values(declared), {'age_group': '65+', 'year': ''})

    # ── Config round trip (Designer / library / builder) ──────────────────

    def test_sync_for_widgets_roundtrip(self):
        src = self.env['dashboard.schema.source'].create(
            {'name': 'wf_src2', 'table_name': 'wf_table2'})
        a = self._wf(default_value='65+')
        b = self._wf(label='State', param_name='', options_mode='mirror',
                     manual_options='', page_filter_id=self.pf_state.id,
                     sequence=20)
        c = self._wf(label='Plan', param_name='plan_name', options_mode='schema',
                     manual_options='', schema_source_id=src.id,
                     value_column='plan_name', label_column='plan_label',
                     ui_type='multiselect', sequence=30)
        items = [x.to_config_dict() for x in (a, b, c)]
        self.assertEqual(items[1]['page_filter_param'], 'state_cd')
        self.assertEqual(items[2]['schema_source_table'], 'wf_table2')

        other = self.env['dashboard.widget'].create({
            'page_id': self.page.id, 'name': 'WF Bar', 'chart_type': 'bar',
            'query_type': 'sql', 'query_sql': 'SELECT 1',
        })
        self.WF.sync_for_widgets(other, items)
        got = other.widget_filter_ids.sorted('sequence')
        self.assertEqual(len(got), 3)
        self.assertEqual(got[0].default_value, '65+')
        self.assertEqual(got[1].page_filter_id, self.pf_state)
        self.assertEqual(got[1].runtime_param, 'state_cd')
        self.assertEqual(got[2].schema_source_id, src)
        self.assertTrue(got[2].is_multiselect)
        # Re-sync replaces (no duplicates), and an empty list clears.
        self.WF.sync_for_widgets(other, items)
        self.assertEqual(len(other.widget_filter_ids), 3)
        self.WF.sync_for_widgets(other, [])
        self.assertEqual(len(other.widget_filter_ids), 0)

    def test_sync_skips_unresolvable_mirror_unless_strict(self):
        other = self.env['dashboard.widget'].create({
            'page_id': self.page.id, 'name': 'WF Bar2', 'chart_type': 'bar',
            'query_type': 'sql', 'query_sql': 'SELECT 1',
        })
        item = {'label': 'Ghost', 'options_mode': 'mirror',
                'page_filter_param': 'ghost_param'}
        self.WF.sync_for_widgets(other, [item])
        self.assertEqual(len(other.widget_filter_ids), 0)
        with self.assertRaises(ValidationError):
            self.WF.sync_for_widgets(other, [item], strict=True)

    # ── Page template restore ─────────────────────────────────────────────

    def test_template_roundtrip_restores_widget_filters(self):
        self._wf(default_value='65+')
        self._wf(label='Year', param_name='', options_mode='mirror',
                 manual_options='', page_filter_id=self.pf_year.id, sequence=20)
        Template = self.env['dashboard.page.template']
        cfg = Template.serialize_page(self.page)
        wcfg = next(w for w in cfg['widgets'] if w['name'] == 'WF Pie')
        self.assertEqual(len(wcfg['widget_filters']), 2)
        tmpl = Template.create({'name': 'WF T', 'page_config': json.dumps(cfg)})
        nav2 = self.env['dashboard.nav.section'].create(
            {'name': 'WF Nav 2', 'key': 'wf_nav2'})
        new_page = tmpl.create_page_from_template(
            self.app.id, nav2.id, key_override='wf_page_copy')
        new_widget = new_page.widget_ids.filtered(lambda w: w.name == 'WF Pie')
        self.assertEqual(len(new_widget), 1)
        got = new_widget.widget_filter_ids.sorted('sequence')
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0].param_name, 'age_group')
        self.assertEqual(got[0].default_value, '65+')
        # The mirror is re-pointed at the NEW page's own Year filter.
        self.assertEqual(got[1].page_filter_id.page_id, new_page)
        self.assertEqual(got[1].runtime_param, 'year')
