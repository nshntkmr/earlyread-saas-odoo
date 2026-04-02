# -*- coding: utf-8 -*-

import json
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ── Color palettes injected into ECharts option['color'] ───────────────────
_PALETTES = {
    'healthcare': ['#0d9488', '#14b8a6', '#2dd4bf', '#6ee7b7', '#34d399', '#059669'],
    'ocean':      ['#1d4ed8', '#3b82f6', '#60a5fa', '#93c5fd', '#0ea5e9', '#38bdf8'],
    'warm':       ['#ea580c', '#f97316', '#fb923c', '#fbbf24', '#f59e0b', '#d97706'],
    'mono':       ['#374151', '#6b7280', '#9ca3af', '#d1d5db', '#e5e7eb', '#f3f4f6'],
}

# ── status_column value → (fa icon class, CSS modifier) ────────────────────
_STATUS_MAP = {
    'up':          ('fa-arrow-up',            'status-up'),
    'disciplined': ('fa-arrow-up',            'status-up'),
    'growing':     ('fa-arrow-up',            'status-up'),
    'down':        ('fa-arrow-down',          'status-down'),
    'retreated':   ('fa-arrow-down',          'status-down'),
    'warning':     ('fa-exclamation-triangle','status-warning'),
    'neutral':     ('fa-minus',               'status-neutral'),
    'stable':      ('fa-minus',               'status-neutral'),
}

# ── Typography mapping dicts ─────────────────────────────────────────────────
_WEIGHT_MAP = {
    'light': '300', 'normal': '400', 'medium': '500',
    'semibold': '600', 'bold': '700',
}
_LABEL_COLOR_MAP = {
    'dark': '#374151', 'medium': '#6b7280',
    'primary': '#1e40af', 'black': '#111827',
}
_VALUE_COLOR_MAP = {
    'dark': '#374151', 'black': '#111827',
    'teal': '#0d9488', 'primary': '#1e40af',
}
# ── Annotation position → ECharts graphic coordinates ────────────────────
_POSITION_MAP = {
    'top_left':      {'left': '5%',  'top': '5%'},
    'top_center':    {'left': '50%', 'top': '5%'},
    'top_right':     {'right': '5%', 'top': '5%'},
    'middle_left':   {'left': '5%',  'top': '50%'},
    'center':        {'left': '50%', 'top': '50%'},
    'middle_right':  {'right': '5%', 'top': '50%'},
    'bottom_left':   {'left': '5%',  'bottom': '5%'},
    'bottom_center': {'left': '50%', 'bottom': '5%'},
    'bottom_right':  {'right': '5%', 'bottom': '5%'},
}

# ── ECharts decal pattern definitions ────────────────────────────────────
_DECAL_STYLES = {
    'hatched':    {'symbol': 'rect', 'dashArrayX': [1, 0], 'dashArrayY': [4, 3], 'rotation': 0.7854},
    'dotted':     {'symbol': 'circle', 'symbolSize': 0.7},
    'crosshatch': {'symbol': 'rect', 'dashArrayX': [1, 0], 'dashArrayY': [4, 3], 'rotation': -0.7854},
    'striped':    {'symbol': 'rect', 'dashArrayX': [1, 0], 'dashArrayY': [2, 5], 'rotation': 0},
}

_ICON_COLOR_MAP = {
    'teal':    {'bg': '#ccfbf1', 'fg': '#0d9488'},
    'blue':    {'bg': '#dbeafe', 'fg': '#2563eb'},
    'green':   {'bg': '#dcfce7', 'fg': '#16a34a'},
    'red':     {'bg': '#fee2e2', 'fg': '#dc2626'},
    'orange':  {'bg': '#ffedd5', 'fg': '#ea580c'},
    'purple':  {'bg': '#f3e8ff', 'fg': '#9333ea'},
    'gray':    {'bg': '#f3f4f6', 'fg': '#6b7280'},
}

# ── DML / DDL keywords that must never appear in admin SQL ─────────────────
_BLOCKED_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|EXECUTE)\b',
    re.IGNORECASE,
)


class DashboardWidget(models.Model):
    _name = 'dashboard.widget'
    _inherit = ['dashboard.widget.action.mixin']
    _description = 'Dashboard Widget'
    _order = 'sequence asc, id asc'

    # ── Link to Widget Library ──────────────────────────────────────────────
    definition_id = fields.Many2one(
        'dashboard.widget.definition', string='From Library',
        ondelete='set null',
        help='Widget definition this instance was created from (if any).')

    # ── Placement ─────────────────────────────────────────────────────────────
    page_id = fields.Many2one(
        'dashboard.page', required=True, ondelete='cascade', string='Page')
    tab_id = fields.Many2one(
        'dashboard.page.tab', string='Tab',
        domain="[('page_id','=',page_id)]",
        ondelete='set null',
        help='Leave empty to show this widget on ALL tabs of the page.')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    # ── Display ───────────────────────────────────────────────────────────────
    name = fields.Char(string='Title', required=True)
    col_span = fields.Selection([
        ('3',  '25%'),
        ('4',  '33%'),
        ('6',  '50%'),
        ('8',  '67%'),
        ('12', '100%'),
    ], default='6', required=True, string='Width (preset)')
    width_pct = fields.Integer(
        default=0, string='Width (%)',
        help='Custom widget width as a percentage (1–100). '
             'When set, overrides the preset Width.')
    max_width_pct = fields.Integer(
        default=0, string='Max Width (%)',
        help='Maximum width this widget can scale to (1–100%). '
             '0 = no limit. Limits auto-scaling when row is underfilled.')
    chart_height = fields.Integer(default=350, string='Height (px)')
    chart_type = fields.Selection([
        ('bar',          'Bar'),
        ('line',         'Line'),
        ('pie',          'Pie'),
        ('donut',        'Donut'),
        ('gauge',        'Gauge / Meter'),
        ('radar',        'Radar / Spider'),
        ('kpi',          'KPI Card'),
        ('status_kpi',   'KPI Card — Dynamic Icon'),
        ('table',        'Data Table'),
        ('scatter',      'Scatter'),
        ('heatmap',      'Heatmap'),
        ('battle_card',  'Battle Card (You vs Them)'),
        ('insight_panel','Insight Panel'),
        ('gauge_kpi',    'Gauge + KPI Breakdown'),
        ('kpi_strip',    'KPI Strip — Compact'),
    ], required=True, default='bar', string='Chart Type')

    display_mode = fields.Selection([
        ('standard', 'Standard'),
        ('compact',  'Compact'),
    ], default='standard', string='Display Mode',
       help='Compact mode renders KPI/Status KPI as a single horizontal row.')

    kpi_layout = fields.Selection([
        ('vertical', 'Vertical'),
        ('inline',   'Inline'),
    ], default='vertical', string='KPI Layout',
       help='Vertical: icon on top, value below. Inline: icon and value side by side.')

    text_align = fields.Selection([
        ('center', 'Center'),
        ('left',   'Left'),
        ('right',  'Right'),
    ], default='center', string='Text Alignment',
       help='Horizontal text alignment for KPI value, label, and trend badge.')

    icon_name = fields.Selection([
        ('none',      'None'),
        ('users',     'People / Users'),
        ('home',      'Home / Building'),
        ('heartbeat', 'Heartbeat / Medical'),
        ('dollar',    'Dollar / Revenue'),
        ('star',      'Star / Quality'),
        ('chart',     'Chart / Trending'),
        ('calendar',  'Calendar / Date'),
        ('clipboard', 'Clipboard / Report'),
    ], default='none', string='Icon',
       help='SVG icon displayed next to the KPI value.')

    icon_color = fields.Selection([
        ('default', 'Default (Status-based)'),
        ('teal',    'Teal'),
        ('blue',    'Blue'),
        ('green',   'Green'),
        ('red',     'Red'),
        ('orange',  'Orange'),
        ('purple',  'Purple'),
        ('gray',    'Gray'),
        ('custom',  'Custom'),
    ], default='default', string='Icon Color',
       help='Color for the icon badge. Default uses status-based colors. Custom uses the hex value below.')

    icon_custom_color = fields.Char(
        string='Icon Custom Color (hex)',
        help='Hex color for the icon foreground, e.g. #1e40af. Only used when Icon Color is "Custom".')

    icon_custom_bg = fields.Char(
        string='Icon Custom Background (hex)',
        help='Hex background color for the icon badge, e.g. #dbeafe. Only used when Icon Color is "Custom".')

    # ── Typography ─────────────────────────────────────────────────────────────
    label_font_weight = fields.Selection([
        ('light', 'Light (300)'),
        ('normal', 'Normal (400)'),
        ('medium', 'Medium (500)'),
        ('semibold', 'Semi-Bold (600)'),
        ('bold', 'Bold (700)'),
    ], default='normal', string='Label Font Weight',
       help='Font weight for label text (titles, headers, metric labels).')

    value_font_weight = fields.Selection([
        ('light', 'Light (300)'),
        ('normal', 'Normal (400)'),
        ('medium', 'Medium (500)'),
        ('semibold', 'Semi-Bold (600)'),
        ('bold', 'Bold (700)'),
    ], default='bold', string='Value Font Weight',
       help='Font weight for value text (KPI values, metric numbers).')

    label_color = fields.Selection([
        ('default', 'Default (Light Gray)'),
        ('dark', 'Dark Gray'),
        ('medium', 'Medium Gray'),
        ('primary', 'Primary Blue'),
        ('black', 'Near Black'),
    ], default='default', string='Label Color',
       help='Color for label text.')

    value_color = fields.Selection([
        ('default', 'Default'),
        ('dark', 'Dark Gray'),
        ('black', 'Near Black'),
        ('teal', 'Teal'),
        ('primary', 'Primary Blue'),
    ], default='default', string='Value Color',
       help='Color for value text.')

    # ── Color palette ─────────────────────────────────────────────────────────
    color_palette = fields.Selection([
        ('default',    'Default (ECharts)'),
        ('healthcare', 'Healthcare (teal/green)'),
        ('ocean',      'Ocean (blue tones)'),
        ('warm',       'Warm (orange/red/amber)'),
        ('mono',       'Monochrome (grey)'),
        ('custom',     'Custom (use override JSON)'),
    ], default='healthcare', string='Color Palette')
    color_custom_json = fields.Char(
        string='Custom Colors (JSON array)',
        help='JSON array of hex color strings, e.g. ["#FF5733","#33FF57","#3357FF"]\n'
             'Only used when Color Palette is set to "Custom".'
    )

    # ── Query mode ────────────────────────────────────────────────────────────
    query_type = fields.Selection([
        ('sql', 'Raw SQL'),
        ('orm', 'Model + Domain'),
    ], required=True, default='sql', string='Query Type')

    # ── SQL branch ────────────────────────────────────────────────────────────
    schema_source_id = fields.Many2one(
        'dashboard.schema.source', string='Schema Source',
        ondelete='set null',
        help='The materialized view or table this widget queries. '
             'Required when using {where_clause} auto-filter.')
    where_clause_exclude = fields.Char(
        string='Exclude from {where_clause}',
        help='Comma-separated param names to exclude from auto-generated '
             'WHERE clause. Use when the widget handles a filter manually '
             '(e.g. "year" for YoY comparison widgets).')
    query_sql = fields.Text(
        string='SQL Query',
        help='SELECT … Only SELECT/WITH allowed.\n'
             'Use %(field_name)s for portal filter values.\n'
             'Use {where_clause} to auto-generate WHERE from page filters.\n'
             'E.g. SELECT ... FROM mv_x WHERE {where_clause}\n'
             'HHA display name is always available as %(hha_name)s')
    x_column = fields.Char(
        string='X / Label Column',
        help='Result column name for X axis or row labels')
    y_columns = fields.Char(
        string='Y / Value Column(s)',
        help='Comma-separated result column names for the value axis')
    series_column = fields.Char(
        string='Series Column',
        help='Result column to split into multiple series (optional)')

    # ── ORM branch ────────────────────────────────────────────────────────────
    orm_model_id = fields.Many2one('ir.model', string='Model', ondelete='set null')
    orm_model_name = fields.Char(
        related='orm_model_id.model', store=True, readonly=True)
    orm_domain = fields.Char(
        string='Domain', default='[]',
        help='Odoo domain expression, e.g. [("is_active","=",True)]')
    orm_groupby_field = fields.Many2one(
        'ir.model.fields', string='Group By',
        domain="[('model_id','=',orm_model_id)]",
        ondelete='set null')
    orm_measure_field = fields.Many2one(
        'ir.model.fields', string='Measure Field',
        domain="[('model_id','=',orm_model_id)]",
        ondelete='set null')
    orm_agg_func = fields.Selection([
        ('count', 'Count'),
        ('sum',   'Sum'),
        ('avg',   'Avg'),
        ('min',   'Min'),
        ('max',   'Max'),
    ], default='count', string='Aggregation')
    orm_series_field = fields.Many2one(
        'ir.model.fields', string='Series Field (optional)',
        domain="[('model_id','=',orm_model_id)]",
        ondelete='set null',
        help='Group results by this field to produce multiple series.')

    # ── status_kpi ────────────────────────────────────────────────────────────
    status_column = fields.Char(
        string='Status Column',
        help='SQL column returning: up / down / neutral / warning / '
             'disciplined / retreated / stable / growing')

    # ── battle_card ───────────────────────────────────────────────────────────
    you_column = fields.Char(
        string='You Column',
        help='SQL column for YOUR metric value')
    them_column = fields.Char(
        string='Them Column',
        help='SQL column for THEIR metric value')
    label_column = fields.Char(
        string='Label Column',
        help='SQL column for the metric row label')
    win_threshold = fields.Selection([
        ('higher', 'Higher is better (you > them = WIN)'),
        ('lower',  'Lower is better (you < them = WIN)'),
    ], default='higher', string='Win Condition')
    competitor_name = fields.Char(
        string='Competitor Label',
        help='Label for the "Them" column, e.g. UNITEDHEALTH')

    # ── insight_panel ─────────────────────────────────────────────────────────
    metric1_label = fields.Char(
        string='Metric 1 Label',
        help='Label for first stat column, e.g. Pre-PDGM Avg (2017-19)')
    metric2_label = fields.Char(
        string='Metric 2 Label',
        help='Label for second stat column, e.g. Post-COVID Avg (2023-25)')
    metric3_label = fields.Char(
        string='Metric 3 Label',
        help='Label for third stat column, e.g. Drift')
    narrative_template = fields.Text(
        string='Narrative Template',
        help='Template text for the insight description.\n'
             'Variables automatically available:\n'
             '  %(hha_name)s       — display name of selected HHA\n'
             '  %(hha_state)s      — selected State filter value\n'
             '  %(hha_county)s     — selected County filter value\n'
             '  %(classification)s — SQL result column "classification"\n'
             '  %(metric1)s        — SQL result column "metric1"\n'
             '  %(metric2)s        — SQL result column "metric2"\n'
             '  %(metric3)s        — SQL result column "metric3"\n'
             '  Any other SQL result column name also works.\n'
             '  Any active page filter field_name also works.\n\n'
             'Example:\n'
             '%(hha_name)s in %(hha_state)s decreased their therapy mix after PDGM.\n'
             'This "%(classification)s" trajectory may indicate a shift toward\n'
             'nursing-heavy models.')

    # ── Advanced ──────────────────────────────────────────────────────────────
    echart_override = fields.Text(
        string='ECharts Override (JSON)',
        help='JSON object deep-merged into the generated ECharts option.\n'
             'Set "color" here to override the color palette.')

    # ── Annotations (all widget types) ─────────────────────────────────────
    subtitle = fields.Char(string='Subtitle',
        help='Displayed under the widget title. For EChart types, also maps to title.subtext.\n'
             'Supports SQL interpolation: %(column_name)s is replaced with first-row values.\n'
             'Example: "MA at %(ma_pct)s%% — %(report_period)s"')
    footnote = fields.Text(string='Footnote',
        help='Displayed below the widget content area.\n'
             'Supports SQL interpolation: %(column_name)s is replaced with first-row values.\n'
             'Example: "Source: CMS data as of %(data_date)s"')
    annotation_text = fields.Char(string='Annotation Text',
        help='Text label for chart annotation. Used with reference_line, text_overlay, or badge.\n'
             'Supports SQL interpolation: %(column_name)s is replaced with first-row values.\n'
             'Example: "MA at %(ma_pct)s%%"')
    annotation_type = fields.Selection([
        ('none',           'None'),
        ('reference_line', 'Reference Line'),
        ('text_overlay',   'Text Overlay'),
        ('badge',          'Badge'),
    ], default='none', string='Annotation Type')
    annotation_value = fields.Float(string='Annotation Value',
        help='Static Y-axis value for reference line. Ignored when Annotation Value Column is set.')
    annotation_value_column = fields.Char(string='Annotation Value Column',
        help='SQL column name returning a numeric value for the reference line.\n'
             'Overrides the static Annotation Value when set.\n'
             'E.g. "ma_pct" from your main SQL query or annotation query.')
    annotation_query_sql = fields.Text(string='Annotation SQL',
        help='Optional separate SQL query for annotation data.\n'
             'Use when annotation values require different aggregation than the chart data.\n'
             'Must return a single row. All columns become available for %(col)s interpolation.\n\n'
             'Example:\n'
             'SELECT ROUND(100.0 * SUM(CASE WHEN payer_type = \'MA\' THEN admits END)\n'
             '       / NULLIF(SUM(admits), 0)) AS ma_pct,\n'
             '       \'MA at \' || ROUND(...) || \'%%\' AS label\n'
             'FROM mv_hha_payer_mix\n'
             'WHERE hha_ccn = %(hha_ccn)s\n\n'
             'If blank, annotation interpolation uses the main chart query\'s first row.')

    # ── Flexible positioning (grid preset + custom override) ───────────────
    annotation_position = fields.Selection([
        ('top_left',      'Top Left'),
        ('top_center',    'Top Center'),
        ('top_right',     'Top Right'),
        ('middle_left',   'Middle Left'),
        ('center',        'Center'),
        ('middle_right',  'Middle Right'),
        ('bottom_left',   'Bottom Left'),
        ('bottom_center', 'Bottom Center'),
        ('bottom_right',  'Bottom Right'),
    ], default='top_right', string='Annotation Position',
        help='Preset grid position. Use custom X/Y below for precise placement.')
    annotation_x = fields.Integer(string='Custom X %', default=0,
        help='Horizontal position 0-100 (0=left, 100=right). Overrides grid when > 0.')
    annotation_y = fields.Integer(string='Custom Y %', default=0,
        help='Vertical position 0-100 (0=top, 100=bottom). Overrides grid when > 0.')
    annotation_align = fields.Selection([
        ('left', 'Left'), ('center', 'Center'), ('right', 'Right'),
    ], default='right', string='Text Align')
    annotation_font_size = fields.Integer(string='Font Size', default=12)
    annotation_color = fields.Char(string='Annotation Color', default='#6b7280',
        help='Hex color for annotation text')

    # ── Hatched / Pattern fills ────────────────────────────────────────────
    pattern_style = fields.Selection([
        ('hatched',    'Hatched'),
        ('dotted',     'Dotted'),
        ('crosshatch', 'Crosshatch'),
        ('striped',    'Striped'),
    ], default='hatched', string='Pattern Style')
    pattern_column = fields.Char(string='Pattern Column',
        help='SQL column returning true/false — rows where true get a pattern fill.\n'
             'Useful for highlighting projected or partial-year data.')
    pattern_series = fields.Char(string='Pattern Series',
        help='Comma-separated series names to apply patterns to.\n'
             'E.g. "Projected,Estimated"')
    enable_aria_decal = fields.Boolean(string='Accessibility Patterns', default=False,
        help='Enable ECharts accessibility decal patterns on all series.\n'
             'Adds distinct visual patterns for colorblind-friendly charts.')

    # ── Visual Config (chart-specific flags from React builder) ─────────
    visual_config = fields.Text(
        string='Visual Config',
        help='JSON object with chart-specific visual flags.\n'
             'Written by the React builder. Overrides dedicated fields when present.\n'
             'Example: {"orientation": "horizontal", "stack": true, "show_labels": true}')

    # ── Bar chart options ────────────────────────────────────────────────
    bar_stack = fields.Boolean(
        string='Stack Bars', default=False,
        help='Stack bar series on top of each other instead of side-by-side.\n'
             'Adds ECharts stack property to all bar series.')

    kpi_format = fields.Selection([
        ('number',   'Number'),
        ('currency', '$'),
        ('percent',  '%'),
        ('decimal',  '0.00'),
    ], default='number', string='KPI Format')
    kpi_prefix = fields.Char(string='KPI Prefix')
    kpi_suffix = fields.Char(string='KPI Suffix')

    # ── Gauge scale + color ───────────────────────────────────────────────────
    gauge_min = fields.Float(
        string='Min Value', default=0,
        help='Minimum of the gauge scale (default 0)')
    gauge_max = fields.Float(
        string='Max Value', default=100,
        help='Maximum of the gauge scale — use 5, 10, 100, etc.')
    gauge_color_mode = fields.Selection([
        ('single',        'Single color (from palette)'),
        ('traffic_light', 'Traffic light — red / amber / green'),
    ], default='traffic_light', string='Color Mode')
    gauge_warn_threshold = fields.Float(
        string='Warning Threshold %', default=50,
        help='Below this % of the max range → red zone (traffic_light mode)')
    gauge_good_threshold = fields.Float(
        string='Good Threshold %', default=70,
        help='Above this % of the max range → green zone (traffic_light mode)')

    # ── gauge_kpi sub-KPI breakdown ───────────────────────────────────────────
    gauge_sub_kpi_columns = fields.Char(
        string='Sub-KPI Value Columns',
        help='Comma-separated SQL column names for sub-KPI values (e.g. ffs_val,ma_val)')
    gauge_sub_kpi_labels = fields.Char(
        string='Sub-KPI Labels',
        help='Comma-separated display labels matching each sub-KPI column (e.g. FFS,MA)')
    gauge_sub_label_columns = fields.Char(
        string='Sub-KPI Sub-label Columns',
        help='Optional SQL columns for secondary text under each card (e.g. ffs_pct_label,ma_pct_label)')
    gauge_alert_column = fields.Char(
        string='Alert Text Column',
        help='SQL column returning warning/insight text shown at the bottom of the widget')

    # ── Library onchange: populate widget from definition ─────────────────────
    @api.onchange('definition_id')
    def _onchange_definition_id(self):
        """When a library definition is selected, copy its config into this widget."""
        defn = self.definition_id
        if not defn:
            return
        self.name = defn.name
        self.chart_type = defn.chart_type
        self.col_span = defn.default_col_span or '6'
        self.chart_height = defn.chart_height or 350
        self.color_palette = defn.color_palette or 'healthcare'
        self.color_custom_json = defn.color_custom_json
        # Data source
        if defn.data_mode == 'custom_sql':
            self.query_type = 'sql'
            self.query_sql = defn.query_sql
        elif defn.data_mode == 'visual' and defn.generated_sql:
            self.query_type = 'sql'
            self.query_sql = defn.generated_sql
        self.x_column = defn.x_column
        self.y_columns = defn.y_columns
        self.series_column = defn.series_column
        # KPI options
        self.kpi_format = defn.kpi_format
        self.kpi_prefix = defn.kpi_prefix
        self.kpi_suffix = defn.kpi_suffix
        # Gauge options
        self.gauge_min = defn.gauge_min
        self.gauge_max = defn.gauge_max
        self.gauge_color_mode = defn.gauge_color_mode
        # Actions (from mixin)
        self.click_action = defn.click_action
        self.action_page_key = defn.action_page_key
        self.action_tab_key = defn.action_tab_key
        self.action_pass_value_as = defn.action_pass_value_as
        self.action_url_template = defn.action_url_template
        self.drill_detail_columns = defn.drill_detail_columns
        # Bar options
        self.bar_stack = defn.bar_stack
        # Visual config (chart-specific flags from builder)
        self.visual_config = defn.visual_config
        # Advanced
        self.echart_override = defn.echart_override
        # Store builder config for reference
        self.builder_config = defn.builder_config
        # Column links and table column config (from mixin)
        self.column_link_config = defn.column_link_config
        self.table_column_config = defn.table_column_config

    # ── ORM onchange ──────────────────────────────────────────────────────────
    @api.onchange('orm_model_id')
    def _onchange_orm_model_id(self):
        self.orm_groupby_field = False
        self.orm_measure_field = False
        self.orm_series_field = False

    # ── Constraints ──────────────────────────────────────────────────────────
    @api.constrains('query_sql', 'schema_source_id')
    def _check_where_clause_requires_source(self):
        for w in self:
            if w.query_sql and '{where_clause}' in w.query_sql and not w.schema_source_id:
                raise ValidationError(
                    'A Schema Source is required when using {where_clause} in SQL.')

    # =========================================================================
    # Public entry point called by controller
    # =========================================================================

    def get_portal_data(self, portal_ctx):
        """Execute this widget's query and return a render-ready dict.

        portal_ctx keys:
            sql_params              — dict{param_name: value} for SQL %(x)s params
            filter_values_by_name   — dict{param_name: value} for narrative/annotation templates
            selected_hha            — hha.provider recordset or empty
        """
        self.ensure_one()
        try:
            if self.query_type == 'sql':
                sql_params = portal_ctx.get('sql_params', {})
                if '{where_clause}' in (self.query_sql or ''):
                    from ..utils.filter_builder import DashboardFilterBuilder
                    source_columns = {
                        c.column_name for c in self.schema_source_id.column_ids
                    } if self.schema_source_id else None
                    exclude = [
                        p.strip() for p in (self.where_clause_exclude or '').split(',')
                        if p.strip()
                    ] or None
                    builder = DashboardFilterBuilder(
                        user_params=sql_params,
                        filter_defs=portal_ctx.get('_filter_defs', []),
                        source_columns=source_columns,
                        exclude_params=exclude,
                    )
                    where_sql, built_params = builder.build()
                    _logger.info(
                        'WIDGET %s [%s] WHERE: %s | source_cols=%s | exclude=%s',
                        self.id, self.name, where_sql, source_columns, exclude,
                    )
                    effective_params = dict(sql_params)
                    effective_params.update(built_params)
                    effective_params['_where_sql'] = where_sql
                    cols, rows = self._execute_sql(effective_params)
                else:
                    cols, rows = self._execute_sql(sql_params)
            else:
                cols, rows = self._execute_orm()

            if self.chart_type in ('kpi', 'status_kpi', 'kpi_strip'):
                result = self._build_kpi_data(cols, rows, portal_ctx)
            elif self.chart_type == 'table':
                result = self._build_table_data(cols, rows)
            elif self.chart_type == 'battle_card':
                result = self._build_battle_data(cols, rows)
            elif self.chart_type == 'insight_panel':
                result = self._build_insight_data(cols, rows, portal_ctx)
            elif self.chart_type == 'gauge_kpi':
                result = self._build_gauge_kpi_data(cols, rows)
            elif self.chart_type == 'gauge':
                # Dispatch gauge variants — non-ECharts styles return plain dicts
                # Merge visual_config: definition flags first, instance overrides on top.
                # This ensures new flags added to the definition (like rag_layout)
                # are picked up even if the instance has an older visual_config.
                _vc = {}
                if self.definition_id and self.definition_id.visual_config:
                    try:
                        _vc = json.loads(self.definition_id.visual_config) or {}
                    except (json.JSONDecodeError, TypeError):
                        pass
                if self.visual_config:
                    try:
                        _vc_inst = json.loads(self.visual_config) or {}
                        _vc.update(_vc_inst)
                    except (json.JSONDecodeError, TypeError):
                        pass
                _gs = _vc.get('gauge_style', 'standard')
                if _gs in ('bullet', 'traffic_light_rag', 'percentile_rank'):
                    result = self._build_gauge_custom(cols, rows, _vc, _gs)
                else:
                    option = self._build_gauge_option(cols, rows)
                    result = {'echart_json': json.dumps(option, default=str)}
                # Typography overrides for all gauge variants
                result.update(self._get_typography_overrides())
            else:
                # Run annotation query once and pass to both chart builder and interpolation
                ann_row = self._get_annotation_row(portal_ctx)
                option = self._build_echart_option(cols, rows, ann_row=ann_row)
                result = {'echart_json': json.dumps(option, default=str)}

            # Interpolate annotation text fields from SQL first row + filter context
            result.update(self._interpolate_annotations(cols, rows, portal_ctx))
            return result
        except Exception as exc:
            _logger.warning('dashboard.widget %s get_portal_data error: %s', self.id, exc)
            return {'error': str(exc)}

    # =========================================================================
    # SQL execution
    # =========================================================================

    def _execute_sql(self, params):
        """Validate and execute the SQL query; return (col_names, rows)."""
        self.ensure_one()
        sql = (self.query_sql or '').strip()
        if not sql:
            return [], []

        # Substitute auto-generated WHERE clause if present
        if '{where_clause}' in sql:
            sql = sql.replace('{where_clause}', params.pop('_where_sql', '1=1'))

        # Process [[...]] optional clauses — "All means omit" for manual SQL
        if '[[' in sql:
            from ..utils.filter_builder import resolve_optional_clauses
            sql = resolve_optional_clauses(sql, params)

        # Strip block and line comments before keyword check
        sql_clean = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        sql_clean = re.sub(r'--[^\n]*', ' ', sql_clean)
        first_word = sql_clean.strip().split()[0].upper() if sql_clean.strip() else ''

        if first_word not in ('SELECT', 'WITH'):
            raise ValueError('Only SELECT or WITH queries are allowed.')
        if _BLOCKED_KEYWORDS.search(sql_clean):
            raise ValueError('SQL contains a disallowed keyword (DML/DDL not permitted).')

        # Build safe params: fill missing keys with None to avoid KeyError
        safe_params = dict(params)
        for m in re.finditer(r'%\(([^)]+)\)s', sql):
            if m.group(1) not in safe_params:
                safe_params[m.group(1)] = None

        # Auto-unwrap single-element tuples ONLY for params used with ``=``
        # (not ``IN``).  build_sql_params() wraps multiselect filter values
        # as tuples even for single selections, but custom SQL may use
        # ``= %(param)s``.  psycopg2 can't bind a tuple with ``=``.
        # We scan the SQL to find which params are used with ``=`` vs ``IN``
        # and only unwrap the ``=`` ones.
        # Params used with ``IN`` must stay as tuples for psycopg2.
        _eq_params = set()
        for m in re.finditer(r'=\s*%\(([^)]+)\)s', sql):
            _eq_params.add(m.group(1))
        _in_params = set()
        for m in re.finditer(r'IN\s*%\(([^)]+)\)s', sql, re.IGNORECASE):
            _in_params.add(m.group(1))
        for k in _eq_params - _in_params:
            v = safe_params.get(k)
            if isinstance(v, (list, tuple)) and len(v) == 1:
                safe_params[k] = v[0]

        # psycopg2 named params: %(key)s  — pass as dict
        # Use a savepoint so a failed query doesn't poison the whole transaction
        with self.env.cr.savepoint():
            self.env.cr.execute(sql, safe_params)
            cols = [desc[0] for desc in self.env.cr.description] if self.env.cr.description else []
            rows = self.env.cr.fetchall()
            return cols, rows

    # =========================================================================
    # ORM execution
    # =========================================================================

    def _execute_orm(self):
        """Execute ORM read_group query; return (col_names, rows)."""
        self.ensure_one()
        if not self.orm_model_name or not self.orm_groupby_field:
            return [], []
        try:
            Model = self.env[self.orm_model_name].sudo()
        except KeyError:
            raise ValueError(f'Model {self.orm_model_name!r} not found.')

        try:
            domain = eval(self.orm_domain or '[]')  # noqa: S307 — admin-only field
        except Exception:
            domain = []

        groupby_name = self.orm_groupby_field.name
        measure_name = self.orm_measure_field.name if self.orm_measure_field else None
        agg = self.orm_agg_func or 'count'
        series_name = self.orm_series_field.name if self.orm_series_field else None

        fields_arg = [groupby_name]
        if measure_name:
            fields_arg.append(f'{measure_name}:{agg}({measure_name})')
        if series_name and series_name not in fields_arg:
            fields_arg.append(series_name)

        groupby_arg = [groupby_name]
        if series_name:
            groupby_arg.append(series_name)

        groups = Model.read_group(domain=domain, fields=fields_arg,
                                  groupby=groupby_arg, lazy=False)

        col_names = groupby_arg + ([measure_name] if measure_name else ['__count'])
        rows = []
        for g in groups:
            row_vals = []
            for col in groupby_arg:
                raw = g.get(col)
                if isinstance(raw, (list, tuple)) and len(raw) == 2:
                    row_vals.append(raw[1])   # Many2one display name
                else:
                    row_vals.append(raw)
            if measure_name:
                row_vals.append(g.get(measure_name) or 0)
            else:
                row_vals.append(g.get('__count', 0))
            rows.append(tuple(row_vals))
        return col_names, rows

    # =========================================================================
    # Color palette
    # =========================================================================

    def _get_palette_colors(self):
        """Return the list of hex color strings for the selected palette."""
        if self.color_palette == 'custom' and self.color_custom_json:
            try:
                colors = json.loads(self.color_custom_json)
                if isinstance(colors, list) and colors:
                    return colors
            except Exception:
                pass
        return _PALETTES.get(self.color_palette or 'healthcare', [])

    # =========================================================================
    # ECharts option builder
    # =========================================================================

    def _get_annotation_row(self, portal_ctx):
        """Execute annotation_query_sql if set; return a dict of column:value or {}."""
        if not self.annotation_query_sql:
            return {}
        try:
            ann_cols, ann_rows = self._execute_annotation_sql(
                portal_ctx.get('sql_params', {}))
            if ann_rows and ann_cols:
                return {c: ann_rows[0][i] for i, c in enumerate(ann_cols)}
        except Exception as exc:
            _logger.warning('widget %s annotation query error: %s', self.id, exc)
        return {}

    def _build_echart_option(self, cols, rows, ann_row=None):
        """Build a minimal ECharts option dict for the configured chart_type."""
        x_col = (self.x_column or '').strip()
        y_cols_raw = (self.y_columns or '').strip()
        y_col_list = [c.strip() for c in y_cols_raw.split(',') if c.strip()]
        series_col = (self.series_column or '').strip()

        # Index columns
        col_idx = {c: i for i, c in enumerate(cols)}

        def col_val(row, name):
            idx = col_idx.get(name)
            return row[idx] if idx is not None else None

        # Default first cols if not configured
        if not x_col and cols:
            x_col = cols[0]
        if not y_col_list and len(cols) > 1:
            y_col_list = [cols[1]]

        option = {'tooltip': {'trigger': 'axis'}, 'animation': True}

        # Inject palette colors
        colors = self._get_palette_colors()
        if colors:
            option['color'] = colors

        ct = self.chart_type

        if ct in ('bar', 'line'):
            # ── Read visual_config flags (backward-compatible) ─────────
            vc = {}
            if self.visual_config:
                try:
                    vc = json.loads(self.visual_config) or {}
                except (json.JSONDecodeError, TypeError):
                    vc = {}

            orientation    = vc.get('orientation', 'vertical')
            stack          = vc.get('stack', self.bar_stack) if ct == 'bar' else False
            stack_mode     = vc.get('stack_mode', 'absolute')
            show_labels    = vc.get('show_labels', False)
            show_pct_label = vc.get('show_percent_in_label', False)
            label_position = vc.get('label_position', 'top')
            sort_mode      = vc.get('sort', 'none')
            vc_limit       = vc.get('limit', 0)
            show_axis_labels = vc.get('show_axis_labels', True)
            bar_width      = vc.get('bar_width')
            bar_gap        = vc.get('bar_gap', '30%')
            target_line    = vc.get('target_line')
            target_label   = vc.get('target_label', '')
            color_mode     = vc.get('color_mode', 'by_series')
            number_format  = vc.get('number_format', 'auto')

            option['tooltip']['trigger'] = 'axis'
            option['legend'] = {}

            # ── Build series data (unchanged logic) ────────────────────
            if series_col and series_col in col_idx:
                # Build unique ordered x values (deduplicated)
                seen_x = set()
                unique_x = []
                for r in rows:
                    xv = str(col_val(r, x_col) or '')
                    if xv not in seen_x:
                        seen_x.add(xv)
                        unique_x.append(xv)
                option['xAxis'] = {'type': 'category', 'data': unique_x}

                # Build (series_name, x_value) → y_value lookup
                data_map = {}
                for r in rows:
                    sv = str(col_val(r, series_col) or 'Other')
                    xv = str(col_val(r, x_col) or '')
                    yv = col_val(r, y_col_list[0]) if y_col_list else 0
                    data_map[(sv, xv)] = yv or 0

                # Preserve insertion order of series names
                series_names = list(dict.fromkeys(
                    str(col_val(r, series_col) or 'Other') for r in rows))
                option['series'] = [
                    {'name': sv, 'type': ct,
                     'data': [data_map.get((sv, xv), 0) for xv in unique_x]}
                    for sv in series_names
                ]
            else:
                x_data = [str(col_val(r, x_col) or '') for r in rows]
                option['xAxis'] = {'type': 'category', 'data': x_data}
                option['series'] = [
                    {'name': yc, 'type': ct, 'data': [col_val(r, yc) or 0 for r in rows]}
                    for yc in y_col_list
                ]

            # ── Sort categories ────────────────────────────────────────
            if sort_mode != 'none' and option.get('xAxis', {}).get('data'):
                x_vals = option['xAxis']['data']
                all_series = option.get('series', [])
                if all_series:
                    # Zip categories with all series data for coordinated sort
                    zipped = list(zip(x_vals, *[s['data'] for s in all_series]))
                    if sort_mode == 'value_desc':
                        zipped.sort(key=lambda p: (p[1] or 0), reverse=True)
                    elif sort_mode == 'value_asc':
                        zipped.sort(key=lambda p: (p[1] or 0))
                    elif sort_mode == 'alpha_asc':
                        zipped.sort(key=lambda p: str(p[0]).lower())
                    elif sort_mode == 'alpha_desc':
                        zipped.sort(key=lambda p: str(p[0]).lower(), reverse=True)
                    option['xAxis']['data'] = [p[0] for p in zipped]
                    for i, s in enumerate(all_series):
                        s['data'] = [p[i + 1] for p in zipped]

            # ── Limit categories ───────────────────────────────────────
            if vc_limit and vc_limit > 0 and option.get('xAxis', {}).get('data'):
                option['xAxis']['data'] = option['xAxis']['data'][:vc_limit]
                for s in option.get('series', []):
                    s['data'] = s['data'][:vc_limit]

            # ── Stack ──────────────────────────────────────────────────
            if ct == 'bar' and stack:
                for s in option.get('series', []):
                    s['stack'] = 'total'

            # ── Percent stacking ───────────────────────────────────────
            if ct == 'bar' and stack and stack_mode == 'percent':
                x_count = len(option.get('xAxis', {}).get('data', []))
                for idx in range(x_count):
                    total = sum(
                        (s['data'][idx] or 0) for s in option.get('series', [])
                        if idx < len(s['data']))
                    if total:
                        for s in option.get('series', []):
                            if idx < len(s['data']):
                                s['data'][idx] = round(
                                    (s['data'][idx] or 0) / total * 100, 1)

            # ── Orientation (horizontal = swap axes) ───────────────────
            if ct == 'bar' and orientation == 'horizontal':
                option['yAxis'] = option.pop('xAxis')
                option['xAxis'] = {'type': 'value'}
            else:
                option['yAxis'] = {'type': 'value'}

            # ── Value labels on bars ───────────────────────────────────
            if show_labels:
                pos = label_position
                if ct == 'bar' and orientation == 'horizontal' and pos == 'top':
                    pos = 'right'
                for s in option.get('series', []):
                    s['label'] = {'show': True, 'position': pos}

                # ── Percent in label: "2,484 (42.9%)" ────────────────
                if show_pct_label and ct == 'bar':
                    # Compute grand total across all series and categories
                    grand_total = 0
                    for s in option.get('series', []):
                        grand_total += sum(v or 0 for v in s.get('data', []))

                    if grand_total > 0:
                        for s in option.get('series', []):
                            # Build formatter data with pct pre-computed
                            new_data = []
                            for v in s.get('data', []):
                                val = v or 0
                                pct = round(val / grand_total * 100, 1)
                                new_data.append({
                                    'value': val,
                                    'label': {
                                        'show': True,
                                        'position': pos,
                                        'formatter': f'{{c}} ({pct}%)',
                                    },
                                })
                            s['data'] = new_data

                # ── Number formatting (comma thousands) ───────────────
                if number_format == 'comma' and not show_pct_label:
                    for s in option.get('series', []):
                        new_data = []
                        for v in s.get('data', []):
                            val = v or 0
                            new_data.append({
                                'value': val,
                                'label': {
                                    'show': True,
                                    'position': pos,
                                    'formatter': '{c:,}' if isinstance(val, (int, float)) else str(val),
                                },
                            })
                        s['data'] = new_data

            # ── Color by category ─────────────────────────────────────
            if ct == 'bar' and color_mode == 'by_category':
                # Assign a different color to each bar within a series
                palette = self._get_palette_colors()
                for s in option.get('series', []):
                    colored_data = []
                    for i, v in enumerate(s.get('data', [])):
                        color = palette[i % len(palette)] if palette else None
                        if isinstance(v, dict):
                            v.setdefault('itemStyle', {})['color'] = color
                            colored_data.append(v)
                        else:
                            colored_data.append({
                                'value': v,
                                'itemStyle': {'color': color},
                            })
                    s['data'] = colored_data

            # ── Axis label visibility ──────────────────────────────────
            if not show_axis_labels:
                for axis_key in ('xAxis', 'yAxis'):
                    if axis_key in option:
                        option[axis_key].setdefault('axisLabel', {})['show'] = False

            # ── Bar width / gap ────────────────────────────────────────
            if ct == 'bar':
                if bar_width:
                    for s in option.get('series', []):
                        s['barWidth'] = bar_width
                if bar_gap != '30%':
                    for s in option.get('series', []):
                        s['barGap'] = bar_gap

            # ── Target / reference line ────────────────────────────────
            if target_line is not None and option.get('series'):
                axis_key = 'yAxis' if orientation == 'vertical' else 'xAxis'
                option['series'][0].setdefault('markLine', {
                    'silent': True,
                    'data': [{axis_key: target_line,
                              'label': {'formatter': target_label or str(target_line)}}],
                    'lineStyle': {'type': 'dashed', 'color': '#ef4444'},
                })

            # ── Line variant flags ────────────────────────────────────
            if ct == 'line':
                self._apply_line_variant_flags(option, vc, cols, rows,
                                               x_col, y_col_list, series_col)

        elif ct in ('pie', 'donut'):
            # ── Read visual_config flags (backward-compatible) ─────────
            vc = {}
            if self.visual_config:
                try:
                    vc = json.loads(self.visual_config) or {}
                except (json.JSONDecodeError, TypeError):
                    vc = {}

            # ── Helper: ensure percentage suffix ─────────────────────
            def _ensure_pct(val, default):
                if not val:
                    return default
                val = str(val).strip()
                if val.replace('.', '', 1).isdigit():
                    val += '%'
                return val

            donut_style    = vc.get('donut_style', 'standard') if ct == 'donut' else 'pie'
            show_labels    = vc.get('show_labels', True)
            label_position = vc.get('label_position', 'outside')
            show_percent   = vc.get('show_percent', False)
            label_format   = vc.get('label_format', '')
            legend_pos     = vc.get('legend_position', 'left')
            sort_mode      = vc.get('sort', 'none')
            vc_limit       = int(vc.get('limit', 0) or 0)
            inner_radius   = _ensure_pct(vc.get('inner_radius', ''), '40%') if ct == 'donut' else '0%'
            outer_radius   = _ensure_pct(vc.get('outer_radius', ''), '70%')
            rose_type_val  = vc.get('rose_type', 'area')
            center_text    = vc.get('center_text', '')
            center_mode    = vc.get('center_mode', 'none')
            center_static  = vc.get('center_static_text', '')
            s_col          = self.series_column.strip() if self.series_column else ''

            # ── Build pie data ─────────────────────────────────────────
            pie_data = [
                {'name': str(col_val(r, x_col) or ''),
                 'value': col_val(r, y_col_list[0]) if y_col_list else 0}
                for r in rows
            ]

            # ── Sort ───────────────────────────────────────────────────
            if sort_mode == 'value_desc':
                pie_data.sort(key=lambda d: (d['value'] or 0), reverse=True)
            elif sort_mode == 'value_asc':
                pie_data.sort(key=lambda d: (d['value'] or 0))

            # ── Limit (group remainder as "Other") ─────────────────────
            if vc_limit > 0 and len(pie_data) > vc_limit:
                shown = pie_data[:vc_limit]
                rest_val = sum((d['value'] or 0) for d in pie_data[vc_limit:])
                if rest_val:
                    shown.append({'name': 'Other', 'value': rest_val})
                pie_data = shown

            # ── Helper: build label config ─────────────────────────────
            _LABEL_FMTS = {
                'name':               '{b}',
                'name_value':         '{b}: {c}',
                'name_percent':       '{b} ({d}%)',
                'name_value_percent': '{b}: {c} ({d}%)',
            }

            def _pie_label_cfg():
                if not show_labels:
                    return {'show': False}
                cfg = {'show': True, 'position': label_position}
                # label_format takes priority; fall back to show_percent for backward compat
                fmt = label_format or ('name_percent' if show_percent else 'name')
                if fmt in _LABEL_FMTS:
                    cfg['formatter'] = _LABEL_FMTS[fmt]
                return cfg

            # ── Helper: build legend config ────────────────────────────
            def _pie_legend_cfg():
                if legend_pos == 'none':
                    return {'show': False}
                orient = 'vertical' if legend_pos in ('left', 'right') else 'horizontal'
                return {'orient': orient, legend_pos: legend_pos}

            # ── Tooltip (always shows value; percent if label_format includes it) ──
            _eff_fmt = label_format or ('name_percent' if show_percent else 'name')
            tooltip_fmt = '{b}: {c} ({d}%)' if 'percent' in _eff_fmt else '{b}: {c}'
            option['tooltip'] = {'trigger': 'item', 'formatter': tooltip_fmt}

            # ── Build series based on donut_style ──────────────────────

            if donut_style == 'pie':
                # pie_standard — solid circle, no hole
                option['series'] = [{
                    'type': 'pie',
                    'radius': outer_radius,
                    'data': pie_data,
                    'label': _pie_label_cfg(),
                    'labelLine': {'show': show_labels and label_position == 'outside'},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }]

            elif donut_style == 'standard':
                # donut_standard — basic ring
                series_cfg = {
                    'type': 'pie',
                    'radius': [inner_radius, outer_radius],
                    'data': pie_data,
                    'label': _pie_label_cfg(),
                    'labelLine': {'show': show_labels and label_position == 'outside'},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }
                option['series'] = [series_cfg]

            elif donut_style == 'label_center':
                # donut_label_center — hover shows name+value in center hole
                # Respects show_labels: when True, slice labels appear alongside center emphasis
                series_cfg = {
                    'type': 'pie',
                    'radius': [inner_radius, outer_radius],
                    'avoidLabelOverlap': False,
                    'data': pie_data,
                    'label': _pie_label_cfg(),
                    'labelLine': {'show': show_labels and label_position == 'outside'},
                    'emphasis': {
                        'label': {
                            'show': True,
                            'fontSize': 18,
                            'fontWeight': 'bold',
                            'position': 'center',
                        },
                        'focus': 'self',
                        'blurScope': 'series',
                        'itemStyle': {'shadowBlur': 10},
                    },
                }
                option['series'] = [series_cfg]

            elif donut_style == 'rounded':
                # donut_rounded — rounded corners with white gaps
                series_cfg = {
                    'type': 'pie',
                    'radius': [inner_radius, outer_radius],
                    'data': pie_data,
                    'label': _pie_label_cfg(),
                    'labelLine': {'show': show_labels and label_position == 'outside'},
                    'itemStyle': {
                        'borderRadius': 10,
                        'borderColor': '#fff',
                        'borderWidth': 2,
                    },
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }
                option['series'] = [series_cfg]

            elif donut_style == 'semi':
                # donut_semi — half donut (180°)
                # endAngle:360 with startAngle:180 restricts to top semicircle.
                # No filler item needed — ECharts fills the 180° arc with real data.
                label_cfg = _pie_label_cfg()
                if show_labels and label_position == 'outside':
                    label_cfg['position'] = 'inside'
                series_cfg = {
                    'type': 'pie',
                    'radius': ['50%', '70%'],
                    'center': ['50%', '70%'],
                    'startAngle': 180,
                    'endAngle': 360,
                    'data': pie_data,
                    'label': label_cfg,
                    'labelLine': {'show': False},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }
                option['series'] = [series_cfg]

            elif donut_style == 'rose':
                # donut_rose — nightingale / rose chart
                series_cfg = {
                    'type': 'pie',
                    'radius': [inner_radius, outer_radius],
                    'roseType': rose_type_val,
                    'data': pie_data,
                    'label': _pie_label_cfg(),
                    'labelLine': {'show': show_labels and label_position == 'outside'},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }
                option['series'] = [series_cfg]

            elif donut_style == 'nested' and s_col:
                # donut_nested — 2 concentric rings (parent=x_col, child=series_column)
                # Group rows by x_col (parent), with series_column as child
                from collections import OrderedDict
                parent_totals = OrderedDict()
                child_items = []
                for r in rows:
                    parent = str(col_val(r, x_col) or '')
                    child = str(col_val(r, s_col) or '')
                    value = col_val(r, y_col_list[0]) if y_col_list else 0
                    parent_totals[parent] = parent_totals.get(parent, 0) + (value or 0)
                    child_items.append({
                        'name': f'{parent} \u2192 {child}' if child else parent,
                        'value': value,
                    })

                inner_data = [{'name': k, 'value': v} for k, v in parent_totals.items()]

                # Apply sort/limit to inner ring
                if sort_mode == 'value_desc':
                    inner_data.sort(key=lambda d: (d['value'] or 0), reverse=True)
                elif sort_mode == 'value_asc':
                    inner_data.sort(key=lambda d: (d['value'] or 0))

                # Read per-ring config (defaults match previous hardcoded values)
                ni_start = _ensure_pct(vc.get('nested_inner_radius_start', ''), '0%')
                ni_end   = _ensure_pct(vc.get('nested_inner_radius_end', ''), '30%')
                ni_lpos  = vc.get('nested_inner_label_pos', 'inner')
                ni_lfmt  = vc.get('nested_inner_label_format', 'name')

                no_start = _ensure_pct(vc.get('nested_outer_radius_start', ''), '40%')
                no_end   = _ensure_pct(vc.get('nested_outer_radius_end', ''), '65%')
                no_lpos  = vc.get('nested_outer_label_pos', 'outside')
                no_lfmt  = vc.get('nested_outer_label_format', 'name')

                inner_series = {
                    'type': 'pie',
                    'radius': [ni_start, ni_end],
                    'data': inner_data,
                    'label': {
                        'show': show_labels,
                        'position': ni_lpos,
                        'fontSize': 11 if ni_lpos == 'inner' else 12,
                        'formatter': _LABEL_FMTS.get(ni_lfmt, '{b}'),
                    },
                    'labelLine': {'show': show_labels and ni_lpos == 'outside'},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }
                outer_series = {
                    'type': 'pie',
                    'radius': [no_start, no_end],
                    'data': child_items,
                    'label': {
                        'show': show_labels,
                        'position': no_lpos,
                        'formatter': _LABEL_FMTS.get(no_lfmt, '{b}'),
                    },
                    'labelLine': {'show': show_labels and no_lpos == 'outside'},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }
                option['series'] = [inner_series, outer_series]

            elif donut_style == 'multi_ring' and s_col:
                # donut_multi_ring — side-by-side rings grouped by series_column
                from collections import OrderedDict
                groups = OrderedDict()
                for r in rows:
                    grp = str(col_val(r, s_col) or '')
                    label = str(col_val(r, x_col) or '')
                    value = col_val(r, y_col_list[0]) if y_col_list else 0
                    groups.setdefault(grp, []).append({'name': label, 'value': value})

                group_keys = list(groups.keys())
                n = len(group_keys) or 1
                series_list = []
                for i, grp in enumerate(group_keys):
                    center_x = f'{int((100 / (n + 1)) * (i + 1))}%'
                    ring_data = groups[grp]
                    # Apply sort/limit per ring
                    if sort_mode == 'value_desc':
                        ring_data.sort(key=lambda d: (d['value'] or 0), reverse=True)
                    elif sort_mode == 'value_asc':
                        ring_data.sort(key=lambda d: (d['value'] or 0))
                    if vc_limit > 0 and len(ring_data) > vc_limit:
                        shown_r = ring_data[:vc_limit]
                        rest_r = sum((d['value'] or 0) for d in ring_data[vc_limit:])
                        if rest_r:
                            shown_r.append({'name': 'Other', 'value': rest_r})
                        ring_data = shown_r

                    series_list.append({
                        'type': 'pie',
                        'radius': [inner_radius, outer_radius],
                        'center': [center_x, '50%'],
                        'data': ring_data,
                        'name': str(grp),
                        'label': _pie_label_cfg(),
                        'labelLine': {'show': show_labels and label_position == 'outside'},
                        'emphasis': {'focus': 'self', 'blurScope': 'series',
                                     'itemStyle': {'shadowBlur': 10}},
                    })
                option['series'] = series_list

                # Add ring title (group name) centered inside each ring
                for i, grp in enumerate(group_keys):
                    center_x = f'{int((100 / (n + 1)) * (i + 1))}%'
                    option.setdefault('graphic', []).append({
                        'type': 'text',
                        'left': center_x,
                        'top': '50%',
                        'style': {
                            'text': str(grp),
                            'fontSize': 14,
                            'fontWeight': 'bold',
                            'fill': '#333',
                            'textAlign': 'center',
                            'textVerticalAlign': 'middle',
                        },
                    })

            else:
                # Fallback for nested/multi_ring without series_column, or unknown style
                # Render as standard donut
                radius = [inner_radius, outer_radius] if ct == 'donut' else outer_radius
                option['series'] = [{
                    'type': 'pie',
                    'radius': radius,
                    'data': pie_data,
                    'label': _pie_label_cfg(),
                    'labelLine': {'show': show_labels and label_position == 'outside'},
                    'emphasis': {'focus': 'self', 'blurScope': 'series',
                                 'itemStyle': {'shadowBlur': 10}},
                }]

            # ── Legend ─────────────────────────────────────────────────
            option['legend'] = _pie_legend_cfg()

            # ── Center display (graphic element) ─────────────────────────
            _center_styles = ('standard', 'label_center', 'rounded', 'rose')
            if center_mode == 'auto_total' and donut_style in _center_styles:
                total_val = sum((d.get('value') or 0) for d in pie_data)
                # Format number with commas
                total_str = f'{total_val:,.0f}' if isinstance(total_val, (int, float)) else str(total_val)
                lines = []
                if center_text:
                    lines.append(center_text)
                lines.append(total_str)
                option.setdefault('graphic', []).append({
                    'type': 'text',
                    'left': 'center',
                    'top': 'center',
                    'style': {
                        'text': '\n'.join(lines),
                        'fontSize': 14,
                        'fill': '#333',
                        'textAlign': 'center',
                        'textVerticalAlign': 'middle',
                        'rich': {
                            'label': {'fontSize': 12, 'fill': '#999', 'padding': [0, 0, 4, 0]},
                            'total': {'fontSize': 20, 'fontWeight': 'bold', 'fill': '#333'},
                        },
                        'text': ('{label|' + center_text + '}\n{total|' + total_str + '}') if center_text else ('{total|' + total_str + '}'),
                    },
                })
            elif center_mode == 'static' and center_static and donut_style in _center_styles:
                option.setdefault('graphic', []).append({
                    'type': 'text',
                    'left': 'center',
                    'top': 'center',
                    'style': {
                        'text': center_static,
                        'fontSize': 16,
                        'fontWeight': 'bold',
                        'fill': '#333',
                        'textAlign': 'center',
                        'textVerticalAlign': 'middle',
                    },
                })
            elif center_mode == 'none' and center_text and donut_style in _center_styles:
                # Backward compat: old widgets with center_text but no center_mode
                option.setdefault('graphic', []).append({
                    'type': 'text',
                    'left': 'center',
                    'top': 'center',
                    'style': {
                        'text': center_text,
                        'fontSize': 16,
                        'fontWeight': 'bold',
                        'fill': '#333',
                        'textAlign': 'center',
                        'textVerticalAlign': 'middle',
                    },
                })

        elif ct == 'gauge':
            # Delegate to shared helper; replaces the initial option dict entirely
            option = self._build_gauge_option(cols, rows)

        elif ct == 'radar':
            # Expects SQL: indicator_col, you_score, [them_score, ...]
            indicators = [{'name': str(col_val(r, x_col) or ''), 'max': 100}
                          for r in rows]
            series_list = []
            for yc in y_col_list:
                vals = [col_val(r, yc) or 0 for r in rows]
                series_list.append({'name': yc, 'type': 'radar',
                                    'data': [{'value': vals, 'name': yc}]})
            option['tooltip'] = {}
            option['legend'] = {'data': y_col_list}
            option['radar'] = {'indicator': indicators}
            option['series'] = series_list

        elif ct == 'scatter':
            x_data = [col_val(r, x_col) or 0 for r in rows]
            y_data = [col_val(r, y_col_list[0]) or 0 for r in rows] if y_col_list else []
            option['xAxis'] = {'type': 'value'}
            option['yAxis'] = {'type': 'value'}
            option['series'] = [{'type': 'scatter',
                                  'data': [[x, y] for x, y in zip(x_data, y_data)]}]

        elif ct == 'heatmap':
            x_vals = sorted({str(col_val(r, x_col) or '') for r in rows})
            y_vals = sorted({str(col_val(r, y_col_list[0]) or '') for r in rows}) if y_col_list else []
            z_col = y_col_list[1] if len(y_col_list) > 1 else (cols[2] if len(cols) > 2 else None)
            heat_data = []
            for r in rows:
                xi = x_vals.index(str(col_val(r, x_col) or ''))
                yi = y_vals.index(str(col_val(r, y_col_list[0]) or '')) if y_col_list else 0
                zv = col_val(r, z_col) if z_col else 0
                heat_data.append([xi, yi, zv or 0])
            option['xAxis'] = {'type': 'category', 'data': x_vals}
            option['yAxis'] = {'type': 'category', 'data': y_vals}
            option['visualMap'] = {
                'min': min((d[2] for d in heat_data), default=0),
                'max': max((d[2] for d in heat_data), default=1),
                'calculable': True,
                'orient': 'horizontal', 'left': 'center', 'bottom': '5%',
                'inRange': {'color': (colors[:2] if len(colors) >= 2
                                      else ['#e0f2f1', '#0d9488'])},
            }
            option['series'] = [{'type': 'heatmap', 'data': heat_data,
                                  'label': {'show': True}}]

        # ── Annotation injection (SQL-interpolated) ──────────────────────────
        # Build a template_vars dict from chart first row + annotation query row
        sql_row = {}
        if rows and cols:
            sql_row = {c: (str(rows[0][i]) if rows[0][i] is not None else '')
                       for i, c in enumerate(cols)}
        # Merge annotation query results (overrides same-named columns)
        if ann_row:
            sql_row.update({k: (str(v) if v is not None else '') for k, v in ann_row.items()})

        def _interp(text):
            """Interpolate %(column_name)s in text using the merged row data."""
            if not text:
                return text
            try:
                return text % sql_row
            except (KeyError, TypeError, ValueError):
                return text

        resolved_subtitle = _interp(self.subtitle)
        resolved_annotation = _interp(self.annotation_text)

        # Resolve annotation_value: annotation_query > chart query column > static field
        resolved_value = self.annotation_value
        if self.annotation_value_column:
            # First check annotation query row, then chart data
            if ann_row and self.annotation_value_column in ann_row:
                try:
                    resolved_value = float(ann_row[self.annotation_value_column] or 0)
                except (TypeError, ValueError):
                    pass
            elif self.annotation_value_column in col_idx and rows:
                try:
                    resolved_value = float(col_val(rows[0], self.annotation_value_column) or 0)
                except (TypeError, ValueError):
                    pass

        if resolved_subtitle:
            option.setdefault('title', {})['subtext'] = resolved_subtitle

        if self.annotation_type == 'reference_line' and resolved_value:
            mark_line = {
                'data': [{
                    'yAxis': resolved_value,
                    'label': {
                        'formatter': resolved_annotation or str(resolved_value),
                        'position': 'end',
                        'fontSize': self.annotation_font_size or 12,
                        'color': self.annotation_color or '#6b7280',
                    },
                }],
                'lineStyle': {'type': 'dashed', 'color': self.annotation_color or '#ef4444'},
                'silent': True,
            }
            if option.get('series'):
                option['series'][0].setdefault('markLine', mark_line)

        elif self.annotation_type == 'text_overlay' and resolved_annotation:
            # Resolve position: custom X/Y override > grid preset
            if self.annotation_x or self.annotation_y:
                pos = {}
                if self.annotation_x:
                    pos['left'] = f'{self.annotation_x}%'
                if self.annotation_y:
                    pos['top'] = f'{self.annotation_y}%'
            else:
                pos = dict(_POSITION_MAP.get(
                    self.annotation_position or 'top_right',
                    _POSITION_MAP['top_right']))
            option['graphic'] = [{
                'type': 'text',
                'z': 100,
                'style': {
                    'text': resolved_annotation,
                    'fontSize': self.annotation_font_size or 12,
                    'fill': self.annotation_color or '#6b7280',
                    'textAlign': self.annotation_align or 'right',
                },
                **pos,
            }]

        # ── Pattern / decal injection ──────────────────────────────────────
        if self.enable_aria_decal:
            option['aria'] = {'enabled': True, 'decal': {'show': True}}

        decal_cfg = _DECAL_STYLES.get(self.pattern_style or 'hatched',
                                       _DECAL_STYLES['hatched'])

        # Data-driven patterns (pattern_column)
        if self.pattern_column and self.pattern_column in col_idx:
            if series_col and series_col in col_idx:
                # Series-column mode: build per-x-index pattern map
                # since rows are pivoted, row[i] doesn't map to data[i]
                pattern_by_x = {}
                for r in rows:
                    xv = str(col_val(r, x_col) or '')
                    flag = col_val(r, self.pattern_column)
                    if bool(flag) and str(flag).lower() not in (
                            '0', 'false', '', 'none'):
                        pattern_by_x[xv] = True
                x_axis_data = option.get('xAxis', {}).get('data', [])
                for series in option.get('series', []):
                    raw_data = series.get('data', [])
                    enhanced = []
                    for i, val in enumerate(raw_data):
                        entry = dict(val) if isinstance(val, dict) else {'value': val}
                        if i < len(x_axis_data) and pattern_by_x.get(x_axis_data[i]):
                            entry['itemStyle'] = {
                                'decal': {**decal_cfg, 'color': 'rgba(0,0,0,0.2)'}
                            }
                        enhanced.append(entry)
                    series['data'] = enhanced
            else:
                # Standard mode: row[i] maps directly to data[i]
                for series in option.get('series', []):
                    raw_data = series.get('data', [])
                    enhanced = []
                    for i, val in enumerate(raw_data):
                        if i < len(rows):
                            flag = col_val(rows[i], self.pattern_column)
                            has_pattern = bool(flag) and str(flag).lower() not in (
                                '0', 'false', '', 'none')
                        else:
                            has_pattern = False
                        entry = dict(val) if isinstance(val, dict) else {'value': val}
                        if has_pattern:
                            entry['itemStyle'] = {
                                'decal': {**decal_cfg, 'color': 'rgba(0,0,0,0.2)'}
                            }
                        enhanced.append(entry)
                    series['data'] = enhanced

        # Manual patterns (pattern_series)
        if self.pattern_series:
            targets = {s.strip() for s in self.pattern_series.split(',') if s.strip()}
            for series in option.get('series', []):
                if series.get('name') in targets:
                    series.setdefault('itemStyle', {})['decal'] = {
                        **decal_cfg, 'color': 'rgba(0,0,0,0.2)'}

        # Deep-merge echart_override JSON if provided
        if self.echart_override:
            try:
                override = json.loads(self.echart_override)
                option = _deep_merge(option, override)
            except Exception as e:
                _logger.warning('widget %s echart_override JSON error: %s', self.id, e)

        return option

    # =========================================================================
    # Line variant builder
    # =========================================================================

    def _apply_line_variant_flags(self, option, vc, cols, rows,
                                  x_col, y_col_list, series_col):
        """Apply line_style variant + universal line flags to the ECharts option.

        Called within _build_echart_option after the shared bar/line data
        extraction and shared post-processing (sort, limit, labels).
        Mutates ``option`` in-place.
        """
        line_style = vc.get('line_style', 'basic')
        colors = self._get_palette_colors() or []

        # ── Universal line appearance flags ──────────────────────
        smooth      = vc.get('smooth', False)
        show_points = vc.get('show_points', True)
        point_size  = int(vc.get('point_size', 4) or 4)
        line_width  = int(vc.get('line_width', 2) or 2)
        step_type   = vc.get('step_type', 'none')
        legend_pos  = vc.get('legend_position', 'top')

        col_idx = {c: i for i, c in enumerate(cols)}

        def col_val(row, name):
            idx = col_idx.get(name)
            return row[idx] if idx is not None else None

        # ── Variant-specific transforms ──────────────────────────

        if line_style in ('basic', 'area', 'stacked_line', 'stacked_area'):
            # Stack
            if line_style in ('stacked_line', 'stacked_area'):
                for s in option.get('series', []):
                    s['stack'] = 'total'
                    s['emphasis'] = {'focus': 'series'}

            # Area fill
            if line_style in ('area', 'stacked_area'):
                area_opacity = float(vc.get('area_opacity', 0.3) or 0.3)
                use_gradient = vc.get('area_gradient', False)
                for idx_s, s in enumerate(option.get('series', [])):
                    if use_gradient:
                        c = colors[idx_s % len(colors)] if colors else '#5470c6'
                        s['areaStyle'] = {
                            'opacity': area_opacity,
                            'color': {
                                'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                                'colorStops': [
                                    {'offset': 0, 'color': c},
                                    {'offset': 1, 'color': 'rgba(255,255,255,0)'},
                                ],
                            },
                        }
                    else:
                        s['areaStyle'] = {'opacity': area_opacity}

            # Step function
            if step_type and step_type != 'none':
                for s in option.get('series', []):
                    s['step'] = step_type

        elif line_style == 'waterfall':
            self._build_waterfall_series(option, vc, colors, col_idx,
                                         col_val, rows, x_col, y_col_list)

        elif line_style == 'combo':
            self._build_combo_series(option, vc, y_col_list)

        elif line_style == 'benchmark':
            self._build_benchmark_series(option, vc, y_col_list)

        # ── Apply universal appearance to all line-type series ───
        for s in option.get('series', []):
            if s.get('type') != 'line':
                continue
            if smooth:
                s['smooth'] = True
            s['symbol'] = 'circle' if show_points else 'none'
            s['symbolSize'] = point_size
            s.setdefault('lineStyle', {})['width'] = line_width

        # ── Legend position ──────────────────────────────────────
        if legend_pos == 'none':
            option['legend'] = {'show': False}
        elif legend_pos in ('left', 'right', 'top', 'bottom'):
            orient = 'vertical' if legend_pos in ('left', 'right') else 'horizontal'
            option['legend'] = {'orient': orient, legend_pos: legend_pos}

    def _build_waterfall_series(self, option, vc, colors, col_idx,
                                col_val, rows, x_col, y_col_list):
        """Replace series with waterfall (bridge) bar segments."""
        pos_color = vc.get('wf_positive_color', '#91cc75')
        neg_color = vc.get('wf_negative_color', '#ee6666')
        total_color = vc.get('wf_total_color', '#5470c6')
        show_connectors = vc.get('wf_show_connectors', True)

        categories = []
        deltas = []
        for r in rows:
            categories.append(str(col_val(r, x_col) or ''))
            val = col_val(r, y_col_list[0]) if y_col_list else 0
            deltas.append(float(val or 0))

        # Compute base / positive / negative arrays
        base_data = []
        pos_data = []
        neg_data = []
        running = 0
        for d in deltas:
            if d >= 0:
                base_data.append(running)
                pos_data.append(d)
                neg_data.append(0)
            else:
                base_data.append(running + d)
                pos_data.append(0)
                neg_data.append(abs(d))
            running += d

        option['xAxis'] = {'type': 'category', 'data': categories}
        option['yAxis'] = {'type': 'value'}
        option['tooltip'] = {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}}

        # Invisible base series
        option['series'] = [
            {
                'name': '_base',
                'type': 'bar',
                'stack': 'waterfall',
                'data': base_data,
                'itemStyle': {'color': 'transparent',
                              'borderColor': 'transparent'},
                'emphasis': {'itemStyle': {'color': 'transparent'}},
            },
            {
                'name': 'Increase',
                'type': 'bar',
                'stack': 'waterfall',
                'data': pos_data,
                'itemStyle': {'color': pos_color},
                'label': {'show': True, 'position': 'top'},
            },
            {
                'name': 'Decrease',
                'type': 'bar',
                'stack': 'waterfall',
                'data': neg_data,
                'itemStyle': {'color': neg_color},
                'label': {'show': True, 'position': 'bottom'},
            },
        ]

        # Connector line showing running total
        if show_connectors:
            connector_data = []
            r_total = 0
            for d in deltas:
                r_total += d
                connector_data.append(r_total)
            option['series'].append({
                'name': 'Total',
                'type': 'line',
                'data': connector_data,
                'symbol': 'none',
                'lineStyle': {'type': 'dashed', 'color': total_color,
                              'width': 1.5},
                'z': 10,
            })

        option['legend'] = {'data': ['Increase', 'Decrease', 'Total']}

    def _build_combo_series(self, option, vc, y_col_list):
        """Retype selected series from line to bar for combo charts."""
        bar_cols_raw = (vc.get('combo_bar_columns') or '').strip()
        bar_cols = set(c.strip() for c in bar_cols_raw.split(',') if c.strip())
        dual_axis = vc.get('combo_secondary_axis', False)

        for s in option.get('series', []):
            if s.get('name', '') in bar_cols:
                s['type'] = 'bar'
            else:
                s['type'] = 'line'
                if dual_axis:
                    s['yAxisIndex'] = 1

        if dual_axis:
            primary_axis = option.get('yAxis', {'type': 'value'})
            if isinstance(primary_axis, dict):
                option['yAxis'] = [
                    primary_axis,
                    {'type': 'value', 'splitLine': {'show': False}},
                ]

    def _build_benchmark_series(self, option, vc, y_col_list):
        """Apply benchmark styling — static markLine or dashed column series."""
        bm_mode = vc.get('benchmark_mode', 'static')
        bm_label = vc.get('benchmark_label', 'Target')

        if bm_mode == 'static':
            bm_value = vc.get('benchmark_value')
            if bm_value is not None and option.get('series'):
                option['series'][0].setdefault('markLine', {
                    'silent': True,
                    'data': [{'yAxis': bm_value,
                              'label': {'formatter': bm_label or str(bm_value)}}],
                    'lineStyle': {'type': 'dashed', 'color': '#ef4444'},
                })
        elif bm_mode == 'column':
            bm_col = (vc.get('benchmark_column') or '').strip()
            if bm_col:
                for s in option.get('series', []):
                    if s.get('name') == bm_col:
                        s['lineStyle'] = {'type': 'dashed', 'width': 2}
                        s['symbol'] = 'none'
                        s['name'] = bm_label or bm_col

    # Gauge option builder (shared by gauge and gauge_kpi)
    # =========================================================================

    def _build_gauge_option(self, cols, rows):
        """Dispatch to the appropriate gauge style builder.

        Reads ``gauge_style`` from ``visual_config`` and dispatches.
        Default is ``'standard'`` for backward compatibility.
        """
        vc = {}
        try:
            vc = json.loads(self.visual_config or '{}') or {}
        except (json.JSONDecodeError, TypeError):
            pass
        style = vc.get('gauge_style', 'standard')
        builder = {
            'standard':      self._build_gauge_standard,
            'half_arc':      self._build_gauge_half_arc,
            'three_quarter': self._build_gauge_three_quarter,
            'multi_ring':    self._build_gauge_multi_ring,
        }.get(style, self._build_gauge_standard)
        return builder(cols, rows, vc)

    # ── Gauge helpers ────────────────────────────────────────────────────────

    def _gauge_extract_value(self, cols, rows):
        """Extract the primary float value from the first row."""
        col_idx = {c: i for i, c in enumerate(cols)}
        x_col = (self.x_column or '').strip()
        if not x_col and cols:
            x_col = cols[0]
        val = 0.0
        if rows:
            idx = col_idx.get(x_col)
            if idx is not None:
                try:
                    val = float(rows[0][idx] or 0)
                except (TypeError, ValueError):
                    val = 0.0
        return val

    def _gauge_color_zones(self, val, vc):
        """Compute axis color zones and pointer color based on visual config.

        Falls back to model-level fields for backward compatibility.
        """
        colors = self._get_palette_colors()
        g_min = float(vc.get('gauge_min', self.gauge_min or 0))
        g_max = float(vc.get('gauge_max', self.gauge_max or 100))
        color_mode = vc.get('gauge_color_mode', self.gauge_color_mode or 'single')
        warn_frac = float(vc.get('gauge_warn_threshold', self.gauge_warn_threshold or 50)) / 100.0
        good_frac = float(vc.get('gauge_good_threshold', self.gauge_good_threshold or 70)) / 100.0

        if color_mode == 'traffic_light':
            axis_color = [
                [warn_frac, '#ef4444'],
                [good_frac, '#f59e0b'],
                [1.0,       '#10b981'],
            ]
            val_range = g_max - g_min
            val_frac = (val - g_min) / val_range if val_range else 0
            if val_frac < warn_frac:
                pt_color = '#ef4444'
            elif val_frac < good_frac:
                pt_color = '#f59e0b'
            else:
                pt_color = '#10b981'
        else:
            pt_color = colors[0] if colors else '#0d9488'
            axis_color = [[1.0, pt_color]]

        return g_min, g_max, axis_color, pt_color, colors

    def _gauge_number_formatter(self, vc, g_min, g_max):
        """Return ECharts formatter string for the gauge center value."""
        fmt_mode = vc.get('gauge_number_format', 'auto')
        if fmt_mode == 'auto':
            return '{value}%' if (g_max == 100 and g_min == 0) else '{value}'
        fmts = {
            'percent': '{value}%',
            'comma': None,  # handled via JS formatter
            'decimal1': None,
            'decimal2': None,
            'integer': None,
            'currency': None,
        }
        return fmts.get(fmt_mode, '{value}')

    def _gauge_inject_annotations(self, option, cols, rows):
        """Inject subtitle, annotation text, and typography into the gauge option."""
        sql_row = {}
        if rows and cols:
            sql_row = {c: (str(rows[0][i]) if rows[0][i] is not None else '')
                       for i, c in enumerate(cols)}

        def _interp(text):
            if not text:
                return text
            try:
                return text % sql_row
            except (KeyError, TypeError, ValueError):
                return text

        resolved_subtitle = _interp(self.subtitle)
        resolved_annotation = _interp(self.annotation_text)

        if resolved_subtitle:
            option.setdefault('title', {})['subtext'] = resolved_subtitle

        if self.annotation_type == 'text_overlay' and resolved_annotation:
            if self.annotation_x or self.annotation_y:
                pos = {}
                if self.annotation_x:
                    pos['left'] = f'{self.annotation_x}%'
                if self.annotation_y:
                    pos['top'] = f'{self.annotation_y}%'
            else:
                pos = dict(_POSITION_MAP.get(
                    self.annotation_position or 'top_right',
                    _POSITION_MAP['top_right']))
            option.setdefault('graphic', []).append({
                'type': 'text',
                'z': 100,
                'style': {
                    'text': resolved_annotation,
                    'fontSize': self.annotation_font_size or 12,
                    'fill': self.annotation_color or '#6b7280',
                    'textAlign': self.annotation_align or 'right',
                },
                **pos,
            })

        # ── Apply typography overrides to ECharts gauge detail ────────────
        typo = self._get_typography_overrides()
        if typo and option.get('series'):
            for s in option['series']:
                if s.get('type') == 'gauge' and 'detail' in s:
                    if typo.get('value_color'):
                        s['detail']['color'] = typo['value_color']
                    if typo.get('value_font_weight'):
                        s['detail']['fontWeight'] = typo['value_font_weight']
                    # Also update pointer/anchor color to match
                    if typo.get('value_color') and 'itemStyle' in s:
                        s['itemStyle']['color'] = typo['value_color']

        return option

    # ── Standard gauge (220° arc — original) ──────────────────────────────

    def _build_gauge_standard(self, cols, rows, vc):
        """Build the classic 220° arc gauge with needle and progress bar."""
        val = self._gauge_extract_value(cols, rows)
        g_min, g_max, axis_color, pt_color, colors = self._gauge_color_zones(val, vc)
        fmt = self._gauge_number_formatter(vc, g_min, g_max)
        show_needle = vc.get('show_needle', True)
        show_progress = vc.get('show_progress_bar', True)
        show_scale = vc.get('show_scale_labels', True)

        option = {
            'animation': True,
            'color': colors or ['#0d9488'],
            'tooltip': {'formatter': '{a} <br/>{b} : {c}'},
            'series': [{
                'name': self.name,
                'type': 'gauge',
                'startAngle': 200,
                'endAngle': -20,
                'min': g_min,
                'max': g_max,
                'splitNumber': 5,
                'radius': '85%',
                'progress': {'show': show_progress, 'width': 14},
                'axisLine': {'lineStyle': {'width': 14, 'color': axis_color}},
                'axisTick': {'show': False},
                'splitLine': {
                    'length': 8,
                    'lineStyle': {'width': 2, 'color': '#aaa'},
                },
                'axisLabel': {'distance': 20, 'color': '#666', 'fontSize': 11,
                              'show': show_scale},
                'anchor': {
                    'show': show_needle,
                    'showAbove': True,
                    'size': 16,
                    'itemStyle': {
                        'borderWidth': 8,
                        'borderColor': pt_color,
                        'color': '#fff',
                    },
                },
                'pointer': {'show': show_needle},
                'title': {'show': False},
                'detail': {
                    'valueAnimation': True,
                    'fontSize': 32,
                    'fontWeight': 'bold',
                    'formatter': fmt,
                    'color': pt_color,
                    'offsetCenter': [0, '60%'],
                },
                'itemStyle': {'color': pt_color},
                'data': [{'value': round(val, 1), 'name': ''}],
            }],
        }

        # Target marker
        target_val = vc.get('target_value')
        if target_val is not None:
            self._gauge_add_target_marker(option, float(target_val),
                                          vc.get('target_label', ''),
                                          g_min, g_max, 200, -20)

        return self._gauge_inject_annotations(option, cols, rows)

    # ── Half-arc gauge (180°) ─────────────────────────────────────────────

    def _build_gauge_half_arc(self, cols, rows, vc):
        """Build a 180° semicircle gauge — clean arc with center value.

        Adapts to chart_height: at small sizes (< 200px), suppresses scale
        labels and reduces arc width/font to avoid overlap.
        """
        val = self._gauge_extract_value(cols, rows)
        g_min, g_max, axis_color, pt_color, colors = self._gauge_color_zones(val, vc)
        fmt = self._gauge_number_formatter(vc, g_min, g_max)
        show_progress = vc.get('show_progress_bar', True)
        show_scale = vc.get('show_scale_labels', True)

        # ── Responsive sizing based on chart_height ──────────────────────
        h = int(self.chart_height or 280)
        is_compact = h < 200
        arc_width = max(8, min(18, int(h * 0.09)))
        value_font = max(14, min(28, int(h * 0.16)))
        label_font = max(8, min(10, int(h * 0.05)))
        label_dist = max(-20, -int(h * 0.15))

        # At compact sizes, suppress scale labels to avoid overlap
        if is_compact:
            show_scale = False

        option = {
            'animation': True,
            'color': colors or ['#0d9488'],
            'series': [{
                'name': self.name,
                'type': 'gauge',
                'startAngle': 180,
                'endAngle': 0,
                'min': g_min,
                'max': g_max,
                'splitNumber': 4,
                'radius': '85%' if is_compact else '90%',
                'center': ['50%', '75%' if is_compact else '70%'],
                'progress': {'show': show_progress, 'width': arc_width,
                             'itemStyle': {'color': pt_color}},
                'axisLine': {'lineStyle': {'width': arc_width, 'color': axis_color}},
                'axisTick': {'show': False},
                'splitLine': {'show': False},
                'axisLabel': {'show': show_scale, 'distance': label_dist,
                              'color': '#999', 'fontSize': label_font},
                'pointer': {'show': False},
                'anchor': {'show': False},
                'title': {'show': False},
                'detail': {
                    'valueAnimation': True,
                    'fontSize': value_font,
                    'fontWeight': 'bold',
                    'formatter': fmt,
                    'color': pt_color,
                    'offsetCenter': [0, '-5%' if is_compact else '-10%'],
                },
                'itemStyle': {'color': pt_color},
                'data': [{'value': round(val, 1), 'name': ''}],
            }],
        }

        # Min/Max labels at edges (only at larger sizes)
        if show_scale and not is_compact:
            option.setdefault('graphic', []).extend([
                {'type': 'text', 'left': '8%', 'bottom': '15%',
                 'style': {'text': str(int(g_min)), 'fontSize': 11, 'fill': '#999'}},
                {'type': 'text', 'right': '8%', 'bottom': '15%',
                 'style': {'text': str(int(g_max)), 'fontSize': 11, 'fill': '#999',
                           'textAlign': 'right'}},
            ])

        # Target marker + label below
        target_val = vc.get('target_value')
        target_label = vc.get('target_label', '')
        if target_val is not None:
            self._gauge_add_target_marker(option, float(target_val), '',
                                          g_min, g_max, 180, 0)
        if target_label:
            option.setdefault('graphic', []).append({
                'type': 'text',
                'left': 'center',
                'bottom': '5%',
                'style': {'text': target_label, 'fontSize': 12,
                          'fill': '#666', 'textAlign': 'center'},
            })

        return self._gauge_inject_annotations(option, cols, rows)

    # ── Three-quarter gauge (270°) ────────────────────────────────────────

    def _build_gauge_three_quarter(self, cols, rows, vc):
        """Build a 270° arc gauge — cockpit style with full scale."""
        val = self._gauge_extract_value(cols, rows)
        g_min, g_max, axis_color, pt_color, colors = self._gauge_color_zones(val, vc)
        fmt = self._gauge_number_formatter(vc, g_min, g_max)
        show_needle = vc.get('show_needle', True)
        show_progress = vc.get('show_progress_bar', True)
        show_scale = vc.get('show_scale_labels', True)

        option = {
            'animation': True,
            'color': colors or ['#0d9488'],
            'series': [{
                'name': self.name,
                'type': 'gauge',
                'startAngle': 225,
                'endAngle': -45,
                'min': g_min,
                'max': g_max,
                'splitNumber': 5,
                'radius': '85%',
                'progress': {'show': show_progress, 'width': 12},
                'axisLine': {'lineStyle': {'width': 12, 'color': axis_color}},
                'axisTick': {'show': True, 'splitNumber': 5,
                             'lineStyle': {'color': '#ccc'}},
                'splitLine': {
                    'length': 10,
                    'lineStyle': {'width': 2, 'color': '#aaa'},
                },
                'axisLabel': {'distance': 18, 'color': '#666', 'fontSize': 11,
                              'show': show_scale},
                'pointer': {'show': show_needle, 'length': '60%', 'width': 5},
                'anchor': {
                    'show': show_needle,
                    'showAbove': True,
                    'size': 14,
                    'itemStyle': {
                        'borderWidth': 6,
                        'borderColor': pt_color,
                        'color': '#fff',
                    },
                },
                'title': {'show': False},
                'detail': {
                    'valueAnimation': True,
                    'fontSize': 30,
                    'fontWeight': 'bold',
                    'formatter': fmt,
                    'color': pt_color,
                    'offsetCenter': [0, '70%'],
                },
                'itemStyle': {'color': pt_color},
                'data': [{'value': round(val, 1), 'name': ''}],
            }],
        }

        target_val = vc.get('target_value')
        if target_val is not None:
            self._gauge_add_target_marker(option, float(target_val),
                                          vc.get('target_label', ''),
                                          g_min, g_max, 225, -45)

        return self._gauge_inject_annotations(option, cols, rows)

    # ── Multi-ring nested gauge ───────────────────────────────────────────

    def _build_gauge_multi_ring(self, cols, rows, vc):
        """Build concentric ring arcs — each row is one ring."""
        colors = self._get_palette_colors() or ['#0d9488', '#f59e0b', '#ef4444',
                                                  '#3b82f6', '#8b5cf6', '#ec4899']
        max_rings = int(vc.get('multi_ring_max_rings', 6))
        arc_width = int(vc.get('multi_ring_arc_width', 10))
        show_center = vc.get('multi_ring_show_center', True)
        center_text = vc.get('multi_ring_center_text', '')
        center_subtitle = vc.get('multi_ring_center_subtitle', '')
        show_legend = vc.get('multi_ring_show_legend', True)
        g_max = float(vc.get('gauge_max', self.gauge_max or 100))

        col_idx = {c: i for i, c in enumerate(cols)}
        x_col = (self.x_column or '').strip() or (cols[0] if cols else '')
        y_cols = [c.strip() for c in (self.y_columns or '').split(',') if c.strip()]
        y_col = y_cols[0] if y_cols else (cols[1] if len(cols) > 1 else '')

        ring_data = []
        for r in rows[:max_rings]:
            name_val = r[col_idx[x_col]] if x_col in col_idx else ''
            try:
                val = float(r[col_idx[y_col]]) if y_col in col_idx else 0
            except (TypeError, ValueError):
                val = 0
            ring_data.append({'name': str(name_val), 'value': round(val, 1)})

        # Build concentric gauge series
        series_list = []
        outer_start = 90  # outermost ring radius %
        ring_gap = arc_width + 4  # gap between rings in %
        for i, rd in enumerate(ring_data):
            radius_pct = outer_start - (i * ring_gap)
            if radius_pct < 15:
                break
            ring_color = colors[i % len(colors)]
            series_list.append({
                'type': 'gauge',
                'startAngle': 225,
                'endAngle': -45,
                'min': 0,
                'max': g_max,
                'radius': f'{radius_pct}%',
                'progress': {'show': True, 'width': arc_width,
                             'itemStyle': {'color': ring_color}},
                'axisLine': {'lineStyle': {'width': arc_width,
                             'color': [[1.0, '#f3f4f6']]}},
                'axisTick': {'show': False},
                'splitLine': {'show': False},
                'axisLabel': {'show': False},
                'pointer': {'show': False},
                'anchor': {'show': False},
                'title': {'show': False},
                'detail': {'show': False},
                'data': [{'value': rd['value'], 'name': rd['name']}],
            })

        option = {
            'animation': True,
            'color': colors,
            'series': series_list,
        }

        # Center label
        if show_center and (center_text or ring_data):
            graphic = []
            display_text = center_text or str(round(sum(d['value'] for d in ring_data) / len(ring_data), 1)) if ring_data else ''
            graphic.append({
                'type': 'text',
                'left': 'center',
                'top': '42%',
                'style': {
                    'text': display_text,
                    'fontSize': 24,
                    'fontWeight': 'bold',
                    'fill': '#1f2937',
                    'textAlign': 'center',
                    'textVerticalAlign': 'middle',
                },
            })
            if center_subtitle:
                graphic.append({
                    'type': 'text',
                    'left': 'center',
                    'top': '52%',
                    'style': {
                        'text': center_subtitle,
                        'fontSize': 11,
                        'fill': '#6b7280',
                        'textAlign': 'center',
                    },
                })
            option['graphic'] = graphic

        # Legend with values
        if show_legend and ring_data:
            option['legend'] = {
                'show': True,
                'bottom': 0,
                'itemGap': 12,
                'data': [rd['name'] for rd in ring_data],
                'textStyle': {'fontSize': 11},
            }
            # Add a hidden pie series for legend coloring
            option['series'].append({
                'type': 'pie',
                'radius': [0, 0],
                'label': {'show': False},
                'data': [{'name': rd['name'], 'value': rd['value'],
                          'itemStyle': {'color': colors[i % len(colors)]}}
                         for i, rd in enumerate(ring_data)],
            })

        return self._gauge_inject_annotations(option, cols, rows)

    # ── Gauge target marker helper ────────────────────────────────────────

    def _gauge_add_target_marker(self, option, target_val, label,
                                  g_min, g_max, start_angle, end_angle):
        """Add a target pointer to the gauge series as a second data item."""
        if not option.get('series'):
            return
        series = option['series'][0]
        # Add a small fixed pointer for the target
        import math
        val_range = g_max - g_min
        if val_range <= 0:
            return
        frac = (target_val - g_min) / val_range
        frac = max(0, min(1, frac))
        # Calculate angle for the target position
        angle_range = start_angle - end_angle
        target_angle = start_angle - frac * angle_range
        rad = math.radians(target_angle)
        # We use a markPoint-style approach via graphic elements
        radius_pct = 0.85  # match series radius
        cx, cy = 0.5, 0.5  # center
        # Add a dashed arc segment as graphic
        option.setdefault('graphic', []).append({
            'type': 'text',
            'left': 'center',
            'bottom': '2%',
            'style': {
                'text': label if label else f'Target: {target_val}',
                'fontSize': 11,
                'fill': '#666',
                'textAlign': 'center',
            },
            'z': 50,
        })

    # ── Non-ECharts gauge builders (bullet, RAG, percentile) ─────────────

    def _build_gauge_custom(self, cols, rows, vc, style):
        """Build plain dict for non-ECharts gauge variants."""
        if style == 'bullet':
            return self._build_bullet_gauge(cols, rows, vc)
        elif style == 'traffic_light_rag':
            return self._build_rag_gauge(cols, rows, vc)
        elif style == 'percentile_rank':
            return self._build_percentile_gauge(cols, rows, vc)
        return {}

    def _build_bullet_gauge(self, cols, rows, vc):
        """Build bullet gauge data dict.

        Supports multi-row: when SQL returns multiple rows, each row becomes
        a stacked bullet bar with its own label, value, target, and target_label.

        Column mapping:
          Single-row:  x_column = value column, y_columns = target (optional)
          Multi-row:   x_column = metric_name (label), y_columns = actual_value, benchmark_value [, benchmark_label]
        """
        col_idx = {c: i for i, c in enumerate(cols)}
        x_col = (self.x_column or '').strip() or (cols[0] if cols else '')
        y_cols = [c.strip() for c in (self.y_columns or '').split(',') if c.strip()]

        b_min = float(vc.get('bullet_min', 0))
        b_max = float(vc.get('bullet_max', 100))

        # Parse custom ranges or build defaults
        ranges = self._bullet_parse_ranges(vc, b_min, b_max)

        # Build threshold text
        threshold_parts = [r.get('label', '') for r in ranges if r.get('label')]
        threshold_text = ' | '.join(threshold_parts) if vc.get('bullet_show_labels', True) else ''

        bar_height = int(vc.get('bullet_bar_height', 12))
        orientation = vc.get('bullet_orientation', 'horizontal')

        # ── Multi-row detection ──────────────────────────────────────────
        # If SQL returns >1 row AND y_columns has at least 1 column (actual_value),
        # treat as multi-row: x_col = label, y_cols[0] = actual, y_cols[1] = benchmark, y_cols[2] = benchmark_label
        if len(rows) > 1 and y_cols:
            items = []
            for row in rows:
                name = str(row[col_idx.get(x_col, 0)] or '') if x_col in col_idx else ''
                try:
                    val = float(row[col_idx[y_cols[0]]] or 0) if y_cols[0] in col_idx else 0.0
                except (TypeError, ValueError):
                    val = 0.0
                benchmark = None
                benchmark_label = ''
                if len(y_cols) >= 2 and y_cols[1] in col_idx:
                    try:
                        benchmark = float(row[col_idx[y_cols[1]]] or 0)
                    except (TypeError, ValueError):
                        pass
                if len(y_cols) >= 3 and y_cols[2] in col_idx:
                    benchmark_label = str(row[col_idx[y_cols[2]]] or '')

                items.append({
                    'label': name,
                    'value': round(val, 1),
                    'formatted_value': self._gauge_format_value(val, vc),
                    'target': round(benchmark, 1) if benchmark is not None else None,
                    'target_label': benchmark_label,
                })

            return {
                'gauge_variant': 'bullet',
                'multi': True,
                'items': items,
                'min': b_min,
                'max': b_max,
                'ranges': ranges,
                'bar_height': bar_height,
                'orientation': orientation,
                'threshold_text': threshold_text,
            }

        # ── Single-row (backward compatible) ─────────────────────────────
        val = 0.0
        target = None
        if rows:
            try:
                val = float(rows[0][col_idx.get(x_col, 0)] or 0)
            except (TypeError, ValueError):
                val = 0.0
            if y_cols and y_cols[0] in col_idx:
                try:
                    target = float(rows[0][col_idx[y_cols[0]]] or 0)
                except (TypeError, ValueError):
                    pass

        target_override = vc.get('target_value')
        if target_override is not None:
            target = float(target_override)

        return {
            'gauge_variant': 'bullet',
            'value': round(val, 1),
            'formatted_value': self._gauge_format_value(val, vc),
            'target': round(target, 1) if target is not None else None,
            'min': b_min,
            'max': b_max,
            'ranges': ranges,
            'label': vc.get('gauge_label', ''),
            'orientation': orientation,
            'bar_height': bar_height,
            'threshold_text': threshold_text,
            'target_label': vc.get('target_label', ''),
        }

    def _bullet_parse_ranges(self, vc, b_min, b_max):
        """Parse bullet range zones from visual_config or build defaults."""
        ranges = []
        raw_ranges = vc.get('bullet_ranges', '')
        if raw_ranges and raw_ranges.strip():
            try:
                ranges = json.loads(raw_ranges)
            except (json.JSONDecodeError, TypeError):
                pass
        if not ranges:
            third = (b_max - b_min) / 3
            ranges = [
                {'to': b_min + third, 'color': '#ef4444', 'label': f'Poor <{round(b_min + third)}'},
                {'to': b_min + 2 * third, 'color': '#f59e0b', 'label': f'Watch {round(b_min + third)}-{round(b_min + 2 * third)}'},
                {'to': b_max, 'color': '#10b981', 'label': f'Good >{round(b_min + 2 * third)}'},
            ]
        return ranges

    def _build_rag_gauge(self, cols, rows, vc):
        """Build traffic light / RAG gauge data dict.

        Single-row mode:
          x_column = value
          y_columns[0] = red_threshold (optional — overrides static config)
          y_columns[1] = green_threshold (optional — overrides static config)
          y_columns[2] = badge_text (optional — overrides auto-computed badge)

        Multi-row mode (when SQL returns >1 row AND y_columns has value column):
          x_column = metric_name (label for each line)
          y_columns[0] = value (the metric value)
          y_columns[1] = rag_status ('green'|'amber'|'red' — optional, auto-computed if missing)
          y_columns[2] = status_text (e.g. "Above 80% target" — optional)

        If y_columns are not set or columns not found, falls back to static
        config values from visual_config (rag_red_threshold, rag_green_threshold).
        """
        col_idx = {c: i for i, c in enumerate(cols)}
        x_col = (self.x_column or '').strip() or (cols[0] if cols else '')
        y_cols = [c.strip() for c in (self.y_columns or '').split(',') if c.strip()]

        red_thresh = float(vc.get('rag_red_threshold', 70))
        green_thresh = float(vc.get('rag_green_threshold', 85))
        invert = vc.get('rag_invert', False)
        rag_layout = vc.get('rag_layout', 'circles')

        # ── Scorecard mode (multi-row list) ──────────────────────────
        if rag_layout == 'scorecard' and y_cols:
            items = []
            for row in rows:
                name = str(row[col_idx.get(x_col, 0)] or '') if x_col in col_idx else ''
                try:
                    val = float(row[col_idx[y_cols[0]]] or 0) if y_cols[0] in col_idx else 0.0
                except (TypeError, ValueError):
                    val = 0.0

                # RAG status: from SQL column or auto-compute
                rag_status = ''
                if len(y_cols) >= 2 and y_cols[1] in col_idx:
                    rag_status = str(row[col_idx[y_cols[1]]] or '').lower().strip()
                if rag_status not in ('green', 'amber', 'red'):
                    rag_status = self._compute_rag_status(val, red_thresh, green_thresh, invert)

                # Status text from SQL column
                status_text = ''
                if len(y_cols) >= 3 and y_cols[2] in col_idx:
                    status_text = str(row[col_idx[y_cols[2]]] or '')

                items.append({
                    'label': name,
                    'value': round(val, 1),
                    'formatted_value': self._gauge_format_value(val, vc),
                    'rag_status': rag_status,
                    'status_text': status_text,
                })

            return {
                'gauge_variant': 'traffic_light_rag',
                'multi': True,
                'items': items,
            }

        # ── Single-row mode (backward compatible) ────────────────────
        val = self._gauge_extract_value(cols, rows)
        row = rows[0] if rows else ()
        badge_override = ''

        if row and y_cols:
            if len(y_cols) >= 1 and y_cols[0] in col_idx:
                try:
                    sql_red = float(row[col_idx[y_cols[0]]] or 0)
                    if sql_red:
                        red_thresh = sql_red
                except (TypeError, ValueError):
                    pass
            if len(y_cols) >= 2 and y_cols[1] in col_idx:
                try:
                    sql_green = float(row[col_idx[y_cols[1]]] or 0)
                    if sql_green:
                        green_thresh = sql_green
                except (TypeError, ValueError):
                    pass
            if len(y_cols) >= 3 and y_cols[2] in col_idx:
                badge_override = str(row[col_idx[y_cols[2]]] or '')

        rag_status = self._compute_rag_status(val, red_thresh, green_thresh, invert)

        badge_text = ''
        if badge_override:
            badge_text = badge_override
        elif vc.get('rag_show_badge', True):
            badge_map = {
                'green': vc.get('rag_badge_green', 'On target'),
                'amber': vc.get('rag_badge_amber', 'Watch'),
                'red':   vc.get('rag_badge_red', 'At risk'),
            }
            badge_text = badge_map.get(rag_status, '')

        threshold_text = ''
        if vc.get('rag_show_thresholds', True):
            rt = round(red_thresh, 1)
            gt = round(green_thresh, 1)
            if invert:
                threshold_text = f'G: <{rt} | A: {rt}-{gt} | R: >{gt}'
            else:
                threshold_text = f'G: \u2265{gt} | A: {rt}-{gt} | R: <{rt}'

        fmt = self._gauge_format_value(val, vc)

        return {
            'gauge_variant': 'traffic_light_rag',
            'value': round(val, 1),
            'formatted_value': fmt,
            'rag_status': rag_status,
            'badge_text': badge_text,
            'threshold_text': threshold_text,
            'label': vc.get('gauge_label', ''),
        }

    def _compute_rag_status(self, val, red_thresh, green_thresh, invert):
        """Compute RAG status from value and thresholds."""
        if invert:
            if val <= red_thresh:
                return 'green'
            elif val <= green_thresh:
                return 'amber'
            return 'red'
        else:
            if val >= green_thresh:
                return 'green'
            elif val >= red_thresh:
                return 'amber'
            return 'red'

    def _build_percentile_gauge(self, cols, rows, vc):
        """Build percentile rank gauge data dict."""
        col_idx = {c: i for i, c in enumerate(cols)}
        x_col = (self.x_column or '').strip() or (cols[0] if cols else '')
        y_cols = [c.strip() for c in (self.y_columns or '').split(',') if c.strip()]

        percentile = 0
        subtitle = ''
        actual_value = ''
        actual_label = ''

        if rows:
            row = rows[0]
            try:
                percentile = int(float(row[col_idx.get(x_col, 0)] or 0))
            except (TypeError, ValueError):
                percentile = 0

            # Optional columns: subtitle, actual_value, actual_label
            if len(y_cols) >= 1 and y_cols[0] in col_idx:
                subtitle = str(row[col_idx[y_cols[0]]] or '')
            if len(y_cols) >= 2 and y_cols[1] in col_idx:
                actual_value = str(row[col_idx[y_cols[1]]] or '')
            if len(y_cols) >= 3 and y_cols[2] in col_idx:
                actual_label = str(row[col_idx[y_cols[2]]] or '')

        # Ordinal suffix
        invert = vc.get('percentile_invert', False)
        suffix = 'th'
        if percentile % 10 == 1 and percentile % 100 != 11:
            suffix = 'st'
        elif percentile % 10 == 2 and percentile % 100 != 12:
            suffix = 'nd'
        elif percentile % 10 == 3 and percentile % 100 != 13:
            suffix = 'rd'

        # Quartile
        if percentile >= 75:
            quartile_label = 'Top quartile'
            quartile_color = '#16a34a'
        elif percentile >= 50:
            quartile_label = '2nd quartile'
            quartile_color = '#2563eb'
        elif percentile >= 25:
            quartile_label = '3rd quartile'
            quartile_color = '#d97706'
        else:
            quartile_label = '4th quartile'
            quartile_color = '#dc2626'

        if invert:
            quartile_label += ' (inverted)'

        return {
            'gauge_variant': 'percentile_rank',
            'percentile': percentile,
            'ordinal_text': f'{percentile}{suffix}',
            'subtitle': subtitle or self.name,
            'quartile_label': quartile_label if vc.get('percentile_show_badge', True) else '',
            'quartile_color': quartile_color,
            'actual_value': actual_value,
            'actual_label': actual_label,
            'show_quartile_markers': vc.get('percentile_show_quartiles', True),
            'label': vc.get('gauge_label', ''),
        }

    def _gauge_format_value(self, val, vc):
        """Format a gauge value based on gauge_number_format flag."""
        fmt_mode = vc.get('gauge_number_format', 'auto')
        if fmt_mode == 'percent' or (fmt_mode == 'auto' and float(vc.get('gauge_max', self.gauge_max or 100)) == 100):
            return f'{round(val, 1)}%'
        elif fmt_mode == 'comma':
            return f'{val:,.0f}'
        elif fmt_mode == 'decimal1':
            return f'{val:.1f}'
        elif fmt_mode == 'decimal2':
            return f'{val:.2f}'
        elif fmt_mode == 'integer':
            return f'{int(round(val))}'
        elif fmt_mode == 'currency':
            return f'${val:,.0f}'
        return str(round(val, 1))

    # =========================================================================
    # gauge_kpi render builder
    # =========================================================================

    def _build_gauge_kpi_data(self, cols, rows):
        """Build render dict for gauge_kpi widgets.

        Supports both ECharts gauge variants (returns echart_json) and
        non-ECharts variants (returns gauge_variant + custom data).

        Returns:
            echart_json / gauge_variant — gauge rendering data
            sub_kpis    — list of {label, value, sub_label} dicts
            alert_text  — optional warning string from gauge_alert_column
        """
        col_idx = {c: i for i, c in enumerate(cols)}

        def col_val(row, name):
            idx = col_idx.get(name)
            return row[idx] if idx is not None else None

        row = rows[0] if rows else ()
        g_min = float(self.gauge_min or 0)
        g_max = float(self.gauge_max or 100)

        # Check gauge style for non-ECharts variants
        vc = {}
        try:
            vc = json.loads(self.visual_config or '{}') or {}
        except (json.JSONDecodeError, TypeError):
            pass
        gauge_style = vc.get('gauge_style', 'standard')

        if gauge_style in ('bullet', 'traffic_light_rag', 'percentile_rank'):
            # Non-ECharts gauge — merge custom data with sub-KPI/alert
            result = self._build_gauge_custom(cols, rows, vc, gauge_style)
        else:
            # ECharts gauge (standard, half_arc, three_quarter, multi_ring)
            gauge_option = self._build_gauge_option(cols, rows)
            result = {'echart_json': json.dumps(gauge_option, default=str)}

        # Sub-KPI cards ───────────────────────────────────────────────────────
        sub_cols   = [c.strip() for c in (self.gauge_sub_kpi_columns  or '').split(',') if c.strip()]
        sub_labels = [l.strip() for l in (self.gauge_sub_kpi_labels   or '').split(',') if l.strip()]
        sub_lcols  = [c.strip() for c in (self.gauge_sub_label_columns or '').split(',') if c.strip()]

        sub_kpis = []
        for i, col_name in enumerate(sub_cols):
            raw       = col_val(row, col_name) if row else None
            label     = sub_labels[i] if i < len(sub_labels) else col_name
            sub_label = str(col_val(row, sub_lcols[i]) or '') if (row and i < len(sub_lcols)) else ''
            try:
                fval = float(raw or 0)
                fmt_val = (f'{round(fval):.0f}%'
                           if (g_max == 100 and g_min == 0)
                           else str(round(fval, 1)))
            except (TypeError, ValueError):
                fmt_val = str(raw or '--')
            sub_kpis.append({'label': label, 'value': fmt_val, 'sub_label': sub_label})

        result['sub_kpis'] = sub_kpis

        # Alert / insight text ────────────────────────────────────────────────
        alert_text = ''
        if self.gauge_alert_column and row:
            alert_text = str(col_val(row, self.gauge_alert_column) or '')
        result['alert_text'] = alert_text

        result.update(self._get_typography_overrides())
        return result

    # =========================================================================
    # Non-chart render builders
    # =========================================================================

    def _build_kpi_data(self, cols, rows, portal_ctx):
        """Build dict for kpi / status_kpi cards."""
        x_col = (self.x_column or '').strip() or (cols[0] if cols else '')
        col_idx = {c: i for i, c in enumerate(cols)}

        raw_val = rows[0][col_idx[x_col]] if (rows and x_col in col_idx) else None
        formatted = self._format_kpi(raw_val)

        result = {
            'type': self.chart_type,
            'formatted_value': formatted,
            'label': self.name,
            'icon_name': self.icon_name or 'none',
            'display_mode': self.display_mode or 'standard',
            'kpi_layout': self.kpi_layout or 'vertical',
            'text_align': self.text_align or 'center',
        }

        if self.chart_type in ('status_kpi', 'kpi_strip') and self.status_column:
            status_idx = col_idx.get(self.status_column)
            status_val = str(rows[0][status_idx]).lower() if (rows and status_idx is not None) else 'neutral'
            icon_cls, css_mod = _STATUS_MAP.get(status_val, ('fa-circle', 'status-neutral'))
            result['icon_class'] = icon_cls
            result['status_css'] = css_mod
            result['status_val'] = status_val
        elif self.chart_type in ('status_kpi', 'kpi_strip') and not self.status_column:
            # Auto-trend: compare x_column (current) vs first y_column (prior)
            y_col_trend = (self.y_columns or '').split(',')[0].strip()
            if y_col_trend and y_col_trend in col_idx and rows:
                try:
                    current = float(raw_val or 0)
                    prior = float(rows[0][col_idx[y_col_trend]] or 0)
                    if current > prior:
                        result['icon_class'] = 'fa-arrow-up'
                        result['status_css'] = 'status-up'
                    elif current < prior:
                        result['icon_class'] = 'fa-arrow-down'
                        result['status_css'] = 'status-down'
                    else:
                        result['icon_class'] = 'fa-minus'
                        result['status_css'] = 'status-neutral'
                except (TypeError, ValueError):
                    pass

        # Secondary value — show percentage change vs prior
        y_col = (self.y_columns or '').split(',')[0].strip()
        if y_col and y_col in col_idx and rows:
            prior_raw = rows[0][col_idx[y_col]]
            try:
                current = float(raw_val or 0)
                prior = float(prior_raw or 0)
                if prior:
                    pct = ((current - prior) / abs(prior)) * 100
                    sign = '+' if pct > 0 else ''
                    result['secondary'] = f'{sign}{pct:.0f}% vs Prior'
                else:
                    result['secondary'] = f'Prior: {prior_raw}'
            except (TypeError, ValueError):
                result['secondary'] = str(prior_raw)

        result.update(self._get_typography_overrides())
        return result

    def _build_table_data(self, cols, rows):
        """Build dict for data table widgets.

        When table_column_config is set (AG Grid mode), returns columnDefs +
        rowData (list of dicts).  Otherwise falls back to legacy cols/rows
        format for backward compatibility with existing table widgets.
        """
        column_config = []
        try:
            column_config = json.loads(self.table_column_config or '[]')
        except (json.JSONDecodeError, TypeError):
            column_config = []

        if column_config:
            # AG Grid mode: columnDefs + rowData (list of dicts)
            row_data = [
                {c: (v if v is not None else '') for c, v in zip(cols, r)}
                for r in rows
            ]
            # Parse visual_config for table display options (pagination, scroll, etc.)
            vc = {}
            try:
                vc = json.loads(self.visual_config or '{}') or {}
            except (json.JSONDecodeError, TypeError):
                vc = {}
            return {
                'type': 'table',
                'columnDefs': column_config,
                'rowData': row_data,
                'row_count': len(rows),
                'visual_config': vc,
            }

        # Legacy mode: plain cols/rows for backward compat
        result = {
            'type': 'table',
            'cols': cols,
            'rows': [[str(cell) if cell is not None else '' for cell in r] for r in rows],
        }
        result.update(self._get_typography_overrides())
        return result

    def _build_battle_data(self, cols, rows):
        """Build dict for battle_card widgets."""
        col_idx = {c: i for i, c in enumerate(cols)}
        label_col = (self.label_column or '').strip() or (cols[0] if cols else '')
        you_col   = (self.you_column or '').strip() or (cols[1] if len(cols) > 1 else '')
        them_col  = (self.them_column or '').strip() or (cols[2] if len(cols) > 2 else '')
        higher_better = (self.win_threshold or 'higher') == 'higher'

        battle_rows = []
        for r in rows:
            lbl  = str(r[col_idx[label_col]]) if label_col in col_idx else ''
            you  = r[col_idx[you_col]]  if you_col  in col_idx else 0
            them = r[col_idx[them_col]] if them_col  in col_idx else 0
            try:
                you_f  = float(you  or 0)
                them_f = float(them or 0)
            except (TypeError, ValueError):
                you_f = them_f = 0.0

            if you_f == them_f:
                result = 'tie'
            elif higher_better:
                result = 'win' if you_f > them_f else 'lose'
            else:
                result = 'win' if you_f < them_f else 'lose'

            diff = abs(you_f - them_f)
            battle_rows.append({
                'label':     lbl,
                'you':       str(you),
                'them':      str(them),
                'you_f':     you_f,
                'them_f':    them_f,
                'result':    result,
                'advantage': f'+{diff:.1f}' if result == 'win' else (f'-{diff:.1f}' if result == 'lose' else 'Even'),
            })

        wins  = sum(1 for r in battle_rows if r['result'] == 'win')
        total = len(battle_rows)
        result = {
            'type':            'battle_card',
            'rows':            battle_rows,
            'competitor_name': self.competitor_name or 'Competitor',
            'wins':            wins,
            'total':           total,
            'summary':         f'You outperform {self.competitor_name or "Competitor"} in {wins} of {total} metrics' if total else '',
        }
        result.update(self._get_typography_overrides())
        return result

    def _build_insight_data(self, cols, rows, portal_ctx):
        """Build dict for insight_panel widgets."""
        col_idx = {c: i for i, c in enumerate(cols)}
        row = {}
        if rows:
            row = {c: (rows[0][i] if i < len(rows[0]) else None)
                   for i, c in enumerate(cols)}

        # Determine classification and status CSS
        classification = str(row.get('classification') or '').lower()
        _, css_mod = _STATUS_MAP.get(classification, ('fa-info-circle', 'status-neutral'))
        icon_cls, _ = _STATUS_MAP.get(classification, ('fa-info-circle', 'status-neutral'))

        narrative = self._build_narrative(row, portal_ctx)

        result = {
            'type':           'insight_panel',
            'classification': row.get('classification') or '',
            'icon_class':     icon_cls,
            'status_css':     css_mod,
            'metric1_label':  self.metric1_label or '',
            'metric1_value':  str(row.get('metric1') or ''),
            'metric2_label':  self.metric2_label or '',
            'metric2_value':  str(row.get('metric2') or ''),
            'metric3_label':  self.metric3_label or '',
            'metric3_value':  str(row.get('metric3') or ''),
            'narrative':      narrative,
        }
        result.update(self._get_typography_overrides())
        return result

    # =========================================================================
    # Narrative template injection
    # =========================================================================

    def _build_narrative(self, sql_row, portal_ctx):
        """Interpolate narrative_template with SQL result + filter context."""
        if not self.narrative_template:
            return ''

        # Layer 1: all SQL result columns
        template_vars = {k: (str(v) if v is not None else '') for k, v in sql_row.items()}

        # Layer 2: all active filter values keyed by field_name
        template_vars.update(portal_ctx.get('filter_values_by_name', {}))

        # Layer 3: HHA display name (geo values already in filter_values_by_name)
        hha = portal_ctx.get('selected_hha')
        if hha:
            template_vars['hha_name'] = (
                hha.hha_brand_name or hha.hha_dba or hha.hha_name or '')
        else:
            template_vars.setdefault('hha_name', '')

        try:
            return self.narrative_template % template_vars
        except (KeyError, TypeError):
            # Return raw template if a placeholder is missing
            return self.narrative_template

    # =========================================================================
    # Annotation interpolation (SQL-driven annotations for all widget types)
    # =========================================================================

    def _interpolate_annotations(self, cols, rows, portal_ctx):
        """Interpolate %(column)s in subtitle, footnote, annotation_text from SQL + filters.

        Returns a dict with resolved values for React-rendered annotations.
        These are merged into the get_portal_data result so the controller
        can serialize them alongside widget data.

        Data sources (layered, later layers override earlier):
          1. Main chart query first row (cols/rows)
          2. Annotation SQL query (annotation_query_sql) — if set, its columns
             override same-named columns from the main query
          3. Active filter values (by param_name from filter_values_by_name)
          4. HHA display name
        """
        # Layer 1: main chart query first row
        template_vars = {}
        if rows and cols:
            template_vars = {c: (str(rows[0][i]) if rows[0][i] is not None else '')
                             for i, c in enumerate(cols)}

        # Layer 2: annotation SQL query (separate aggregation)
        if self.annotation_query_sql:
            try:
                ann_cols, ann_rows = self._execute_annotation_sql(
                    portal_ctx.get('sql_params', {}))
                if ann_rows and ann_cols:
                    ann_row = {c: (str(ann_rows[0][i]) if ann_rows[0][i] is not None else '')
                               for i, c in enumerate(ann_cols)}
                    template_vars.update(ann_row)
            except Exception as exc:
                _logger.warning(
                    'widget %s annotation_query_sql error: %s', self.id, exc)

        # Layer 3: filter values
        template_vars.update(portal_ctx.get('filter_values_by_name', {}))

        # Layer 4: HHA display name (geo values already in filter_values_by_name above)
        hha = portal_ctx.get('selected_hha')
        if hha:
            template_vars['hha_name'] = (
                hha.hha_brand_name or hha.hha_dba or hha.hha_name or '')
        else:
            template_vars.setdefault('hha_name', '')

        def _interp(text):
            if not text:
                return ''
            try:
                return text % template_vars
            except (KeyError, TypeError, ValueError):
                return text

        result = {}
        resolved_subtitle = _interp(self.subtitle)
        if resolved_subtitle:
            result['_resolved_subtitle'] = resolved_subtitle
        resolved_footnote = _interp(self.footnote)
        if resolved_footnote:
            result['_resolved_footnote'] = resolved_footnote
        resolved_annotation = _interp(self.annotation_text)
        if resolved_annotation:
            result['_resolved_annotation_text'] = resolved_annotation

        # Also resolve annotation_value from annotation query if column is set
        if self.annotation_value_column and self.annotation_value_column in template_vars:
            try:
                result['_resolved_annotation_value'] = float(
                    template_vars[self.annotation_value_column])
            except (TypeError, ValueError):
                pass

        return result

    def _execute_annotation_sql(self, params):
        """Execute annotation_query_sql separately; return (col_names, rows).

        Same safety checks as _execute_sql: SELECT/WITH only, no DML/DDL.
        """
        self.ensure_one()
        sql = (self.annotation_query_sql or '').strip()
        if not sql:
            return [], []

        # Reuse the same SQL sanitisation from dashboard_page_section
        import re as _re
        _BLOCKED = _re.compile(
            r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|EXECUTE)\b',
            _re.IGNORECASE)
        sql_clean = _re.sub(r'/\*.*?\*/', ' ', sql, flags=_re.DOTALL)
        sql_clean = _re.sub(r'--[^\n]*', ' ', sql_clean)
        first_word = sql_clean.strip().split()[0].upper() if sql_clean.strip() else ''

        if first_word not in ('SELECT', 'WITH'):
            raise ValueError('Annotation SQL: only SELECT or WITH allowed.')
        if _BLOCKED.search(sql_clean):
            raise ValueError('Annotation SQL contains a disallowed keyword.')

        with self.env.cr.savepoint():
            self.env.cr.execute(sql, dict(params))
            ann_cols = [desc[0] for desc in self.env.cr.description] if self.env.cr.description else []
            ann_rows = self.env.cr.fetchall()
            return ann_cols, ann_rows

    # =========================================================================
    # Typography style helper
    # =========================================================================

    def _get_typography_overrides(self):
        """Return a dict of typography overrides (only non-default values)."""
        overrides = {}
        if self.label_font_weight and self.label_font_weight != 'normal':
            overrides['label_font_weight'] = _WEIGHT_MAP[self.label_font_weight]
        if self.value_font_weight and self.value_font_weight != 'bold':
            overrides['value_font_weight'] = _WEIGHT_MAP[self.value_font_weight]
        if self.label_color and self.label_color != 'default':
            overrides['label_color'] = _LABEL_COLOR_MAP[self.label_color]
        if self.value_color and self.value_color != 'default':
            overrides['value_color'] = _VALUE_COLOR_MAP[self.value_color]
        if self.icon_color and self.icon_color != 'default':
            if self.icon_color == 'custom':
                overrides['icon_color'] = self.icon_custom_color or '#2563eb'
                overrides['icon_bg'] = self.icon_custom_bg or '#dbeafe'
            elif self.icon_color in _ICON_COLOR_MAP:
                overrides['icon_color'] = _ICON_COLOR_MAP[self.icon_color]['fg']
                overrides['icon_bg'] = _ICON_COLOR_MAP[self.icon_color]['bg']
        return overrides

    # =========================================================================
    # KPI formatting helper
    # =========================================================================

    def _format_kpi(self, raw):
        """Format a raw numeric value according to kpi_format setting."""
        if raw is None:
            return '--'
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return str(raw)

        fmt = self.kpi_format or 'number'
        prefix = self.kpi_prefix or ''
        suffix = self.kpi_suffix or ''

        if fmt == 'currency':
            formatted = f'${val:,.0f}'
        elif fmt == 'percent':
            formatted = f'{val:.1f}%'
        elif fmt == 'decimal':
            formatted = f'{val:,.2f}'
        else:  # number
            formatted = f'{val:,.0f}'

        return f'{prefix}{formatted}{suffix}'


# ── Deep merge utility ────────────────────────────────────────────────────────

def _deep_merge(base, override):
    """Recursively merge override dict into base dict; returns new dict."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
