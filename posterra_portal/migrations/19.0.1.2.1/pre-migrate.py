"""19.0.1.2.1 pre-migrate — repair col_span if a prior failed migration
left it as integer.  Restore it to varchar so the ORM Selection field works."""
import logging

_logger = logging.getLogger(__name__)

_REVERSE_MAP = {25: '3', 33: '4', 50: '6', 67: '8', 100: '12'}


def _repair_col_span(cr, table, col):
    """If a previous failed migration converted the column to integer,
    convert it back to varchar and map values to Selection keys."""
    cr.execute("""
        SELECT data_type FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, col))
    row = cr.fetchone()
    if not row:
        return
    if row[0] == 'integer':
        _logger.info('Repairing %s.%s from integer back to varchar', table, col)
        tmp = col + '_char'
        cr.execute(f'ALTER TABLE "{table}" ADD COLUMN "{tmp}" varchar')
        for int_val, sel_key in _REVERSE_MAP.items():
            cr.execute(
                f'UPDATE "{table}" SET "{tmp}" = %s WHERE "{col}" = %s',
                (sel_key, int_val),
            )
        # Default unmapped rows to '6' (50%)
        cr.execute(f"UPDATE \"{table}\" SET \"{tmp}\" = '6' WHERE \"{tmp}\" IS NULL")
        cr.execute(f'ALTER TABLE "{table}" DROP COLUMN "{col}"')
        cr.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{tmp}" TO "{col}"')


def migrate(cr, version):
    if not version:
        return
    _repair_col_span(cr, 'dashboard_widget', 'col_span')
    _repair_col_span(cr, 'dashboard_widget_definition', 'default_col_span')
