"""19.0.1.2.0 pre-migrate — drop the obsolete global UNIQUE on
``dashboard_schema_source.table_name``.

Phase 1 of the ClickHouse integration replaced this constraint with a
Python ``@api.constrains`` on ``(connection_id, table_name)`` so the
same physical table name can exist on multiple backends (e.g. local
Postgres ``hha_provider`` AND a CH-side ``shared.hha_provider``).
Removing the constraint from ``_sql_constraints`` does NOT make Odoo
drop the existing constraint from upgraded databases — it has to come
out explicitly here.

Idempotent: ``DROP CONSTRAINT IF EXISTS`` is safe on databases that
were freshly installed at 19.0.1.2.0+ (no constraint to drop).

Pre-migrate (rather than post-migrate) so the constraint is gone before
any seed data load could exercise the new uniqueness rule and trip on
the old one.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Odoo names SQL constraints ``<table>_<constraint_key>``; the
    # constraint we want to drop was declared as
    # ``('table_name_uniq', 'unique(table_name)', ...)`` on
    # ``dashboard.schema.source``, so the actual Postgres constraint
    # name is ``dashboard_schema_source_table_name_uniq``.
    cr.execute("""
        SELECT conname
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
         WHERE t.relname = 'dashboard_schema_source'
           AND c.contype = 'u'
           AND c.conname = 'dashboard_schema_source_table_name_uniq'
    """)
    if cr.fetchone():
        _logger.info(
            'Dropping obsolete global UNIQUE on dashboard_schema_source'
            '.table_name; per-connection uniqueness now enforced via '
            '@api.constrains.'
        )
        cr.execute(
            'ALTER TABLE dashboard_schema_source '
            'DROP CONSTRAINT IF EXISTS '
            'dashboard_schema_source_table_name_uniq'
        )
    else:
        _logger.info(
            'No legacy global UNIQUE on dashboard_schema_source.table_name '
            'to drop (fresh install or already migrated).'
        )
