# -*- coding: utf-8 -*-
"""Append-only PHI query audit trail.

Every PHI query against a Snowflake ``hospital_phi`` connection writes a
two-event record:
  - ``phi_query_started`` BEFORE execution. If it cannot be written, the
    query does not run (fail closed).
  - ``phi_query_completed`` / ``phi_query_failed`` AFTER execution. If the
    completion event cannot be written, data is not returned (fail closed).

Only non-PHI metadata is stored — user / org / app / page / widget / source
IDs, the Snowflake query id, row count, outcome, and the parameter NAMES +
count. NEVER parameter VALUES (no MBI / patient identifiers).

Durability: the events are written on an autonomous cursor and committed
immediately, so the audit survives a rollback of the request transaction
(e.g. when the query itself fails and the controller rolls back). The model
is append-only — ``write`` and ``unlink`` raise for everyone, including the
superuser (ACL rows alone are bypassed by the superuser, so the method
overrides are the real guard).
"""

import logging

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class PortalAuditLog(models.Model):
    _name = 'portal.audit.log'
    _description = 'PHI Query Audit Log (append-only)'
    _order = 'id desc'
    _rec_name = 'event_type'

    event_type = fields.Selection([
        ('phi_query_started', 'PHI Query Started'),
        ('phi_query_completed', 'PHI Query Completed'),
        ('phi_query_failed', 'PHI Query Failed'),
    ], required=True, index=True, readonly=True)

    user_id = fields.Many2one('res.users', readonly=True, index=True)
    org_id = fields.Char(readonly=True, index=True)
    app_id = fields.Many2one('saas.app', readonly=True, ondelete='set null')
    connection_id = fields.Many2one(
        'dashboard.connection', readonly=True, ondelete='set null')
    source_id = fields.Many2one(
        'dashboard.schema.source', readonly=True, ondelete='set null')

    # Query origin (from execution_context) — IDs only, never values.
    origin_model = fields.Char(readonly=True)
    origin_id = fields.Integer(readonly=True)
    page_id = fields.Integer(readonly=True)

    # Outcome facts (completion event).
    started_id = fields.Many2one('portal.audit.log', readonly=True)
    query_id = fields.Char(string='Snowflake Query ID', readonly=True)
    row_count = fields.Integer(readonly=True)
    outcome = fields.Char(readonly=True)
    error_code = fields.Char(readonly=True)

    # Parameter NAMES + count only — never values.
    param_names = fields.Char(readonly=True)
    param_count = fields.Integer(readonly=True)

    # ── Append-only enforcement (blocks superuser too) ─────────────────
    def write(self, vals):
        raise AccessError("portal.audit.log is append-only; records cannot be modified.")

    def unlink(self):
        raise AccessError("portal.audit.log is append-only; records cannot be deleted.")

    # ── Autonomous-cursor append ───────────────────────────────────────
    @api.model
    def _append_event(self, vals):
        """Create one audit row on a fresh cursor and commit, so it survives a
        rollback of the request transaction. Returns the new row id.

        Raises on failure — callers treat that as fail-closed (no query / no
        data returned).
        """
        registry = self.env.registry
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            rec = env['portal.audit.log'].create(vals)
            cr.commit()
            return rec.id

    @api.model
    def log_phi_started(self, connection, schema_source, org_id,
                        execution_context, param_names):
        ctx = execution_context or {}
        app = self.env['saas.app'].sudo().search(
            [('app_key', '=', ctx.get('app_key'))], limit=1
        ) if ctx.get('app_key') else self.env['saas.app']
        app_id = ctx.get('app_id') or (app.id if app else False)
        names = sorted(param_names or [])
        return self._append_event({
            'event_type': 'phi_query_started',
            'user_id': self.env.uid,
            'org_id': org_id or False,
            'app_id': app_id or False,
            'connection_id': connection.id if connection else False,
            'source_id': schema_source.id if schema_source else False,
            'origin_model': ctx.get('origin_model') or False,
            'origin_id': ctx.get('origin_id') or 0,
            'page_id': ctx.get('page_id') or 0,
            'param_names': ', '.join(names)[:2000] or False,
            'param_count': len(names),
        })

    @api.model
    def log_phi_finished(self, started, outcome, query_id=None,
                         row_count=None, error_code=None):
        event = 'phi_query_completed' if outcome == 'completed' else 'phi_query_failed'
        return self._append_event({
            'event_type': event,
            'user_id': self.env.uid,
            'started_id': started or False,
            'query_id': query_id or False,
            'row_count': row_count if row_count is not None else 0,
            'outcome': outcome or False,
            'error_code': error_code or False,
        })
