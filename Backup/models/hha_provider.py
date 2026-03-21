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

    @api.depends('hha_dba', 'hha_name')
    def _compute_domain_match_name(self):
        """Priority: HHA DBA (if not null) → HHA Name.

        HHA Brand Name is intentionally excluded from this cascade.
        The email domain (e.g. 'elaracaring' from 'john@elaracaring.com')
        is matched against the normalised value of this field.
        """
        for record in self:
            record.domain_match_name = record.hha_dba or record.hha_name

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
        'john@elaracaring.com') and searches for providers whose
        domain_match_name matches (normalized, case-insensitive).

        The domain_match_name field uses: HHA DBA if set, otherwise HHA Name.
        """
        email = (email or '').lower().strip()
        if '@' not in email:
            return self.browse()

        domain_part = email.split('@')[1]  # elaracaring.com
        domain_name = domain_part.split('.')[0]  # elaracaring
        normalized_domain = re.sub(r'[^a-z0-9]', '', domain_name)

        if not normalized_domain:
            return self.browse()

        # Search all providers and filter by normalized prefix match.
        #
        # We use startswith() instead of equality so that brand variants are
        # automatically included.  Examples for domain 'elaracaring':
        #
        #   domain_match_name          normalised            match?
        #   ──────────────────────     ────────────────────  ──────
        #   ELARA CARING               elaracaring           ✓  (exact)
        #   ELARA CARING XVIII         elaracaringxviii      ✓  (prefix)
        #   ELARA CARING PARTNERS      elaracaringpartners   ✓  (prefix)
        #   SOME OTHER COMPANY         someothercompany      ✗
        #
        # The reverse is also safe: a user with @elaracaringxviii.com will only
        # match records whose normalised name starts with 'elaracaringxviii',
        # so 'elaracaring' (base brand) is NOT included for them.
        candidates = self.sudo().search([
            ('domain_match_name', '!=', False),
        ])
        matched = candidates.filtered(
            lambda p: re.sub(r'[^a-z0-9]', '', (p.domain_match_name or '').lower()).startswith(normalized_domain)
        )
        return matched
