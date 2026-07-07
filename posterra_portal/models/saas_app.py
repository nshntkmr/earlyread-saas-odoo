# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# RFC 1035 DNS label regex (also RFC 1123 — leading digits allowed):
# lowercase alphanumeric and hyphens, no leading or trailing hyphen,
# 1-63 characters. ``app_key`` doubles as the subdomain label, so
# wildcard TLS (Let's Encrypt) and Azure ingress both reject anything
# non-conforming. Enforce here so admins can't save an unusable value.
_DNS_LABEL_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


class SaaSApp(models.Model):
    _name        = 'saas.app'
    _description = 'SaaS Application'
    _rec_name    = 'name'
    _order       = 'name asc'

    # DB-level uniqueness on app_key. The Python ``_check_app_key_unique``
    # constraint provides a friendly error message for normal flows, but
    # in a multi-replica deployment two pods could pass the Python check
    # concurrently and both insert the same key — the Python constraint
    # is not atomic. The SQL UNIQUE catches the race at the DB level.
    # ``get_app_from_host(..., limit=1)`` would otherwise be
    # non-deterministic across duplicates, which silently breaks
    # multi-tenant routing.
    #
    # Migration note: pre-deploy duplicate check
    #   SELECT app_key, COUNT(*) FROM saas_app
    #    GROUP BY app_key HAVING COUNT(*) > 1;
    # must return zero rows or the upgrade will fail with a clear
    # "duplicate key value violates unique constraint" error.
    _sql_constraints = [
        ('app_key_uniq',
         'unique(app_key)',
         'App key must be unique across all apps.'),
    ]

    name             = fields.Char(required=True)
    app_key          = fields.Char(
        required=True, index=True,
        help='URL slug for this app (e.g. posterra, mssp). Must be unique.',
    )
    is_active        = fields.Boolean(default=True)
    default_page_key = fields.Char(
        default='overview',
        help='Key of the default page to land on when the user navigates to the app root URL.',
    )

    # ── Branding ────────────────────────────────────────────────────────────
    logo           = fields.Binary(attachment=True)
    logo_filename  = fields.Char()
    favicon        = fields.Binary(attachment=True)
    tagline        = fields.Char(
        help='Subtitle shown under the app name (e.g. on the branded login page).',
    )
    primary_color  = fields.Char(default='#0066cc')
    login_bg_color = fields.Char(default='#f8fafc')
    sidebar_theme  = fields.Selection([
        ('dark', 'Dark'),
        ('light', 'Light'),
    ], default='dark', string='Sidebar Theme',
        help='Dark: dark blue sidebar (default). Light: white sidebar with gray text.')
    custom_css     = fields.Text(
        help='Additional CSS injected on portal pages for this app.',
    )

    # ── Access control ───────────────────────────────────────────────────────
    access_mode = fields.Selection([
        ('hha_provider', 'HHA Provider'),
        ('group',        'Security Group'),
    ], required=True, default='hha_provider',
       help='HHA Provider — user must have a linked HHA provider (direct or scope group).\n'
            'Security Group — user must belong to the specified Odoo security group.')

    access_group_xmlid = fields.Char(
        string='Required Group (XML ID)',
        help='Full XML ID of the required security group, '
             'e.g. posterra_portal.group_posterra_mssp_user.\n'
             'Only used when Access Mode = Security Group.',
    )

    session_idle_timeout_mins = fields.Integer(
        string='Session Idle Timeout (minutes)',
        default=0,
        help='Minutes of user inactivity before automatic portal logout. '
             '0 disables the timeout (default). Minimum 5 minutes when enabled. '
             'Applies to portal dashboards only — Designer/admin surfaces are '
             'not affected.',
    )

    # ── Relationships ────────────────────────────────────────────────────────
    page_ids   = fields.One2many('dashboard.page', 'app_id', string='Pages')
    page_count = fields.Integer(compute='_compute_page_count', string='Page Count')

    # ── Computed ─────────────────────────────────────────────────────────────
    @api.depends('page_ids')
    def _compute_page_count(self):
        for app in self:
            app.page_count = len(app.page_ids)

    # ── Constraints ──────────────────────────────────────────────────────────

    # Subdomain labels that must NOT be used as app_key. The platform serves
    # each app on its own subdomain (e.g. posterra.example.com), so app_key
    # collisions with reserved subdomains (`www`, `api`, ...) or with Odoo's
    # own root routes (`web`, `odoo`, `static`, ...) would silently break
    # routing — admin tooling, asset URLs, longpolling endpoints all live at
    # the bare host and are reserved across every subdomain.
    _RESERVED_APP_KEYS = frozenset({
        'www', 'api', 'admin', 'admin-probe', 'mail', 'app', 'odoo',
        'web', 'static', 'longpolling', 'jsonrpc', 'websocket',
        'dashboard', 'portal', 'login', 'logout', 'signup',
        'auth', 'mailto', 'localhost',
    })

    @api.constrains('app_key')
    def _check_app_key_valid(self):
        # ``app_key`` is the lookup label that maps the request's
        # subdomain to a saas.app record AND the tenant_id used by
        # ClickHouse row policies (P0-10). It must be:
        #   1. Non-empty.
        #   2. A valid RFC 1035 DNS label (lowercase alphanumeric and
        #      hyphens, no leading/trailing hyphen, 1-63 chars). Wildcard
        #      TLS and ingress route by this label — invalid forms break
        #      both at runtime.
        #   3. Not in the reserved set (would collide with platform
        #      routes such as ``www``, ``api``, ``admin-probe`` for
        #      K8s liveness probes, etc.).
        # Note: write-time normalisation (.strip().lower()) is performed
        # in create() / write() overrides BEFORE this constraint runs.
        for app in self:
            key = (app.app_key or '').strip()
            if not key:
                raise ValidationError("App key is required.")
            if not _DNS_LABEL_RE.match(key):
                raise ValidationError(
                    f"App key '{app.app_key}' is not a valid DNS label. "
                    "Use lowercase letters, digits, and hyphens only "
                    "(e.g. 'inhome-v1', not 'inhome_v1'). Underscores, "
                    "uppercase letters, and leading/trailing hyphens are "
                    "not allowed because the key is used as a subdomain."
                )
            if key in self._RESERVED_APP_KEYS:
                raise ValidationError(
                    f"App key '{app.app_key}' is reserved and cannot be used "
                    "as an app subdomain. Reserved keys: "
                    f"{', '.join(sorted(self._RESERVED_APP_KEYS))}"
                )

    @api.constrains('session_idle_timeout_mins')
    def _check_session_idle_timeout(self):
        # 1–4 minutes is rejected (not clamped): a timeout below 5 minutes
        # fights the client's 60s stamp cadence and the 60s warning lead,
        # producing false logouts for active users.
        for app in self:
            val = app.session_idle_timeout_mins or 0
            if val < 0:
                raise ValidationError(
                    "Session Idle Timeout cannot be negative. "
                    "Use 0 to disable the timeout."
                )
            if 0 < val < 5:
                raise ValidationError(
                    "Session Idle Timeout must be 0 (disabled) or at least "
                    "5 minutes. Shorter timeouts conflict with the warning "
                    "countdown and token refresh cadence."
                )

    @api.constrains('app_key')
    def _check_app_key_unique(self):
        for app in self:
            duplicate = self.search([
                ('app_key', '=', app.app_key),
                ('id', '!=', app.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f"App key '{app.app_key}' is already used by app '{duplicate.name}'."
                )

    # ── Auto-create security group for group-based apps ──────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        # Normalise app_key BEFORE super() so the DB-stored value matches
        # what the validator checks. ``@api.constrains`` sees the stored
        # value, not a transient .strip().lower() copy — without write-
        # time normalisation, ``"Inhome "`` (trailing space, capital I)
        # passes the validator's local strip-and-lower check but lands
        # in the DB as-is, then ``app_resolver.get_app_from_host()``
        # (which lowercases the leftmost label) fails to match it.
        for vals in vals_list:
            if 'app_key' in vals and isinstance(vals['app_key'], str):
                vals['app_key'] = vals['app_key'].strip().lower()
        records = super().create(vals_list)
        for app in records:
            if app.access_mode == 'group' and app._needs_access_group():
                app._ensure_access_group()
        return records

    def write(self, vals):
        if 'app_key' in vals and isinstance(vals['app_key'], str):
            vals['app_key'] = vals['app_key'].strip().lower()
        res = super().write(vals)
        if vals.get('access_mode') == 'group':
            for app in self:
                if app.access_mode == 'group' and app._needs_access_group():
                    app._ensure_access_group()
        return res

    def _needs_access_group(self):
        """Check if this app needs an auto-created security group.

        Returns True when:
        - access_group_xmlid is empty (no group configured), OR
        - access_group_xmlid is set but the referenced group no longer exists
          (stale reference from a deleted group)
        """
        self.ensure_one()
        if not self.access_group_xmlid:
            return True
        # Verify the referenced group actually exists
        try:
            group = self.env.ref(self.access_group_xmlid, raise_if_not_found=False)
            return not group or not group.exists()
        except Exception:
            return True

    def _ensure_access_group(self):
        """Auto-create a security group for this group-based app.

        Creates a res.groups record that inherits from base.group_portal,
        registers a stable ir.model.data XML ID with noupdate=True (so
        module upgrades never delete it), and sets access_group_xmlid
        on this app record.

        Safe to call multiple times -- if the group/XML ID already exist,
        it links to the existing record instead of creating duplicates.

        Triggered by:
        - create() when access_mode='group' and no group is set
        - write() when access_mode is switched to 'group'
        - write() when existing group reference is stale (group was deleted)
        """
        self.ensure_one()
        Group = self.env['res.groups'].sudo()
        IMD = self.env['ir.model.data'].sudo()

        # Build a stable XML ID from the app_key
        safe_key = (self.app_key or 'app').replace('-', '_')
        xmlid_name = 'group_%s_user' % safe_key
        xmlid_full = 'posterra_portal.%s' % xmlid_name

        # Check if the group already exists via XML ID
        existing_imd = IMD.search([
            ('module', '=', 'posterra_portal'),
            ('name', '=', xmlid_name),
            ('model', '=', 'res.groups'),
        ], limit=1)

        if existing_imd:
            group = Group.browse(existing_imd.res_id)
            if group.exists():
                # Group exists and is valid -- just link it
                self.access_group_xmlid = xmlid_full
                return
            # Stale ir.model.data pointing to deleted group -- clean up
            existing_imd.unlink()

        # Create the security group inheriting from Portal
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        group_vals = {
            'name': '%s Portal User' % self.name,
            'comment': (
                'Auto-created access group for the %s app (%s.* subdomain). '
                'Assign this group to portal users who need access.'
            ) % (self.name, self.app_key),
        }
        if portal_group:
            group_vals['implied_ids'] = [(4, portal_group.id)]
        group = Group.create(group_vals)

        # Register a stable XML ID with noupdate=True so -u never deletes it
        IMD.create({
            'module': 'posterra_portal',
            'name': xmlid_name,
            'model': 'res.groups',
            'res_id': group.id,
            'noupdate': True,
        })

        self.access_group_xmlid = xmlid_full
