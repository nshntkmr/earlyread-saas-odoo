# -*- coding: utf-8 -*-
"""Projections ("Mark Projected Compliant") — Projection Type, cycle records
and the append-only audit trail.

Design (spec v16, accepted 2026-09-08):

* ``dashboard.projection.config`` — one **Projection Type** per app and
  purpose (e.g. ``quality_compliance``). It names the source Schema Source,
  the identity columns, the snapshot (month) column, how "compliant" and
  "eligible" are read, who may act, the popover fields and the card labels
  and colours. It also **renders** the SQL an admin pastes into the database
  by hand: the identity-key expression, the ClickHouse mirror DDL and the
  combined reporting view (§4.1). Odoo never executes DDL on ClickHouse.
* ``dashboard.projection`` — one record per **cycle**
  ``(type, identity, cycle_no)``: a saved expectation that starts with Mark,
  may gain Re-project attempts and ends when the data confirms compliance
  (never stored — computed from the source rows) or when a user undoes it.
  Records are never deleted.
* ``dashboard.projection.event`` — append-only history and publisher outbox.
  Every successful change keeps the acting user, the time and the previous /
  new values. Rows cannot be edited (except the outbox bookkeeping) or
  deleted.

Existing behaviour is unchanged until an admin creates a Projection Type
and a drawer carries the ``card.projection`` block.
"""

import json
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..utils import projection_identity as pid
from ..utils.sql_idents import IDENT_RE, TABLE_RE, quote_table

_logger = logging.getLogger(__name__)

_KEY_RE = re.compile(r'^[a-z][a-z0-9_]{1,60}$')
_IDENTITY_TYPES = ('text', 'integer')

PROJECTION_STATES = [('active', 'Active'), ('undone', 'Undone')]
PUBLISH_STATES = [
    ('none', 'Not required'), ('pending', 'Pending'), ('published', 'Published'),
    ('failed', 'Failed'), ('dead', 'Dead'),
]
EVENT_ACTIONS = [
    ('mark', 'Marked'), ('edit', 'Edited'), ('reproject', 'Re-projected'),
    ('undo', 'Undone'), ('admin_undo', 'Undone (admin)'),
    ('admin_void', 'Voided'), ('republish', 'Republished'),
]
# Actions shown on the card's "latest changes" lines; technical events
# (publisher retries / Republish) are never user-facing.
USER_FACING_ACTIONS = ('mark', 'edit', 'reproject', 'undo', 'admin_undo', 'admin_void')

_DEFAULT_STYLES = {
    'projected': ('Projected compliant', '#2563eb'),
    'missed': ('Not matched in {month} data', '#d97706'),
    'matched': ('Matched in {month} data', '#16a34a'),
    'ineligible': ('Not eligible', '#9ca3af'),
}


def _months_to_text(months):
    return ','.join(m for m in months if m)


def _months_from_text(text):
    return [m for m in (text or '').split(',') if m]


class DashboardProjectionConfig(models.Model):
    _name = 'dashboard.projection.config'
    _description = 'Projection Type'
    _order = 'app_id, key'

    name = fields.Char(required=True)
    app_id = fields.Many2one(
        'saas.app', string='App', required=True, ondelete='restrict', index=True)
    app_key = fields.Char(related='app_id.app_key', readonly=True)
    key = fields.Char(
        required=True,
        help='Portable capability key, unique per app (e.g. quality_compliance). '
             'Drawer blocks and templates reference it.')
    is_active = fields.Boolean(default=True)

    # ── Source and columns ────────────────────────────────────────────────
    source_id = fields.Many2one(
        'dashboard.schema.source', string='Source', required=True,
        ondelete='restrict',
        help='The registered source table the projections are about. Must be '
             'active and available to the app.')
    engine = fields.Char(compute='_compute_engine', store=False)
    identity_column_ids = fields.One2many(
        'dashboard.projection.config.identity', 'config_id',
        string='Identity Columns',
        help='Ordered columns that identify what a projection is about '
             '(e.g. HUM_ID, MEASURE_CAT, MEASUREMENT_YEAR). All required; '
             'text or integer only; frozen once projections exist.')
    snapshot_column_id = fields.Many2one(
        'dashboard.schema.column', string='Snapshot (Month) Column',
        required=True, ondelete='restrict',
        help='The monthly row key (e.g. YEAR_MONTH). Not part of the identity. '
             'Values must sort chronologically as text (YYYYMM).')
    status_column_id = fields.Many2one(
        'dashboard.schema.column', string='Status Column', required=True,
        ondelete='restrict')
    status_true_values = fields.Char(
        string='Compliant Values', default='1', required=True,
        help='Comma-separated values meaning "compliant" (after trimming).')
    eligibility_column_id = fields.Many2one(
        'dashboard.schema.column', string='Eligibility Column', ondelete='restrict')
    eligible_values = fields.Char(
        string='Eligible Values', default='1',
        help='Comma-separated values meaning "eligible". Ineligible rows are '
             'excluded from denominators, projected uplift and match detection.')

    # ── Permissions ───────────────────────────────────────────────────────
    scope_mode = fields.Selection(
        [('app', 'Any app member'), ('provider', "The user's providers")],
        default='app', required=True,
        help='provider: the source scope column must match one of the '
             "user's providers (field named in Provider Field).")
    scope_column_id = fields.Many2one(
        'dashboard.schema.column', string='Scope Column', ondelete='restrict')
    scope_provider_field = fields.Char(
        string='Provider Field', help='Field of hha.provider compared with the '
                                       'scope column (e.g. hha_ccn).')
    allowed_group_ids = fields.Many2many(
        'res.groups', 'dashboard_projection_config_group_rel', 'config_id',
        'group_id', string='Allowed Groups',
        help='Empty = any member of the app may mark / edit / re-project / undo.')
    undo_policy = fields.Selection(
        [('anyone_allowed', 'Anyone in the app'), ('owner_or_admin', 'Owner or admin')],
        default='anyone_allowed', required=True)
    allow_historical_mark = fields.Boolean(
        default=False,
        help='Off = Mark and Re-project are accepted only on the identity\'s '
             'latest available month.')
    history_shown = fields.Integer(
        default=3, help='Latest changes (user, action, date/time) shown on the card.')

    # ── Capture and labels ────────────────────────────────────────────────
    evidence_options = fields.Text(
        help='One option per line as value|Label (e.g. appt_scheduled|Appointment scheduled).')
    note_enabled = fields.Boolean(string='Comment field', default=True)
    expected_date_enabled = fields.Boolean(
        string='Expected closure date', default=True,
        help='Informational only: the date never changes an outcome.')
    label_mark = fields.Char(default='Mark Projected Compliant', required=True)
    label_reproject = fields.Char(default='Re-project', required=True)
    style_projected_label = fields.Char(default=_DEFAULT_STYLES['projected'][0])
    style_projected_color = fields.Char(default=_DEFAULT_STYLES['projected'][1])
    style_missed_label = fields.Char(default=_DEFAULT_STYLES['missed'][0])
    style_missed_color = fields.Char(default=_DEFAULT_STYLES['missed'][1])
    style_matched_label = fields.Char(default=_DEFAULT_STYLES['matched'][0])
    style_matched_color = fields.Char(default=_DEFAULT_STYLES['matched'][1])
    style_ineligible_label = fields.Char(default=_DEFAULT_STYLES['ineligible'][0])
    style_ineligible_color = fields.Char(default=_DEFAULT_STYLES['ineligible'][1])
    poll_seconds = fields.Integer(
        default=30, help='Drawer / consumer refresh while visible. 0 = off.')

    # ── Reporting (ClickHouse types) ──────────────────────────────────────
    publisher_connection_id = fields.Many2one(
        'dashboard.connection', string='Publisher Connection', ondelete='restrict',
        help='Dedicated INSERT-only connection used to mirror saved cycles into '
             'ClickHouse. Never used for reading.')
    mirror_table = fields.Char(
        string='Mirror Table', help='Qualified ClickHouse table, e.g. '
                                    'shared.dashboard_projections.')
    mirror_note = fields.Boolean(
        string='Mirror comments', default=False,
        help='Off: the free-text comment stays in Odoo only.')
    view_name = fields.Char(
        string='Reporting View Name',
        help='Name of the combined reporting view you create from the rendered '
             'SQL (e.g. shared.v_humana_stars_tracker). Used only to render it.')

    identity_expr_sql = fields.Text(compute='_compute_rendered_sql', store=False)
    view_sql = fields.Text(compute='_compute_rendered_sql', store=False)
    mirror_ddl_sql = fields.Text(compute='_compute_rendered_sql', store=False)
    projection_count = fields.Integer(compute='_compute_projection_count')

    _app_key_unique = models.Constraint(
        'UNIQUE (app_id, key)', 'A Projection Type key must be unique per app.')

    # ── Computes ──────────────────────────────────────────────────────────
    @api.depends('source_id', 'source_id.connection_id', 'source_id.connection_id.engine')
    def _compute_engine(self):
        for rec in self:
            src = rec.source_id
            rec.engine = (src.connection_id.engine if src and src.connection_id
                          else 'postgres_local')

    def _compute_projection_count(self):
        counts = {}
        if self.ids:
            groups = self.env['dashboard.projection'].sudo()._read_group(
                [('config_id', 'in', self.ids)], ['config_id'], ['__count'])
            counts = {cfg.id: n for cfg, n in groups}
        for rec in self:
            rec.projection_count = counts.get(rec.id, 0)

    @api.depends('source_id', 'identity_column_ids.column_id', 'snapshot_column_id',
                 'status_column_id', 'status_true_values', 'eligibility_column_id',
                 'eligible_values', 'mirror_table', 'view_name', 'app_id', 'key')
    def _compute_rendered_sql(self):
        for rec in self:
            try:
                rec.identity_expr_sql = rec._render_identity_expr()
            except Exception as exc:  # incomplete configuration while editing
                rec.identity_expr_sql = '-- %s' % exc
            try:
                rec.view_sql = rec._render_view_sql()
            except Exception as exc:
                rec.view_sql = '-- %s' % exc
            try:
                rec.mirror_ddl_sql = rec._render_mirror_ddl()
            except Exception as exc:
                rec.mirror_ddl_sql = '-- %s' % exc

    # ── Validation ────────────────────────────────────────────────────────
    @api.constrains('key')
    def _check_key(self):
        for rec in self:
            if not _KEY_RE.match(rec.key or ''):
                raise ValidationError(
                    'Projection Type key %r must be lowercase letters, digits and '
                    'underscores, starting with a letter.' % (rec.key,))

    @api.constrains('source_id', 'app_id')
    def _check_source(self):
        for rec in self:
            src = rec.source_id
            if not src.is_active:
                raise ValidationError('The source %r is not active.' % src.name)
            if src.app_ids and rec.app_id not in src.app_ids:
                raise ValidationError(
                    'The source %r is not available to app %r (Available in Apps).'
                    % (src.name, rec.app_id.app_key))
            if rec.engine == 'snowflake':
                raise ValidationError(
                    'Projections are not supported on Snowflake sources.')
            if not TABLE_RE.match(src.table_name or ''):
                raise ValidationError('The source table name %r is not a valid '
                                      'identifier.' % (src.table_name,))

    @api.constrains('identity_column_ids', 'snapshot_column_id', 'status_column_id',
                    'eligibility_column_id', 'scope_column_id', 'source_id')
    def _check_columns(self):
        for rec in self:
            if not rec.identity_column_ids:
                raise ValidationError('At least one identity column is required.')
            seen = set()
            for line in rec.identity_column_ids:
                col = line.column_id
                if col.source_id != rec.source_id:
                    raise ValidationError(
                        'Identity column %r does not belong to the source.'
                        % col.column_name)
                if col.data_type not in _IDENTITY_TYPES:
                    raise ValidationError(
                        'Identity column %r must be text or integer.' % col.column_name)
                if col.id in seen:
                    raise ValidationError(
                        'Identity column %r is listed twice.' % col.column_name)
                seen.add(col.id)
            for label, col in (('Snapshot', rec.snapshot_column_id),
                               ('Status', rec.status_column_id),
                               ('Eligibility', rec.eligibility_column_id),
                               ('Scope', rec.scope_column_id)):
                if col and col.source_id != rec.source_id:
                    raise ValidationError(
                        '%s column %r does not belong to the source.'
                        % (label, col.column_name))
            if rec.snapshot_column_id.data_type not in _IDENTITY_TYPES:
                raise ValidationError('The snapshot column must be text or integer.')
            if rec.snapshot_column_id.id in seen:
                raise ValidationError(
                    'The snapshot column cannot be part of the identity.')

    @api.constrains('scope_mode', 'scope_column_id', 'scope_provider_field')
    def _check_scope(self):
        for rec in self:
            if rec.scope_mode == 'provider':
                if not rec.scope_column_id or not rec.scope_provider_field:
                    raise ValidationError(
                        'Provider scope needs both a scope column and a provider field.')
                if rec.scope_provider_field not in self.env['hha.provider']._fields:
                    raise ValidationError(
                        '%r is not a field of hha.provider.' % rec.scope_provider_field)

    @api.constrains('history_shown', 'poll_seconds', 'mirror_table', 'view_name')
    def _check_misc(self):
        for rec in self:
            if not 1 <= rec.history_shown <= 10:
                raise ValidationError('History shown must be between 1 and 10.')
            if rec.poll_seconds < 0:
                raise ValidationError('Poll seconds cannot be negative.')
            for label, value in (('Mirror table', rec.mirror_table),
                                 ('Reporting view name', rec.view_name)):
                if value and not TABLE_RE.match(value):
                    raise ValidationError(
                        '%s %r is not a valid (optionally qualified) name.' % (label, value))

    @api.constrains('publisher_connection_id', 'mirror_table', 'source_id')
    def _check_publisher(self):
        for rec in self:
            conn = rec.publisher_connection_id
            if not conn:
                continue
            if rec.engine != 'clickhouse':
                raise ValidationError(
                    'A publisher connection is only used for ClickHouse-backed types.')
            if conn.engine != 'clickhouse' or getattr(conn, 'purpose', 'analytics') != 'publisher':
                raise ValidationError(
                    'The publisher connection must be a ClickHouse connection with '
                    'purpose "Projections publisher".')
            if not rec.mirror_table:
                raise ValidationError('A mirror table is required with a publisher connection.')

    # ── Cron entry points (data/projection_cron.xml) ──────────────────────
    @api.model
    def _cron_publish_pending(self):
        from ..utils.projection_publisher import publish_pending
        published, failed = publish_pending(self.env)
        if published or failed:
            _logger.info('projection publisher: %s published, %s failed', published, failed)
        return True

    @api.model
    def _cron_check_mirror(self):
        from ..utils.projection_publisher import check_mirror
        for cfg in self.sudo().search([('is_active', '=', True)]):
            if cfg.engine == 'clickhouse' and cfg.publisher_connection_id:
                check_mirror(self.env, cfg)
        return True

    _FROZEN_FIELDS = ('source_id', 'snapshot_column_id')

    def write(self, vals):
        frozen = set(vals) & set(self._FROZEN_FIELDS)
        if 'identity_column_ids' in vals:
            frozen.add('identity_column_ids')
        if frozen:
            Proj = self.env['dashboard.projection'].sudo()
            for rec in self:
                if Proj.search_count([('config_id', '=', rec.id)], limit=1):
                    raise UserError(
                        'Projection Type %r already has projections; its source, '
                        'identity and snapshot columns are frozen. Create a new '
                        'type for a different identity.' % rec.name)
        return super().write(vals)

    # ── Configuration helpers ─────────────────────────────────────────────
    def _identity_column_names(self):
        self.ensure_one()
        return [line.column_id.column_name for line in self.identity_column_ids.sorted(
            key=lambda l: (l.sequence, l.id))]

    def _status_values(self):
        return pid.parse_value_list(self.status_true_values, '1')

    def _eligible_values(self):
        return pid.parse_value_list(self.eligible_values, '1')

    def value_is_positive(self, value):
        return pid.normalize_component(value) in self._status_values()

    def value_is_eligible(self, value):
        if not self.eligibility_column_id:
            return True
        return pid.normalize_component(value) in self._eligible_values()

    def evidence_choices(self):
        """[(value, label)] parsed from ``evidence_options``."""
        out = []
        for line in (self.evidence_options or '').splitlines():
            line = line.strip()
            if not line:
                continue
            value, _, label = line.partition('|')
            value = value.strip()
            if value:
                out.append((value, (label or value).strip()))
        return out

    def outcome_styles(self):
        self.ensure_one()
        return {
            'projected': {'label': self.style_projected_label or _DEFAULT_STYLES['projected'][0],
                          'color': self.style_projected_color or _DEFAULT_STYLES['projected'][1]},
            'missed': {'label': self.style_missed_label or _DEFAULT_STYLES['missed'][0],
                       'color': self.style_missed_color or _DEFAULT_STYLES['missed'][1]},
            'matched': {'label': self.style_matched_label or _DEFAULT_STYLES['matched'][0],
                        'color': self.style_matched_color or _DEFAULT_STYLES['matched'][1]},
            'ineligible': {'label': self.style_ineligible_label or _DEFAULT_STYLES['ineligible'][0],
                           'color': self.style_ineligible_color or _DEFAULT_STYLES['ineligible'][1]},
        }

    def get_public_meta(self):
        """Labels, colours and capture settings sent to the drawer."""
        self.ensure_one()
        return {
            'type_key': self.key,
            'labels': {'mark': self.label_mark, 'reproject': self.label_reproject},
            'styles': self.outcome_styles(),
            'capture': {
                'evidence_options': [{'value': v, 'label': l} for v, l in self.evidence_choices()],
                'note_enabled': bool(self.note_enabled),
                'expected_date_enabled': bool(self.expected_date_enabled),
            },
            'history_shown': self.history_shown,
            'poll_seconds': self.poll_seconds,
            'allow_historical_mark': bool(self.allow_historical_mark),
        }

    # ── SQL rendering (identity expression, history query, mirror, view) ──
    def _render_identity_expr(self, table_alias=None):
        self.ensure_one()
        return pid.render_identity_expr(
            self._identity_column_names(), self.engine, table_alias)

    def _render_month_expr(self, table_alias=None):
        return pid.month_text_expr(
            self.snapshot_column_id.column_name, self.engine, table_alias)

    def _render_compliant_expr(self, table_alias=None):
        return pid.render_in_list_expr(
            self.status_column_id.column_name, self._status_values(),
            self.engine, table_alias)

    def _render_eligible_expr(self, table_alias=None):
        if not self.eligibility_column_id:
            return '1' if self.engine == 'clickhouse' else 'true'
        return pid.render_in_list_expr(
            self.eligibility_column_id.column_name, self._eligible_values(),
            self.engine, table_alias)

    def _quoted_source(self):
        return quote_table(self.source_id.table_name)

    def _render_mirror_ddl(self):
        self.ensure_one()
        if self.engine != 'clickhouse':
            return '-- Postgres-backed type: cycles are read from the Odoo table directly.'
        table = self.mirror_table or 'shared.dashboard_projections'
        return (
            "-- Run as a ClickHouse admin. The publisher user needs INSERT only.\n"
            "CREATE TABLE IF NOT EXISTS %(t)s (\n"
            "  tenant_id LowCardinality(String), config_key LowCardinality(String),\n"
            "  identity_hash String, identity_json String,\n"
            "  cycle_no UInt32, revision UInt64, state LowCardinality(String),\n"
            "  attempt_no UInt32, first_applies_from String, applies_from String,\n"
            "  attempt_months Array(String), undone_month String, expected_date String,\n"
            "  evidence String, note String, actor String, owner String,\n"
            "  asserted_at String, undone_at String, published_at DateTime DEFAULT now()\n"
            ") ENGINE = ReplacingMergeTree(revision)\n"
            "ORDER BY (tenant_id, config_key, identity_hash, cycle_no);\n"
            "CREATE ROW POLICY IF NOT EXISTS pv_tenant ON %(t)s\n"
            "  FOR SELECT USING tenant_id = getSetting('SQL_tenant_id') TO app_role;\n"
            "GRANT SELECT ON %(t)s TO app_role;\n"
            "-- GRANT INSERT ON %(t)s TO <publisher_user>;\n"
        ) % {'t': table}

    def _render_view_sql(self):
        self.ensure_one()
        if self.engine == 'clickhouse':
            return self._render_view_sql_clickhouse()
        return self._render_view_sql_postgres()

    def _render_view_sql_clickhouse(self):
        ident = self._render_identity_expr()
        month = self._render_month_expr()
        ctx = {
            'view': self.view_name or 'shared.v_%s_%s' % (
                re.sub(r'[^a-z0-9_]', '_', (self.app_key or 'app').lower()), self.key),
            'mirror': self.mirror_table or 'shared.dashboard_projections',
            'app_key': (self.app_key or '').replace("'", "''"),
            'key': self.key.replace("'", "''"),
            'source': self._quoted_source(),
            'ident': ident,
            'month': month,
            'eligible': self._render_eligible_expr(),
            'compliant': self._render_compliant_expr(),
        }
        return """-- Combined reporting view for %(app_key)s / %(key)s (one row per source row).
CREATE OR REPLACE VIEW %(view)s AS
WITH cur AS (
  SELECT identity_hash, cycle_no,
         argMax(tuple(state, first_applies_from, applies_from, attempt_months, undone_month,
                      expected_date, evidence, actor, owner, asserted_at, undone_at), revision) AS rec
  FROM %(mirror)s
  WHERE tenant_id = '%(app_key)s' AND config_key = '%(key)s'
  GROUP BY identity_hash, cycle_no
),
cyc AS (
  SELECT identity_hash, cycle_no, rec.1 AS state, rec.2 AS first_applies_from, rec.3 AS applies_from,
         rec.4 AS attempt_months, rec.5 AS undone_month, rec.6 AS expected_date, rec.7 AS evidence,
         rec.8 AS actor, rec.9 AS owner
  FROM cur
),
months AS (
  SELECT DISTINCT %(ident)s AS h, %(month)s AS s FROM %(source)s WHERE %(ident)s != ''
),
cover AS (
  SELECT m.h AS h, m.s AS s, argMax(c.cycle_no, (c.first_applies_from, c.cycle_no)) AS cycle_no
  FROM months m INNER JOIN cyc c ON c.identity_hash = m.h
  WHERE c.first_applies_from <= m.s
  GROUP BY m.h, m.s
),
assigned AS (
  SELECT d.*,
         %(ident)s AS pv_identity_hash, %(month)s AS pv_month,
         ifNull(cv.cycle_no, 0) AS pv_cycle_no,
         ifNull(c.state, '') AS pv_state,
         ifNull(c.first_applies_from, '') AS pv_first_applies_from,
         ifNull(c.applies_from, '') AS pv_applies_from,
         ifNull(c.attempt_months, []) AS pv_attempt_months,
         ifNull(c.undone_month, '') AS pv_undone_month,
         ifNull(c.expected_date, '') AS pv_expected_date,
         ifNull(c.evidence, '') AS pv_evidence,
         ifNull(c.owner, '') AS pv_owner,
         toUInt8(%(eligible)s) AS pv_eligible,
         toUInt8(%(compliant)s) AS pv_source_positive
  FROM %(source)s d
  LEFT JOIN cover cv ON cv.h = %(ident)s AND cv.s = %(month)s
  LEFT JOIN cyc c ON c.identity_hash = cv.h AND c.cycle_no = cv.cycle_no
),
matches AS (
  SELECT pv_identity_hash AS h, pv_cycle_no AS cycle_no, min(pv_month) AS match_month, 1 AS has_match
  FROM assigned
  WHERE pv_cycle_no > 0 AND pv_eligible = 1 AND pv_source_positive = 1
    AND (pv_state != 'undone' OR pv_month < pv_undone_month)
  GROUP BY h, cycle_no
)
SELECT a.*,
       ifNull(mt.has_match, 0) AS pv_has_match,
       ifNull(mt.match_month, '') AS pv_match_month,
       multiIf(a.pv_eligible = 0, 'ineligible',
               a.pv_cycle_no = 0, '',
               a.pv_state = 'undone' AND a.pv_month >= a.pv_undone_month, '',
               ifNull(mt.has_match, 0) = 1 AND a.pv_month = ifNull(mt.match_month, ''), 'matched',
               ifNull(mt.has_match, 0) = 1 AND a.pv_month > ifNull(mt.match_month, ''), '',
               has(a.pv_attempt_months, a.pv_month), 'projected',
               'missed') AS pv_outcome,
       toUInt8(pv_outcome = 'projected') AS pv_projected,
       toUInt8(a.pv_eligible = 1 AND (a.pv_source_positive = 1 OR pv_outcome = 'projected')) AS pv_projected_compliant,
       multiIf(a.pv_eligible = 0, 'ineligible',
               a.pv_source_positive = 1, 'positive',
               pv_outcome = 'projected', 'projected',
               pv_outcome = 'missed', 'missed',
               'open') AS pv_gap_state
FROM assigned a
LEFT JOIN matches mt ON mt.h = a.pv_identity_hash AND mt.cycle_no = a.pv_cycle_no;
""" % ctx

    def _render_view_sql_postgres(self):
        ident = self._render_identity_expr()
        month = self._render_month_expr()
        ctx = {
            'view': self.view_name or 'pv_proj_%s_%s' % (
                re.sub(r'[^a-z0-9_]', '_', (self.app_key or 'app').lower()), self.key),
            'config_id': int(self.id) if self.id else 0,
            'source': self._quoted_source(),
            'ident': ident,
            'month': month,
            'eligible': self._render_eligible_expr(),
            'compliant': self._render_compliant_expr(),
        }
        return """-- Combined reporting view for Postgres-backed type (one row per source row).
CREATE OR REPLACE VIEW %(view)s AS
%(select)s;
""" % {'view': ctx['view'], 'select': self._render_view_select_postgres(ctx)}

    def _render_view_select_postgres(self, ctx=None):
        """The SELECT of the Postgres combined view (also used by tests)."""
        self.ensure_one()
        if ctx is None:
            ctx = {
                'config_id': int(self.id) if self.id else 0,
                'source': self._quoted_source(),
                'ident': self._render_identity_expr(),
                'month': self._render_month_expr(),
                'eligible': self._render_eligible_expr(),
                'compliant': self._render_compliant_expr(),
            }
        return """WITH cyc AS (
  SELECT p.identity_hash, p.cycle_no, p.state,
         coalesce(p.first_applies_from, '') AS first_applies_from,
         coalesce(p.applies_from, '') AS applies_from,
         string_to_array(coalesce(p.attempt_months, ''), ',') AS attempt_months,
         coalesce(p.undone_month, '') AS undone_month,
         coalesce(p.expected_date::text, '') AS expected_date,
         coalesce(p.evidence, '') AS evidence,
         coalesce(p.owner_name, '') AS owner
  FROM dashboard_projection p
  WHERE p.config_id = %(config_id)s
),
months AS (
  SELECT DISTINCT %(ident)s AS h, %(month)s AS s FROM %(source)s WHERE %(ident)s IS NOT NULL
),
cover AS (
  SELECT m.h, m.s, c.cycle_no
  FROM months m
  JOIN LATERAL (
    SELECT c.cycle_no FROM cyc c
    WHERE c.identity_hash = m.h AND c.first_applies_from <= m.s
    ORDER BY c.first_applies_from DESC, c.cycle_no DESC LIMIT 1
  ) c ON true
),
assigned AS (
  SELECT d.*,
         %(ident)s AS pv_identity_hash, %(month)s AS pv_month,
         coalesce(cv.cycle_no, 0) AS pv_cycle_no,
         coalesce(c.state, '') AS pv_state,
         coalesce(c.first_applies_from, '') AS pv_first_applies_from,
         coalesce(c.applies_from, '') AS pv_applies_from,
         coalesce(c.attempt_months, ARRAY[]::text[]) AS pv_attempt_months,
         coalesce(c.undone_month, '') AS pv_undone_month,
         coalesce(c.expected_date, '') AS pv_expected_date,
         coalesce(c.evidence, '') AS pv_evidence,
         coalesce(c.owner, '') AS pv_owner,
         (%(eligible)s) AS pv_eligible,
         (%(compliant)s) AS pv_source_positive
  FROM %(source)s d
  LEFT JOIN cover cv ON cv.h = %(ident)s AND cv.s = %(month)s
  LEFT JOIN cyc c ON c.identity_hash = cv.h AND c.cycle_no = cv.cycle_no
),
matches AS (
  SELECT pv_identity_hash AS h, pv_cycle_no AS cycle_no, min(pv_month) AS match_month
  FROM assigned
  WHERE pv_cycle_no > 0 AND pv_eligible AND pv_source_positive
    AND (pv_state <> 'undone' OR pv_month < pv_undone_month)
  GROUP BY 1, 2
),
outcomes AS (
  SELECT a.*,
         (mt.match_month IS NOT NULL) AS pv_has_match,
         coalesce(mt.match_month, '') AS pv_match_month,
         CASE WHEN NOT a.pv_eligible THEN 'ineligible'
              WHEN a.pv_cycle_no = 0 THEN ''
              WHEN a.pv_state = 'undone' AND a.pv_month >= a.pv_undone_month THEN ''
              WHEN mt.match_month IS NOT NULL AND a.pv_month = mt.match_month THEN 'matched'
              WHEN mt.match_month IS NOT NULL AND a.pv_month > mt.match_month THEN ''
              WHEN a.pv_month = ANY(a.pv_attempt_months) THEN 'projected'
              ELSE 'missed' END AS pv_outcome
  FROM assigned a
  LEFT JOIN matches mt ON mt.h = a.pv_identity_hash AND mt.cycle_no = a.pv_cycle_no
)
SELECT o.*,
       (o.pv_outcome = 'projected') AS pv_projected,
       (o.pv_eligible AND (o.pv_source_positive OR o.pv_outcome = 'projected')) AS pv_projected_compliant,
       CASE WHEN NOT o.pv_eligible THEN 'ineligible'
            WHEN o.pv_source_positive THEN 'positive'
            WHEN o.pv_outcome = 'projected' THEN 'projected'
            WHEN o.pv_outcome = 'missed' THEN 'missed'
            ELSE 'open' END AS pv_gap_state
FROM outcomes o""" % ctx

    def render_history_sql(self, member_key_column, scope_column=None):
        """Per-member history query used by the drawer and the service:
        ``identity_hash, month, eligible, compliant`` for every row of the
        member (``%(member_key)s``), optionally scoped (``%(pv_scope)s``)."""
        self.ensure_one()
        if not IDENT_RE.match(member_key_column or ''):
            raise ValueError('invalid member key column %r' % (member_key_column,))
        engine = self.engine
        member = pid.normalized_column_expr(member_key_column, engine)
        eligible = self._render_eligible_expr()
        compliant = self._render_compliant_expr()
        if engine == 'clickhouse':
            eligible = 'toUInt8(%s)' % eligible
            compliant = 'toUInt8(%s)' % compliant
        else:
            eligible = '(%s)::int' % eligible
            compliant = '(%s)::int' % compliant
        where = ['%s = %%(member_key)s' % member]
        if scope_column:
            if not IDENT_RE.match(scope_column):
                raise ValueError('invalid scope column %r' % (scope_column,))
            where.append('%s IN %%(pv_scope)s' % pid.normalized_column_expr(scope_column, engine))
        return 'SELECT %s AS h, %s AS s, %s AS e, %s AS c FROM %s WHERE %s' % (
            self._render_identity_expr(), self._render_month_expr(), eligible,
            compliant, self._quoted_source(), ' AND '.join(where))


class DashboardProjectionConfigIdentity(models.Model):
    _name = 'dashboard.projection.config.identity'
    _description = 'Projection Type identity column'
    _order = 'sequence, id'

    config_id = fields.Many2one(
        'dashboard.projection.config', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    column_id = fields.Many2one(
        'dashboard.schema.column', required=True, ondelete='restrict')
    column_name = fields.Char(related='column_id.column_name', readonly=True)
    data_type = fields.Selection(related='column_id.data_type', readonly=True)


class DashboardProjection(models.Model):
    """One projection **cycle**. Never deleted."""
    _name = 'dashboard.projection'
    _description = 'Projection cycle'
    _order = 'config_id, identity_hash, cycle_no desc'
    _rec_name = 'display_label'

    config_id = fields.Many2one(
        'dashboard.projection.config', string='Projection Type', required=True,
        ondelete='restrict', index=True)
    app_id = fields.Many2one(related='config_id.app_id', store=True, readonly=True)
    identity_hash = fields.Char(required=True, index=True)
    identity_json = fields.Text(required=True)
    identity_label = fields.Char(help='Human-readable identity (from the row at Mark time).')
    cycle_no = fields.Integer(required=True, default=1)
    state = fields.Selection(PROJECTION_STATES, default='active', required=True, index=True)
    revision = fields.Integer(
        default=1, required=True,
        help='Identity-wide revision at this cycle\'s last change.')
    published_revision = fields.Integer(default=0)
    attempt_no = fields.Integer(default=1)
    first_applies_from = fields.Char(string='First month', required=True)
    applies_from = fields.Char(string='Latest attempt month', required=True)
    attempt_months = fields.Char(
        help='Comma-separated months of the Mark and every Re-project.')
    undone_month = fields.Char(
        help='Month from which the cancellation applies (empty while active).')
    expected_date = fields.Date(string='Expected closure date')
    evidence = fields.Char()
    note = fields.Text(string='Comment')
    owner_id = fields.Many2one('res.users', string='Marked by', ondelete='restrict')
    owner_name = fields.Char()
    asserted_at = fields.Datetime()
    last_action_at = fields.Datetime()
    undone_at = fields.Datetime()
    undone_by_id = fields.Many2one('res.users', ondelete='restrict')
    source_snapshot = fields.Text(help='Row values at the last save (JSON).')
    publish_state = fields.Selection(PUBLISH_STATES, default='none', required=True)
    event_ids = fields.One2many('dashboard.projection.event', 'projection_id')
    display_label = fields.Char(compute='_compute_display_label')

    _cycle_unique = models.Constraint(
        'UNIQUE (config_id, identity_hash, cycle_no)',
        'One record per projection cycle.')

    @api.depends('identity_label', 'identity_hash', 'cycle_no')
    def _compute_display_label(self):
        for rec in self:
            rec.display_label = '%s · cycle %s' % (
                rec.identity_label or rec.identity_hash[:12], rec.cycle_no)

    def unlink(self):
        raise UserError('Projection records are never deleted. Use Undo or Void.')

    def attempt_month_list(self):
        return _months_from_text(self.attempt_months)

    def to_cycle(self):
        """:class:`projection_outcomes.Cycle` for the rule engine."""
        from ..utils.projection_outcomes import Cycle
        return Cycle(self.cycle_no, self.state, self.first_applies_from,
                     self.attempt_month_list(), self.undone_month or '',
                     self.applies_from, record=self)

    def identity_values(self):
        try:
            return json.loads(self.identity_json or '[]')
        except (ValueError, TypeError):
            return []

    def to_public_dict(self):
        """Cycle payload for the drawer (no capability flags)."""
        self.ensure_one()
        return {
            'cycle_no': self.cycle_no,
            'state': self.state,
            'revision': self.revision,
            'published_revision': self.published_revision,
            'publish_state': self.publish_state,
            'attempt_no': self.attempt_no,
            'first_applies_from': self.first_applies_from,
            'applies_from': self.applies_from,
            'attempt_months': self.attempt_month_list(),
            'undone_month': self.undone_month or '',
            'expected_date': fields.Date.to_string(self.expected_date) if self.expected_date else '',
            'evidence': self.evidence or '',
            'note': self.note or '',
            'owner': self.owner_name or '',
            'owner_id': self.owner_id.id or 0,
            'asserted_at': fields.Datetime.to_string(self.asserted_at) if self.asserted_at else '',
        }

    def to_publish_payload(self):
        """The immutable row published to the mirror (spec §4.1 columns)."""
        self.ensure_one()
        return {
            'tenant_id': self.config_id.app_id.app_key,
            'config_key': self.config_id.key,
            'identity_hash': self.identity_hash,
            'identity_json': self.identity_json or '[]',
            'cycle_no': self.cycle_no,
            'revision': self.revision,
            'state': self.state,
            'attempt_no': self.attempt_no,
            'first_applies_from': self.first_applies_from or '',
            'applies_from': self.applies_from or '',
            'attempt_months': self.attempt_month_list(),
            'undone_month': self.undone_month or '',
            'expected_date': fields.Date.to_string(self.expected_date) if self.expected_date else '',
            'evidence': self.evidence or '',
            'note': (self.note or '') if self.config_id.mirror_note else '',
            'actor': '',
            'owner': self.owner_name or '',
            'asserted_at': fields.Datetime.to_string(self.asserted_at) if self.asserted_at else '',
            'undone_at': fields.Datetime.to_string(self.undone_at) if self.undone_at else '',
        }

    # ── Admin actions (audited through the service) ───────────────────────
    def action_admin_undo(self):
        from ..services import projection_service
        for rec in self:
            projection_service.admin_undo(self.env, self.env.user, rec)
        return True

    def action_open_void_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'dashboard.projection.void.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_projection_id': self.id},
        }

    def action_republish(self):
        """Admin: resend the cycle's latest event to the mirror (audited as a
        ``republish`` event, no revision change)."""
        from ..utils.projection_publisher import republish_cycle, schedule_post_commit
        ids = []
        for rec in self:
            if rec.config_id.engine != 'clickhouse':
                continue
            event = republish_cycle(rec)
            if event:
                self.env['dashboard.projection.event'].sudo().create({
                    'projection_id': rec.id, 'config_id': rec.config_id.id,
                    'identity_hash': rec.identity_hash, 'cycle_no': rec.cycle_no,
                    'action': 'republish', 'actor_id': self.env.user.id,
                    'actor_name': self.env.user.name, 'at': fields.Datetime.now(),
                    'revision': rec.revision,
                    'publish_state': 'none',
                })
                ids.append(event.id)
        if ids:
            schedule_post_commit(self.env, ids)
        return True


class DashboardProjectionEvent(models.Model):
    """Append-only history + publisher outbox."""
    _name = 'dashboard.projection.event'
    _description = 'Projection event'
    _order = 'id desc'

    projection_id = fields.Many2one(
        'dashboard.projection', required=True, ondelete='restrict', index=True)
    config_id = fields.Many2one(
        'dashboard.projection.config', required=True, ondelete='restrict', index=True)
    app_id = fields.Many2one(related='config_id.app_id', store=True, readonly=True)
    identity_hash = fields.Char(required=True, index=True)
    cycle_no = fields.Integer(required=True)
    action = fields.Selection(EVENT_ACTIONS, required=True)
    reason = fields.Char(help='Required for Void; immutable.')
    actor_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    actor_name = fields.Char(required=True)
    at = fields.Datetime(required=True)
    revision = fields.Integer(required=True)
    before_json = fields.Text()
    after_json = fields.Text()
    request_id = fields.Char(index=True)
    request_fingerprint = fields.Char()
    payload_json = fields.Text(help='Row published to the mirror (immutable).')
    result_json = fields.Text(help='Response returned for this request (replayed on retry).')
    publish_state = fields.Selection(PUBLISH_STATES, default='none', required=True)
    attempts = fields.Integer(default=0)
    last_error = fields.Char()
    published_at = fields.Datetime()

    # User-facing changes allocate one revision each; a technical Republish
    # entry re-uses the cycle's current revision and is excluded here.
    _revision_unique = models.UniqueIndex(
        "(config_id, identity_hash, revision) WHERE action <> 'republish'",
        'Revisions are unique per identity.')
    _request_unique = models.UniqueIndex(
        '(config_id, request_id) WHERE request_id IS NOT NULL',
        'A request id can only be used once per Projection Type.')

    # Outbox bookkeeping and the stored response are the only writable
    # fields; the audit content (actor, time, before/after, reason) is not.
    _OUTBOX_FIELDS = {'publish_state', 'attempts', 'last_error', 'published_at',
                      'result_json'}

    def write(self, vals):
        if set(vals) - self._OUTBOX_FIELDS:
            raise UserError('Projection events are append-only.')
        return super().write(vals)

    def unlink(self):
        raise UserError('Projection events are never deleted.')

    def to_history_dict(self):
        self.ensure_one()
        return {
            'user': self.actor_name,
            'action': self.action,
            'at': fields.Datetime.to_string(self.at),
            'reason': self.reason or '',
            'revision': self.revision,
            'cycle_no': self.cycle_no,
        }


class DashboardProjectionVoidWizard(models.TransientModel):
    _name = 'dashboard.projection.void.wizard'
    _description = 'Void a projection cycle'

    projection_id = fields.Many2one('dashboard.projection', required=True)
    reason = fields.Char(required=True)

    def action_void(self):
        from ..services import projection_service
        self.ensure_one()
        projection_service.admin_void(
            self.env, self.env.user, self.projection_id, self.reason)
        return {'type': 'ir.actions.act_window_close'}
