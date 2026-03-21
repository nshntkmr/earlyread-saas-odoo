from odoo import models, fields, api

class PosterraCreatePortalUser(models.TransientModel):
    _name = 'posterra.create.portal.user'
    _description = 'Create Portal User Wizard'

    partner_ids = fields.Many2many('res.partner', string='Partners')
    send_email = fields.Boolean('Send Email Notification', default=True)
    
    def action_create_portal_users(self):
        portal_group = self.env.ref('base.group_portal')
        for partner in self.partner_ids:
            if not partner.email:
                continue
            
            # Check if user exists
            user = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
            if not user:
                user = self.env['res.users'].create({
                    'name': partner.name,
                    'login': partner.email,
                    'email': partner.email,
                    'partner_id': partner.id,
                    'groups_id': [(4, portal_group.id)],
                })
            elif portal_group not in user.groups_id:
                user.write({'groups_id': [(4, portal_group.id)]})
            
            if self.send_email:
                user.action_reset_password()

        return {'type': 'ir.actions.act_window_close'}