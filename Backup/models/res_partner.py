# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    hha_provider_id = fields.Many2one(
        'hha.provider', string='HHA Provider',
        help='The Home Health Agency this partner is associated with',
        index=True,
    )
    is_posterra_user = fields.Boolean(
        'Posterra User',
        compute='_compute_is_posterra_user', store=True,
    )

    @api.depends('hha_provider_id')
    def _compute_is_posterra_user(self):
        for partner in self:
            partner.is_posterra_user = bool(partner.hha_provider_id)
