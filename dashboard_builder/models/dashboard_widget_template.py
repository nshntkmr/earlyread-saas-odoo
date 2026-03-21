# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# ── Category choices ─────────────────────────────────────────────────────────
_CATEGORIES = [
    ('kpi',        'KPI'),
    ('trend',      'Trend'),
    ('comparison', 'Comparison'),
    ('ranking',    'Ranking'),
    ('profile',    'Profile'),
    ('overview',   'Overview'),
]


class DashboardWidgetTemplate(models.Model):
    _name = 'dashboard.widget.template'
    _description = 'Widget Template'
    _order = 'category, name'

    name = fields.Char(required=True, string='Template Name')
    description = fields.Text(
        string='Description',
        help='Short description of what this template creates.')
    category = fields.Selection(
        _CATEGORIES, required=True, default='kpi',
        string='Category')
    preview_image = fields.Binary(
        string='Preview Image', attachment=True,
        help='Thumbnail shown in the template picker.')
    widget_configs = fields.Text(
        string='Widget Configs (JSON)',
        help='JSON array of widget configuration objects. '
             'Each object becomes one dashboard.widget record when the template is used.')
    creates_count = fields.Integer(
        compute='_compute_creates_count', string='Creates',
        help='Number of widgets this template produces.')

    # ── Computed fields ──────────────────────────────────────────────────────

    @api.depends('widget_configs')
    def _compute_creates_count(self):
        for rec in self:
            try:
                configs = json.loads(rec.widget_configs or '[]')
                rec.creates_count = len(configs) if isinstance(configs, list) else 0
            except (json.JSONDecodeError, TypeError):
                rec.creates_count = 0

    # ── Public API ───────────────────────────────────────────────────────────

    def action_use_template(self, page_id, tab_id=None):
        """Create dashboard.widget records from widget_configs JSON.

        Args:
            page_id: int — ID of the dashboard.page to place widgets on
            tab_id:  int or None — optional dashboard.page.tab ID

        Returns:
            list of created widget IDs
        """
        self.ensure_one()
        configs = json.loads(self.widget_configs or '[]')
        if not isinstance(configs, list):
            raise ValueError('widget_configs must be a JSON array.')

        Widget = self.env['dashboard.widget'].sudo()
        created_ids = []
        seq = 10

        for cfg in configs:
            if not isinstance(cfg, dict):
                _logger.warning('Template %s: skipping non-dict config entry', self.name)
                continue

            vals = self._config_to_widget_vals(cfg, page_id, tab_id, seq)
            widget = Widget.create(vals)
            created_ids.append(widget.id)
            seq += 10

        _logger.info(
            'Template "%s" created %d widgets on page %s',
            self.name, len(created_ids), page_id,
        )
        return created_ids

    # ── Private helpers ──────────────────────────────────────────────────────

    def _config_to_widget_vals(self, cfg, page_id, tab_id, seq):
        """Convert a single template config dict into dashboard.widget create values."""
        vals = {
            'page_id': page_id,
            'sequence': seq,
            'is_active': True,
        }
        if tab_id:
            vals['tab_id'] = tab_id

        # Direct field mappings
        direct_fields = [
            'name', 'chart_type', 'col_span', 'chart_height',
            'color_palette', 'color_custom_json',
            'query_type', 'query_sql',
            'x_column', 'y_columns', 'series_column',
            'status_column', 'you_column', 'them_column', 'label_column',
            'win_threshold', 'competitor_name',
            'metric1_label', 'metric2_label', 'metric3_label',
            'narrative_template', 'echart_override',
            'kpi_format', 'kpi_prefix', 'kpi_suffix',
            'gauge_min', 'gauge_max', 'gauge_color_mode',
            'gauge_warn_threshold', 'gauge_good_threshold',
            'gauge_sub_kpi_columns', 'gauge_sub_kpi_labels',
            'gauge_sub_label_columns', 'gauge_alert_column',
            # Action mixin fields
            'click_action', 'action_page_key', 'action_tab_key',
            'action_pass_value_as', 'drill_detail_columns',
            'action_url_template', 'column_link_config',
            'builder_config',
        ]

        for field in direct_fields:
            if field in cfg:
                vals[field] = cfg[field]

        # Defaults
        vals.setdefault('name', f'Widget {seq // 10}')
        vals.setdefault('chart_type', 'kpi')
        vals.setdefault('col_span', '6')
        vals.setdefault('query_type', 'sql')
        vals.setdefault('color_palette', 'healthcare')

        # Handle nested appearance config → flat fields
        appearance = cfg.get('appearance', {})
        if appearance:
            if 'kpi_format' in appearance:
                vals.setdefault('kpi_format', appearance['kpi_format'])
            if 'kpi_prefix' in appearance:
                vals.setdefault('kpi_prefix', appearance['kpi_prefix'])
            if 'kpi_suffix' in appearance:
                vals.setdefault('kpi_suffix', appearance['kpi_suffix'])

        # Handle nested columns config → x_column / y_columns
        columns = cfg.get('columns', {})
        if columns:
            if 'x' in columns:
                x_items = columns['x']
                if isinstance(x_items, list) and x_items:
                    vals.setdefault('x_column', x_items[0].get('column', ''))
            if 'y' in columns:
                y_items = columns['y']
                if isinstance(y_items, list):
                    y_cols = [y.get('column', '') for y in y_items if y.get('column')]
                    vals.setdefault('y_columns', ','.join(y_cols))
            if 'series' in columns:
                vals.setdefault('series_column', columns['series'])

        return vals
