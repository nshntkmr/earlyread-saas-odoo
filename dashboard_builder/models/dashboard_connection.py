# -*- coding: utf-8 -*-
"""External database connection.

A ``dashboard.connection`` record describes how to reach an external
analytics backend (today: ClickHouse). Schema sources with a
``connection_id`` route their queries through that backend; sources
without one use Odoo's local Postgres cursor.

Credentials are kept out of this table on purpose — the
``password_param_key`` field stores the ``ir.config_parameter`` name
that holds the actual password. Admins set the password once via
``self.env['ir.config_parameter'].sudo().set_param(...)``; rotating
it does not require touching the connection record.

Caching: the executor keeps a per-process client cached by connection
id. Writing or unlinking the record invalidates that cache so password
or host changes take effect without an Odoo restart.
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DashboardConnection(models.Model):
    _name = 'dashboard.connection'
    _description = 'External Database Connection'
    _order = 'name'

    name = fields.Char(
        required=True, string='Display Name',
        help='Shown in the schema source dropdown, e.g. '
             '"ClickHouse — Production".',
    )

    engine = fields.Selection(
        [
            ('postgres_local', 'Postgres (Odoo local)'),
            ('clickhouse', 'ClickHouse'),
        ],
        required=True, default='clickhouse',
        help='Which executor handles queries against this connection. '
             'Postgres-local is reserved for advanced cases — most '
             'admins want the empty (default) connection_id on the '
             'schema source instead.',
    )

    is_active = fields.Boolean(
        default=True,
        help='Disable to take all schema sources using this connection '
             'offline without deleting the record. Existing widgets '
             'will surface per-widget errors rather than crash the page.',
    )

    # ── Connection details ─────────────────────────────────────────────
    host = fields.Char(string='Host')
    port = fields.Integer(string='Port', default=8443)
    database = fields.Char(string='Database')
    username = fields.Char(string='Username')
    password_param_key = fields.Char(
        string='Password Config Key',
        help='ir.config_parameter key that stores the password. '
             'Set the value via the Odoo shell:\n'
             '  env["ir.config_parameter"].sudo().set_param('
             '"clickhouse.password.prod", "<password>")',
    )
    use_tls = fields.Boolean(string='Use TLS', default=True)

    # ── Tenancy enforcement ────────────────────────────────────────────
    requires_tenant_filter = fields.Boolean(
        string='Enforce Tenant Filter',
        default=True,
        help='When True (recommended), every query against this '
             'connection runs after a SET SQL_tenant_id = ... so '
             'CH row policies enforce isolation. Disable only for '
             'admin tooling that legitimately reads cross-tenant data.',
    )

    # ── Query execution limits ─────────────────────────────────────────
    query_timeout_seconds = fields.Integer(
        string='Query Timeout (seconds)',
        default=30,
        help='Sent as max_execution_time on every query. Prevents '
             'runaway queries from holding cluster resources.',
    )

    # ── Test result ────────────────────────────────────────────────────
    last_test_result = fields.Char(readonly=True)
    last_test_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)',
         'Connection names must be unique.'),
    ]

    # ── ORM hooks: invalidate cached executor clients ─────────────────
    def write(self, vals):
        res = super().write(vals)
        self._invalidate_clients()
        return res

    def unlink(self):
        ids = self.ids
        res = super().unlink()
        for cid in ids:
            self._invalidate_one(cid)
        return res

    def _invalidate_clients(self):
        for rec in self:
            self._invalidate_one(rec.id)

    @staticmethod
    def _invalidate_one(connection_id):
        # Lazy import — clickhouse-connect may not be installed; we still
        # want write/unlink to succeed for postgres_local connections.
        try:
            from posterra_portal.utils.query_executors.clickhouse import (
                _invalidate_client,
            )
        except Exception:
            return
        _invalidate_client(connection_id)

    # ── Test Connection button ────────────────────────────────────────
    def action_test_connection(self):
        """Ping the connection and store the result.

        Always invalidates the cached client first so the test uses
        the current host/port/credentials — covers the case where an
        admin rotates the password under ``password_param_key`` and
        wants to verify it without saving a no-op record change.

        Reports through the standard Odoo notification rather than
        raising on success, so admins get a clear green/red answer
        without a stack trace.
        """
        from posterra_portal.utils.query_executors import (
            get_executor_for_connection,
        )

        for rec in self:
            self._invalidate_one(rec.id)
            try:
                executor = get_executor_for_connection(self.env, rec)
                ok = executor.ping()
                if not ok:
                    raise RuntimeError('ping returned False')
                rec.last_test_result = 'OK'
                rec.last_test_at = fields.Datetime.now()
            except Exception as exc:
                msg = str(exc)[:200]
                rec.last_test_result = f'FAIL: {msg}'
                rec.last_test_at = fields.Datetime.now()
                raise UserError(f'Connection test failed: {msg}') from exc

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Connection Test',
                'message': 'Connection succeeded.',
                'type': 'success',
                'sticky': False,
            },
        }

    # ── Invalidate Cache button ───────────────────────────────────────
    def action_invalidate_cache(self):
        """Drop the cached client so the next query opens a fresh one.

        Use this when:
        - You've rotated the password under ``password_param_key``
          (changing ``ir.config_parameter`` doesn't trigger ``write()``
          on this record, so the cache invalidation hook never fires).
        - You suspect the cluster reset connections (e.g. CH server
          restart) and want to force a clean reconnect.
        - You're debugging connection-state issues.

        Per-Odoo-worker: this only invalidates the cache in the worker
        that handled the click. Other workers will get a fresh client
        on their next query (or when their cached client times out).
        For multi-worker deployments, restart Odoo if you need a global
        flush — or accept that other workers reconnect lazily.
        """
        for rec in self:
            self._invalidate_one(rec.id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cache Invalidated',
                'message': (
                    'Cached client dropped on this Odoo worker. Other '
                    'workers will refresh on their next query.'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
