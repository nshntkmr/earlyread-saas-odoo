# -*- coding: utf-8 -*-
"""AI Assist query log.

One row per AI gateway call (``/api/v1/ai/query``; scope reads are not
logged). Serves two purposes:

  1. Audit trail — who asked what, which SQL actually ran, against which
     source, and what came back. The chatbot is a new query surface over
     tenant healthcare data; even non-PHI traffic needs attribution.
  2. Rate limiting — the per-user daily cap in the AI gateway is a
     ``search_count`` over today's rows, so there is no separate counter
     model and no reset cron.

Unlike ``portal.audit.log`` (PHI, fail-closed, autonomous cursor), this log
is best-effort and written in the request transaction: AI Assist serves
non-PHI sources only, so a lost log row on rollback is acceptable — the
failed request never returned data anyway.
"""

from datetime import timedelta

from odoo import api, fields, models


class AiQueryLog(models.Model):
    _name = 'ai.query.log'
    _description = 'AI Assist Query Log'
    _order = 'id desc'
    _rec_name = 'mode'

    user_id = fields.Many2one(
        'res.users', required=True, index=True, ondelete='restrict',
        readonly=True)
    app_id = fields.Many2one(
        'saas.app', index=True, ondelete='set null', readonly=True)
    # Survives app deletion / re-seeding — matches the tenant_id contract.
    app_key = fields.Char(readonly=True, index=True)
    source_id = fields.Many2one(
        'dashboard.schema.source', ondelete='set null', readonly=True)

    channel = fields.Selection([
        ('mcp', 'MCP (desktop client)'),
        ('panel', 'Embedded panel'),
    ], default='mcp', readonly=True)
    mode = fields.Selection([
        ('sql', 'run_sql'),
        ('question', 'ask_data'),
    ], readonly=True)

    question = fields.Text(readonly=True)  # null in sql mode
    # What the caller submitted vs. what actually ran — the policy layer
    # REWRITES SQL (outer LIMIT enforcement), so both matter for audit.
    requested_sql = fields.Text(readonly=True)
    sql = fields.Text(readonly=True, string='Executed SQL')
    row_count = fields.Integer(readonly=True)
    duration_ms = fields.Integer(readonly=True)
    status = fields.Selection([
        ('ok', 'OK'),
        ('validation_error', 'Validation error'),
        ('exec_error', 'Execution error'),
        ('rate_limited', 'Rate limited'),
    ], readonly=True, index=True)
    error = fields.Char(readonly=True)

    RETENTION_DAYS_PARAM = 'posterra_ai.log_retention_days'
    DEFAULT_RETENTION_DAYS = 180

    @api.autovacuum
    def _gc_old_logs(self):
        """Retention: drop rows older than the configured window (default
        180 days). SQL/question text is operator-authored analytics intent,
        not PHI, but it still should not accumulate forever."""
        ICP = self.env['ir.config_parameter'].sudo()
        try:
            days = int(ICP.get_param(
                self.RETENTION_DAYS_PARAM, self.DEFAULT_RETENTION_DAYS))
        except (TypeError, ValueError):
            days = self.DEFAULT_RETENTION_DAYS
        if days <= 0:
            return
        cutoff = fields.Datetime.now() - timedelta(days=days)
        self.sudo().search([('create_date', '<', cutoff)]).unlink()
