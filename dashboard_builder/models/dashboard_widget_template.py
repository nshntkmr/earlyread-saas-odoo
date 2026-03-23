# -*- coding: utf-8 -*-

import json
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

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

_TEMPLATE_MODES = [
    ('legacy_json',   'Legacy JSON'),
    ('parameterized', 'Parameterized'),
]

# Chart types — mirrors dashboard.widget selection
_CHART_TYPES = [
    ('bar', 'Bar'), ('line', 'Line'), ('pie', 'Pie'), ('donut', 'Donut'),
    ('gauge', 'Gauge / Meter'), ('radar', 'Radar / Spider'),
    ('kpi', 'KPI Card'), ('status_kpi', 'KPI Card — Dynamic Icon'),
    ('table', 'Data Table'), ('scatter', 'Scatter'),
    ('heatmap', 'Heatmap'), ('battle_card', 'Battle Card'),
    ('insight_panel', 'Insight Panel'), ('gauge_kpi', 'Gauge + KPI'),
    ('kpi_strip', 'KPI Strip'),
]

_COL_SPAN_CHOICES = [
    ('2', '2/12'), ('3', '3/12 (25%)'), ('4', '4/12 (33%)'),
    ('6', '6/12 (50%)'), ('8', '8/12 (67%)'), ('12', '12/12 (100%)'),
]

_KPI_FORMAT = [
    ('number', 'Number'), ('currency', 'Currency'),
    ('percent', 'Percent'), ('decimal', 'Decimal'),
]

_COLOR_PALETTES = [
    ('default', 'Default'), ('healthcare', 'Healthcare (teal/green)'),
    ('ocean', 'Ocean'), ('warm', 'Warm'), ('mono', 'Mono'), ('custom', 'Custom'),
]

# Regex for design-time placeholders: {{slot_name}}
_SLOT_RE = re.compile(r'\{\{(\w+)\}\}')
# Blocked SQL keywords for text slot values
_BLOCKED_SQL = re.compile(
    r'\b(DROP|DELETE|INSERT|UPDATE|ALTER|EXEC|TRUNCATE|CREATE|GRANT|REVOKE)\b',
    re.IGNORECASE,
)


class DashboardWidgetTemplate(models.Model):
    _name = 'dashboard.widget.template'
    _description = 'Widget Template'
    _order = 'category, name'

    # ── Common fields ─────────────────────────────────────────────────────
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

    template_mode = fields.Selection(
        _TEMPLATE_MODES, default='legacy_json', required=True,
        string='Mode',
        help='legacy_json = old JSON blob; parameterized = slot-based SQL pattern.')

    # ── Legacy mode fields ────────────────────────────────────────────────
    widget_configs = fields.Text(
        string='Widget Configs (JSON)',
        help='JSON array of widget configuration objects. '
             'Each object becomes one dashboard.widget record when the template is used.')
    creates_count = fields.Integer(
        compute='_compute_creates_count', string='Creates',
        help='Number of widgets this template produces.')

    # ── Parameterized mode fields ─────────────────────────────────────────
    sql_pattern = fields.Text(
        string='SQL Pattern',
        help='SQL query with {{slot_name}} design-time placeholders and '
             '%(param)s runtime filter placeholders. '
             'Use {{schema_table}} for the schema source table name.')
    title_pattern = fields.Char(
        string='Title Pattern',
        help='Widget title with {{slot_name}} support, e.g. "Total {{metric_label}}".')
    slot_ids = fields.One2many(
        'dashboard.widget.template.slot', 'template_id',
        string='Template Slots')
    chart_type = fields.Selection(
        _CHART_TYPES, string='Chart Type',
        help='Chart type for generated widgets.')
    col_span = fields.Selection(
        _COL_SPAN_CHOICES, string='Column Span', default='6')
    chart_height = fields.Integer(
        string='Height (px)', default=350)
    color_palette = fields.Selection(
        _COLOR_PALETTES, string='Color Palette', default='healthcare')
    kpi_format = fields.Selection(
        _KPI_FORMAT, string='KPI Format', default='number')
    kpi_prefix = fields.Char(string='KPI Prefix')
    kpi_suffix = fields.Char(string='KPI Suffix')
    where_clause_exclude = fields.Char(
        string='Exclude from {where_clause}',
        help='Comma-separated param names to exclude from auto WHERE generation.')
    multi_instance_configs = fields.Text(
        string='Multi-Instance Configs (JSON)',
        help='JSON array of slot mappings. Each entry creates one widget. '
             'Example: [{"metric_column":"total_admits","metric_label":"Admits"}]')

    # ── Computed fields ──────────────────────────────────────────────────────

    @api.depends('widget_configs', 'template_mode', 'multi_instance_configs')
    def _compute_creates_count(self):
        for rec in self:
            if rec.template_mode == 'parameterized':
                try:
                    instances = json.loads(rec.multi_instance_configs or '[]')
                    rec.creates_count = max(len(instances), 1)
                except (json.JSONDecodeError, TypeError):
                    rec.creates_count = 1
            else:
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

    # ── Parameterized template API ────────────────────────────────────────

    def action_use_parameterized(self, page_id, tab_id=None,
                                  schema_source_id=None,
                                  slot_mappings=None,
                                  instances=None):
        """Create widgets from a parameterized SQL pattern template.

        Args:
            page_id: int — dashboard.page ID
            tab_id: int or None — dashboard.page.tab ID
            schema_source_id: int — dashboard.schema.source ID
            slot_mappings: dict — common {slot_name: value} for all instances
            instances: list[dict] or None — per-widget slot overrides

        Returns:
            list of created widget IDs
        """
        self.ensure_one()
        if self.template_mode != 'parameterized':
            raise ValueError('Template is not parameterized.')
        if not schema_source_id:
            raise ValueError('schema_source_id is required.')

        SchemaSource = self.env['dashboard.schema.source'].sudo()
        source = SchemaSource.browse(schema_source_id)
        if not source.exists():
            raise ValueError(f'Schema source {schema_source_id} not found.')

        # Valid column names for injection prevention
        valid_columns = set(source.column_ids.mapped('column_name'))

        # Build instance list
        slot_mappings = slot_mappings or {}
        if not instances:
            try:
                instances = json.loads(self.multi_instance_configs or '[]')
            except (json.JSONDecodeError, TypeError):
                instances = []
        if not instances:
            instances = [{}]

        Widget = self.env['dashboard.widget'].sudo()
        created_ids = []
        seq = 10

        for inst_cfg in instances:
            if not isinstance(inst_cfg, dict):
                continue

            # Merge: instance overrides common mappings
            merged = dict(slot_mappings)
            merged.update(inst_cfg)
            # Always add schema_table
            merged['schema_table'] = source.table_name

            # Validate slot values
            for slot in self.slot_ids:
                val = merged.get(slot.slot_name, slot.default_value or '')
                if slot.required and not val:
                    raise ValueError(
                        f'Required slot "{slot.label}" ({slot.slot_name}) is empty.')
                if slot.slot_type == 'column' and val:
                    if val not in valid_columns:
                        raise ValueError(
                            f'Column "{val}" not found in schema source '
                            f'"{source.name}". Valid columns: '
                            f'{", ".join(sorted(valid_columns))}')
                if slot.slot_type == 'text' and val and _BLOCKED_SQL.search(val):
                    raise ValueError(
                        f'Slot "{slot.label}" contains blocked SQL keyword.')
                # Ensure merged dict has the value
                merged.setdefault(slot.slot_name, val)

            # Replace {{slot_name}} in SQL pattern
            sql = self.sql_pattern or ''
            title = self.title_pattern or ''

            def replace_slot(match):
                key = match.group(1)
                if key in merged:
                    return str(merged[key])
                return match.group(0)

            sql = _SLOT_RE.sub(replace_slot, sql)
            title = _SLOT_RE.sub(replace_slot, title)

            # Validate no unresolved placeholders
            remaining = _SLOT_RE.findall(sql)
            if remaining:
                raise ValueError(
                    f'Unresolved placeholders in SQL: {remaining}')

            # Build widget values
            vals = {
                'page_id': page_id,
                'sequence': seq,
                'is_active': True,
                'name': title or f'Widget {seq // 10}',
                'chart_type': self.chart_type or 'kpi',
                'col_span': self.col_span or '6',
                'chart_height': self.chart_height or 350,
                'color_palette': self.color_palette or 'healthcare',
                'query_type': 'sql',
                'query_sql': sql,
                'schema_source_id': source.id,
                'where_clause_exclude': self.where_clause_exclude or '',
            }
            if tab_id:
                vals['tab_id'] = tab_id
            if self.kpi_format:
                vals['kpi_format'] = self.kpi_format
            if self.kpi_prefix:
                vals['kpi_prefix'] = self.kpi_prefix
            if self.kpi_suffix:
                vals['kpi_suffix'] = self.kpi_suffix

            widget = Widget.create(vals)
            created_ids.append(widget.id)
            seq += 10

        _logger.info(
            'Parameterized template "%s" created %d widgets on page %s',
            self.name, len(created_ids), page_id,
        )
        return created_ids


class DashboardWidgetTemplateSlot(models.Model):
    _name = 'dashboard.widget.template.slot'
    _description = 'Widget Template Slot'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'dashboard.widget.template', required=True,
        ondelete='cascade', string='Template')
    slot_name = fields.Char(
        required=True, string='Slot Name',
        help='Machine name used in {{slot_name}} placeholders (e.g. metric_column).')
    label = fields.Char(
        required=True, string='Label',
        help='Human-readable label shown in the wizard (e.g. "Metric Column").')
    slot_type = fields.Selection([
        ('column', 'Column (from schema)'),
        ('text', 'Text'),
        ('number', 'Number'),
    ], required=True, default='column', string='Type')
    column_filter = fields.Selection([
        ('any', 'Any column'),
        ('measure', 'Measures only (numeric)'),
        ('dimension', 'Dimensions only (text/date)'),
    ], default='any', string='Column Filter',
        help='For column slots: which columns to show in the dropdown.')
    required = fields.Boolean(default=True, string='Required')
    default_value = fields.Char(string='Default Value')
    sequence = fields.Integer(default=10, string='Sequence')
    help_text = fields.Char(
        string='Help Text',
        help='Tooltip shown in the wizard.')

    _sql_constraints = [
        ('unique_slot_per_template',
         'UNIQUE(template_id, slot_name)',
         'Slot name must be unique within a template.'),
    ]
