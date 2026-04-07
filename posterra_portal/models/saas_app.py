# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaaSApp(models.Model):
    _name        = 'saas.app'
    _description = 'SaaS Application'
    _rec_name    = 'name'
    _order       = 'name asc'

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

    # ── Relationships ────────────────────────────────────────────────────────
    page_ids   = fields.One2many('dashboard.page', 'app_id', string='Pages')
    page_count = fields.Integer(compute='_compute_page_count', string='Page Count')

    # ── Computed ─────────────────────────────────────────────────────────────
    @api.depends('page_ids')
    def _compute_page_count(self):
        for app in self:
            app.page_count = len(app.page_ids)

    # ── Constraints ──────────────────────────────────────────────────────────
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
        records = super().create(vals_list)
        for app in records:
            if app.access_mode == 'group' and app._needs_access_group():
                app._ensure_access_group()
        return records

    def write(self, vals):
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
                'Auto-created access group for the %s app (/my/%s). '
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
