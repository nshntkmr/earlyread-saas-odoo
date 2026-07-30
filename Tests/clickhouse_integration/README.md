# ClickHouse Integration Tests

Test suite for the ClickHouse / executor-abstraction work covered by
`C:\Users\nisha\.claude\plans\go-throught-the-current-mutable-mountain.md`.

## Layout

```
clickhouse_integration/
  unit/         # Pure Python — no Odoo, no DB. Run with: pytest unit/
  integration/  # Odoo TransactionCase / HttpCase — run via odoo-bin --test-enable
  manual/       # Markdown checklists for QA passes that need a human
  fixtures/     # SQL seeds, sample CH data, etc.
```

## Running unit tests

Unit tests import the live module source from the worktree. Set
`POSTERRA_ADDONS_ROOT` if your worktree path differs from the default in
`conftest.py`.

```bash
# From this directory:
pytest unit/

# Or with a custom addon root:
POSTERRA_ADDONS_ROOT=/path/to/addons pytest unit/
```

The unit tests cover Phase 1's pure-Python surface:

- `test_translate_params.py` — the CH placeholder translator handles
  None, empty list, bool-vs-int, datetime, mixed-type lists.
- `test_normalise_type.py` — Postgres and ClickHouse native types both
  map down to one of (text, integer, float, date, boolean).
- `test_executor_factory.py` — `get_executor()` returns
  PostgresLocalExecutor when no connection is set, the right class for
  each engine otherwise.
- `test_tenant_context.py` — `get_current_tenant_id()` reads
  `request.tenant_id` first, falls back to user.first_app, raises on
  ambiguity.

## Running integration tests

Integration tests come in two flavours:

### Odoo-runtime tests

Files in `integration/test_connection_model.py`,
`test_postgres_local_executor.py`, `test_dispatch_parity.py`,
`test_request_tenant_id.py` are `TransactionCase` / `HttpCase`
subclasses — they need Odoo's registry. To execute, either symlink
the `integration/` directory into `posterra_portal/tests/` or pass
this folder as an additional addons path so Odoo's test runner picks
them up:

```bash
python odoo-bin -c odoo.conf \
    --test-enable \
    --stop-after-init \
    -d <test-db> \
    --test-tags clickhouse_integration
```

Coverage targets (Phase 1):

- `test_connection_model.py` — CRUD on `dashboard.connection`,
  Test Connection button success/failure, cache invalidation on
  write/unlink, manual Invalidate Cache button, inactive-connection
  blocking, schema source uniqueness across connections.
- `test_postgres_local_executor.py` — parity with the pre-executor
  cursor path (savepoint, params, fetchall).
- `test_dispatch_parity.py` — existing PG-backed widgets and filter
  options render identical data after the executor refactor.
- `test_request_tenant_id.py` — placeholder for Phase 2's probe
  endpoint; manual coverage via `manual/phase1_smoke_test.md`.

### Live ClickHouse tests (Phase 2)

`integration/test_clickhouse_live.py` exercises the executor against
a real ClickHouse cluster — no Odoo runtime needed, just network
access to a cluster that has the bootstrap DDL applied. The tests
skip cleanly when the env vars below aren't set, so the file can sit
in CI without breaking jobs that don't have CH credentials.

#### Required env vars

| Var | Purpose | Example |
|---|---|---|
| `CH_TEST_HOST` | Cluster hostname | `ch-dev.internal.posterra.com` |
| `CH_TEST_PORT` | HTTPS port | `8443` (clickhouse-connect is HTTP-only — do not use 9440 here, that's the native TCP TLS port for `clickhouse-driver` / `clickhouse-client` CLI) |
| `CH_TEST_USER` | CH user (typically the bootstrap-created `app_user`) | `app_user` |
| `CH_TEST_PASSWORD` | Rotated password (from `ALTER USER ... IDENTIFIED BY ...`) | *secret* |
| `CH_TEST_DATABASE` | Default database for queries that don't qualify | `default` |
| `CH_TEST_USE_TLS` | `1` for TLS, `0` to disable | `1` |

#### Optional env vars (tenant-row-policy smoke test)

| Var | Purpose | Example |
|---|---|---|
| `CH_TEST_TENANT_ID` | Tenant id the test sets via `SQL_tenant_id` | `1` |
| `CH_TEST_FACT_TABLE` | Tenant-tagged fact table to query for the row-policy smoke test | `silver.fact_referrals` |

#### Run

```bash
cd C:/Users/nisha/Odoo_Dev/Tests/clickhouse_integration

CH_TEST_HOST=<host> \
CH_TEST_PORT=8443 \
CH_TEST_USER=app_user \
CH_TEST_PASSWORD=<rotated-password> \
CH_TEST_DATABASE=default \
pytest integration/test_clickhouse_live.py -v
```

#### Cluster-side prerequisites

Three things must be true on the cluster before live tests pass —
`manual/phase2_verification.md` walks through each:

1. **Server config** (section A) — the cluster must allow the
   `SQL_` setting prefix. ClickHouse Cloud / Aiven / Azure Database
   for ClickHouse have this pre-configured. Self-managed clusters
   need `<custom_settings_prefixes>SQL_</custom_settings_prefixes>`
   declared in `users.xml`. Without it, every `SQL_tenant_id`
   setting the tests send is rejected with "Setting SQL_tenant_id
   is neither a built-in setting...". This is a server-level
   setting only — it cannot be set in a profile.

2. **Bootstrap DDL applied** (section B) — run
   `dashboard_builder/sql/clickhouse_bootstrap.sql`. This creates
   `app_role`, `app_profile`, and `GRANT SELECT ON shared.*`. It
   does NOT create `app_user` (no passwordless window) and does NOT
   grant on tenant-scoped schemas (no exposure before per-table row
   policies exist).

3. **User created with password** (section C) — operator runs
   `CREATE USER app_user IDENTIFIED BY '<password>' DEFAULT ROLE
   app_role SETTINGS PROFILE 'app_profile';` atomically. The same
   password goes into `ir.config_parameter` for the connection's
   `password_param_key` to reference (section E).

## Manual checks

| File | Phase | When to run |
|---|---|---|
| `manual/phase1_smoke_test.md` | 1 | After Phase 1 merge — the 27 CLAUDE.md filter scenarios on PG-backed pages |
| `manual/admin_workflow_connection.md` | 1+ | Reference for admins adding a CH connection |
| `manual/phase2_verification.md` | 2 | After Phase 2 merge against the Dev cluster — bootstrap DDL apply, test connection, live pytest suite, regression sanity |
