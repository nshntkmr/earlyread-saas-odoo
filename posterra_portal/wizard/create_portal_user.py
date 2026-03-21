from odoo import models, fields, api

class PosterraCreatePortalUser(models.TransientModel):
    _name = 'posterra.create.portal.user'
    _description = 'Create Portal User Wizard'

    partner_ids = fields.Many2many('res.partner', string='Partners')
    hha_scope_group_id = fields.Many2one(
        'hha.scope.group', string='HHA Scope Group',
        help='Optional: assign all created users to this scope group.',
    )
    app_ids = fields.Many2many(
        'saas.app',
        string='Portal Apps',
        help='Select which apps these users will be able to sign into. '
             'The corresponding security groups are assigned automatically.',
    )
    send_email = fields.Boolean('Send Email Notification', default=True)

    def action_create_portal_users(self):
        portal_group = self.env.ref('base.group_portal')
        for partner in self.partner_ids:
            if not partner.email:
                continue

            # Create user if not exists, otherwise ensure portal group.
            # In Odoo 19, groups_id is not writable on res.users directly;
            # group membership is managed from the res.groups side.
            user = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
            if not user:
                user = self.env['res.users'].create({
                    'name': partner.name,
                    'login': partner.email,
                    'email': partner.email,
                    'partner_id': partner.id,
                })
            if user not in portal_group.user_ids:
                portal_group.write({'user_ids': [(4, user.id)]})

            # Assign scope group if provided and not already set
            if self.hha_scope_group_id and not partner.hha_scope_group_id:
                partner.write({'hha_scope_group_id': self.hha_scope_group_id.id})

            # Assign app access — partner.write() triggers group auto-sync
            if self.app_ids:
                partner.write({'portal_app_ids': [(4, app.id) for app in self.app_ids]})

            if self.send_email:
                user.action_reset_password()

        return {'type': 'ir.actions.act_window_close'}
