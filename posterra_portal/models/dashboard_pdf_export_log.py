# -*- coding: utf-8 -*-
"""Append-only audit log for page PDF exports (plan v5 §6).

* Writes go through an AUTONOMOUS cursor (``_append_event``, same pattern as
  ``portal.audit.log``): the export route runs on a read-only request cursor,
  and the log must survive a request rollback.
* ORM ``write()`` / ``unlink()`` always raise — for every user and context.
  The only delete path is the private autovacuum purge (Odoo refuses RPC
  calls to ``_``-prefixed methods), which deletes expired STARTED rows with
  SQL; terminal rows go with them through ``ON DELETE CASCADE``.
* At most one terminal event per export: a partial unique index on
  ``started_id`` for every non-``started`` row. The reconciler appends
  ``completion_unknown`` for exports that never recorded an outcome (worker
  crash OR a failed terminal write — the cause is not claimed).
* Minimal sensitive data: filter PARAMETER NAMES only, a keyed HMAC
  fingerprint of the inputs, a keynote flag (never its text), widget ids,
  counts, timings and a stable error code (never an error message).
"""

import logging
from datetime import timedelta

import psycopg2

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

TERMINAL_EVENTS = ('completed', 'failed', 'completion_unknown')
RECONCILE_AFTER_MINUTES = 10


class DashboardPdfExportLog(models.Model):
    _name = 'dashboard.pdf.export.log'
    _description = 'PDF Export Audit Log (append-only)'
    _order = 'id desc'
    _rec_name = 'event_type'

    event_type = fields.Selection([
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('completion_unknown', 'Completion Unknown'),
    ], required=True, index=True, readonly=True)
    started_id = fields.Many2one(
        'dashboard.pdf.export.log', string='Started Event', readonly=True,
        index=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', readonly=True, ondelete='set null')
    app_id = fields.Many2one('saas.app', readonly=True, index=True, ondelete='set null')
    page_id = fields.Many2one('dashboard.page', readonly=True, ondelete='set null')
    tab_key = fields.Char(readonly=True)
    input_fingerprint = fields.Char(readonly=True, index=True)
    fingerprint_key_version = fields.Char(readonly=True)
    filter_params = fields.Char(readonly=True, help='Parameter NAMES only (never values).')
    widget_ids = fields.Char(readonly=True)
    scope_option_ids = fields.Char(readonly=True)
    notices_json = fields.Text(readonly=True)
    row_totals_json = fields.Text(readonly=True)
    keynote_used = fields.Boolean(readonly=True)
    orientation = fields.Char(readonly=True)
    bytes = fields.Integer(readonly=True)
    duration_ms = fields.Integer(readonly=True)
    collect_ms = fields.Integer(readonly=True)
    render_ms = fields.Integer(readonly=True)
    error_code = fields.Char(readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS dashboard_pdf_export_log_terminal_uniq
                ON dashboard_pdf_export_log (started_id)
             WHERE event_type <> 'started'
        """)

    # ── append-only ──────────────────────────────────────────────────────
    def write(self, vals):
        raise AccessError('dashboard.pdf.export.log is append-only; records cannot be modified.')

    def unlink(self):
        raise AccessError('dashboard.pdf.export.log is append-only; records cannot be deleted.')

    @api.model
    def _append_event(self, vals):
        """Insert on an autonomous cursor and commit. Returns the id, or None
        when a terminal event already exists for ``started_id`` (unique
        index). Any other failure raises."""
        registry = self.env.registry
        with registry.cursor() as cr:
            cr.execute("SET LOCAL statement_timeout = '3s'")
            if vals.get('started_id') and vals.get('event_type') != 'started':
                # Cheap pre-check (keeps the expected duplicate out of the SQL
                # error log); the unique index below stays the race-proof guard.
                cr.execute("SELECT 1 FROM dashboard_pdf_export_log WHERE started_id = %s "
                           "AND event_type <> 'started' LIMIT 1", (vals['started_id'],))
                if cr.fetchone():
                    return None
            env = api.Environment(cr, SUPERUSER_ID, {})
            try:
                with cr.savepoint():
                    rec = env['dashboard.pdf.export.log'].create(vals)
            except psycopg2.errors.UniqueViolation:
                return None
            cr.commit()
            return rec.id

    @api.model
    def log_started(self, vals):
        return self._append_event(dict(vals, event_type='started'))

    @api.model
    def log_terminal(self, started_id, event_type, vals=None):
        if event_type not in TERMINAL_EVENTS:
            raise ValueError(event_type)
        return self._append_event(dict(vals or {}, event_type=event_type, started_id=started_id))

    # ── reconciler (cron) ────────────────────────────────────────────────
    @api.model
    def _cron_reconcile(self):
        """Append ``completion_unknown`` for every ``started`` event older than
        RECONCILE_AFTER_MINUTES without a terminal event. Idempotent: the
        partial unique index rejects a second terminal row."""
        cutoff = fields.Datetime.now() - timedelta(minutes=RECONCILE_AFTER_MINUTES)
        self.env.cr.execute("""
            SELECT s.id, s.user_id, s.app_id, s.page_id, s.tab_key
              FROM dashboard_pdf_export_log s
             WHERE s.event_type = 'started' AND s.create_date < %s
               AND NOT EXISTS (SELECT 1 FROM dashboard_pdf_export_log t
                                WHERE t.started_id = s.id AND t.event_type <> 'started')
             ORDER BY s.id
             LIMIT 500
        """, (cutoff,))
        closed = 0
        for sid, uid, app_id, page_id, tab_key in self.env.cr.fetchall():
            try:
                with self.env.cr.savepoint():
                    self.sudo().create({
                        'event_type': 'completion_unknown', 'started_id': sid,
                        'user_id': uid, 'app_id': app_id, 'page_id': page_id,
                        'tab_key': tab_key, 'error_code': 'completion_unknown',
                    })
                closed += 1
            except psycopg2.errors.UniqueViolation:
                continue
        if closed:
            _logger.info('PDF export log: %d export(s) closed as completion_unknown', closed)
        return closed

    # ── retention (autovacuum — the ONLY delete path) ────────────────────
    @api.autovacuum
    def _gc_expired_pdf_export_logs(self):
        from ..services.pdf_export.limits import (
            ICP_LOG_RETENTION_DAYS, LOG_RETENTION_DAYS_DEFAULT)
        try:
            days = int(self.env['ir.config_parameter'].sudo().get_param(
                ICP_LOG_RETENTION_DAYS, LOG_RETENTION_DAYS_DEFAULT))
        except (TypeError, ValueError):
            days = LOG_RETENTION_DAYS_DEFAULT
        if days <= 0:
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=days)
        self.env.cr.execute("""
            DELETE FROM dashboard_pdf_export_log
             WHERE create_date < %s
               AND (event_type = 'started' OR started_id IS NULL)
        """, (cutoff,))
        deleted = self.env.cr.rowcount
        if deleted:
            _logger.info('PDF export log retention: %d started event(s) purged (>%d days)',
                         deleted, days)
        return deleted
