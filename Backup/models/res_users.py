# -*- coding: utf-8 -*-

from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    hha_provider_id = fields.Many2one(
        related='partner_id.hha_provider_id',
        string='HHA Provider', readonly=True, store=True,
    )
