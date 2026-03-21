"""19.0.1.2.1 post-migrate — set width_pct from col_span for existing widgets."""
import logging

_logger = logging.getLogger(__name__)

_MAP = {'3': 25, '4': 33, '6': 50, '8': 67, '12': 100}


def migrate(cr, version):
    if not version:
        return

    # Populate width_pct from col_span for existing widgets
    # (only if width_pct column exists and is 0/NULL)
    cr.execute("""
        SELECT column_name FROM information_schema.columns
         WHERE table_name = 'dashboard_widget' AND column_name = 'width_pct'
    """)
    if cr.fetchone():
        for sel_key, pct in _MAP.items():
            cr.execute(
                "UPDATE dashboard_widget SET width_pct = %s "
                "WHERE col_span = %s AND (width_pct IS NULL OR width_pct = 0)",
                (pct, sel_key),
            )
        _logger.info('Populated width_pct from col_span for existing widgets')
