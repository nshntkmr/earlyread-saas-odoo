# -*- coding: utf-8 -*-

import base64
import csv
import io
import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Mapping from CSV column headers to hha.provider field names
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

        missing_required = []
        for required_col in ['HHA CCN', 'HHA Name']:
            if required_col not in reader.fieldnames:
                missing_required.append(required_col)
        if missing_required:
            raise UserError(
                _("Missing required columns: %s\n\nFound columns: %s")
                % (', '.join(missing_required), ', '.join(reader.fieldnames))
            )

        Provider = self.env['hha.provider']
        created_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is headers
            try:
                # Map CSV columns to model fields
                vals = {}
                for csv_col, field_name in CSV_FIELD_MAP.items():
                    value = row.get(csv_col, '').strip()
                    if value:
                        vals[field_name] = value

                if not vals.get('hha_ccn'):
                    skipped_count += 1
                    continue

                # Check if provider already exists
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
                errors.append(_("Row %d (CCN: %s): %s") % (row_num, row.get('HHA CCN', '?'), str(e)))
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
