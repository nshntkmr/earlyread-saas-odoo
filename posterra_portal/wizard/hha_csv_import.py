# -*- coding: utf-8 -*-

import base64
import csv
import io
import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Primary mapping from CSV column headers to hha.provider field names.
# This is checked first for an exact match.
CSV_FIELD_MAP = {
    'HHA CCN': 'hha_ccn',
    'HHA Brand Name': 'hha_brand_name',
    'HHA ID Owner': 'hha_id_owner',
    'HHA Name Owner': 'hha_name_owner',
    'HHA DBA Owner': 'hha_dba_owner',
    'HHA NPI': 'hha_npi',
    'HHA ID': 'hha_id',
    'HHA Name': 'hha_name',
    'HHA DBA': 'hha_dba',
    'HHA Address': 'hha_address',
    'HHA City': 'hha_city',
    'HHA Zip': 'hha_zip',
    'HHA Fips': 'hha_fips',
    'HHA County': 'hha_county',
    'HHA State': 'hha_state',
    'HHA State Cd': 'hha_state_cd',
    'HHA CBSA': 'hha_cbsa',
    'HHA Rating': 'hha_rating',
    'HHA Auth Person': 'hha_auth_person',
    'HHA Auth Person Desgn': 'hha_auth_person_desgn',
    'HHA Auth Person Tele': 'hha_auth_person_tele',
}

# Alternative / alias column names used by CMS and other standard datasets.
# Applied only when the primary column is absent from the CSV.
# Each entry is (alias_col_name, target_field_name).
CSV_COLUMN_ALIASES = [
    # County — CMS Home Health Compare uses "County Name" instead of "HHA County"
    ('County Name',  'hha_county'),
    ('County',       'hha_county'),
    # State — some exports use the full state name column
    ('State Name',   'hha_state'),
    ('Provider State', 'hha_state'),
    ('State',        'hha_state'),
    # City
    ('City',         'hha_city'),
    ('Provider City', 'hha_city'),
    # Zip
    ('Zip Code',     'hha_zip'),
    ('ZIP Code',     'hha_zip'),
    ('Zip',          'hha_zip'),
    # FIPS
    ('FIPS',         'hha_fips'),
    ('County FIPS',  'hha_fips'),
    # CCN / Provider ID
    ('CMS Certification Number (CCN)', 'hha_ccn'),
    ('Provider ID', 'hha_ccn'),
    # Provider name
    ('Agency Name',  'hha_name'),
    ('Provider Name', 'hha_name'),
    # Address
    ('Address',      'hha_address'),
    ('Provider Address', 'hha_address'),
]


class HHACsvImport(models.TransientModel):
    _name = 'hha.csv.import'
    _description = 'Import HHA Provider Data from CSV'

    csv_file = fields.Binary('CSV File', required=True)
    csv_filename = fields.Char('Filename')
    update_existing = fields.Boolean(
        'Update Existing Records',
        default=True,
        help='If checked, existing providers (matched by HHA CCN) will be updated with new data. '
             'If unchecked, existing records will be skipped.',
    )

    def action_import(self):
        self.ensure_one()
        if not self.csv_file:
            raise UserError(_("Please upload a CSV file."))

        # Decode the base64 file
        try:
            csv_data = base64.b64decode(self.csv_file).decode('utf-8-sig')
        except Exception as e:
            raise UserError(_("Could not read the CSV file: %s") % str(e))

        reader = csv.DictReader(io.StringIO(csv_data))

        # Validate headers
        if not reader.fieldnames:
            raise UserError(_("The CSV file appears to be empty or has no headers."))

        fieldnames_set = set(reader.fieldnames)

        # Build effective field map: start with primary map, then fill gaps
        # from aliases for columns that are absent from the CSV.
        effective_map = dict(CSV_FIELD_MAP)
        already_mapped = set(effective_map.values())  # fields already covered
        for alias_col, target_field in CSV_COLUMN_ALIASES:
            if alias_col in fieldnames_set and target_field not in already_mapped:
                effective_map[alias_col] = target_field
                already_mapped.add(target_field)
                _logger.info(
                    'HHA CSV import: using alias column %r for field %r',
                    alias_col, target_field,
                )

        # Determine which column will supply the CCN (required)
        ccn_col = 'HHA CCN' if 'HHA CCN' in fieldnames_set else None
        if not ccn_col:
            # Check aliases
            for alias_col, target_field in CSV_COLUMN_ALIASES:
                if alias_col in fieldnames_set and target_field == 'hha_ccn':
                    ccn_col = alias_col
                    break

        if not ccn_col:
            raise UserError(
                _("Missing required column for Provider ID (CCN).\n"
                  "Expected one of: 'HHA CCN', 'CMS Certification Number (CCN)', 'Provider ID'\n\n"
                  "Found columns: %s")
                % ', '.join(reader.fieldnames)
            )

        Provider = self.env['hha.provider']
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is headers
            try:
                # Map CSV columns to model fields using the effective map
                vals = {}
                for csv_col, field_name in effective_map.items():
                    value = row.get(csv_col, '').strip()
                    if value:
                        vals[field_name] = value

                if not vals.get('hha_ccn'):
                    skipped_count += 1
                    continue

                # Check if provider already exists (match by CCN)
                existing = Provider.search([('hha_ccn', '=', vals['hha_ccn'])], limit=1)
                if existing:
                    if self.update_existing:
                        existing.write(vals)
                        updated_count += 1
                    else:
                        skipped_count += 1
                else:
                    Provider.create(vals)
                    created_count += 1

            except Exception as e:
                errors.append(_("Row %d (CCN: %s): %s") % (row_num, row.get(ccn_col, '?'), str(e)))
                if len(errors) > 50:
                    errors.append(_("... too many errors, stopping."))
                    break

        # Build result message
        message = _("Import completed:\n"
                     "- Created: %d\n"
                     "- Updated: %d\n"
                     "- Skipped: %d") % (created_count, updated_count, skipped_count)
        if errors:
            message += _("\n\nErrors (%d):\n%s") % (len(errors), '\n'.join(errors))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('HHA CSV Import'),
                'message': message,
                'type': 'warning' if errors else 'success',
                'sticky': bool(errors),
            },
        }
