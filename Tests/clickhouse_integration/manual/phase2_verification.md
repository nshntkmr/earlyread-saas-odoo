# Phase 2 Verification — Live ClickHouse Connectivity

Phase 2 acceptance: an admin can add a `dashboard.connection` pointing
at the Dev cluster, click **Test Connection**, see green. The CH
executor runs `SELECT 1` against real CH. No widget is wired up yet.

This checklist covers the manual steps you walk through against the
shared Dev cluster. Each box should produce a clean signal — green
notification, expected log line, or a `pytest` pass.

**Tester:** _____________________   **Date:** _____________________

**Cluster:** _____________________   **CH version:** ______________

---

## A. Cluster server-config prerequisite (one-time per cluster)

The addon uses the `SQL_tenant_id` per-query setting. ClickHouse only
permits custom settings whose prefix is declared in
`custom_settings_prefixes` at server level.

**Quick verify** — run from any client connected as a super-user;
should return `'42'`:

```sql
SELECT getSetting('SQL_tenant_id') SETTINGS SQL_tenant_id='42';
```

- [ ] Returns `'42'` → prefix is registered, skip the rest of this section
- [ ] Errors with `Setting SQL_tenant_id is neither a built-in
      setting nor started with the prefix...` → fix below

**On ClickHouse Cloud / Aiven / Azure Database for ClickHouse**:
`SQL_` may be pre-configured (varies by provider, tier, and region —
do not assume). If the quick verify above errors, contact provider
support to add `SQL_` to `custom_settings_prefixes`. This is a
server-level config and cannot be set via a profile.

**On self-managed ClickHouse**, add to `users.xml` (or a drop-in
under `config.d/`):

```xml
<yandex>
  <custom_settings_prefixes>SQL_</custom_settings_prefixes>
</yandex>
```

Apply: `SYSTEM RELOAD CONFIG;` then re-run the verify query above.

## B. Bootstrap DDL — load-bearing primitives (one-time per cluster)

Run on the cluster as a CH administrator. Subsequent re-runs are
idempotent. Note: the bootstrap does NOT create the `app_user` —
that's the next step, done manually with a password.

**Precondition before applying:** the `shared` database must exist
on this cluster. Database lifecycle is the data engineering team's
responsibility — the addon bootstrap doesn't create databases. CH
accepts grants on non-existent databases without raising, so a
missing `shared` schema would let the script "succeed" but the grant
would be dormant and fail later with "Unknown database" the first
time the addon queries `shared.dim_*`. Confirm before running:

- [ ] `SELECT name FROM system.databases WHERE name='shared'` returns
      one row. If empty, escalate to data engineering — do NOT
      `CREATE DATABASE shared` here as a workaround.

Then apply and verify:

- [ ] Apply `dashboard_builder/sql/clickhouse_bootstrap.sql`
- [ ] `SELECT name FROM system.roles WHERE name='app_role'` returns one row
- [ ] `SELECT name FROM system.settings_profiles WHERE name='app_profile'` returns one row
- [ ] `SELECT * FROM system.grants WHERE role_name='app_role'` shows
      SELECT only on `shared.*` (NOT on `silver.*` or `gold.*` — those
      come per-table paired with row policies, see section K)
- [ ] `app_user` does NOT yet exist:
      `SELECT count() FROM system.users WHERE name='app_user'` = 0

## C. Create the connecting user (manual, password-included)

Done as a separate step so the password is set atomically with
creation — no passwordless window where grants are exposed.

- [ ] Generate a strong password (e.g. via `openssl rand -base64 24`)
- [ ] Run on the cluster as admin:
      ```sql
      CREATE USER app_user
        IDENTIFIED BY '<the-password>'
        DEFAULT ROLE app_role
        SETTINGS PROFILE 'app_profile';
      ```
- [ ] Verify the user exists with the expected role:
      `SHOW GRANTS FOR app_user` lists the inherited `app_role` grants
- [ ] Smoke-test as `app_user` over HTTPS — same protocol Odoo will
      use via `clickhouse-connect`. Returns `1`:
      ```bash
      curl -u app_user:'<password>' --get \
           --data-urlencode 'query=SELECT 1' \
           https://<ch-host>:8443/
      ```
- [ ] Smoke-test the per-query setting (still over HTTPS). Returns `42`:
      ```bash
      curl -u app_user:'<password>' --get \
           --data-urlencode "query=SELECT getSetting('SQL_tenant_id') SETTINGS SQL_tenant_id='42'" \
           https://<ch-host>:8443/
      ```
      If this fails with "Setting SQL_tenant_id is neither a built-in
      setting...", section A's server-config step didn't take.

(Optional native-TCP CLI smoke test, only if you have
`clickhouse-client` installed locally — note port 9440, NOT what
Odoo uses:
`clickhouse-client --host <ch-host> --port 9440 --secure --user app_user --password '<...>' --query 'SELECT 1'`)

## D. Odoo host prerequisites

The Odoo addon connects via `clickhouse-connect`, which uses the
HTTPS interface on port `8443` (or HTTP on `8123` if TLS is
disabled). The native-TCP TLS port `9440` is **not** usable from
Odoo — it's a different protocol served by `clickhouse-driver` /
`clickhouse-client`.

- [ ] `pip install clickhouse-connect` succeeds in the Odoo virtualenv
      (or whichever environment Odoo workers run in)
- [ ] From the Odoo host, `curl -v https://<ch-host>:8443/ping`
      returns a 200 with body `Ok.`
- [ ] Network ACL / VPC peering / firewall: confirmed open from Odoo
      workers to CH on `8443`
- [ ] TLS cert chain validates against the Odoo host's CA bundle
      (self-signed certs on the cluster need the issuer added to the
      OS trust store; otherwise tests fail with `SSL: CERTIFICATE_VERIFY_FAILED`)

## E. Store the password in `ir.config_parameter`

The connection record holds a *reference* to a config-parameter key,
not the password itself.

- [ ] In the Odoo shell:
      ```python
      env['ir.config_parameter'].sudo().set_param(
          'clickhouse.password.dev',  # match the key you'll use on the connection
          '<the-password-from-step-C>',
      )
      ```
- [ ] Verify: `env['ir.config_parameter'].sudo().get_param('clickhouse.password.dev')` returns the password

## F. Create the connection in the admin UI

- [ ] Navigate to **Dashboard Builder → Configuration → Database Connections**
- [ ] Click **New** and fill in:
  - Display Name: `ClickHouse — Dev`
  - Engine: `ClickHouse`
  - Active: ☑ on
  - Enforce Tenant Filter: ☑ on
  - Host: `<ch-host>`
  - Port: `8443` — HTTPS, what `clickhouse-connect` uses. Do NOT
    enter `9440` here; that's the native TCP port and the addon
    cannot speak that protocol.
  - Database: `default` (or whatever the bootstrap-targeted db is)
  - Username: `app_user`
  - Password Config Key: `clickhouse.password.dev` (matches step E)
  - Use TLS: ☑ on
  - Query Timeout (seconds): `30`
- [ ] Click **Save** — record persists, no traceback in the server log
- [ ] Click **Test Connection** — green notification "Connection succeeded."
- [ ] Form's **Last Test** field reads "OK" with a recent timestamp

## G. Negative-path checks

- [ ] Edit the connection, change Host to `bogus.invalid`, save
- [ ] Click **Test Connection** — red `UserError` with a truncated
      error message (NOT a 500 page or stack trace)
- [ ] Form's **Last Test** field reads `FAIL: ...`
- [ ] Restore the original host, save, re-test — green again
- [ ] Set **Active** to off, save
- [ ] Click **Test Connection** in the form header — must show a
      red `UserError` whose message contains
      `Connection '<Display Name>' is inactive; enable it in
      Dashboard Builder → Configuration → Database Connections...`
      *(NOT a generic ping/auth failure. The inactive check fires
      from `action_test_connection` because it goes through
      `get_executor_for_connection`. The live pytest suite below
      instantiates `ClickHouseExecutor` directly and bypasses the
      check, so don't rely on pytest to verify this — the button is
      the only reliable path.)*
- [ ] Restore Active to on, save, click **Test Connection** again —
      green

## H. Cache invalidation

- [ ] With the connection active and Test passing, change the
      password in `ir.config_parameter` to a deliberately-wrong value
- [ ] Click **Test Connection** — should now FAIL (auto-invalidates
      cache before testing, picks up the new bad value)
- [ ] Restore the correct password in `ir.config_parameter`
- [ ] Click **Invalidate Cache** — green "Cached client dropped..." notification
- [ ] Click **Test Connection** — green again

## I. Live executor pytest suite

Set env vars and run the live suite. PowerShell is primary on this
Windows repo; Git Bash / WSL alternative below.

**PowerShell** (default):

```powershell
cd C:\Users\nisha\Odoo_Dev\Tests\clickhouse_integration
$env:CH_TEST_HOST     = '<ch-host>'
$env:CH_TEST_PORT     = '8443'
$env:CH_TEST_USER     = 'app_user'
$env:CH_TEST_PASSWORD = '<password-from-step-C>'
$env:CH_TEST_DATABASE = 'default'
python -m pytest integration/test_clickhouse_live.py -v
```

**Git Bash / WSL** (alternative):

```bash
cd /c/Users/nisha/Odoo_Dev/Tests/clickhouse_integration
CH_TEST_HOST=<ch-host> \
CH_TEST_PORT=8443 \
CH_TEST_USER=app_user \
CH_TEST_PASSWORD='<password-from-step-C>' \
CH_TEST_DATABASE=default \
python -m pytest integration/test_clickhouse_live.py -v
```

Note: `conftest.py` defaults `POSTERRA_ADDONS_ROOT` to
`C:\Users\nisha\Odoo_Dev` (the main work tree). If you're running
the suite against an unmerged worktree instead, set
`POSTERRA_ADDONS_ROOT=<path-to-worktree>` so the loader picks up
the right addon source.

- [ ] `TestClickHouseLivePing::test_ping_returns_true` — PASS
- [ ] `TestClickHouseLivePing::test_ping_after_invalidate` — PASS
- [ ] `TestClickHouseLiveExecute::test_select_one` — PASS
- [ ] `TestClickHouseLiveExecute::test_named_string_param` — PASS
- [ ] `TestClickHouseLiveExecute::test_named_int_param` — PASS
- [ ] `TestClickHouseLiveExecute::test_in_clause_array` — PASS
- [ ] `TestClickHouseLiveExecute::test_null_value` — PASS
- [ ] `TestClickHouseLiveExecute::test_select_only_validation` — PASS
- [ ] `TestClickHouseLiveExecute::test_blocked_keyword` — PASS
- [ ] `TestClickHouseLiveDiscoverColumns::test_discover_system_columns` — PASS
- [ ] `TestClickHouseLiveDiscoverColumns::test_discover_with_default_database` — PASS
- [ ] `TestClickHouseLiveTenantSetting::test_SQL_tenant_id_setting_round_trips` — PASS
      *(if this fails with "Cluster did not echo back tenant_id",
      either section A's server-config or section B's `app_profile`
      didn't take)*
- [ ] `TestClickHouseLiveTenantSetting::test_concurrent_tenant_isolation` — PASS
      *(regression test for the Codex-flagged race; if it fails,
      something's wrong with per-query settings binding)*

## J. Existing-PG-widget regression check

Phase 2 must not regress anything Phase 1 left working. Quick sanity:

- [ ] `/my/posterra` (or any browser URL pointing at an existing app)
      loads without error
- [ ] At least one PG-backed widget renders the same data as before
- [ ] Filter cascade on a PG-backed page still works
- [ ] No new WARNING/ERROR lines in the server log mentioning
      `clickhouse-connect`, `SQL_tenant_id`, or `query_executors`

## K. Per-table grant + row policy (informational, applies in Phase 3+)

For each tenant-scoped table the addon will read from, the cluster
admin must add BOTH a row policy AND a grant in one block — never
grant first and add the policy later. Section 4 of
`clickhouse_bootstrap.sql` has the template:

```sql
CREATE ROW POLICY OR REPLACE tenant_iso_<schema>_<table>
  ON <schema>.<table>
  FOR SELECT
  USING tenant_id = getSetting('SQL_tenant_id')
  TO app_role;
GRANT SELECT ON <schema>.<table> TO app_role;
```

Audit query — should always return zero rows:

```sql
SELECT g.access_type, g.database, g.table
  FROM system.grants g
  LEFT JOIN system.row_policies p
    ON p.database = g.database
   AND p.table = g.table
   AND has(p.apply_to_list, 'app_role')
 WHERE g.role_name = 'app_role'
   AND g.access_type = 'SELECT'
   AND g.database IN ('silver','gold')
   AND p.name IS NULL
 ORDER BY g.database, g.table;
```

This becomes a Phase 3+ checklist item per CH-backed table that gets
wired up. Ignore for Phase 2.

---

## Result

- [ ] PASS — Phase 2 done; ready to start Phase 3 (first CH-backed schema source)
- [ ] FAIL — record failures below; do NOT proceed to Phase 3 until resolved

**Failures (if any):**

```
(write here)
```

**Phase 3 prerequisite reminder:** before Phase 3 starts, the data
engineering pipeline must produce at least one CH table with a
populated `tenant_id` column AND that table must have its row policy
+ grant added per section K. The first CH-backed widget will read
from that table.
