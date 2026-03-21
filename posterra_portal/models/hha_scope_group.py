# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HHAScopeGroup(models.Model):
    _name = 'hha.scope.group'
    _description = 'HHA Scope Group'
    _rec_name = 'name'

    name = fields.Char(required=True)
    match_field_ids = fields.One2many(
        'hha.scope.group.match.field', 'scope_group_id',
        string='Match Fields',
        help='Ordered list of fields to match against. '
             'The system tries each field in sequence order and returns '
             'the first set of matching providers.',
    )
    match_value = fields.Char(string='Match Value')
    match_mode = fields.Selection([
        ('exact', 'Exact Match'),
        ('starts_with', 'Starts With'),
        ('contains', 'Contains'),
    ], default='exact', required=True, string='Match Mode')
    auto_resolve = fields.Boolean(
        default=True,
        help='Auto-compute matched providers from match fields + value. '
             'Turn off to manually curate the provider list.',
    )
    provider_ids = fields.Many2many(
        'hha.provider',
        'hha_scope_group_provider_rel',
        'scope_group_id', 'provider_id',
        string='Matched Providers',
    )
    provider_count = fields.Integer(
        compute='_compute_provider_count', store=True,
    )
    partner_ids = fields.One2many(
        'res.partner', 'hha_scope_group_id', string='Assigned Users',
    )
    user_count = fields.Integer(compute='_compute_user_count')

    @api.depends('provider_ids')
    def _compute_provider_count(self):
        for rec in self:
            rec.provider_count = len(rec.provider_ids)

    def _compute_user_count(self):
        for rec in self:
            rec.user_count = len(rec.partner_ids)

    def _search_by_field(self, column, value):
        """Search hha.provider using the given column, value, and match_mode."""
        Provider = self.env['hha.provider'].sudo()
        if self.match_mode == 'exact':
            return Provider.search([(column, '=ilike', value)])
        elif self.match_mode == 'starts_with':
            return Provider.search([(column, '=ilike', value + '%')])
        else:  # contains
            return Provider.search([(column, 'ilike', value)])

    def _resolve_providers(self):
        """Find hha.provider records matching the configured fields + value + mode.

        Iterates match_field_ids in sequence order and returns the first
        non-empty result set (priority cascade).
        """
        self.ensure_one()
        if not self.match_value or not self.match_field_ids:
            return self.env['hha.provider']

        Provider = self.env['hha.provider'].sudo()
        value = self.match_value.strip()

        for mf in self.match_field_ids.sorted('sequence'):
            # Only match against hha.provider fields
            if mf.field_id.model != 'hha.provider':
                continue
            column = mf.field_id.name
            if column not in Provider._fields:
                continue
            result = self._search_by_field(column, value)
            if result:
                return result

        return self.env['hha.provider']

    def action_resolve_providers(self):
        """Button action: re-resolve providers from match criteria."""
        for rec in self:
            if rec.auto_resolve:
                rec.provider_ids = rec._resolve_providers()

    def action_view_users(self):
        """Open list of partners assigned to this scope group."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Users — {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('hha_scope_group_id', '=', self.id)],
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered('auto_resolve')._auto_resolve_providers()
        return records

    def write(self, vals):
        res = super().write(vals)
        trigger_fields = {'match_field_ids', 'match_value', 'match_mode', 'auto_resolve'}
        if trigger_fields & set(vals):
            self.filtered('auto_resolve')._auto_resolve_providers()
        return res

    def _auto_resolve_providers(self):
        """Server-side auto-resolve: called on create/write so providers persist."""
        for rec in self:
            rec.provider_ids = rec._resolve_providers()

    @api.onchange('match_field_ids', 'match_value', 'match_mode', 'auto_resolve')
    def _onchange_match_fields(self):
        if self.auto_resolve and self.match_field_ids and self.match_value:
            self.provider_ids = self._resolve_providers()
