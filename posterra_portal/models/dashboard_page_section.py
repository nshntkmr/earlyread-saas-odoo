# -*- coding: utf-8 -*-

import json
import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# ── Color palette cycling for comparison_bar progress bars ────────────────────
_BAR_COLORS = ['pv-bar-blue', 'pv-bar-purple', 'pv-bar-orange', 'pv-bar-teal']

# ── Status label → CSS modifier ───────────────────────────────────────────────
_STATUS_CLASS = {
    'strong':   'strong',
    'good':     'strong',
    'moderate': 'moderate',
    'warning':  'moderate',
    'weak':     'weak',
    'bad':      'weak',
    'neutral':  'neutral',
    'stable':   'neutral',
    'normal':   'neutral',
}

# ── DML / DDL keywords that must never appear in admin SQL ────────────────────
_BLOCKED_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|EXECUTE)\b',
    re.IGNORECASE,
)


class DashboardPageSection(models.Model):
    _name        = 'dashboard.page.section'
    _description = 'Dashboard Page Section'
    _order       = 'sequence asc, id asc'

    # ── Placement ─────────────────────────────────────────────────────────────
    page_id   = fields.Many2one(
        'dashboard.page', required=True, ondelete='cascade', string='Page')
    tab_id    = fields.Many2one(
        'dashboard.page.tab', string='Tab', ondelete='set null',
        domain="[('page_id', '=', page_id)]",
        help='Show only on this tab (below the tab bar). '
             'Leave empty to show above all tabs (between filters and tabs).')
    sequence  = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    # ── Identity ──────────────────────────────────────────────────────────────
    name         = fields.Char(required=True, string='Section Title')
    icon         = fields.Char(
        default='fa-star-o', string='Icon (FA class)',
        help='Font Awesome icon class, e.g. fa-star-o, fa-trophy, fa-bar-chart')
    action_label = fields.Char(
        string='Badge Label',
        help='Static pill/badge displayed at the top-right of the section header.\n'
             'Example: "vs State HHAs" or "All States"')
    section_type = fields.Selection([
        ('comparison_bar',    'Comparison Bar (KPI cards + progress bars)'),
        ('leaderboard_table', 'Leaderboard Table (ranked rows)'),
    ], required=True, default='comparison_bar', string='Section Type')

    # ── Scoping Dropdown ──────────────────────────────────────────────────
    scope_mode = fields.Selection([
        ('none',        'No Dropdown'),
        ('dependent',   'Linked to Page Filter'),
        ('independent', 'Custom Schema Source'),
    ], default='none', string='Scope Mode',
        help='Controls the section-level scoping dropdown.\n'
             'Dependent: mirrors a page filter\'s options.\n'
             'Independent: custom dropdown from a schema source.')

    scope_filter_id = fields.Many2one(
        'dashboard.page.filter', string='Linked Filter',
        ondelete='set null', domain="[('page_id', '=', page_id)]",
        help='Dropdown mirrors this page filter\'s options and current value.')

    scope_schema_source_id = fields.Many2one(
        'dashboard.schema.source', string='Scope Source',
        ondelete='set null',
        help='MV/table to query for custom dropdown options.')
    scope_value_column = fields.Char(string='Value Column',
        help='Column for option value (e.g., hha_state)')
    scope_label_column = fields.Char(string='Label Column',
        help='Column for option label. Falls back to value column if blank.')
    scope_param_name = fields.Char(string='SQL Param Name',
        help='Param name used in section SQL as %%(param)s for the scoped value.')

    scope_label = fields.Char(string='Dropdown Label',
        help='Label shown on the dropdown (e.g., "State").')
    scope_default_value = fields.Char(string='Default Scope',
        help='Initial dropdown value. Blank = use filter value (dependent) or first option.')

    # ── Row Limit ───────────────────────────────────────────────────────
    max_rows = fields.Integer(default=0, string='Max Rows',
        help='Limit displayed rows (0 = show all). "You" row is always shown.')

    # ── Annotations ────────────────────────────────────────────────────────
    subtitle    = fields.Char(string='Subtitle',
        help='Displayed below the section title')
    description = fields.Text(string='Description',
        help='Explanatory text shown below the section header')
    footnote    = fields.Text(string='Footnote',
        help='Displayed at the bottom of the section')

    # ── SQL Query ─────────────────────────────────────────────────────────────
    schema_source_id = fields.Many2one(
        'dashboard.schema.source', string='Schema Source',
        ondelete='set null',
        help='The materialized view or table this section queries. '
             'Required when using {where_clause} auto-filter.')
    where_clause_exclude = fields.Char(
        string='Exclude from {where_clause}',
        help='Comma-separated param names to exclude from auto-generated '
             'WHERE clause (e.g. "year" for YoY comparison).')
    query_sql = fields.Text(
        string='SQL Query',
        help='SELECT only. Use %(param_name)s for portal filter values.\n'
             'Use {where_clause} to auto-generate WHERE from page filters.\n'
             'Available params: any active page filter field_name.\n\n'
             'comparison_bar: one row per card.\n'
             'leaderboard_table: one row per entity, ordered by rank.')

    # ── Comparison Bar column mapping ─────────────────────────────────────────
    cb_label_col = fields.Char(
        string='Label Column',
        help='SQL column for the card title (e.g. metric_name)')
    cb_value_col = fields.Char(
        string='Value Column',
        help='SQL column for the numeric value — also used to set bar width.\n'
             'Values 0-100 are treated as percentages.')
    cb_status_col = fields.Char(
        string='Status Column',
        help='SQL column for the status badge: Strong / Moderate / Weak / Neutral')
    cb_desc_col = fields.Char(
        string='Description Column',
        help='SQL column for the small description text at the bottom of the card')
    cb_sublabel_col = fields.Char(
        string='Sub-label Column',
        help='SQL column for optional small text shown next to the value (e.g. "Primary")')

    # ── Leaderboard Table column mapping ──────────────────────────────────────
    lt_rank_col = fields.Char(
        string='Rank Column',
        help='SQL column for the rank number shown in the # column')
    lt_name_col = fields.Char(
        string='Name Column',
        help='SQL column for the primary entity name — gets bold name-cell styling')
    lt_sub_name_cols = fields.Char(
        string='Sub-name Columns',
        help='Comma-separated SQL columns shown as smaller text below the name\n'
             'Multiple values are joined with " · "')
    lt_display_cols = fields.Char(
        string='Metric Columns',
        help='Comma-separated SQL column names for the numeric metric cells')
    lt_display_labels = fields.Char(
        string='Column Headers',
        help='Comma-separated display labels for metric columns.\n'
             'Falls back to column names when blank.')
    lt_you_col = fields.Char(
        string='You Marker Column',
        help='SQL column returning 1 (or truthy) for the row that should be highlighted\n'
             'as the current user\'s entity (shown with "You" badge + highlighted row)')
    lt_color_col = fields.Char(
        string='Color-coded Column',
        help='SQL column whose value is color-coded green/amber/red.\n'
             'Typically the last metric column (e.g. timely_access).')
    lt_good_threshold = fields.Float(
        string='Good Threshold', default=70,
        help='Values ≥ this → green (pv-val-good)')
    lt_warn_threshold = fields.Float(
        string='Warn Threshold', default=50,
        help='Values ≥ this but < Good → amber (pv-val-warn); below → red (pv-val-bad)')

    @api.model
    def default_get(self, fields_list):
        """New sections always land after the last section on the same page."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            page_id = self.env.context.get('default_page_id')
            domain = [('page_id', '=', page_id)] if page_id else []
            last = self.search(domain, order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res

    # =========================================================================
    # Scope options (independent mode)
    # =========================================================================

    def get_scope_options(self):
        """Return [{value, label}] for independent-mode scoping dropdown."""
        self.ensure_one()
        if self.scope_mode != 'independent' or not self.scope_schema_source_id:
            return []
        val_col = (self.scope_value_column or '').strip()
        if not val_col:
            return []
        lbl_col = (self.scope_label_column or '').strip() or val_col
        table = self.scope_schema_source_id.source_name
        if not table:
            return []
        sql = f'SELECT DISTINCT {val_col}'
        if lbl_col != val_col:
            sql += f', {lbl_col}'
        sql += f' FROM {table} WHERE {val_col} IS NOT NULL ORDER BY 1'
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(sql)
                rows = self.env.cr.fetchall()
        except Exception as exc:
            _logger.warning('get_scope_options error section=%s: %s', self.id, exc)
            return []
        if lbl_col != val_col:
            return [{'value': str(r[0]), 'label': str(r[1] or r[0])} for r in rows]
        return [{'value': str(r[0]), 'label': str(r[0])} for r in rows]

    # =========================================================================
    # Public entry point — called by controller
    # =========================================================================

    def get_portal_data(self, portal_ctx, scope_overrides=None):
        """Execute the SQL query and return a render-ready dict.

        portal_ctx keys:
            sql_params — dict{field_name: value} for SQL %(x)s params
        scope_overrides:
            Optional dict {param_name: value} for section-level scoping.
            Merged into sql_params before execution (overrides page filters
            for this section only).
        """
        self.ensure_one()
        try:
            sql_params = dict(portal_ctx.get('sql_params', {}))
            if scope_overrides:
                sql_params.update(scope_overrides)
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
                effective_params = dict(sql_params)
                effective_params.update(built_params)
                effective_params['_where_sql'] = where_sql
                cols, rows = self._execute_sql(effective_params)
            else:
                cols, rows = self._execute_sql(sql_params)
            if self.section_type == 'comparison_bar':
                data = self._build_comparison_bar(cols, rows)
                return self._apply_row_limit(data)
            elif self.section_type == 'leaderboard_table':
                data = self._build_leaderboard(cols, rows)
                return self._apply_row_limit(data)
        except Exception as exc:
            _logger.warning(
                'dashboard.page.section %s get_portal_data error: %s', self.id, exc)
            return {'error': str(exc)}
        return {}

    # =========================================================================
    # SQL execution (same pattern as dashboard.widget)
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

        sql_clean = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        sql_clean = re.sub(r'--[^\n]*', ' ', sql_clean)
        first_word = sql_clean.strip().split()[0].upper() if sql_clean.strip() else ''

        if first_word not in ('SELECT', 'WITH'):
            raise ValueError('Only SELECT or WITH queries are allowed.')
        if _BLOCKED_KEYWORDS.search(sql_clean):
            raise ValueError('SQL contains a disallowed keyword (DML/DDL not permitted).')

        # Convert tuple/list params to comma-separated strings.
        # portal.py converts multiselect values to tuples for psycopg2 ANY(),
        # but section SQL uses string_to_array(%(param)s, ',') expecting CSV.
        safe_params = {}
        for k, v in params.items():
            if isinstance(v, (list, tuple)):
                safe_params[k] = ','.join(str(item) for item in v)
            else:
                safe_params[k] = v
        # Fill missing keys with None to avoid KeyError
        for m in re.finditer(r'%\(([^)]+)\)s', sql):
            if m.group(1) not in safe_params:
                safe_params[m.group(1)] = None

        # Use a savepoint so a failed query doesn't poison the whole transaction
        with self.env.cr.savepoint():
            self.env.cr.execute(sql, safe_params)
            cols = [desc[0] for desc in self.env.cr.description] if self.env.cr.description else []
            rows = self.env.cr.fetchall()
            return cols, rows

    # =========================================================================
    # Comparison Bar builder
    # =========================================================================

    def _build_comparison_bar(self, cols, rows):
        """Return {'cards': [...]} for comparison_bar section type."""
        col_idx = {c: i for i, c in enumerate(cols)}

        def col_val(row, name):
            idx = col_idx.get(name)
            return row[idx] if idx is not None else None

        label_col    = (self.cb_label_col    or '').strip() or (cols[0] if cols else '')
        value_col    = (self.cb_value_col    or '').strip() or (cols[1] if len(cols) > 1 else '')
        status_col   = (self.cb_status_col   or '').strip()
        desc_col     = (self.cb_desc_col     or '').strip()
        sublabel_col = (self.cb_sublabel_col or '').strip()

        cards = []
        for i, row in enumerate(rows):
            # Value / bar width
            raw_val = col_val(row, value_col)
            try:
                fval = float(raw_val or 0)
            except (TypeError, ValueError):
                fval = 0.0
            bar_pct = max(0.0, min(100.0, fval))   # clamp 0-100
            val_str = f'{round(fval):.0f}%' if (0 <= fval <= 100) else str(round(fval, 1))

            # Status badge
            raw_status = str(col_val(row, status_col) or '') if status_col else ''
            status_key = raw_status.lower().strip()
            status_cls = _STATUS_CLASS.get(status_key, 'neutral')

            cards.append({
                'label':        str(col_val(row, label_col) or '') if label_col else '',
                'value':        val_str,
                'bar_pct':      bar_pct,
                'status':       raw_status,
                'status_class': status_cls,
                'bar_color':    _BAR_COLORS[i % len(_BAR_COLORS)],
                'desc':         str(col_val(row, desc_col) or '') if desc_col else '',
                'sublabel':     str(col_val(row, sublabel_col) or '') if sublabel_col else '',
            })

        return {'cards': cards}

    # =========================================================================
    # Leaderboard Table builder
    # =========================================================================

    def _build_leaderboard(self, cols, rows):
        """Return {'name_header', 'headers', 'rows'} for leaderboard_table section type."""
        col_idx = {c: i for i, c in enumerate(cols)}

        def col_val(row, name):
            idx = col_idx.get(name)
            return row[idx] if idx is not None else None

        rank_col     = (self.lt_rank_col     or '').strip()
        name_col     = (self.lt_name_col     or '').strip()
        you_col      = (self.lt_you_col      or '').strip()
        color_col    = (self.lt_color_col    or '').strip()
        good_thr     = float(self.lt_good_threshold or 70)
        warn_thr     = float(self.lt_warn_threshold or 50)

        # Sub-name columns
        sub_name_col_list = [c.strip() for c in
                             (self.lt_sub_name_cols or '').split(',') if c.strip()]

        # Metric columns + headers
        metric_col_list = [c.strip() for c in
                           (self.lt_display_cols or '').split(',') if c.strip()]
        label_list = [l.strip() for l in
                      (self.lt_display_labels or '').split(',') if l.strip()]
        headers = []
        for j, mc in enumerate(metric_col_list):
            headers.append(label_list[j] if j < len(label_list) else mc)

        name_header = label_list[0] if (label_list and not metric_col_list) else (
            label_list[len(metric_col_list)] if len(label_list) > len(metric_col_list) else 'HHA Name')

        table_rows = []
        for row in rows:
            # Rank
            rank = str(col_val(row, rank_col) or '') if rank_col else ''

            # Name + sub-name
            name     = str(col_val(row, name_col) or '') if name_col else ''
            sub_parts = [str(col_val(row, sc) or '') for sc in sub_name_col_list]
            sub_name = ' · '.join(p for p in sub_parts if p)

            # Is this the "You" row?
            is_you = False
            if you_col:
                you_raw = col_val(row, you_col)
                is_you  = bool(you_raw) and str(you_raw) not in ('0', 'false', 'False', '')

            # Metric cells
            metrics = []
            for j, mc in enumerate(metric_col_list):
                raw = col_val(row, mc)
                val_str = str(raw) if raw is not None else ''

                # Color code only the designated color column
                color_class = ''
                if mc == color_col:
                    try:
                        nval = float(raw or 0)
                        if nval >= good_thr:
                            color_class = 'pv-val-good'
                        elif nval >= warn_thr:
                            color_class = 'pv-val-warn'
                        else:
                            color_class = 'pv-val-bad'
                    except (TypeError, ValueError):
                        pass

                metrics.append({'val': val_str, 'color_class': color_class})

            table_rows.append({
                'rank':     rank,
                'name':     name,
                'sub_name': sub_name,
                'metrics':  metrics,
                'is_you':   is_you,
            })

        return {
            'name_header': name_header,
            'headers':     headers,
            'rows':        table_rows,
        }

    # =========================================================================
    # Row limit with "You" pinning
    # =========================================================================

    def _apply_row_limit(self, data):
        """Truncate rows/cards to max_rows, always keeping the 'You' row."""
        if not self.max_rows or self.max_rows <= 0:
            return data

        if self.section_type == 'comparison_bar':
            cards = data.get('cards', [])
            if len(cards) > self.max_rows:
                data['cards'] = cards[:self.max_rows]
            return data

        if self.section_type == 'leaderboard_table':
            all_rows = data.get('rows', [])
            if len(all_rows) <= self.max_rows:
                return data
            limited = []
            you_row = None
            for row in all_rows:
                if row.get('is_you'):
                    you_row = row
                if len(limited) < self.max_rows:
                    if row.get('is_you'):
                        you_row = None  # already in the limited set
                    limited.append(row)
            # Pin "You" row at the bottom if it was beyond the limit
            if you_row:
                you_row['pinned'] = True
                limited.append(you_row)
            data['rows'] = limited
            return data

        return data
