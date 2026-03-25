# -*- coding: utf-8 -*-

from odoo import fields, models


class DashboardWidgetActionMixin(models.AbstractModel):
    _name = 'dashboard.widget.action.mixin'
    _description = 'Widget Action Mixin'

    # ── Click Action Preset ──────────────────────────────────────────────────
    click_action = fields.Selection([
        ('none',           'No action'),
        ('filter_page',    'Filter this page'),
        ('go_to_page',     'Go to another page'),
        ('show_details',   'Show detail table'),
        ('open_url',       'Open URL'),
    ], default='none', string='When Clicked')

    # For 'go_to_page': navigate to another page with filter pre-set
    action_page_key = fields.Char(
        string='Target Page Key',
        help='Page key to navigate to (e.g., "physicians")')
    action_tab_key = fields.Char(
        string='Target Tab Key',
        help='Optional tab key on the target page')
    action_pass_value_as = fields.Char(
        string='Pass Clicked Value As',
        help='URL parameter name for clicked value (e.g., "physician_name")')

    # For 'show_details': auto-generate drill-down query
    drill_detail_columns = fields.Char(
        string='Detail Columns',
        help='Comma-separated columns to show in drill-down modal. '
             'Leave empty = show all columns from the base query.')

    # For 'open_url': URL template with placeholder
    action_url_template = fields.Char(
        string='URL Template',
        help='URL with {value} placeholder. E.g.: /my/posterra/hha/{value}')

    # ── Column Links (for table-type widgets) ────────────────────────────────
    column_link_config = fields.Text(
        string='Column Links (JSON)',
        help='JSON config for clickable columns in table widgets. Format: '
             '[{"column": "physician_name", "page_key": "physicians", '
             '"filter_param": "physician_name"}]')

    # ── Builder Config (stored for edit/rebuild) ─────────────────────────────
    builder_config = fields.Text(
        string='Builder Config (JSON)',
        help='Stores the full widget builder config so the widget can be '
             'edited in the builder later. Auto-populated by builder API.')

    # ── Table Column Config (AG Grid columnDefs) ──────────────────────────
    table_column_config = fields.Text(
        string='Table Column Config (JSON)',
        help='AG Grid columnDefs JSON array. Stores full column configuration '
             'including renderers, formatters, sorting, pinning, conditional '
             'formatting, and per-column click actions. Only used when '
             'chart_type is "table". Auto-populated by builder.')
