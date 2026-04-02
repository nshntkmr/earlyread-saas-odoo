# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── Mapping from PostgreSQL data_type → simplified type ──────────────────────
_PG_TYPE_MAP = {
    'character varying': 'text',
    'character':         'text',
    'varchar':           'text',
    'text':              'text',
    'name':              'text',
    'uuid':              'text',
    'integer':           'integer',
    'bigint':            'integer',
    'smallint':          'integer',
    'int':               'integer',
    'int2':              'integer',
    'int4':              'integer',
    'int8':              'integer',
    'serial':            'integer',
    'bigserial':         'integer',
    'numeric':           'float',
    'decimal':           'float',
    'real':              'float',
    'double precision':  'float',
    'float':             'float',
    'float4':            'float',
    'float8':            'float',
    'money':             'float',
    'date':              'date',
    'timestamp':         'date',
    'timestamp without time zone': 'date',
    'timestamp with time zone':    'date',
    'timestamptz':       'date',
    'boolean':           'boolean',
    'bool':              'boolean',
}

# ── Measure vs dimension defaults based on type ─────────────────────────────
_MEASURE_TYPES  = {'integer', 'float'}
_DIMENSION_TYPES = {'text', 'date'}

# ── Column role auto-detection from naming conventions ──────────────────────
_RATE_SUFFIXES = ('_pct', '_rate', '_ratio')
_COUNT_SUFFIXES = ('_count',)
_IDENTIFIER_NAMES = {'id', 'hha_ccn', 'hha_npi', 'source_ccn', 'source_npi'}


def _auto_detect_column_role(col_name, data_type):
    """Auto-detect column_role and never_avg from naming conventions.

    Returns (column_role, never_avg) tuple.
    Admin can override any auto-detection in the UI.
    """
    lower = col_name.lower()

    # Pre-computed rate: never AVG these
    if any(lower.endswith(s) for s in _RATE_SUFFIXES):
        return 'pre_computed_rate', True

    # Columns starting with 'avg_' are pre-computed averages — never AVG
    if lower.startswith('avg_'):
        return 'pre_computed_rate', True

    # Count columns are typically ratio numerators
    if any(lower.endswith(s) for s in _COUNT_SUFFIXES):
        return 'ratio_numerator', False

    # Identifiers
    if lower in _IDENTIFIER_NAMES:
        return 'identifier', False

    # Numeric columns that are likely additive measures
    if data_type in _MEASURE_TYPES:
        # Common additive measure patterns
        if lower.startswith('total_') or lower.startswith('sum_'):
            return 'additive_measure', False
        if lower in ('episode_count', 'unique_patients'):
            return 'additive_measure', False
        # Default for numeric: additive_measure (safe to SUM)
        return 'additive_measure', False

    # Text/date columns are dimensions
    if data_type in _DIMENSION_TYPES:
        return 'dimension', False

    return None, False


class DashboardSchemaSource(models.Model):
    _name = 'dashboard.schema.source'
    _description = 'Schema Source (Database Table)'
    _order = 'name asc'

    name         = fields.Char(required=True, string='Display Name')
    table_name   = fields.Char(required=True, string='Table Name')
    table_alias  = fields.Char(string='SQL Alias', size=5)
    description  = fields.Text(string='Description')
    is_active    = fields.Boolean(default=True)
    column_ids   = fields.One2many(
        'dashboard.schema.column', 'source_id', string='Columns')
    relation_ids = fields.One2many(
        'dashboard.schema.relation', 'source_id', string='Outgoing Relations')
    column_count = fields.Integer(
        compute='_compute_column_count', string='# Columns', store=True)

    _sql_constraints = [
        ('table_name_uniq', 'unique(table_name)',
         'A schema source already exists for this table.'),
    ]

    @api.depends('column_ids')
    def _compute_column_count(self):
        for rec in self:
            rec.column_count = len(rec.column_ids)

    # ── Auto-discover materialized views from pg_catalog ──────────────────────

    @api.model
    def action_sync_materialized_views(self):
        """Discover all materialized views in the public schema and create
        schema source records for any that don't already exist.  Also runs
        column discovery on newly created sources.

        Can be called as a button action or programmatically.
        """
        self.env.cr.execute("""
            SELECT c.relname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relkind = 'm'
             ORDER BY c.relname
        """)
        mv_names = [row[0] for row in self.env.cr.fetchall()]
        if not mv_names:
            _logger.info('No materialized views found in public schema.')
            return

        # Existing table_names already registered
        existing = set(
            self.sudo().search([]).mapped('table_name')
        )

        created = 0
        for mv_name in mv_names:
            if mv_name in existing:
                continue
            # Auto-generate display name: mv_hha_kpi_summary → Mv Hha Kpi Summary
            display = mv_name.replace('_', ' ').title()
            source = self.sudo().create({
                'name': display,
                'table_name': mv_name,
                'description': f'Auto-discovered materialized view: {mv_name}',
            })
            # Auto-discover columns for the new source
            try:
                source.action_discover_columns()
            except Exception as exc:
                _logger.warning(
                    'Failed to discover columns for MV %s: %s', mv_name, exc)
            created += 1

        _logger.info(
            'Schema source sync: %d new MVs registered (%d already existed)',
            created, len(existing))

        if created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Materialized Views Synced',
                    'message': f'{created} new materialized view(s) registered '
                               f'with columns discovered.',
                    'type': 'success',
                    'sticky': False,
                },
            }

    # ── Auto-discover columns from pg_catalog ─────────────────────────────────
    def action_discover_columns(self):
        """Button action: reads columns for self.table_name from pg_catalog.
        Supports regular tables, views, AND materialized views.
        Creates dashboard.schema.column records for each column found.
        Skips columns that already exist (matched by column_name)."""
        self.ensure_one()
        if not self.table_name:
            raise UserError("Table name is required to discover columns.")

        # Verify the table/view/matview exists in pg_class
        # relkind: 'r' = table, 'v' = view, 'm' = materialized view
        self.env.cr.execute("""
            SELECT c.relkind
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relname = %s
               AND c.relkind IN ('r', 'v', 'm')
        """, (self.table_name,))
        result = self.env.cr.fetchone()
        if not result:
            raise UserError(
                f"Table/view '{self.table_name}' does not exist in the public schema.")

        relkind_label = {'r': 'table', 'v': 'view', 'm': 'materialized view'}
        _logger.info("Discovering columns for %s '%s'",
                     relkind_label.get(result[0], 'relation'), self.table_name)

        # Read columns from pg_attribute + pg_type (works for tables, views, matviews)
        self.env.cr.execute("""
            SELECT a.attname                       AS column_name,
                   format_type(a.atttypid, a.atttypmod) AS data_type,
                   NOT a.attnotnull                AS is_nullable
              FROM pg_attribute a
              JOIN pg_class c ON c.oid = a.attrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public'
               AND c.relname = %s
               AND a.attnum > 0
               AND NOT a.attisdropped
             ORDER BY a.attnum
        """, (self.table_name,))
        rows = self.env.cr.fetchall()

        if not rows:
            raise UserError(
                f"No columns found for table '{self.table_name}'.")

        # Existing column names for this source
        existing = set(self.column_ids.mapped('column_name'))
        ColumnModel = self.env['dashboard.schema.column']
        created = 0

        for col_name, pg_type, _nullable in rows:
            if col_name in existing:
                continue

            # Map PostgreSQL type to simplified type
            # format_type() may return e.g. 'character varying(255)' or 'numeric(10,2)'
            # so try exact match first, then match the base type (before parentheses)
            pg_lower = pg_type.lower()
            base_type = pg_lower.split('(')[0].strip()
            data_type = _PG_TYPE_MAP.get(pg_lower) or _PG_TYPE_MAP.get(base_type, 'text')

            # Auto-generate display name: hha_state → Hha State
            display_name = col_name.replace('_', ' ').title()

            # Auto-detect column_role from naming conventions
            column_role, never_avg = _auto_detect_column_role(col_name, data_type)

            ColumnModel.create({
                'source_id': self.id,
                'column_name': col_name,
                'display_name': display_name,
                'data_type': data_type,
                'is_measure': data_type in _MEASURE_TYPES,
                'is_dimension': data_type in _DIMENSION_TYPES,
                'is_filterable': data_type in _DIMENSION_TYPES,
                'column_role': column_role,
                'never_avg': never_avg,
            })
            created += 1

        _logger.info(
            "Schema source '%s': discovered %d new columns (%d already existed)",
            self.table_name, created, len(existing))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Columns Discovered',
                'message': f'{created} new columns discovered, '
                           f'{len(existing)} already existed.',
                'type': 'success',
                'sticky': False,
            },
        }


class DashboardSchemaColumn(models.Model):
    _name = 'dashboard.schema.column'
    _description = 'Schema Column'
    _rec_name = 'column_name'
    _order = 'source_id, column_name'

    source_id    = fields.Many2one(
        'dashboard.schema.source', required=True, ondelete='cascade',
        string='Schema Source')
    column_name  = fields.Char(required=True, string='Column Name')
    display_name = fields.Char(required=True, string='Display Name')
    data_type    = fields.Selection([
        ('text',    'Text'),
        ('integer', 'Integer'),
        ('float',   'Float / Decimal'),
        ('date',    'Date / Timestamp'),
        ('boolean', 'Boolean'),
    ], required=True, default='text', string='Data Type')
    is_measure   = fields.Boolean(
        default=False,
        help='Can be used as Y-axis value (aggregated). Auto-set for int/float.')
    is_dimension = fields.Boolean(
        default=False,
        help='Can be used as X-axis / group-by. Auto-set for text/date.')
    is_filterable = fields.Boolean(
        default=False,
        help='Available in WHERE conditions.')

    # ── Column Intelligence (Layer 2) ────────────────────────────────────
    column_role = fields.Selection([
        ('dimension', 'Dimension'),
        ('additive_measure', 'Additive Measure (safe to SUM)'),
        ('ratio_numerator', 'Ratio Numerator'),
        ('ratio_denominator', 'Ratio Denominator'),
        ('pre_computed_rate', 'Pre-computed Rate (NEVER AVG)'),
        ('weight', 'Weight Column (for weighted avg)'),
        ('identifier', 'Identifier (CCN, NPI, etc.)'),
    ], string='Column Role',
       help='Semantic role determines how the AI uses this column in SQL. '
            'Pre-computed rates trigger "NEVER AVG" warnings. '
            'Ratio numerator/denominator pairs enable correct weighted formulas.')
    paired_column_id = fields.Many2one(
        'dashboard.schema.column',
        string='Paired Column',
        domain="[('source_id', '=', source_id)]",
        help='For ratio_numerator: its denominator column. '
             'For pre_computed_rate: the numerator count column. '
             'Example: timely_access_pct → ip_timely_count.')
    never_avg = fields.Boolean(
        string='Never AVG',
        default=False,
        help='When True, AI is told to NEVER use AVG() on this column. '
             'Auto-set when column_role is pre_computed_rate.')

    # ── Domain Context (Layer 3) ─────────────────────────────────────────
    description = fields.Text(
        string='Business Description',
        help='What this column means in business terms. '
             'Examples: "IP referrals seen within 48 hours", '
             '"Total home health admissions for the period"')
    domain_notes = fields.Text(
        string='Domain Notes',
        help='Special rules or caveats for the AI. '
             'Examples: "Always $0 for MA records", '
             '"FFS-only metric — filter to ffs_ma=FFS", '
             '"Exclude hha_ccn starting with 9 (test data)"')

    _sql_constraints = [
        ('source_column_uniq', 'unique(source_id, column_name)',
         'Column name must be unique within a schema source.'),
    ]

    @api.onchange('column_role')
    def _onchange_column_role(self):
        """Auto-set never_avg when role is pre_computed_rate."""
        if self.column_role == 'pre_computed_rate':
            self.never_avg = True


class DashboardSchemaRelation(models.Model):
    _name = 'dashboard.schema.relation'
    _description = 'Schema Relation (JOIN)'
    _order = 'source_id, target_source_id'

    name             = fields.Char(string='Label')
    source_id        = fields.Many2one(
        'dashboard.schema.source', required=True, ondelete='cascade',
        string='From Table')
    target_source_id = fields.Many2one(
        'dashboard.schema.source', required=True, ondelete='cascade',
        string='To Table')
    join_type        = fields.Selection([
        ('inner', 'INNER JOIN'),
        ('left',  'LEFT JOIN'),
        ('right', 'RIGHT JOIN'),
    ], required=True, default='left', string='Join Type')
    source_column    = fields.Char(required=True, string='From Column')
    target_column    = fields.Char(required=True, string='To Column')

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate name if not provided."""
        for vals in vals_list:
            if not vals.get('name'):
                src = self.env['dashboard.schema.source'].browse(
                    vals.get('source_id'))
                tgt = self.env['dashboard.schema.source'].browse(
                    vals.get('target_source_id'))
                if src and tgt:
                    vals['name'] = f"{src.name} → {tgt.name}"
        return super().create(vals_list)
