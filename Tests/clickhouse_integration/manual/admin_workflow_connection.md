# Admin Workflow — Adding a ClickHouse Connection

Walks an admin through registering a new ClickHouse cluster end-to-end.
Phase 1 ships steps 1–3; steps 4+ become available with later phases.

## Prerequisites

- You are a member of the **Dashboard Builder Admin** group (or are a
  system administrator).
- The Odoo host has `clickhouse-connect` installed (`pip install
  clickhouse-connect`). If missing, the form still saves but the **Test
  Connection** button surfaces a clear "not installed" error.
- The CH cluster is reachable from the Odoo host (firewall, DNS, TLS
  cert valid).
- A CH user (e.g. `app_user`) exists on the cluster with SELECT grants
  on the schemas you want to expose.

## Step 1 — Store the password in `ir.config_parameter`

Passwords are NEVER stored on the connection record itself. The
connection only holds a *reference* to a config-parameter key. Set the
actual password once via the Odoo shell:

```python
self.env['ir.config_parameter'].sudo().set_param(
    'clickhouse.password.prod',  # <- this is the key you'll reference
    '<the-actual-password>',
)
```

The key name is arbitrary — pick one per environment, e.g.
`clickhouse.password.prod`, `clickhouse.password.staging`.

## Step 2 — Create the connection

1. Navigate to **Dashboard Builder → Configuration → Database
   Connections** and click **New**.
2. Fill in:
   - **Display Name** — what other admins will see in dropdowns, e.g.
     `ClickHouse — Production`.
   - **Engine** — `ClickHouse`.
   - **Host** — `ch-prod.example.azure.com` (or your cluster's
     hostname).
   - **Port** — `8443` (HTTPS). The Odoo addon uses
     `clickhouse-connect`, which is HTTP-only — it cannot use the
     native-TCP TLS port `9440`. Reserve `9440` for `clickhouse-client`
     CLI smoke testing only.
   - **Database** — the default database for queries that don't qualify
     a schema, e.g. `posterra_analytics`.
   - **Username** — `app_user`.
   - **Password Config Key** — the key you set in Step 1, e.g.
     `clickhouse.password.prod`.
   - **Use TLS** — leave checked for any production cluster.
   - **Enforce Tenant Filter** — leave checked. Only disable for admin
     tooling that legitimately reads cross-tenant data.
   - **Query Timeout (seconds)** — `30` is a reasonable default for
     interactive dashboards.
3. Click **Save**.

## Step 3 — Test the connection

Click the **Test Connection** button at the top of the form. The Odoo
notification will turn green if the cluster is reachable and the user/
password are valid. Red errors include the underlying exception
message (truncated to 200 chars). The result and timestamp are stored
on the record so you can audit when it last passed.

If the test fails:
- **`clickhouse-connect is not installed`** — install on the Odoo
  host: `pip install clickhouse-connect`. Restart Odoo.
- **TLS / certificate error** — confirm the CH cluster's cert chain is
  trusted by the Odoo host's CA bundle.
- **Authentication failure** — confirm the password in
  `ir.config_parameter` matches what the cluster expects.
- **Network timeout** — confirm firewall rules and the host's DNS
  resolution.

## Step 4 — Point a schema source at the connection (Phase 3+)

Once Phase 3 ships:

1. Open **Dashboard Builder → Configuration → Schema Sources** and
   click **New** (or open an existing source).
2. In the **Connection** dropdown, pick your new connection.
3. Set **Table Name** to the CH-side table, e.g.
   `gold.mv_hha_summary` (or just `mv_hha_summary` if your connection's
   default database is `gold`).
4. Click **Discover Columns**. The platform queries CH's
   `system.columns` and creates `dashboard.schema.column` rows with
   normalised types (`text`, `integer`, `float`, `date`, `boolean`).
5. Configure column intelligence on the **AI Intelligence** tab as you
   would for a Postgres source — dialect-agnostic.

## Step 5 — Build widgets and filters (Phase 3+)

When you create a new widget or filter, the Schema Source dropdown
shows both Postgres-backed and ClickHouse-backed sources. Pick yours,
write SQL using the same `%(param)s` placeholder syntax as before —
the executor translates to ClickHouse's `{name:Type}` format
automatically.

## Rotating the password

1. Update the value in `ir.config_parameter`:
   ```python
   self.env['ir.config_parameter'].sudo().set_param(
       'clickhouse.password.prod', '<new-password>')
   ```
2. Open any connection record that uses this key, click **Save** (no
   field changes needed). The save invalidates the cached client; the
   next query opens a fresh connection with the new password.
3. Click **Test Connection** to confirm the new password works.

## Disabling a connection

Set **Active** to off. Existing schema sources pointing at the
connection start surfacing per-widget errors (clear, contained — not
500 pages). Re-enable when ready.

## Deleting a connection

Schema sources with `connection_id` referencing the connection block
deletion (`ondelete='restrict'`). Migrate or delete those sources
first, then unlink. The unlink hook clears any cached client.
