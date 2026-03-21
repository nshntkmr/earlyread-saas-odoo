"""Save match_column values before the ORM drops the column."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Check if the old column exists
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'hha_scope_group' AND column_name = 'match_column'
    """)
    if not cr.fetchone():
        _logger.info('match_column already removed — skipping pre-migrate.')
        return

    _logger.info('Saving match_column values to _legacy_match_column...')
    cr.execute("""
        ALTER TABLE hha_scope_group
        ADD COLUMN IF NOT EXISTS _legacy_match_column VARCHAR
    """)
    cr.execute("""
        UPDATE hha_scope_group
        SET _legacy_match_column = match_column
        WHERE match_column IS NOT NULL
    """)
