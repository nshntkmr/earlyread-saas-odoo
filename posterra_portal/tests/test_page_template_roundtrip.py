# -*- coding: utf-8 -*-
"""Page-template round-trip tests for the Part D remote_autocomplete filter.

Verifies that saving a page with a Remote Search filter as a template and
re-applying it preserves ui_type + placement + apply behavior + the remote
search config, resolves the Schema Source by connector identity, and that a
failed preflight leaves NO new page/filter behind (atomic restore).
"""
import json

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPageTemplateRoundtrip(TransactionCase):

    def setUp(self):
        super().setUp()
        self.app = self.env['saas.app'].create({
            'name': 'RT App', 'app_key': 'rtapp', 'access_mode': 'group'})
        self.sec1 = self.env['dashboard.nav.section'].create({'name': 'S1', 'key': 'rt_s1'})
        self.sec2 = self.env['dashboard.nav.section'].create({'name': 'S2', 'key': 'rt_s2'})
        self.source = self.env['dashboard.schema.source'].create({
            'name': 'rt_src', 'table_name': 'patient_dim'})
        self.col_eid = self.env['dashboard.schema.column'].create({
            'source_id': self.source.id, 'column_name': 'eid',
            'display_name': 'EID', 'data_type': 'text'})
        self.col_name = self.env['dashboard.schema.column'].create({
            'source_id': self.source.id, 'column_name': 'patient_name',
            'display_name': 'Name', 'data_type': 'text'})
        self.src_page = self.env['dashboard.page'].create({
            'name': 'RT Src Page', 'key': 'rt_src_page', 'app_id': self.app.id,
            'nav_section_id': self.sec1.id, 'portal_type': 'all', 'is_active': True})
        self.remote = self.env['dashboard.page.filter'].create({
            'page_id': self.src_page.id, 'name': 'Find patient', 'param_name': 'EID',
            'ui_type': 'remote_autocomplete', 'schema_source_id': self.source.id,
            'schema_column_id': self.col_eid.id, 'display_template_source': 'schema',
            'display_template': '{patient_name}',
            'search_column_ids': [(6, 0, [self.col_eid.id, self.col_name.id])],
            'search_page_size': 300, 'search_min_chars': 2, 'is_active': True,
            'display_region': 'page_header_end', 'apply_behavior': 'immediate',
            'control_width_px': 320})
        self.Template = self.env['dashboard.page.template']

    def _make_template(self):
        cfg = self.Template.serialize_page(self.src_page)
        return cfg, self.Template.create({
            'name': 'RT Template', 'page_config': json.dumps(cfg)})

    def test_roundtrip_preserves_remote_config(self):
        _cfg, tmpl = self._make_template()
        new_page = tmpl.create_page_from_template(self.app.id, self.sec2.id,
                                                  key_override='rt_new_page')
        rf = new_page.filter_ids.filtered(lambda f: f.param_name == 'EID')
        self.assertEqual(len(rf), 1)
        self.assertEqual(rf.ui_type, 'remote_autocomplete')
        self.assertEqual(rf.display_region, 'page_header_end')
        self.assertEqual(rf.apply_behavior, 'immediate')
        self.assertEqual(rf.search_page_size, 300)
        self.assertEqual(rf.search_min_chars, 2)
        self.assertEqual(rf.control_width_px, 320)
        self.assertEqual(rf.display_template_source, 'schema')
        self.assertEqual(rf.display_template, '{patient_name}')
        # Source + columns resolved by name against the target environment.
        self.assertEqual(rf.schema_source_id, self.source)
        self.assertEqual(rf.schema_column_id, self.col_eid)
        self.assertEqual(set(rf.search_column_ids.ids),
                         {self.col_eid.id, self.col_name.id})

    def test_serialize_carries_connector_identity(self):
        cfg = self.Template.serialize_page(self.src_page)
        fdict = next(f for f in cfg['filters'] if f['param_name'] == 'EID')
        # Local-PG source (connection_id NULL) → explicit marker, not blank.
        self.assertEqual(fdict['schema_source_connection'], '__local_pg__')
        self.assertEqual(fdict['schema_source_table'], 'patient_dim')
        self.assertEqual(sorted(fdict['search_column_names']), ['eid', 'patient_name'])

    def test_preflight_missing_column_creates_nothing(self):
        cfg, tmpl = self._make_template()
        # Tamper: point the value column at a column that doesn't exist.
        data = json.loads(tmpl.page_config)
        for f in data['filters']:
            if f['param_name'] == 'EID':
                f['schema_column_name'] = 'ghost_col'
        tmpl.page_config = json.dumps(data)
        before = self.env['dashboard.page'].search_count([('app_id', '=', self.app.id)])
        with self.assertRaises(ValidationError):
            tmpl.create_page_from_template(self.app.id, self.sec2.id, key_override='rt_bad')
        after = self.env['dashboard.page'].search_count([('app_id', '=', self.app.id)])
        # Preflight raises before Page.create → no partial page.
        self.assertEqual(before, after)
        self.assertFalse(self.env['dashboard.page'].search([('key', '=', 'rt_bad')]))

    def test_preflight_missing_search_column_raises(self):
        cfg, tmpl = self._make_template()
        data = json.loads(tmpl.page_config)
        for f in data['filters']:
            if f['param_name'] == 'EID':
                f['search_column_names'] = ['eid', 'ghost_search']
        tmpl.page_config = json.dumps(data)
        with self.assertRaises(ValidationError):
            tmpl.create_page_from_template(self.app.id, self.sec2.id, key_override='rt_bad2')
        self.assertFalse(self.env['dashboard.page'].search([('key', '=', 'rt_bad2')]))
