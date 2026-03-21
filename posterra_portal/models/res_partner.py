# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    hha_provider_id = fields.Many2one(
        'hha.provider', string='HHA Provider',
        help='The Home Health Agency this partner is associated with',
        index=True,
    )
    hha_scope_group_id = fields.Many2one(
        'hha.scope.group', string='HHA Scope Group',
        help='Scope group that determines which HHA providers this user can access. '
             'Overridden by a direct HHA Provider assignment above.',
        index=True,
    )
    portal_app_ids = fields.Many2many(
        'saas.app',
        relation='res_partner_saas_app_rel',
        column1='partner_id',
        column2='app_id',
        string='Portal App Access',
        help='Apps this contact can sign into. Updating this list automatically '
             'adds/removes the corresponding security groups on the linked user.',
    )
    is_posterra_user = fields.Boolean(
        'Posterra User',
        compute='_compute_is_posterra_user', store=True,
    )

    @api.depends('hha_provider_id', 'hha_scope_group_id', 'portal_app_ids')
    def _compute_is_posterra_user(self):
        for partner in self:
            partner.is_posterra_user = bool(
                partner.hha_provider_id or partner.hha_scope_group_id or partner.portal_app_ids
            )

    # ── App-group sync helpers ────────────────────────────────────────────────

    def _get_app_required_groups(self, apps):
        """Return the union of security groups required by the given saas.app records."""
        groups = self.env['res.groups']
        hha_group = self.env.ref(
            'posterra_portal.group_posterra_user', raise_if_not_found=False)
        for app in apps:
            if app.access_mode == 'hha_provider' and hha_group:
                groups |= hha_group
            elif app.access_mode == 'group' and app.access_group_xmlid:
                try:
                    groups |= self.env.ref(app.access_group_xmlid)
                except ValueError:
                    pass
        return groups

    def _get_all_managed_app_groups(self):
        """All groups that any saas.app record could ever add or remove.

        Used to compute the set of groups that are safe to remove when
        portal_app_ids changes, without touching unrelated groups.
        """
        groups = self.env['res.groups']
        hha_group = self.env.ref(
            'posterra_portal.group_posterra_user', raise_if_not_found=False)
        if hha_group:
            groups |= hha_group
        for app in self.env['saas.app'].sudo().search([('access_mode', '=', 'group')]):
            if app.access_group_xmlid:
                try:
                    groups |= self.env.ref(app.access_group_xmlid)
                except ValueError:
                    pass
        return groups

    def write(self, vals):
        result = super().write(vals)
        if 'portal_app_ids' in vals:
            # Compute the full set of managed groups once (one DB query)
            all_managed = self._get_all_managed_app_groups()
            for partner in self:
                # Only sync portal (share=True) users — never touch internal users
                user = self.env['res.users'].sudo().search(
                    [('partner_id', '=', partner.id), ('share', '=', True)], limit=1)
                if not user:
                    continue
                required = partner._get_app_required_groups(partner.portal_app_ids)
                to_remove = all_managed - required
                # In Odoo 19 the field is user_ids on res.groups (not 'users').
                for group in to_remove:
                    group.sudo().write({'user_ids': [(3, user.id)]})
                for group in required:
                    group.sudo().write({'user_ids': [(4, user.id)]})
        return result

    # ── Wizard launcher ───────────────────────────────────────────────────────

    def action_open_create_portal_user_wizard(self):
        """Open the Create Portal User wizard pre-populated with this contact."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Portal User',
            'res_model': 'posterra.create.portal.user',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_ids': [(6, 0, [self.id])]},
        }
