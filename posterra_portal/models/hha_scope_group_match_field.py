# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HHAScopeGroupMatchField(models.Model):
    _name = 'hha.scope.group.match.field'
    _description = 'Scope Group Match Field'
    _order = 'sequence, id'

    scope_group_id = fields.Many2one(
        'hha.scope.group', required=True, ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    model_id = fields.Many2one(
        'ir.model', string='Table',
        default=lambda self: self.env['ir.model'].sudo().search(
            [('model', '=', 'hha.provider')], limit=1,
        ),
        ondelete='cascade',
        required=True,
    )
    field_id = fields.Many2one(
        'ir.model.fields', string='Column',
        domain="[('model_id', '=', model_id),"
               " ('ttype', 'in', ['char', 'text']),"
               " ('store', '=', True)]",
        ondelete='cascade',
        required=True,
    )

    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.field_id = False
