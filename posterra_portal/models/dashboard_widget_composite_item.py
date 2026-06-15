# -*- coding: utf-8 -*-
"""Composite Widget — Child Block model.

A `dashboard.widget` with `chart_type='composite'` owns 1..N child blocks
defined by this model. Each child carries the subset of widget chart-config
fields needed to render its chart_type via the EXISTING per-chart builders
on `dashboard.widget`.

Render path (see `dashboard.widget._build_composite_data`):
    1. Parent SQL executes once if any active non-text_note child uses
       data_mode='inherit_parent'.
    2. For each child, the builder constructs a transient
       `dashboard.widget.new({...})` populated from this record's fields,
       then dispatches through `_dispatch_chart_builder` — reusing every
       existing chart renderer unchanged. No rendering code is duplicated.
    3. `legend_list` and `text_note` are composite-only types (not present
       on the parent `dashboard.widget.chart_type` Selection) and are built
       directly, bypassing the transient `.new()` dispatch path.

Fields mirror the parent widget's Selections via callable selectors
(`_get_*_selection`) so the dropdowns stay in sync automatically as the
parent evolves — no drift.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# v1 child chart_types — keep aligned with childRegistry.jsx on the React side.
_CHILD_CHART_TYPES = [
    ('bar', 'Bar'),
    ('line', 'Line'),
    ('pie', 'Pie'),
    ('donut', 'Donut'),
    ('kpi', 'KPI'),
    ('status_kpi', 'Status KPI'),
    ('kpi_strip', 'KPI Strip'),
    ('table', 'Table'),
    ('gauge', 'Gauge'),
    ('gauge_kpi', 'Gauge KPI'),
    ('sankey', 'Sankey'),
    ('smart_table', 'Smart Table'),
    ('legend_list', 'Legend List'),  # composite-only
    ('text_note', 'Text Note'),      # composite-only
]


class DashboardWidgetCompositeItem(models.Model):
    _name = 'dashboard.widget.composite.item'
    _description = 'Composite Widget — Child Block'
    _order = 'sequence, id'

    parent_widget_id = fields.Many2one(
        'dashboard.widget',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
    name = fields.Char(
        string='Block Title',
        help='Optional title shown above this child block.',
    )

    chart_type = fields.Selection(
        _CHILD_CHART_TYPES,
        required=True,
        default='kpi',
        help='Chart type for this child block. Child set excludes '
             'ranked_detail_list, map, battle_card, and insight_panel — '
             'those remain available as top-level widgets.',
    )

    # ── Data sourcing — v1 supports inherit_parent + own_sql only ────────
    # No `query_type` field: composite always uses SQL internally; ORM
    # children are not supported in v1.
    data_mode = fields.Selection(
        [
            ('inherit_parent', 'Inherit Parent Query'),
            ('own_sql', 'Own SQL'),
        ],
        required=True,
        default='inherit_parent',
        help='inherit_parent: reuse the composite parent widget\'s already-'
             'executed SQL rows (efficient when multiple children render '
             'different views of the same data). own_sql: this child runs '
             'its own independent SQL.',
    )
    query_sql = fields.Text(
        string='SQL (when Own SQL)',
        help='Only used when data_mode=own_sql. Supports the same '
             '{where_clause} placeholder as parent widgets — schema_source_id '
             'must be set when used.',
    )
    schema_source_id = fields.Many2one(
        'dashboard.schema.source',
        string='Schema Source',
        help='Required when query_sql uses {where_clause}. Drives which '
             'page filters are eligible to be auto-injected.',
    )
    where_clause_exclude = fields.Char(
        string='Exclude from {where_clause}',
        help='Comma-separated param names to skip when auto-building the '
             'WHERE clause. Same semantics as the parent widget.',
    )

    # ── Column mappings ───────────────────────────────────────────────────
    x_column = fields.Char(string='X / Label Column')
    y_columns = fields.Char(
        string='Y / Value Column(s)',
        help='Comma-separated. For legend_list, first = value column, '
             'optional second = explicit pct column.',
    )
    series_column = fields.Char(string='Series Column')
    status_column = fields.Char(string='Status Column')

    # ── Text Note specific ────────────────────────────────────────────────
    text_note_body = fields.Text(
        string='Note Body',
        help='Body text for chart_type=text_note. Plain text; line breaks '
             'preserved. Ignored for other chart types.',
    )

    # ── KPI / chart options (mirrored Selections) ─────────────────────────
    kpi_format = fields.Selection(
        selection='_get_kpi_format_selection',
        default='number',
    )
    kpi_prefix = fields.Char()
    kpi_suffix = fields.Char()
    metric_direction = fields.Selection(
        selection='_get_metric_direction_selection',
        default='higher_better',
    )
    icon_name = fields.Selection(
        selection='_get_icon_selection',
        default='none',
    )
    icon_position = fields.Selection(
        selection='_get_icon_position_selection',
        default='title',
    )
    title_icon_color = fields.Selection(
        selection='_get_title_icon_color_selection',
        default='default',
    )
    kpi_layout = fields.Selection(
        selection='_get_kpi_layout_selection',
        default='vertical',
    )
    display_mode = fields.Selection(
        selection='_get_display_mode_selection',
        default='standard',
    )
    text_align = fields.Selection(
        selection='_get_text_align_selection',
        default='center',
    )

    # ── Color & ECharts overrides ────────────────────────────────────────
    color_custom_json = fields.Text()
    echart_override = fields.Text()
    bar_stack = fields.Boolean(default=False)

    # ── Gauge ─────────────────────────────────────────────────────────────
    gauge_min = fields.Float(default=0.0)
    gauge_max = fields.Float(default=100.0)
    gauge_color_mode = fields.Selection(
        selection='_get_gauge_color_mode_selection',
        default='traffic_light',
    )
    gauge_warn_threshold = fields.Float(default=50.0)
    gauge_good_threshold = fields.Float(default=80.0)

    # ── Visual config (chart-specific flags JSON) ─────────────────────────
    visual_config = fields.Text(default='{}')

    # ── Tables / RDL JSON configs ─────────────────────────────────────────
    table_column_config = fields.Text()
    column_link_config = fields.Text()
    ranked_master_config = fields.Text()
    ranked_detail_config = fields.Text()
    smart_table_config = fields.Text(
        help='Smart Table schema JSON ({"columns": [...], "table": {...}}) '
             'for chart_type=smart_table children. Same shape as the parent '
             'widget field — rendered by dashboard.widget._build_smart_table_data.',
    )

    # ── Layout — 12-col grid inside the composite card ───────────────────
    col_start = fields.Integer(
        default=1,
        help='Grid column start (1-12).',
    )
    col_span = fields.Integer(
        default=12,
        help='Number of columns to span (1-12).',
    )
    row_start = fields.Integer(
        default=0,
        help='Grid row start (0 = auto-place on next available row).',
    )
    row_span = fields.Integer(
        default=1,
        help='Number of rows to span.',
    )
    min_height_px = fields.Integer(
        default=240,
        help='Minimum render height in pixels for this child block. ECharts '
             'and gauges need an explicit height; KPI cards ignore this and '
             'size naturally. Default 240; raise for chart-heavy children.',
    )
    content_vertical_align = fields.Selection(
        [
            ('stretch', 'Stretch'),
            ('top', 'Top'),
            ('center', 'Center'),
            ('bottom', 'Bottom'),
        ],
        default='stretch',
        help='Vertical alignment of the rendered content inside this child '
             'block. Stretch (default) preserves the original fill behavior; '
             'Top/Center/Bottom let content size naturally and align within '
             'the block (e.g. a Legend List vertically centered beside a '
             'taller Donut).',
    )
    content_horizontal_align = fields.Selection(
        [
            ('stretch', 'Stretch'),
            ('left', 'Left'),
            ('center', 'Center'),
            ('right', 'Right'),
        ],
        default='stretch',
        help='Horizontal alignment of the rendered content inside this child '
             'block. Stretch (default) preserves the original full-width '
             'behavior — best for tables.',
    )

    # =========================================================================
    # Mirrored Selection helpers — read parent widget's options at runtime
    # so child dropdowns stay in sync automatically. No hard-coded lists →
    # no drift when the parent gains new options.
    # =========================================================================
    def _mirror_selection(self, field_name):
        try:
            return self.env['dashboard.widget']._fields[field_name].selection
        except (KeyError, AttributeError):
            return []

    def _get_kpi_format_selection(self):
        return self._mirror_selection('kpi_format')

    def _get_metric_direction_selection(self):
        return self._mirror_selection('metric_direction')

    def _get_icon_selection(self):
        return self._mirror_selection('icon_name')

    def _get_icon_position_selection(self):
        return self._mirror_selection('icon_position')

    def _get_title_icon_color_selection(self):
        return self._mirror_selection('title_icon_color')

    def _get_kpi_layout_selection(self):
        return self._mirror_selection('kpi_layout')

    def _get_display_mode_selection(self):
        return self._mirror_selection('display_mode')

    def _get_text_align_selection(self):
        return self._mirror_selection('text_align')

    def _get_gauge_color_mode_selection(self):
        return self._mirror_selection('gauge_color_mode')

    # =========================================================================
    # Constraints
    # =========================================================================
    @api.constrains('col_start', 'col_span')
    def _check_grid_bounds(self):
        for r in self:
            if r.col_start < 1 or r.col_start > 12:
                raise ValidationError(_(
                    "Composite item '%s': col_start must be between 1 and 12."
                ) % (r.name or '(unnamed)'))
            if r.col_span < 1 or (r.col_start + r.col_span - 1) > 12:
                raise ValidationError(_(
                    "Composite item '%s': col_start + col_span must fit "
                    "within the 12-column grid (got col_start=%d, col_span=%d)."
                ) % (r.name or '(unnamed)', r.col_start, r.col_span))

    @api.constrains('query_sql', 'schema_source_id', 'data_mode', 'chart_type')
    def _check_where_clause_needs_source(self):
        """Mirror the parent widget's constraint: if own_sql child uses
        {where_clause}, a schema source is required."""
        for r in self:
            if (r.data_mode == 'own_sql' and r.query_sql
                    and '{where_clause}' in r.query_sql
                    and not r.schema_source_id):
                raise ValidationError(_(
                    "Composite item '%s': own-SQL with {where_clause} "
                    "requires a Schema Source. Either set the source, remove "
                    "the {where_clause} placeholder, or switch data_mode to "
                    "'Inherit Parent Query'."
                ) % (r.name or '(unnamed)'))

    @api.constrains('chart_type', 'data_mode', 'query_sql')
    def _check_own_sql_has_query(self):
        """data_mode='own_sql' requires query_sql for every chart_type EXCEPT
        text_note (which has no SQL at all — its body is in text_note_body)."""
        for r in self:
            if r.chart_type == 'text_note':
                continue
            if r.data_mode == 'own_sql' and not (r.query_sql or '').strip():
                raise ValidationError(_(
                    "Composite item '%s': data_mode='Own SQL' requires a "
                    "non-empty SQL query. Either provide query_sql or switch "
                    "to 'Inherit Parent Query'."
                ) % (r.name or '(unnamed)'))

    @api.constrains('chart_type', 'data_mode', 'parent_widget_id')
    def _check_inherit_parent_has_query(self):
        """Defense in depth — mirror the parent-side constraint
        _check_composite_parent_has_query_if_inherit. Catches direct child
        create/write paths (programmatic, template restore, future wizard)
        that bypass the parent One2many save."""
        for r in self:
            if r.chart_type == 'text_note':
                continue
            if r.data_mode != 'inherit_parent':
                continue
            parent = r.parent_widget_id
            if not parent:
                continue
            if parent.query_type != 'sql' or not (parent.query_sql or '').strip():
                raise ValidationError(_(
                    "Composite item '%s' uses data_mode='Inherit Parent "
                    "Query', but its parent widget '%s' has no SQL configured. "
                    "Either provide a parent query_sql, or switch this child's "
                    "data_mode to 'Own SQL'."
                ) % (r.name or '(unnamed)', parent.name or '(unnamed)'))
