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
