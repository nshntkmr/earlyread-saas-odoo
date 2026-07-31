# -*- coding: utf-8 -*-
"""Regression tests for the opt-in Detail Drawer chart section."""

import json

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'posterra_detail_drawer_chart')
class TestDetailDrawerChart(TransactionCase):

    def _widget(self, config):
        return self.env['dashboard.widget'].new({
            'name': 'Drawer chart test',
            'chart_type': 'table',
            'detail_drawer_config': json.dumps(config),
        })

    def _chart_config(self, **section_overrides):
        section = {
            'id': 'quarterly_rx',
            'title': 'Quarterly breakdown — Rx Quantity',
            'type': 'chart',
            'source': 'sql',
            'chart_type': 'bar',
            'x_column': 'quarter',
            'y_column': 'rx_qty',
            'series_name': 'Rx Quantity',
            'number_format': 'compact',
            'sql': 'SELECT quarter, rx_qty FROM source '
                   'WHERE npi = %(row_key)s',
        }
        section.update(section_overrides)
        return {
            'enabled': True,
            'trigger': 'row',
            'row_key_column': 'npi',
            'sections': [section],
        }

    def test_chart_section_is_valid_and_sql_is_not_sent_to_portal(self):
        widget = self._widget(self._chart_config())
        widget._check_detail_drawer_config()

        schema = widget._build_drawer_render_schema()
        section = schema['sections'][0]
        self.assertEqual(section['type'], 'chart')
        self.assertEqual(section['series_name'], 'Rx Quantity')
        self.assertTrue(section['has_sql'])
        self.assertNotIn('sql', section)

    def test_existing_section_schema_is_unchanged(self):
        config = {
            'enabled': True,
            'trigger': 'cell',
            'row_key_column': 'member_id',
            'sections': [{
                'id': 'summary',
                'type': 'field_grid',
                'source': 'master_row',
                'columns': 2,
                'fields': [{'label': 'Member', 'column': 'member_id'}],
            }],
        }
        widget = self._widget(config)
        widget._check_detail_drawer_config()

        self.assertEqual(widget._build_drawer_render_schema(), {
            'enabled': True,
            'trigger': 'cell',
            'row_key_column': 'member_id',
            'title_template': '',
            'subtitle_template': '',
            'sections': [{
                'id': 'summary',
                'type': 'field_grid',
                'source': 'master_row',
                'columns': 2,
                'fields': [{'label': 'Member', 'column': 'member_id'}],
                'has_sql': False,
            }],
        })

    def test_chart_requires_data_columns(self):
        widget = self._widget(self._chart_config(x_column=''))
        with self.assertRaisesRegex(ValidationError, 'requires x_column'):
            widget._check_detail_drawer_config()

    def test_chart_rejects_unstandardized_chart_type(self):
        widget = self._widget(self._chart_config(chart_type='pie'))
        with self.assertRaisesRegex(ValidationError, 'supports only'):
            widget._check_detail_drawer_config()
