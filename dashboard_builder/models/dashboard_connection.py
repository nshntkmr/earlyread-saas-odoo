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
            ('snowflake', 'Snowflake'),
        ],
        required=True, default='clickhouse',
        help='Which executor handles queries against this connection. '
             'Postgres-local is reserved for advanced cases — most '
             'admins want the empty (default) connection_id on the '
             'schema source instead.',
    )

    # ── Security profile ────────────────────────────────────────────────
    # Generic (engine-agnostic) flag that switches on the fail-closed PHI
    # controls. The app/org binding + constraints that make a connection a
    # valid hospital-PHI connection live in posterra_portal's
    # dashboard_builder_ext (they reference saas.app, which dashboard_builder
    # cannot depend on without a circular dependency).
    security_profile = fields.Selection(
        [
            ('standard', 'Standard'),
            ('hospital_phi', 'Hospital PHI'),
        ],
        required=True, default='standard',
        help='Hospital PHI activates fail-closed controls: a four-condition '
             'execution guard, classification-driven masking/preview/export/'
             'AI/HTTP rules, and two-event audit. Only Snowflake connections '
             'scoped to exactly one hospital app may use it.',
    )

    is_active = fields.Boolean(
        default=True,
        help='Disable to take all schema sources using this connection '
             'offline without deleting the record. Existing widgets '
             'will surface per-widget errors rather than crash the page.',
    )

    # ── Connection details ─────────────────────────────────────────────
    host = fields.Char(string='Host')
    # Stored as Char (not Integer) so the form renders the raw digits
    # without applying the user's locale thousands separator —
    # ``8443`` instead of ``8,443`` / ``8.443``. Coerced to int by the
    # executor before being passed to ``clickhouse-connect``.
    port = fields.Char(string='Port', default='8443', size=5)
    database = fields.Char(string='Database')
    username = fields.Char(string='Username')
    # Direct password field — the simple, common case. Typed in the
    # form, saved on the record. Odoo's password=True flag tells the
    # logger / auditor to redact it; widget="password" in the view
    # masks the input.
    password = fields.Char(
        string='Password',
        help='Database password for this connection. Saved on the '
             'record (encrypted at rest by Postgres if encryption is '
             'enabled at the cluster level). For high-security '
             'deployments that require secrets in ir.config_parameter '
             'or an external secret manager, leave this blank and set '
             'Password Config Key instead.',
    )
    # Legacy / advanced indirection — kept for deployments that already
    # use it. Looked up only when the direct ``password`` field is empty.
    password_param_key = fields.Char(
        string='Password Config Key (advanced)',
        help='Optional. Alternative to typing the password directly: '
             'name of an ir.config_parameter row that stores the '
             'password. Used only if the Password field above is left '
             'empty. Set via Odoo shell:\n'
             '  env["ir.config_parameter"].sudo().set_param('
             '"clickhouse.password.prod", "<password>")',
    )
    use_tls = fields.Boolean(string='Use TLS', default=True)

    # ── Snowflake-specific connection details ──────────────────────────
    # Snowflake derives its endpoint from the account identifier, so it does
    # NOT use host/port/use_tls. These fields are shown only when
    # engine == 'snowflake' (see the form view).
    sf_account = fields.Char(
        string='Account Identifier',
        help='Snowflake account identifier, e.g. "xy12345.us-east-1" or '
             '"myorg-myacct". The connector derives the host from this.',
    )
    sf_warehouse = fields.Char(string='Warehouse')
    sf_db_schema = fields.Char(
        string='Schema',
        help='Default Snowflake schema (e.g. the approved secure-view schema).',
    )
    sf_role = fields.Char(
        string='Role',
        help='The dedicated read-only Snowflake role granted access to the '
             "hospital's approved secure views only (no base-table / "
             'cross-hospital grants).',
    )
    auth_method = fields.Selection(
        [
            ('key_pair', 'Key Pair (RSA / JWT)'),
            ('password', 'Username / Password'),
        ],
        default='key_pair',
        help='Key-pair is the recommended production default. Snowflake auth '
             'uses the sf_* secret fields below — never the shared ClickHouse '
             'password fields.',
    )

    # ── Snowflake secrets — System-Admin only, copy=False ──────────────
    # Deliberately SEPARATE from the shared `password`/`password_param_key`
    # fields (which ClickHouse uses): Snowflake auth NEVER falls back to them,
    # and these are restricted to base.group_system so a Dashboard Builder
    # Admin cannot read hospital credentials. Production forbids direct
    # storage (see _check_sf_direct_secret_forbidden) — use the *_param_key
    # env / Key-Vault indirection instead.
    sf_password = fields.Char(
        string='Snowflake Password', copy=False, groups='base.group_system',
        help='Dev/legacy only. Production: leave blank and set Password '
             'Config Key (resolved from env / Key Vault).',
    )
    sf_password_param_key = fields.Char(
        string='Snowflake Password Config Key', groups='base.group_system',
        help='Env var / ir.config_parameter name holding the Snowflake '
             'password. Resolved env-first.',
    )
    sf_private_key = fields.Text(
        string='Private Key (PEM)', copy=False, groups='base.group_system',
        help='Dev only. RSA private key in PEM (encrypted PKCS#8 supported). '
             'Production: leave blank and set Private Key Config Key.',
    )
    sf_private_key_passphrase = fields.Char(
        string='Private Key Passphrase', copy=False, groups='base.group_system',
    )
    sf_private_key_param_key = fields.Char(
        string='Private Key Config Key', groups='base.group_system',
        help='Env var / ir.config_parameter name holding the PEM private key. '
             'Resolved env-first.',
    )
    sf_passphrase_param_key = fields.Char(
        string='Passphrase Config Key', groups='base.group_system',
        help='Env var / ir.config_parameter name holding the private-key '
             'passphrase. Resolved env-first.',
    )

    # ── Verification state (connection-level) ──────────────────────────
    # Distinct from per-source `source_verified` (in posterra_portal ext):
    # this records that auth/config has been validated. A sensitive-field
    # change clears it (and deactivates the connection) until re-validated.
    configuration_verified = fields.Boolean(
        string='Configuration Verified', default=False, copy=False, readonly=True,
    )
    configuration_verified_at = fields.Datetime(
        string='Configuration Verified At', copy=False, readonly=True,
    )

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

    # Fields whose change on a hospital_phi connection invalidates the
    # verified state and deactivates the connection until re-validated —
    # prevents security-boundary repointing (changing where/who the
    # connection talks to while leaving it live).
    _SF_SENSITIVE_FIELDS = (
        'sf_account', 'sf_warehouse', 'sf_db_schema', 'sf_role', 'username',
        'auth_method', 'sf_password', 'sf_password_param_key',
        'sf_private_key', 'sf_private_key_passphrase',
        'sf_private_key_param_key', 'sf_passphrase_param_key', 'engine',
    )

    @api.constrains('security_profile', 'sf_password', 'sf_private_key')
    def _check_sf_direct_secret_forbidden(self):
        """In production, forbid storing the Snowflake password/private key
        directly on the record — secrets must come from env / Key Vault via
        the *_param_key indirection. Controlled by an ir.config_parameter so
        dev / single-Odoo installs keep working unchanged."""
        forbid = self.env['ir.config_parameter'].sudo().get_param(
            'posterra.phi.forbid_direct_secrets', '')
        if str(forbid).strip() not in ('1', 'true', 'True'):
            return
        for rec in self:
            if rec.engine != 'snowflake':
                continue
            if (rec.sf_password or rec.sf_private_key):
                raise UserError(
                    'Direct Snowflake secret storage is forbidden in this '
                    'environment. Leave the password / private key blank and '
                    'set the corresponding Config Key (resolved from env / '
                    'Key Vault).')

    # ── ORM hooks: invalidate cached executor clients ─────────────────
    def write(self, vals):
        # Repointing guard: on a hospital_phi connection, any change to a
        # sensitive endpoint/credential field deactivates the connection and
        # clears its verified state. Reactivation goes through the explicit
        # "Activate PHI Connection" action (in posterra_portal ext).
        touched_sensitive = any(f in vals for f in self._SF_SENSITIVE_FIELDS)
        if touched_sensitive:
            for rec in self:
                if rec.security_profile == 'hospital_phi':
                    vals_self = dict(vals)
                    vals_self.setdefault('configuration_verified', False)
                    # Don't re-activate within the same write that changed a
                    # sensitive field; force it down unless caller is the
                    # activation action (which writes is_active alone).
                    if 'is_active' not in vals:
                        vals_self['is_active'] = False
                    super(DashboardConnection, rec).write(vals_self)
                else:
                    super(DashboardConnection, rec).write(vals)
            self._invalidate_clients()
            return True
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
        # Lazy import — the engine drivers may not be installed; we still
        # want write/unlink to succeed for postgres_local connections.
        # Cross-addon import: dashboard_builder → posterra_portal must
        # use ``odoo.addons.<addon>`` namespace, not bare ``posterra_portal``
        # (which is not on sys.path under Odoo's loader). Both invalidators
        # are no-ops when nothing is cached, so calling both is safe.
        for module in (
            'odoo.addons.posterra_portal.utils.query_executors.clickhouse',
            'odoo.addons.posterra_portal.utils.query_executors.snowflake',
        ):
            try:
                mod = __import__(module, fromlist=['_invalidate_client'])
                mod._invalidate_client(connection_id)
            except Exception:
                continue

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
        # Cross-addon import: dashboard_builder → posterra_portal must
        # use ``odoo.addons.<addon>`` namespace.
        from odoo.addons.posterra_portal.utils.query_executors import (
            get_executor_for_connection,
        )

        for rec in self:
            self._invalidate_one(rec.id)
            try:
                # allow_inactive: Test Connection is an explicit admin action
                # and must work on a connection that a sensitive-field change
                # just auto-deactivated (the revalidation path).
                executor = get_executor_for_connection(
                    self.env, rec, allow_inactive=True)
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
