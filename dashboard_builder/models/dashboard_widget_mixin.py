# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_DRAWER_SECTION_TYPES = (
    'field_grid', 'flag_chips', 'measure_cards', 'alert_blocks', 'chart')
_DRAWER_TRIGGERS = ('row', 'cell')
_DRAWER_SOURCES = ('master_row', 'sql')
_DRAWER_CHART_TYPES = ('bar',)
_DRAWER_CHART_ORIENTATIONS = ('vertical', 'horizontal')
_DRAWER_CHART_NUMBER_FORMATS = ('compact', 'number', 'raw')


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

    # ── Detail Drawer config (generic DataTable row-detail drawer) ────────
    # Drives the configurable "open a detail drawer on row/cell click" feature
    # for table widgets. JSON shape: {enabled, trigger ('row'|'cell'),
    # row_key_column, title_template, subtitle_template, sections:[...]}.
    # Member-360 is one preset of this. Authored by the Detail Drawer designer
    # panel (or the advanced JSON editor). SQL-backed sections run against the
    # widget's own schema_source_id (source-inherited, v1). The raw value
    # (with SQL) is admin-only; the portal payload carries a SQL-stripped
    # projection (see dashboard.widget._build_drawer_render_schema).
    detail_drawer_config = fields.Text(
        string='Detail Drawer Config (JSON)',
        help='JSON config for the row/cell Detail Drawer on table widgets. '
             'Sections of type field_grid / flag_chips / measure_cards / '
             'alert_blocks / chart, each master_row or sql (with row_key param). '
             'Member-360 ships as a preset.')

    # ── Ranked Detail List configs (v2 consolidated) ──────────────────────
    ranked_master_config = fields.Text(
        string='Ranked Master Layout (JSON)',
        help='JSON describing the master row layout for ranked_detail_list '
             'widgets. Produced by the Dashboard Builder.')
    ranked_detail_config = fields.Text(
        string='Ranked Detail Config (JSON)',
        help='JSON describing the detail panel (row key, detail SQL, tiles, '
             'sub-list) for ranked_detail_list widgets.')

    # ── Smart Table config (chart_type='smart_table') ─────────────────────
    # Stored separately from table_column_config (which is AG Grid's schema)
    # so the two widget types can never accidentally cross-contaminate. The
    # JSON shape is documented in SmartTable.jsx — { columns: [...],
    # table: { density, height, stickyHeader, zebraRows, sortable } }.
    smart_table_config = fields.Text(
        string='Smart Table Config (JSON)',
        help='JSON schema defining columns + cell recipes for smart_table '
             'widgets. Five recipes supported: text, metric, '
             'metric_with_delta, badge, composite. Auto-populated by builder.')

    # ── Detail Drawer config validation (save-time, every API path) ────────
    @api.constrains('detail_drawer_config')
    def _check_detail_drawer_config(self):
        """Validate the Detail Drawer JSON on save (designer, builder, Odoo
        form — all paths) so a bad config produces a clear admin error instead
        of a broken portal. Runtime adds per-section error isolation on top."""
        for rec in self:
            raw = (rec.detail_drawer_config or '').strip()
            if not raw:
                continue
            try:
                cfg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                raise ValidationError('Detail Drawer config is not valid JSON.')
            if not isinstance(cfg, dict):
                raise ValidationError('Detail Drawer config must be a JSON object.')
            if not cfg.get('enabled'):
                continue  # disabled config need not be fully valid
            trigger = cfg.get('trigger')
            if trigger not in _DRAWER_TRIGGERS:
                raise ValidationError(
                    "Detail Drawer 'trigger' must be 'row' or 'cell'.")
            if not (cfg.get('row_key_column') or '').strip():
                raise ValidationError(
                    'Detail Drawer requires a row_key_column.')
            sections = cfg.get('sections')
            if not isinstance(sections, list) or not sections:
                raise ValidationError(
                    'Detail Drawer requires at least one section.')
            seen_ids = set()
            for s in sections:
                if not isinstance(s, dict):
                    raise ValidationError('Each drawer section must be an object.')
                sid = s.get('id')
                if not sid:
                    raise ValidationError('Each drawer section needs an id.')
                if sid in seen_ids:
                    raise ValidationError(
                        'Duplicate drawer section id: %s' % sid)
                seen_ids.add(sid)
                if s.get('type') not in _DRAWER_SECTION_TYPES:
                    raise ValidationError(
                        "Section '%s' has an invalid type." % sid)
                src = s.get('source')
                if src not in _DRAWER_SOURCES:
                    raise ValidationError(
                        "Section '%s' source must be 'master_row' or 'sql'." % sid)
                if src == 'sql':
                    sql = (s.get('sql') or '').strip()
                    if not sql:
                        raise ValidationError(
                            "Section '%s' is source 'sql' but has no SQL." % sid)
                    if '%(row_key)s' not in sql:
                        raise ValidationError(
                            "Section '%s' SQL must reference %%(row_key)s." % sid)
                if s.get('type') == 'chart':
                    chart_type = s.get('chart_type') or 'bar'
                    if chart_type not in _DRAWER_CHART_TYPES:
                        raise ValidationError(
                            "Chart section '%s' currently supports only "
                            "chart_type 'bar'." % sid)
                    if not (s.get('x_column') or '').strip():
                        raise ValidationError(
                            "Chart section '%s' requires x_column." % sid)
                    if not (s.get('y_column') or '').strip():
                        raise ValidationError(
                            "Chart section '%s' requires y_column." % sid)
                    orientation = s.get('orientation') or 'vertical'
                    if orientation not in _DRAWER_CHART_ORIENTATIONS:
                        raise ValidationError(
                            "Chart section '%s' orientation must be "
                            "'vertical' or 'horizontal'." % sid)
                    number_format = s.get('number_format') or 'compact'
                    if number_format not in _DRAWER_CHART_NUMBER_FORMATS:
                        raise ValidationError(
                            "Chart section '%s' number_format must be "
                            "'compact', 'number', or 'raw'." % sid)
