"""19.0.1.3.0 pre-migrate — convert ``dashboard_connection.port`` from
integer to varchar.

Originally typed ``fields.Integer`` so Odoo's form widget formatted the
value with the user's locale thousands separator (port 8443 displayed
as ``8,443`` / ``8.443`` — confusing for admins entering connection
details). The ``options='{"format": false}'`` view escape hatch isn't
honoured consistently across Odoo versions, so we move to ``Char``
which Odoo never reformats.

The executor's ``_coerce_port`` helper int-converts the value before
passing to ``clickhouse-connect``, so the runtime contract is unchanged.

Idempotent: skips if the column is already varchar (fresh installs at
19.0.1.3.0+ create it as varchar from the field definition; only
upgrades from earlier versions need the cast).
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute("""
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = 'dashboard_connection'
           AND column_name = 'port'
    """)
    row = cr.fetchone()
    if not row:
        # Table doesn't have the column yet — fresh-ish install,
        # field will be created as varchar by the model.
        _logger.info('dashboard_connection.port not found; nothing to migrate.')
        return

    if row[0] in ('integer', 'smallint', 'bigint'):
        _logger.info(
            'Converting dashboard_connection.port from %s to varchar(5).',
            row[0],
        )
        cr.execute("""
            ALTER TABLE dashboard_connection
              ALTER COLUMN port TYPE varchar(5)
              USING port::varchar
        """)
    elif row[0] in ('character varying', 'character', 'text'):
        _logger.info(
            'dashboard_connection.port already %s; no migration needed.',
            row[0],
        )
    else:
        _logger.warning(
            'dashboard_connection.port is unexpected type %s; skipping.',
            row[0],
        )
