# -*- coding: utf-8 -*-
"""AI Assist API-key issuance.

Desktop MCP clients (Claude Desktop / ChatGPT Desktop) authenticate to the
AI gateway with a long-lived per-person API key. We reuse Odoo core's
``res.users.apikeys`` (salted-hashed at rest, revocable per key from the
user's Account Security page) with the dedicated scope ``'posterra_ai'`` —
a key minted here cannot be replayed against XML-RPC (scope ``'rpc'``) and
vice versa.

Issuance is admin-driven via a small wizard (button on the user form)
instead of Odoo's stock new-key dialog, because the stock dialog cannot set
a custom scope and internal users shouldn't have to know about scopes at
all. The wizard shows the key exactly once; only the hash is stored.
"""

from odoo import fields, models
from odoo.exceptions import UserError

AI_APIKEY_SCOPE = 'posterra_ai'


class ResUsersAiExt(models.Model):
    _inherit = 'res.users'

    def action_open_ai_key_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ai.apikey.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_user_id': self.id},
        }


class AiApiKeyWizard(models.TransientModel):
    _name = 'ai.apikey.wizard'
    _description = 'Generate AI Assist API Key'

    user_id = fields.Many2one('res.users', required=True, string='For User')
    name = fields.Char(
        string='Key Label', required=True,
        default=lambda self: 'AI Assist key %s' % fields.Date.today())
    expires_days = fields.Integer(
        string='Expires in (days)', default=90,
        help='0 = no expiry (not recommended).')
    key = fields.Char(readonly=True, string='API Key')

    def action_generate(self):
        self.ensure_one()
        if not (self.env.user.has_group('base.group_system')
                or self.env.user.has_group('posterra_portal.group_posterra_admin')):
            raise UserError('Only administrators may issue AI Assist keys.')
        if not self.user_id.active:
            raise UserError('Cannot issue a key for an archived user.')
        expiration = False
        if self.expires_days and self.expires_days > 0:
            expiration = fields.Datetime.add(
                fields.Datetime.now(), days=self.expires_days)
        # with_user only — _generate creates the key for env.user, so a
        # trailing sudo() would mint it for the superuser instead.
        Apikeys = self.env['res.users.apikeys'].with_user(self.user_id)
        # Odoo 17+ _generate takes (scope, name, expiration_date); guard the
        # call so an older/newer core signature degrades cleanly.
        try:
            key = Apikeys._generate(AI_APIKEY_SCOPE, self.name, expiration)
        except TypeError:
            key = Apikeys._generate(AI_APIKEY_SCOPE, self.name)
        self.key = key
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
