# -*- coding: utf-8 -*-

import re

from odoo import models, fields, api


class HHAProvider(models.Model):
    _name = 'hha.provider'
    _description = 'HHA Provider'
    _rec_name = 'hha_name'

    hha_ccn = fields.Char('HHA CCN', required=True, index=True)
    hha_name = fields.Char('HHA Name', required=True)
    hha_brand_name = fields.Char('Brand Name', index=True)

    domain_match_name = fields.Char(
        string='Domain Match Name',
        compute='_compute_domain_match_name',
        store=True,
        help="Name used for email domain validation: HHA DBA if set, otherwise HHA Name."
    )

    @api.depends('hha_dba', 'hha_brand_name', 'hha_name')
    def _compute_domain_match_name(self):
        """Priority: HHA DBA (if not null) → HHA Brand Name → HHA Name.

        Used by the Scope Group matching system to determine a provider's
        canonical identity for group-based access resolution.
        """
        for record in self:
            record.domain_match_name = (
                record.hha_dba or record.hha_brand_name or record.hha_name
            )

    @api.depends('hha_ccn', 'hha_name')
    def _compute_display_name(self):
        """Display as 'CCN - HHA Name' for dropdowns and selectors."""
        for rec in self:
            if rec.hha_ccn and rec.hha_name:
                rec.display_name = f"{rec.hha_ccn} - {rec.hha_name}"
            else:
                rec.display_name = rec.hha_name or rec.hha_ccn or ''

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """Search by CCN, HHA Name, Brand Name, or DBA in dropdown fields."""
        domain = domain or []
        if name:
            domain = ['|', '|', '|',
                       ('hha_ccn', operator, name),
                       ('hha_name', operator, name),
                       ('hha_brand_name', operator, name),
                       ('hha_dba', operator, name),
                       ] + domain
        return self._search(domain, limit=limit, order=order)

    # Owner Info
    hha_id_owner = fields.Char('Owner ID')
    hha_name_owner = fields.Char('Owner Name')
    hha_dba_owner = fields.Char('Owner DBA')

    # Details
    hha_npi = fields.Char('NPI')
    hha_id = fields.Char('HHA ID')
    hha_dba = fields.Char('DBA')
    hha_address = fields.Char('Address')
    hha_city = fields.Char('City')
    hha_zip = fields.Char('Zip')
    hha_state = fields.Char('State')
    hha_state_cd = fields.Char('State Code')
    hha_county = fields.Char('County')
    hha_fips = fields.Char('FIPS')
    hha_cbsa = fields.Char('CBSA')
    hha_rating = fields.Char('Rating')
    hha_auth_person = fields.Char('Auth Person')
    hha_auth_person_desgn = fields.Char('Auth Person Designation')
    hha_auth_person_tele = fields.Char('Auth Person Telephone')

    partner_ids = fields.One2many('res.partner', 'hha_provider_id', string='Associated Partners')

    @api.model
    def find_by_email_domain(self, email):
        """Find all HHA providers matching an email domain.

        Extracts the domain part from the email (e.g. 'elaracaring' from
        'john@elaracaring.com') and searches for providers whose RLS match
        field matches (normalized, case-insensitive prefix).

        The match field is admin-configurable via the system parameter
        ``posterra_portal.rls_match_field`` (default: ``domain_match_name``).
        """
        email = (email or '').lower().strip()
        if '@' not in email:
            return self.browse()

        domain_part = email.split('@')[1]  # elaracaring.com
        domain_name = domain_part.split('.')[0]  # elaracaring
        normalized_domain = re.sub(r'[^a-z0-9]', '', domain_name)

        if not normalized_domain:
            return self.browse()

        # Admin-configurable RLS field (Settings → Posterra → RLS Match Field)
        match_field = (
            self.env['ir.config_parameter'].sudo()
                .get_param('posterra_portal.rls_match_field', 'domain_match_name')
        )
        if match_field not in self._fields:
            match_field = 'domain_match_name'

        candidates = self.sudo().search([
            (match_field, '!=', False),
        ])
        matched = candidates.filtered(
            lambda p: re.sub(
                r'[^a-z0-9]', '',
                (getattr(p, match_field, '') or '').lower(),
            ).startswith(normalized_domain)
        )
        return matched
