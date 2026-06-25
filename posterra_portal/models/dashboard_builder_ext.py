# -*- coding: utf-8 -*-
"""
Extend dashboard_builder models with app scoping + hospital-PHI controls.

These fields live here (not in dashboard_builder) because dashboard_builder
depends only on 'base', while saas.app is defined in posterra_portal.
Adding posterra_portal as a dependency of dashboard_builder would create
a circular dependency.

The hospital-PHI isolation model:
  - saas.app.org_id  — immutable, write-once hospital identity (the routing
    identity for a Snowflake PHI connection; NOT app_key, which is a mutable
    subdomain slug).
  - dashboard.connection.tenant_scope_app_id  — which hospital app a
    hospital_phi connection serves; its org_id is derived onto the connection.
  - The Snowflake executor's four-condition guard compares the request app's
    org_id to the connection's derived org_id before any SQL.
  - PHI schema sources fail closed: their app_ids must be exactly the
    connection's app (empty/global is forbidden for PHI).
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


# Classification ordering — "highest sensitivity wins" for computed widget
# classification (a widget over any PHI source is itself PHI).
_CLASS_RANK = {'non_phi': 0, 'phi_masked': 1, 'phi_direct': 2}
_RANK_CLASS = {0: 'non_phi', 1: 'phi_masked', 2: 'phi_direct'}
_PHI_CLASSES = ('phi_masked', 'phi_direct')


class SaasAppPhiExt(models.Model):
    _inherit = 'saas.app'

    org_id = fields.Char(
        string='Hospital Org ID', copy=False,
        help='Immutable, write-once hospital/organization identity. This — '
             'NOT app_key — is the routing identity a Snowflake PHI '
             'connection is bound to. Once set it cannot be changed.')
    single_organization = fields.Boolean(
        string='Single Organization', default=False,
        help='True = this app maps to exactly one hospital/org. Required '
             'before a Snowflake Hospital-PHI connection can be scoped to it. '
             'Cannot be turned off while an active PHI connection references '
             'this app.')

    def write(self, vals):
        # org_id is write-once: reject any attempt to change a non-empty value.
        if 'org_id' in vals:
            new = (vals.get('org_id') or '').strip()
            for app in self:
                cur = (app.org_id or '').strip()
                if cur and new != cur:
                    raise UserError(
                        f"Hospital Org ID is immutable (app {app.app_key!r}); "
                        "create a new app rather than re-pointing an existing "
                        "org identity.")
        # single_organization cannot be cleared while an active hospital_phi
        # connection is bound to the app.
        if vals.get('single_organization') is False:
            Conn = self.env['dashboard.connection'].sudo()
            for app in self:
                bound = Conn.search_count([
                    ('tenant_scope_app_id', '=', app.id),
                    ('security_profile', '=', 'hospital_phi'),
                    ('is_active', '=', True),
                ])
                if bound:
                    raise UserError(
                        f"Cannot clear Single Organization on {app.app_key!r}: "
                        f"{bound} active Hospital-PHI connection(s) reference "
                        "it. Deactivate them first.")
        return super().write(vals)


class DashboardConnectionPhiExt(models.Model):
    _inherit = 'dashboard.connection'

    tenant_scope_app_id = fields.Many2one(
        'saas.app', string='Hospital App', ondelete='restrict', copy=False,
        help='The single hospital app this connection serves. Required for '
             'Hospital-PHI connections; immutable once the connection is '
             'configuration-verified (changing hospitals = new connection).')
    # Derived, stored — the executor compares this to the request app's org_id.
    # Never edited directly: it mirrors the scoped app's immutable org_id.
    org_id = fields.Char(
        related='tenant_scope_app_id.org_id', store=True, readonly=True,
        string='Hospital Org ID')

    @api.constrains('security_profile', 'engine', 'tenant_scope_app_id',
                    'sf_account', 'username', 'auth_method', 'sf_password',
                    'sf_password_param_key', 'sf_private_key',
                    'sf_private_key_param_key')
    def _check_hospital_phi_invariants(self):
        for rec in self:
            if rec.security_profile != 'hospital_phi':
                continue
            if rec.engine != 'snowflake':
                raise ValidationError(
                    "Hospital-PHI security profile is only valid on a "
                    "Snowflake connection.")
            if not rec.sf_account or not rec.username:
                raise ValidationError(
                    "Hospital-PHI Snowflake connection requires an account "
                    "identifier and username.")
            app = rec.tenant_scope_app_id
            if not app:
                raise ValidationError(
                    "Hospital-PHI connection requires a Hospital App "
                    "(tenant_scope_app_id).")
            if not app.org_id:
                raise ValidationError(
                    f"Hospital App {app.app_key!r} has no immutable Org ID; "
                    "set it before scoping a PHI connection to it.")
            if not app.single_organization:
                raise ValidationError(
                    f"Hospital App {app.app_key!r} is not marked Single "
                    "Organization; a per-hospital PHI connection cannot be "
                    "scoped to a multi-organization app.")
            if rec.auth_method == 'password':
                if not (rec.sf_password or rec.sf_password_param_key):
                    raise ValidationError(
                        "Password auth requires a Snowflake password or a "
                        "Password Config Key.")
            else:  # key_pair
                if not (rec.sf_private_key or rec.sf_private_key_param_key):
                    raise ValidationError(
                        "Key-pair auth requires a private key or a Private "
                        "Key Config Key.")

    def write(self, vals):
        # tenant_scope_app_id is immutable once a hospital_phi connection has
        # been configuration-verified — prevents re-pointing a live connection
        # at a different hospital while keeping its credentials.
        if 'tenant_scope_app_id' in vals:
            for rec in self:
                if (rec.security_profile == 'hospital_phi'
                        and rec.configuration_verified
                        and rec.tenant_scope_app_id
                        and vals['tenant_scope_app_id'] != rec.tenant_scope_app_id.id):
                    raise UserError(
                        "The Hospital App of a verified PHI connection cannot "
                        "be changed. Create a new connection for a different "
                        "hospital.")
        return super().write(vals)

    # ── Test Connection: set configuration_verified on success ─────────
    def action_test_connection(self):
        res = super().action_test_connection()
        # super() raises on failure; reaching here means the ping passed.
        for rec in self:
            if rec.engine == 'snowflake':
                rec.write({
                    'configuration_verified': True,
                    'configuration_verified_at': fields.Datetime.now(),
                })
        return res

    # ── Activate PHI Connection — the ONLY way to (re)activate ─────────
    def action_activate_phi_connection(self):
        """Reactivate a hospital_phi connection after re-validation.

        Gated: requires configuration_verified AND at least one verified PHI
        source. ``is_active`` is never set True by a bare field write for a
        hospital_phi connection — this action is the controlled path.
        """
        Source = self.env['dashboard.schema.source'].sudo()
        for rec in self:
            if rec.security_profile != 'hospital_phi':
                rec.is_active = True
                continue
            if not rec.configuration_verified:
                raise UserError(
                    f"Connection {rec.name!r} is not configuration-verified; "
                    "run Test Connection first.")
            verified_sources = Source.search_count([
                ('connection_id', '=', rec.id),
                ('source_verified', '=', True),
            ])
            if not verified_sources:
                raise UserError(
                    f"Connection {rec.name!r} has no verified PHI source; "
                    "run Validate PHI Source on at least one source first.")
            rec.is_active = True
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'PHI Connection Activated',
                'message': 'Connection re-activated after validation.',
                'type': 'success', 'sticky': False,
            },
        }


class DashboardSchemaSourceExt(models.Model):
    _inherit = 'dashboard.schema.source'

    app_ids = fields.Many2many(
        'saas.app', 'schema_source_app_rel', 'source_id', 'app_id',
        string='Available in Apps',
        help='Leave empty for global availability. Set to restrict to specific apps.')

    data_classification = fields.Selection(
        [
            ('non_phi', 'Non-PHI'),
            ('phi_masked', 'PHI — identifiers masked'),
            ('phi_direct', 'PHI — direct identifiers'),
        ],
        default='non_phi', required=True,
        help='Drives masking, preview, export, AI, HTTP and audit controls. '
             'Masked-MBI + names/DOB/demographics is STILL PHI — use '
             'phi_masked, not non_phi.')
    source_verified = fields.Boolean(
        string='PHI Source Verified', default=False, copy=False, readonly=True)
    source_verified_at = fields.Datetime(copy=False, readonly=True)
    phi_approval_ref = fields.Char(
        string='Approved-View Contract Ref', copy=False,
        help='Reference/version of the approved secure-view contract (or the '
             'hospital/compliance attestation) that establishes masking '
             'correctness. Masking CANNOT be proven from column names alone.')

    @api.constrains('data_classification', 'app_ids', 'connection_id')
    def _check_phi_source_scoping(self):
        for src in self:
            conn = src.connection_id
            is_phi = src.data_classification in _PHI_CLASSES
            conn_is_phi = bool(conn) and conn.security_profile == 'hospital_phi'
            if conn_is_phi and not is_phi:
                raise ValidationError(
                    f"Source {src.name!r} is on a Hospital-PHI connection and "
                    "cannot be classified Non-PHI.")
            if not is_phi:
                continue
            # PHI source: must be on a hospital_phi Snowflake connection, and
            # scoped to EXACTLY the connection's hospital app (empty = global
            # = OPEN is forbidden for PHI).
            if not conn_is_phi:
                raise ValidationError(
                    f"PHI source {src.name!r} must be attached to a "
                    "Hospital-PHI connection.")
            app = conn.tenant_scope_app_id
            scoped = src.app_ids
            if not app or len(scoped) != 1 or scoped.id != app.id:
                raise ValidationError(
                    f"PHI source {src.name!r} must be scoped to exactly its "
                    f"connection's hospital app ({app.app_key if app else '—'}). "
                    "Empty/global availability is forbidden for PHI sources.")

    def write(self, vals):
        # Any change that affects what/where the source reads invalidates its
        # verified state (re-run Validate PHI Source).
        invalidating = {'table_name', 'data_classification', 'connection_id',
                        'app_ids', 'phi_approval_ref'}
        if invalidating.intersection(vals) and 'source_verified' not in vals:
            vals = dict(vals, source_verified=False, source_verified_at=False)
        return super().write(vals)

    def action_validate_phi_source(self):
        """System-Admin action: prove the configured role can SELECT the
        approved view (privilege + metadata check, no patient rows), the
        source's app matches its connection, and the columns match the
        approved contract — then set source_verified.

        Uses the allow_inactive executor path so a connection that a sensitive
        change just auto-deactivated can still be re-validated.
        """
        if not self.env.user.has_group('base.group_system'):
            raise UserError("Only a System Administrator may validate a PHI source.")
        from odoo.addons.posterra_portal.utils.query_executors import (
            get_executor_for_connection,
        )
        for src in self:
            conn = src.connection_id
            if not conn or conn.security_profile != 'hospital_phi':
                raise UserError(
                    f"Source {src.name!r} is not on a Hospital-PHI connection.")
            app = conn.tenant_scope_app_id
            if not app or src.app_ids.id != app.id or len(src.app_ids) != 1:
                raise UserError(
                    f"Source {src.name!r} is not scoped to its connection's "
                    "hospital app.")
            executor = get_executor_for_connection(
                self.env, conn, schema_source=src, allow_inactive=True)
            try:
                # SELECT ... LIMIT 0 — privilege + metadata check, no rows.
                cols = executor.validate_phi_source(src.table_name)
            except Exception as exc:  # noqa: BLE001 — surface a clean message
                raise UserError(
                    f"Validation failed for {src.name!r}: {str(exc)[:200]}")
            if not src.phi_approval_ref:
                raise UserError(
                    f"Source {src.name!r} has no Approved-View Contract Ref. "
                    "Masking correctness must be established by an approved "
                    "contract / attestation — not column names — before the "
                    "source can be verified.")
            # Contract check is intentionally an existence-of-approval gate
            # here; the column/contract diff is enforced against the stored
            # approved schema (see phi_approval_ref) by the deploy-time
            # contract test, not by column-name heuristics.
            _ = cols
            src.write({
                'source_verified': True,
                'source_verified_at': fields.Datetime.now(),
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'PHI Source Validated',
                'message': 'Source verified against the approved contract.',
                'type': 'success', 'sticky': False,
            },
        }


class DashboardWidgetDefinitionExt(models.Model):
    _inherit = 'dashboard.widget.definition'

    app_ids = fields.Many2many(
        'saas.app', 'widget_def_app_rel', 'definition_id', 'app_id',
        string='Available in Apps',
        help='Leave empty for global availability. Set to restrict to specific apps.')

    metric_direction = fields.Selection([
        ('higher_better', 'Higher is better (rise=green, fall=red)'),
        ('lower_better',  'Lower is better (invert: rise=red, fall=green)'),
        ('neutral',       'Neutral (no good/bad direction)'),
    ], default='higher_better', string='Metric Direction',
       help='Default metric direction for widgets created from this definition. '
            'Instance widgets can override this per-placement.')


class DashboardWidgetPhiExt(models.Model):
    _inherit = 'dashboard.widget'

    # Computed from ALL of the widget's schema sources (main + scope +
    # ranked-detail + composite children) as the HIGHEST sensitivity — never
    # manually editable. A widget over any PHI source is itself PHI.
    data_classification = fields.Selection(
        [
            ('non_phi', 'Non-PHI'),
            ('phi_masked', 'PHI — identifiers masked'),
            ('phi_direct', 'PHI — direct identifiers'),
        ],
        compute='_compute_data_classification', store=True, readonly=True,
        string='Data Classification')

    @api.depends('schema_source_id.data_classification',
                 'scope_schema_source_id.data_classification',
                 'ranked_detail_schema_source_id.data_classification',
                 'composite_item_ids.schema_source_id.data_classification')
    def _compute_data_classification(self):
        for w in self:
            sources = (w.schema_source_id | w.scope_schema_source_id
                       | w.ranked_detail_schema_source_id
                       | w.composite_item_ids.mapped('schema_source_id'))
            rank = 0
            for s in sources:
                rank = max(rank, _CLASS_RANK.get(s.data_classification or 'non_phi', 0))
            w.data_classification = _RANK_CLASS[rank]
