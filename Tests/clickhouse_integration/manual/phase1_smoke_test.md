# Phase 1 Smoke Test — Existing Behaviour Preserved

The Phase 1 deliverable is a **zero-regression refactor**: every
existing Postgres-backed widget, filter, and page MUST behave
identically to before. This checklist confirms that.

Run after Phase 1 is merged but before any CH-backed widget is wired
up. Sign each item.

**Tester:** _____________________   **Date:** _____________________

---

## A. Module loads cleanly

- [ ] `python odoo-bin -c odoo.conf -u dashboard_builder,posterra_portal --stop-after-init` exits 0 with no traceback
- [ ] No new WARNING/ERROR lines in the upgrade log
- [ ] `dashboard.connection` table created (psql `\d dashboard_connection`)
- [ ] `dashboard.schema.source` has new `connection_id` column (psql `\d dashboard_schema_source`)

## B. Admin UI

- [ ] `Dashboard Builder → Configuration → Database Connections` menu visible to a user in `Dashboard Builder Admin`
- [ ] Empty list view displays the "Add a connection" empty-state message
- [ ] Form view opens; all fields render (engine, host, port, database, username, password key, TLS, timeout, requires-tenant-filter)
- [ ] **Test Connection** button visible
- [ ] Schema Source form now shows a `Connection` dropdown
- [ ] Schema Source list shows the `Connection` and `Engine` columns (Engine column hidden by default but selectable from the column toggler)
- [ ] Existing Schema Source records open without error; `Connection` field is empty; `Engine` reads `postgres_local`

## C. The 27 filter scenarios from CLAUDE.md

For each item below: load `/my/posterra` (or the relevant app), exercise
the scenario, confirm the dashboard renders identical data to before
the refactor.

### Core filter flow (1–10)
- [ ] 1. Single provider: `/my/posterra?hha_ccn=017014&year=2024,2023&ffs_ma=MA&tab=command_center`
- [ ] 2. State/County/City auto-populate from provider's geo data (not "All")
- [ ] 3. Multi-provider CSV: `hha_ccn=017014,047114` → geo auto-selects if shared, else "All"
- [ ] 4. Load without provider param (multi-provider user) → geo filters show "All"
- [ ] 5. Single-provider user → geo filters auto-populate regardless of URL
- [ ] 6. Change State dropdown → Provider/County/City cascade correctly
- [ ] 7. Click Apply → URL updates with all filter values
- [ ] 8. Widget data reflects correct sql_params (network tab)
- [ ] 9. Different pages each have their own filter set
- [ ] 10. `is_provider_selector` ON for Provider filter (Settings → Pages → Context Filters)

### Cascade multi-select auto-select (11–15)
- [ ] 11. Select 3 providers from different states → State filter shows CSV
- [ ] 12. Select 1 provider where county has 1 option → County auto-selects
- [ ] 13. Multi-select filter with `include_all_option=True` → still resets to "All"
- [ ] 14. Single-select filter in cascade with 2+ options → resets to empty
- [ ] 15. Change Provider → multi-select child filters auto-select all cascaded values

### First login / deferred resolution (16–17)
- [ ] 16. First login (no URL params) with `default_strategy=all_values` on Provider → all selected, geo filters cascade correctly
- [ ] 17. First login with URL params → child filters show options matching parent values

### Default strategy (18–24)
- [ ] 18. `static`, `default_value=2023` → Year=2023
- [ ] 19. `first` on Provider → first provider selected
- [ ] 20. `latest` on Year → most recent year selected
- [ ] 21. `all_values` on multi-select Provider → all providers as CSV
- [ ] 22. URL `?year=2022` with `default_strategy=latest` → URL wins
- [ ] 23. Single-provider user with `auto_fill_from_hha=True` → auto-fill wins
- [ ] 24. Default Strategy dropdown visible in admin (4 options)

### Clear All + Apply (25–27)
- [ ] 25. Clear All resets all dropdowns to empty, full unfiltered options
- [ ] 26. After Clear All + Apply → URL has no filter params
- [ ] 27. Clear All → State=TX → cascade fills others → Apply → URL has all 4

## D. Tenant context wiring

- [ ] Visit `/my/posterra` → server log shows the request handled successfully (no tenant resolution warnings)
- [ ] Visit `/my/mssp` (if MSSP is set up) → same
- [ ] Visit `/api/v1/page/<page_key>/config?app_id=<id>` with a valid JWT → returns the page config without tenant_id errors
- [ ] Visit `/api/v1/widget/<widget_id>/data?app_id=<id>` with a valid JWT → returns widget data
- [ ] If any widget loads with empty data where before it had data, **stop** — that's a regression in `request.tenant_id` plumbing

## E. Connection model behaviour

- [ ] Create a `dashboard.connection` with engine=`clickhouse` and a fake host
- [ ] Click Test Connection → red error notification (host unreachable) — confirms wiring
- [ ] Edit the connection's name → save → no traceback
- [ ] Delete the connection → no traceback

## F. Backwards compat

- [ ] Open Designer SPA at `/dashboard/designer` → still loads
- [ ] Open the AI SQL editor in Designer → still works
- [ ] Existing widgets in Widget Library list view → all visible
- [ ] No dashboard page returns a 500 in the access log

---

**Result:**

- [ ] PASS — Phase 1 may merge
- [ ] FAIL — block merge; record failures below

**Failures (if any):**

```
(write here)
```
