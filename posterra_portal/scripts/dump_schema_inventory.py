# Dump the full dashboard-builder schema-source inventory.
#
# Run on the Odoo host (Windows install):
#   cd "C:\Program Files\Odoo 19.0.20251113\server"
#   ..\python\python.exe odoo-bin shell -c odoo.conf -d <your-db-name> ^
#       < path\to\repo\posterra_portal\scripts\dump_schema_inventory.py
#
# (If odoo.conf sets db_name, the -d flag can be dropped. On Linux:
#   python3 odoo-bin shell -c odoo.conf -d <db> < posterra_portal/scripts/dump_schema_inventory.py)
#
# Prints a pipe-delimited inventory of every dashboard.schema.source —
# engine, connection, app mapping, PHI classification, column counts,
# AI-column-intelligence fill rate — followed by a full column dump for
# every source mapped to an app (so classification can be reviewed
# column by column). Read-only: no writes anywhere.

def _get(rec, field, default=''):
    return getattr(rec, field, default) or default


Source = env['dashboard.schema.source'].sudo()
sources = Source.search([], order='table_name')

print('\n===== SCHEMA SOURCE INVENTORY (%d sources) =====' % len(sources))
print('source_name | table_name | engine | connection | apps | classification'
      ' | active | cols | ai_filled')
for s in sources:
    conn = s.connection_id
    engine = _get(conn, 'engine', 'postgres_local') if conn else 'postgres_local'
    apps = ','.join(s.app_ids.mapped('app_key')) if _get(s, 'app_ids') else 'GLOBAL'
    cols = s.column_ids
    filled = len(cols.filtered(lambda c: _get(c, 'description')))
    print('%s | %s | %s | %s | %s | %s | %s | %d | %d' % (
        s.name, s.table_name, engine,
        conn.name if conn else 'local-pg',
        apps, _get(s, 'data_classification', 'n/a'),
        s.is_active, len(cols), filled))

app_scoped = sources.filtered(lambda s: _get(s, 'app_ids'))
print('\n===== COLUMN DETAIL (app-scoped sources: %d) =====' % len(app_scoped))
for s in app_scoped:
    print('\n--- %s (%s) apps=%s class=%s ---' % (
        s.table_name, s.name,
        ','.join(s.app_ids.mapped('app_key')),
        _get(s, 'data_classification', 'n/a')))
    for c in s.column_ids:
        print('  %s | %s | role=%s | measure=%s dim=%s | never_avg=%s'
              ' | desc=%s' % (
                  c.column_name, c.data_type,
                  _get(c, 'column_role', '-'),
                  c.is_measure, c.is_dimension,
                  _get(c, 'never_avg', False),
                  'Y' if _get(c, 'description') else 'N'))

Conn = env['dashboard.connection'].sudo()
print('\n===== CONNECTIONS =====')
for c in Conn.search([]):
    print('%s | engine=%s | active=%s | profile=%s | scoped_app=%s' % (
        c.name, c.engine, c.is_active,
        _get(c, 'security_profile', 'n/a'),
        _get(c, 'tenant_scope_app_id') and c.tenant_scope_app_id.app_key or '-'))
