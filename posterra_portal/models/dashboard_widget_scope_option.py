# -*- coding: utf-8 -*-

import json
import logging
import re

from odoo import api, fields, models

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

            self.env.cr.execute(sql, safe_params)
            cols = [d[0] for d in self.env.cr.description]
            rows = self.env.cr.fetchall()

            # Format result using the parent widget's chart type
            return self.widget_id._format_scope_result(cols, rows)

        except Exception as exc:
            _logger.warning(
                'Scope option %s (%s) SQL execution error: %s',
                self.id, self.label, exc)
            return {'error': str(exc)}
