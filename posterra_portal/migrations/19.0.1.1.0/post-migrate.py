"""Convert legacy match_column Selection to match_field_ids One2many records."""
import logging

_logger = logging.getLogger(__name__)

# Old 'domain_match_name' mapped to this cascade of real fields:
_AUTO_CASCADE = ['hha_dba', 'hha_brand_name', 'hha_name']

# Old single-column selections:
_SINGLE_FIELDS = {
    'hha_dba': 'hha_dba',
    'hha_brand_name': 'hha_brand_name',
    'hha_name': 'hha_name',
}


def migrate(cr, version):
    # Check if legacy column exists
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'hha_scope_group' AND column_name = '_legacy_match_column'
    """)
    if not cr.fetchone():
        _logger.info('No _legacy_match_column found — skipping post-migrate.')
        return

    cr.execute("""
        SELECT id, _legacy_match_column
        FROM hha_scope_group
        WHERE _legacy_match_column IS NOT NULL
    """)
    rows = cr.fetchall()
    if not rows:
        _logger.info('No legacy data to migrate.')
        _drop_legacy_column(cr)
        return

    from odoo import SUPERUSER_ID, api
    env = api.Environment(cr, SUPERUSER_ID, {})

    provider_model = env['ir.model'].search([('model', '=', 'hha.provider')], limit=1)
    if not provider_model:
        _logger.warning('ir.model record for hha.provider not found — cannot migrate.')
        return

    # Cache field lookups
    field_cache = {}
    for fname in set(_AUTO_CASCADE) | set(_SINGLE_FIELDS.values()):
        f = env['ir.model.fields'].search([
            ('model_id', '=', provider_model.id),
            ('name', '=', fname),
        ], limit=1)
        if f:
            field_cache[fname] = f.id

    MatchField = env['hha.scope.group.match.field']

    for scope_id, legacy_col in rows:
        if legacy_col == 'domain_match_name':
            # Create 3 ordered match fields (DBA→Brand→Name cascade)
            for seq, fname in enumerate(_AUTO_CASCADE, start=1):
                fid = field_cache.get(fname)
                if fid:
                    MatchField.create({
                        'scope_group_id': scope_id,
                        'sequence': seq * 10,
                        'model_id': provider_model.id,
                        'field_id': fid,
                    })
        elif legacy_col in _SINGLE_FIELDS:
            fname = _SINGLE_FIELDS[legacy_col]
            fid = field_cache.get(fname)
            if fid:
                MatchField.create({
                    'scope_group_id': scope_id,
                    'sequence': 10,
                    'model_id': provider_model.id,
                    'field_id': fid,
                })

    _logger.info('Migrated %d scope groups to match_field_ids.', len(rows))
    _drop_legacy_column(cr)


def _drop_legacy_column(cr):
    cr.execute('ALTER TABLE hha_scope_group DROP COLUMN IF EXISTS _legacy_match_column')
