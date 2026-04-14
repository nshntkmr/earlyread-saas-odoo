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


class DashboardPageBadge(models.Model):
    _name = 'dashboard.page.badge'
    _description = 'Page Header Badge'
    _order = 'sequence asc, id asc'

    # ── Placement ─────────────────────────────────────────────────────────────
    page_id = fields.Many2one(
        'dashboard.page', required=True, ondelete='cascade', string='Page')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(required=True, string='Label',
        help='Internal name for this badge (not displayed on portal)')

    # ── Icon ──────────────────────────────────────────────────────────────────
    icon = fields.Char(
        string='Icon (FA class)', default='fa-info-circle',
        help='Font Awesome icon class, e.g. fa-building, fa-phone, fa-user')

    # ── Value Source (SQL) ────────────────────────────────────────────────────
    query_sql = fields.Text(
        string='SQL Query', required=True,
        help='Must return a single column "value" with one row.\n'
             'Use %(param_name)s for filter values.\n'
             'Use {where_clause} to auto-generate WHERE from page filters.\n'
             'Example: SELECT COUNT(*) || \' hospitals\' as value '
             'FROM mv_hospitals WHERE {where_clause}')
    schema_source_id = fields.Many2one(
        'dashboard.schema.source', string='Schema Source',
        ondelete='set null',
        help='The materialized view or table this badge queries.\n'
             'Required when using {where_clause} auto-filter.')
    where_clause_exclude = fields.Char(
        string='Exclude from {where_clause}',
        help='Comma-separated param names to exclude from auto-generated '
             'WHERE clause (e.g. "year" for cross-year counts).')

    # ── Styling ───────────────────────────────────────────────────────────────
    font_size = fields.Integer(
        default=0, string='Font Size (px)',
        help='0 = use default (13px)')
    text_color = fields.Char(
        string='Text Color', default='',
        help='Hex color for value text. Empty = default gray (#6b7280)')
    icon_color = fields.Char(
        string='Icon Color', default='',
        help='Hex color for icon. Empty = default (#9ca3af)')
    is_link = fields.Boolean(
        string='Render as Link', default=False,
        help='If true, renders value as a clickable tel: link (for phone numbers)')

    # ── Validation ────────────────────────────────────────────────────────────

    @api.constrains('query_sql')
    def _check_sql_safe(self):
        for rec in self:
            sql = rec.query_sql or ''
            if _BLOCKED_KEYWORDS.search(sql):
                raise models.ValidationError(
                    'Badge SQL must be SELECT only. '
                    'DML/DDL keywords are not allowed.')

    @api.constrains('query_sql', 'schema_source_id')
    def _check_where_clause_requires_source(self):
        for rec in self:
            if rec.query_sql and '{where_clause}' in rec.query_sql and not rec.schema_source_id:
                raise models.ValidationError(
                    'A Schema Source is required when using {where_clause} in SQL.')

    # ── SQL Execution ─────────────────────────────────────────────────────────

    def execute_badge_sql(self, portal_ctx):
        """Execute this badge's SQL and return the scalar value string.

        portal_ctx keys (same as widget pipeline):
            sql_params       — dict{param_name: value}
            _filter_defs     — list of filter definition dicts
        Returns: str value or empty string on error/no data.
        """
        self.ensure_one()
        sql = (self.query_sql or '').strip()
        if not sql:
            return ''

        sql_params = portal_ctx.get('sql_params', {})

        try:
            # Handle {where_clause} substitution (same logic as widgets)
            if '{where_clause}' in sql:
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
                sql = sql.replace('{where_clause}', where_sql or '1=1')
                exec_params = effective_params
            else:
                exec_params = sql_params

            # Process [[...]] optional clauses (same as widgets)
            if '[[' in sql:
                from ..utils.filter_builder import resolve_optional_clauses
                sql = resolve_optional_clauses(sql, exec_params)

            # Safety check — SELECT/WITH only
            sql_clean = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
            sql_clean = re.sub(r'--[^\n]*', ' ', sql_clean)
            first_word = sql_clean.strip().split()[0].upper() if sql_clean.strip() else ''
            if first_word not in ('SELECT', 'WITH'):
                _logger.warning(
                    'Badge %s (%s): SQL must start with SELECT or WITH, got %s',
                    self.id, self.name, first_word)
                return ''

            self.env.cr.execute(sql, exec_params)
            row = self.env.cr.dictfetchone()
            if row:
                return str(row.get('value', '') or '')
            return ''

        except Exception as exc:
            _logger.warning(
                'Badge %s (%s) SQL execution error: %s', self.id, self.name, exc)
            return ''
