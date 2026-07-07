# -*- coding: utf-8 -*-

import json
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# ── DML / DDL keywords that must never appear in admin SQL ────────────────────
_BLOCKED_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|EXECUTE)\b',
    re.IGNORECASE,
)


class DashboardWidgetScopeOption(models.Model):
    _name = 'dashboard.widget.scope.option'
    _description = 'Widget Scope Option'
    _order = 'sequence asc, id asc'

    # ── Placement ─────────────────────────────────────────────────────────────
    widget_id = fields.Many2one(
        'dashboard.widget', required=True, ondelete='cascade', string='Widget')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    # ── Option Identity ───────────────────────────────────────────────────────
    label = fields.Char(required=True, string='Label',
        help='Button text or dropdown option text (e.g., "Hospitals")')
    value = fields.Char(string='Value',
        help='Parameter value passed to SQL. Empty = "All" (no filter applied).')
    icon = fields.Char(string='Icon (FA class)',
        help='Font Awesome icon for toggle buttons. e.g., fa-hospital-o')
    color = fields.Char(string='Option Color',
        help='Accent color for this option (hex, e.g. #4f46e5). Drives the active '
             'toggle button background (and the selected dropdown accent). '
             'Blank = default styling.')
    icon_color = fields.Char(string='Icon Color',
        help='Color for this option\'s Font Awesome icon (hex). '
             'Blank = falls back to Option Color, then default.')

    # ── Map choropleth geo level (per-option; drives state vs county render) ────
    # default_geo_level = what this option RENDERS by default.
    # allowed_geo_levels = which levels its SQL CAN render.
    # supports_drill     = whether clicking a state may request county.
    default_geo_level = fields.Selection(
        [('state', 'State'), ('county', 'County')],
        string='Default Geo Level', default='state',
        help='For choropleth map scope options: the geographic level this option '
             'renders by default.')
    allowed_geo_levels = fields.Char(
        string='Allowed Geo Levels', default='state',
        help='Comma-separated levels this option\'s SQL can render, e.g. "state" or '
             '"state,county". Must include the Default Geo Level.')
    supports_drill = fields.Boolean(
        string='Supports Drill', default=False,
        help='When ON, clicking a state on this option may drill into its counties '
             '(requires "county" in Allowed Geo Levels).')

    @api.constrains('default_geo_level', 'allowed_geo_levels')
    def _check_geo_levels(self):
        valid = {'state', 'county'}
        for rec in self:
            allowed = {t.strip() for t in (rec.allowed_geo_levels or '').split(',') if t.strip()}
            if not allowed:
                continue  # blank → treated as widget default elsewhere
            bad = allowed - valid
            if bad:
                raise ValidationError(
                    'Allowed Geo Levels may only contain "state" or "county"; got: %s'
                    % ', '.join(sorted(bad)))
            if (rec.default_geo_level or 'state') not in allowed:
                raise ValidationError(
                    'Default Geo Level "%s" must be included in Allowed Geo Levels (%s).'
                    % (rec.default_geo_level, ', '.join(sorted(allowed))))

    # ── Query Mode: per-option SQL ────────────────────────────────────────────
    query_sql = fields.Text(string='SQL Query (Query Mode)',
        help='If set, this SQL replaces the widget\'s main SQL when this option is active.\n'
             'Use %(param_name)s for page filter values.\n'
             'Use {where_clause} for auto-generated WHERE from page filters.\n'
             'Leave empty to use the widget\'s main SQL with parameter mode.')
    schema_source_id = fields.Many2one(
        'dashboard.schema.source', string='Schema Source',
        ondelete='set null',
        help='Schema source for this option\'s SQL.\n'
             'Falls back to widget\'s schema source if empty.')
    where_clause_exclude = fields.Char(
        string='Exclude from {where_clause}',
        help='Comma-separated param names to exclude from auto-generated WHERE.\n'
             'Falls back to widget\'s exclude if empty.')

    # ── Column Config (Query Mode) ────────────────────────────────────────────
    table_column_config = fields.Text(
        string='Table Column Config (JSON)',
        help='AG Grid columnDefs for this option. Only for table widgets in query mode.\n'
             'JSON array of column definitions with field, headerName, width, cellRenderer, etc.')
    x_column = fields.Char(string='X Column',
        help='X-axis/label column for chart widgets in query mode.')
    y_columns = fields.Char(string='Y Column(s)',
        help='Comma-separated Y-axis value columns for chart widgets in query mode.')
    series_column = fields.Char(string='Series Column',
        help='Series/grouping column for chart widgets in query mode.')

    # ── Per-Option Click Actions ──────────────────────────────────────────────
    click_action = fields.Selection([
        ('none', 'No Action'),
        ('filter_page', 'Filter Page'),
        ('go_to_page', 'Go to Page'),
        ('show_details', 'Show Details'),
        ('open_url', 'Open URL'),
    ], default='none', string='Click Action')
    action_page_key = fields.Char(string='Target Page Key')
    action_tab_key = fields.Char(string='Target Tab Key')
    action_pass_value_as = fields.Char(string='Pass Value As')
    drill_detail_columns = fields.Char(string='Detail Columns')
    action_url_template = fields.Char(string='URL Template')

    # ── Ranked Detail List per-option configs (Mode B — Different SQL Per Option)
    # When the parent widget is chart_type='ranked_detail_list' and
    # scope_query_mode='query', each scope option can have its own full
    # layout: master row config + detail config. This lets FFS, MA, ALL tabs
    # each show totally different column structures (e.g. FFS = hospitals,
    # MA = health plans, ALL = aggregated metrics).
    ranked_master_config = fields.Text(
        string='Master Layout Config (JSON, per-option)',
        help='v2 master row layout for this scope option when the widget '
             'uses "Different SQL Per Option" mode. Overrides the widget-'
             'level ranked_master_config when set.')
    ranked_detail_config = fields.Text(
        string='Detail Config (JSON, per-option)',
        help='v2 detail config (row key, detail SQL, tiles, sub-list) for '
             'this scope option when the widget uses "Different SQL Per '
             'Option" mode. Overrides the widget-level ranked_detail_config.')

    # ── Computed ──────────────────────────────────────────────────────────────

    has_custom_sql = fields.Boolean(
        compute='_compute_has_custom_sql', store=False,
        string='Has SQL',
        help='Indicates whether this option has its own SQL query (Query Mode).')

    @api.depends('query_sql')
    def _compute_has_custom_sql(self):
        for rec in self:
            rec.has_custom_sql = bool((rec.query_sql or '').strip())

    # ── Validation ────────────────────────────────────────────────────────────

    @api.constrains('query_sql')
    def _check_sql_safe(self):
        for rec in self:
            sql = rec.query_sql or ''
            if sql and _BLOCKED_KEYWORDS.search(sql):
                raise models.ValidationError(
                    'Option SQL must be SELECT only. '
                    'DML/DDL keywords are not allowed.')

    @api.constrains('query_sql', 'schema_source_id')
    def _check_where_clause_requires_source(self):
        for rec in self:
            if (rec.query_sql and '{where_clause}' in rec.query_sql
                    and not rec.schema_source_id
                    and not rec.widget_id.schema_source_id):
                raise models.ValidationError(
                    'A Schema Source is required (on the option or the widget) '
                    'when using {where_clause} in SQL.')

    # ── SQL Execution ─────────────────────────────────────────────────────────

    def execute_option_sql(self, portal_ctx):
        """Execute this option's SQL query.

        Returns widget-compatible data dict (same format as widget.get_portal_data).
        Uses option's schema_source if set, otherwise falls back to widget's.

        portal_ctx keys (same as widget pipeline):
            sql_params       — dict{param_name: value}
            _filter_defs     — list of filter definition dicts
        """
        self.ensure_one()
        sql = (self.query_sql or '').strip()
        if not sql:
            return {'error': 'No SQL configured for this option'}

        sql_params = dict(portal_ctx.get('sql_params', {}))

        # Map choropleth: resolve THIS option's effective geo level (widget helper
        # is the single source of truth) and inject into the LOCAL params so
        # level-aware SQL (%(_map_level)s / [[ ... ]]) resolves — initial + drill.
        if self.widget_id.chart_type in ('map', 'albers_choropleth'):
            _lvl = self.widget_id._effective_map_level(
                option=self, raw_map_level=sql_params.get('_map_level'))
            sql_params['_map_level'] = _lvl
            # Drill filters only apply at county level. If the effective level
            # fell back to state (drill not supported, or a forged _map_level),
            # drop the drill scope so a [[ AND state_cd = %(_drill_state_code)s ]]
            # clause can't silently filter a state query by stale drill params.
            if _lvl != 'county':
                sql_params.pop('_drill_state_code', None)
                sql_params.pop('_drill_state_fips', None)

        try:
            # Handle {where_clause} — use option's source or fall back to widget's
            if '{where_clause}' in sql:
                from ..utils.filter_builder import DashboardFilterBuilder
                source = self.schema_source_id or self.widget_id.schema_source_id
                source_columns = {
                    c.column_name for c in source.column_ids
                } if source else None
                exclude_raw = (
                    self.where_clause_exclude
                    or self.widget_id.where_clause_exclude
                    or ''
                )
                exclude = [
                    p.strip() for p in exclude_raw.split(',') if p.strip()
                ] or None

                builder = DashboardFilterBuilder(
                    user_params=sql_params,
                    filter_defs=portal_ctx.get('_filter_defs', []),
                    source_columns=source_columns,
                    exclude_params=exclude,
                )
                where_sql, built_params = builder.build()
                sql_params.update(built_params)
                sql_params['_where_sql'] = where_sql
                sql = sql.replace('{where_clause}', sql_params.pop('_where_sql', '1=1'))

            # Process [[...]] optional clauses (same as widgets)
            if '[[' in sql:
                from ..utils.filter_builder import resolve_optional_clauses
                sql = resolve_optional_clauses(sql, sql_params)

            # Safety check — SELECT/WITH only
            sql_clean = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
            sql_clean = re.sub(r'--[^\n]*', ' ', sql_clean)
            first_word = sql_clean.strip().split()[0].upper() if sql_clean.strip() else ''
            if first_word not in ('SELECT', 'WITH'):
                _logger.warning(
                    'Scope option %s (%s): SQL must start with SELECT or WITH',
                    self.id, self.label)
                return {'error': 'SQL must start with SELECT or WITH'}

            # Fill missing params with None (prevent KeyError)
            safe_params = dict(sql_params)
            for m in re.finditer(r'%\(([^)]+)\)s', sql):
                if m.group(1) not in safe_params:
                    safe_params[m.group(1)] = None

            # Dispatch through the executor. The scope option's own
            # ``schema_source_id`` wins; if unset, fall back to the
            # parent widget's schema source. This means a CH-backed
            # widget scope-option SQL runs against CH automatically.
            from ..utils.query_executors import get_executor
            source = self.schema_source_id or self.widget_id.schema_source_id
            executor = get_executor(self.env, source)
            cols, rows = executor.execute(sql, safe_params)

            # Format result using per-option column config when available
            widget = self.widget_id
            if widget.chart_type == 'table':
                # AG Grid columnDefs resolution — generic fallback chain so
                # every Data Table scope widget in every app (Posterra, MSSP,
                # Inhome, Inhome_v1, future apps) renders as AG Grid whenever
                # ANY usable column config exists, rather than silently falling
                # back to plain HTML.
                #
                # Priority order:
                #   1. This scope option's own table_column_config
                #      (admin explicitly configured columns for this tab).
                #   2. Any sibling scope option's table_column_config — used
                #      as a reasonable default when the admin only configured
                #      columns on one tab and the other tabs share the same
                #      SQL column names (the common case for metric-switch
                #      tables like Admits / Visits / Therapy Share).
                #   3. Widget-level table_column_config, handled implicitly
                #      by _build_table_data() when both of the above are empty.
                #
                # The new #2 step is the additive fix — it doesn't override
                # any explicit per-tab config, it only activates when the
                # current tab has none.
                raw_config = self.table_column_config or ''
                if not raw_config:
                    for sibling in (widget.scope_option_ids - self).sorted('sequence'):
                        if sibling.table_column_config:
                            raw_config = sibling.table_column_config
                            break
                col_config = None
                if raw_config:
                    try:
                        col_config = json.loads(raw_config)
                    except (json.JSONDecodeError, TypeError):
                        col_config = None
                result = widget._build_table_data(cols, rows)
                if col_config:
                    result['columnDefs'] = col_config
                return result
            elif widget.chart_type == 'ranked_detail_list':
                # Ranked list (Mode B): option overrides master layout.
                # Parse option's v2 configs; fall back to widget's if empty.
                opt_master = {}
                opt_detail = {}
                try:
                    opt_master = json.loads(self.ranked_master_config or '{}') or {}
                except (json.JSONDecodeError, TypeError):
                    pass
                try:
                    opt_detail = json.loads(self.ranked_detail_config or '{}') or {}
                except (json.JSONDecodeError, TypeError):
                    pass

                # Build rowData from this option's SQL result
                row_data = [
                    {c: (v if v is not None else '') for c, v in zip(cols, r)}
                    for r in rows
                ]
                for i, rd in enumerate(row_data):
                    rd['_rank'] = i + 1

                # Use option's configs if present, else fall back to widget's
                master_config = opt_master if opt_master else widget._get_ranked_master_config()
                detail_config = opt_detail if opt_detail else widget._get_ranked_detail_config()
                key_column = (
                    detail_config.get('rowKey')
                    or widget.ranked_detail_key_column
                    or ''
                )
                has_detail = bool(
                    (detail_config.get('sql')
                     or widget.ranked_detail_sql or '').strip()
                    or any(t.get('sql') for t in (detail_config.get('tiles') or []))
                    or ((detail_config.get('sublist') or {}).get('sql') or '').strip()
                )

                return {
                    'type': 'ranked_detail_list',
                    'rowData': row_data,
                    'row_count': len(rows),
                    'key_column': key_column,
                    'has_detail': has_detail,
                    'master_config': master_config,
                    'detail_config': detail_config,
                    # v1 legacy (empty when v2 config is used)
                    'columnDefs': [],
                    'detail_chart_config': [],
                    'detail_sublist_config': {},
                }
            elif widget.chart_type in ('map', 'albers_choropleth'):
                # Build map data, then OVERWRITE geo_level/join_property with this
                # option's effective level — _build_map_choropleth reads the widget
                # visual_config level and has NO option awareness, so injecting the
                # SQL param alone is not enough (Codex).
                result = widget._format_scope_result(cols, rows)
                if isinstance(result, dict):
                    lvl = widget._effective_map_level(
                        option=self, raw_map_level=sql_params.get('_map_level'))
                    result['geo_level'] = lvl
                    jp = (result.get('map_config') or {}).get('choropleth_join_property')
                    result['join_property'] = jp or ('GEOID' if lvl == 'county' else 'STUSPS')
                return result
            elif widget.chart_type not in ('table',) and (self.x_column or self.y_columns):
                # Chart with per-option column mapping — override x/y/series
                # Temporarily set widget columns to option's columns for formatting
                orig_x = widget.x_column
                orig_y = widget.y_columns
                orig_s = widget.series_column
                try:
                    widget.x_column = self.x_column or orig_x
                    widget.y_columns = self.y_columns or orig_y
                    widget.series_column = self.series_column or orig_s
                    return widget._format_scope_result(cols, rows)
                finally:
                    widget.x_column = orig_x
                    widget.y_columns = orig_y
                    widget.series_column = orig_s
            else:
                return widget._format_scope_result(cols, rows)

        except Exception as exc:
            _logger.warning(
                'Scope option %s (%s) SQL execution error: %s',
                self.id, self.label, exc)
            return {'error': str(exc)}
