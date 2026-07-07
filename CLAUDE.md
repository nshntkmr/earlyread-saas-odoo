# Posterra Platform — Developer Context

## What This Is

Multi-tenant healthcare analytics SaaS built on Odoo 19 CE + React + PostgreSQL.
Multiple independent apps (Posterra HHA, MSSP, future: St. Johns, Parx MA, etc.) share one codebase.
Each app has its own branding, login, data scope, pages, widgets, and filters — all admin-configurable, zero code.

## Core Principle: No Regressions

**HARD RULE:** When building any new feature, fixing a bug, or modifying existing code:
1. **Existing features MUST NOT break.** Before committing, mentally trace every modified function's callers and verify they still work.
2. **If a change affects shared code** (models, controllers, shared components, `@posterra/grid-utils`), explicitly list ALL consumers that could be impacted and verify each one.
3. **If a field is added/removed/renamed**, check every reference: Python models, controllers, XML views, React components, API endpoints, builder payload, and `place_on_page`/`library_update` sync.
4. **Notify the user** before making changes that could affect existing widgets, pages, or apps — even if the change seems safe.
5. **Test both designer AND portal** — a feature that works in preview but breaks on the dashboard page is a regression.
6. **Widget name, placement, layout fields** must always be preserved when syncing definitions to instances.

## Core Principle: No Hardcoding

Every feature must be **config-driven** and work across any app, any page, any dataset.
- Filter param names, field names, display templates — all read from DB records at runtime
- Provider resolution uses the filter's own `param_name` and `field_name`, never hardcoded `hha_id` or `hha_ccn`
- Widget SQL uses `%(param)s` placeholders filled from filter values — no hardcoded column names in controllers
- New app = new `saas.app` record + filter/widget/page records. No Python changes.

## Commands

```bash
# Start Odoo (from Odoo root, not this dir)
python odoo-bin -c odoo.conf

# React dev build (hot reload)
cd posterra_portal/static/src/react && npm run dev

# React production build
cd posterra_portal/static/src/react && npm run build
```

## Architecture Overview

```
Browser URL: <app_key>.<base-host>/<page_key>/<tab_key>?<filter_params>
             (e.g. posterra.example.com/overview/command_center?hha_ccn=017014)
     |
     v
portal.py (app_dashboard)
  1. Resolve app from request host subdomain (utils/app_resolver.get_app_from_host)
  2. Access check (hha_provider mode OR group mode)
  3. Load pages, nav, current page/tab
  4. Load page_filters (per-page, from DB)
  5. Generic provider resolution (reads filter config, no hardcoding)
  6. Geo data from selected provider
  7. Auto-fill geo filters from provider (auto_fill_from_hha)
  8. Build filter_values (root deferred defaults resolved early, then filter_options, then remaining deferred), sql_params
  9. Execute widget SQL with sql_params
  10. Render template with React data attributes
     |
     v
React (main.jsx → App.jsx)
  - TokenProvider (JWT auth)
  - FilterProvider (filter state + URL sync)
    - FilterBar (dropdowns + cascade logic)
    - TabBar
    - WidgetGrid (ECharts, KPIs, DataTables, etc.)
```

## Key Models

| Model | Purpose |
|-------|---------|
| `saas.app` | App definition (Posterra, MSSP, etc.). `access_mode`: `hha_provider` or `group` |
| `hha.provider` | Reference data: CCN, name, state, county, city. One record per HHA agency |
| `dashboard.page` | A page within an app (Overview, Hospitals, etc.) |
| `dashboard.page.filter` | Filter definition per page. Configures param_name, field, cascade, auto-fill |
| `dashboard.filter.dependency` | Multi-directional cascade edges between filters |
| `dashboard.widget` | Widget definition: SQL, chart type, layout position |
| `dashboard.schema.source` | Materialized view / SQL view reference for filters and widgets |

## Filter System — Complete Flow

### Data Model

Each `dashboard.page.filter` record defines ONE dropdown in the filter bar:

```
page_id          → which page this filter belongs to
model_id/field_id → ORM source (e.g., hha.provider.hha_state)
schema_source_id/schema_column_id → SQL source (materialized views)
param_name       → URL parameter name (e.g., "hha_ccn", "hha_state", "year")
field_name       → derived from field_id.name (stored, readonly)
display_template → label format: "{hha_ccn} - {hha_brand_name}"
include_all_option → prepend "All N items" option
is_provider_selector → marks THIS filter as the Provider selector for provider resolution + auto-fill
auto_fill_from_hha → auto-populate from selected provider on page load
scope_to_user_hha → restrict options to user's accessible providers
is_visible       → False = hidden SQL context param, not shown in UI
is_multiselect   → allow multiple selections (CSV in URL)
default_value    → static default when no URL param present
default_strategy → how to compute initial value: static | first | latest | all_values
depends_on_filter_id → legacy single-parent cascade
```

### Cascade Dependencies (Multi-Directional)

`dashboard.filter.dependency` records define cascade edges:

```
source_filter_id → "when this changes..."
target_filter_id → "...refresh this filter's options"
resets_target    → clear target value on source change
propagation      → 'required' (always cascade) or 'optional' (skip if target has value)
```

### Dependency Graph (Cycles Allowed)

Filter dependencies form a **general directed graph** — bidirectional/cyclic edges are allowed (e.g., Provider ↔ State). Self-loops are still rejected.

**Circuit breaker:** The visited set at every runtime layer prevents infinite loops. When a filter is already in the visited set, traversal stops — each filter is processed exactly once per cascade event.

**Pre-clear on cascade:** Before traversing, a full graph walk finds ALL reachable filters with `resets_target=True` and clears their stale values in the snapshot. This prevents filters from being constrained by sibling values that are about to be reset (e.g., switching from a CA to TX provider won't see stale County=LA when refreshing State).

**Traversal by layer:**

| Layer | Algorithm | File | Key Detail |
|-------|-----------|------|------------|
| DB save | Self-loop + same-page checks only | `dashboard_filter_dependency.py` | Cycles allowed; visited set is the runtime guard |
| Server page load | Implicit topo order (roots first) | `portal.py` step 8 | In bidirectional graphs, no root filters → all deferred defaults resolve in post-loop phase |
| Server cascade API | BFS + visited set | `widget_api.py:api_filters_resolve` | Full graph pre-clear, then single HTTP call resolves cascade |
| Client cascade | Recursive DFS + visited set | `FilterBar.jsx:handleGraphCascade` | Full graph pre-clear, two-phase: fetch all targets, then recurse |

**Root filter = in-degree 0** — identified by checking which filter IDs never appear as `target_filter_id` in any dependency edge. In bidirectional graphs, all filters are targets → no root filters → early resolution phase is a no-op. This is correct: on first login, `__DEFERRED__` values are skipped as constraints, so every filter gets unfiltered options.

**Visited sets at every layer** — all runtime traversals carry a visited set to prevent re-processing nodes reachable via multiple paths (diamond dependencies or cycles).

### Provider Resolution (Generic — Step 8 in portal.py)

```python
# Find the Provider filter for this page (admin marks it via is_provider_selector)
provider_filter = page_filters.filtered(
    lambda f: f.is_provider_selector
)
# Read its param_name and field_name from the DB record
pf_param = pf.param_name   # e.g., "hha_ccn" or "hha_id"
pf_field = pf.field_name or pf.param_name or pf.schema_column_name  # fallback chain
pf_value = kw.get(pf_param) # e.g., "017014"

# Match against providers using the configured field
if pf_field == 'id':
    matched = providers.filtered(lambda p: p.id == int(pf_value))
else:
    matched = providers.filtered(lambda p: str(getattr(p, pf_field, '')) == pf_value)
```

**Why `is_provider_selector`**: Explicit admin toggle — no assumptions about `model_name`, `display_template`, or `include_all_option`. Works with both ORM and schema-source filters. Admin toggles it ON for exactly one filter per page.

### Auto-Fill (Step 8.5 in portal.py)

When `selected_provider` is resolved, filters with `auto_fill_from_hha=True` are populated:

```python
if selected_provider:
    for f in page_filters:
        if f.auto_fill_from_hha:
            actual_field = f.field_name or f.param_name or f.schema_column_name or ''
            param_key = f.param_name or f.field_name or ''
            if actual_field and param_key and hasattr(selected_provider, actual_field):
                val = getattr(selected_provider, actual_field, '')
                hha_auto_fill[param_key] = str(val)
```

This fills State, County, City from the provider's record — no hardcoded field names.
Works whether filters use ORM models (field_name) or schema sources (param_name/schema_column_name).

### Default Strategy (Admin-Configurable Initial Values)

The `default_strategy` field on each filter controls how the initial value is computed when no URL param is present:

| Strategy | Behavior | Example |
|----------|----------|---------|
| `static` | Use the `default_value` text field (backward-compatible default) | Admin types `2023` → filter starts at `2023` |
| `first` | Pick the first available option from `get_options()` | Year options `[2021,2022,2023,2024]` → picks `2021` |
| `latest` | Pick the last available option | Year options `[2021,2022,2023,2024]` → picks `2024` |
| `all_values` | Select every option as CSV (multi-select only) | Providers `[A,B,C]` → value `A,B,C` |

**Resolution priority (unchanged):**
```
URL param (wins) → auto_fill from provider (wins) → default_strategy → empty
```

**Implementation:** Non-static strategies use deferred resolution — marked as `'__DEFERRED__'` in the first pass. Root filters (those with no incoming dependency edges) are resolved early, before the main `filter_options` loop, so their real values are available as constraints for child filters. Any remaining deferred filters are resolved after `filter_options` are computed via `compute_default_value(options)`.

### How Filter Values Reach React

1. Server resolves `filter_values` dict (auto-fill + URL params + default_strategy)
2. Deferred defaults resolved in two phases: root filters early (before child options), remaining filters after `filter_options` are computed
3. `_build_page_config_json()` puts resolved values into `default_value` for each filter
4. React `FilterContext.buildDefaults()` reads `default_value`, then overrides with URL params
5. Geo params NOT in URL → server-resolved auto-fill values persist
6. After user clicks Apply → URL sync pushes all values to URL

### Server-Side Auto-Select (Step 8.7 in portal.py)

After `filter_options` are computed, filters with exactly 1 cascaded option (and no `include_all_option`) are auto-selected:

```python
for f in page_filters:
    if not f.include_all_option and f.id in filter_options:
        opts = filter_options[f.id]
        if not filter_values.get(f.id, '') and len(opts) == 1:
            filter_values[f.id] = opts[0]['value']
```

This handles multi-CCN URLs (e.g., `hha_ccn=A,B` where both share the same state → State auto-selected).

**Deferred defaults** for root filters are resolved before this loop runs (so their values are available as constraints). Any remaining deferred defaults are resolved immediately after auto-select, before `filter_values_by_name` is built.

### Client-Side Cascade (FilterBar.jsx)

When user changes a dropdown:
1. `handleGraphCascade()` fires
2. For each dependent filter: fetch new options from `/api/v1/filters/cascade/multi`
3. If `resets_target=True`:
   - Exactly 1 option + no `include_all_option` → auto-select that option
   - Multi-select target + 2+ options + no `include_all_option` → auto-select ALL as CSV (e.g., `AR,IL,TX`)
   - Otherwise (0 options, or `include_all_option=True`) → reset to `''` (user must choose)
4. If `resets_target=False`: keep value if still valid in new options (prune invalid CSV values for multi-select)
5. Recurse into children's children (Phase 2 picks up auto-selected values from snapshot)

**Multi-select cascade example:** User selects 3 providers from AR, IL, TX → State filter gets `AR,IL,TX` (not "All"). Admin can set `include_all_option=True` on State to revert to the old "reset to All" behavior.

The same auto-select logic is mirrored server-side in `api_filters_resolve` (widget_api.py) for batch cascade resolution.

### Clear All (FilterBar.jsx)

Resets all visible filters to empty and clears `dynamicOptions` so dropdowns revert to the full unfiltered option lists from page load. Does NOT trigger cascade — user must click Apply after clearing.

### SQL Parameter Flow

```
filter_values_by_name = {param_name: value} for all filters
    ↓
sql_params = same, but multiselect values converted to tuples
    ↓
widget.get_portal_data(portal_ctx) → SQL interpolation with %(param)s
```

## Key Files

| File | Purpose |
|------|---------|
| `controllers/portal.py` | Main page controller. Provider resolution, filter values, widget execution, template render |
| `controllers/widget_api.py` | API endpoints for widget data refresh + filter cascade. Has `_build_portal_ctx()` mirroring portal.py |
| `models/dashboard_page_filter.py` | Filter model: `get_options()`, `compute_default_value()`, `_build_orm_domain_from_constraints()`, `_build_schema_where()` |
| `models/dashboard_filter_dependency.py` | Cascade dependency edges between filters |
| `models/dashboard_widget.py` | Widget model: SQL execution, data formatting |
| `data/filters_data.xml` | Seed data for geo filters (State, County, City) per page |
| `static/src/react/src/components/FilterBar.jsx` | React filter UI + cascade handler (`handleGraphCascade`) |
| `static/src/react/src/state/FilterContext.jsx` | Filter state management, URL sync, Apply logic |
| `static/src/react/src/main.jsx` | React entry point, reads `data-page-config` from DOM |
| `views/dashboard_templates.xml` | QWeb template: embeds `page_config_json` as `data-*` attribute on `#app-root` |

## Gotchas

- **App resolution is by host subdomain, NOT URL prefix** — every request resolves its `saas.app` from the leftmost label of `request.httprequest.host` via `posterra_portal.utils.app_resolver.get_app_from_host`. The legacy `/my/<app_key>/...` routes were removed entirely; URLs are now `<app_key>.<base-host>/<page>/<tab>` (e.g. `posterra.localhost:8069/overview/command_center`). Cross-subdomain redirects (`/web/login` → user's app, the `home()` override) use `app_resolver.build_app_url(app, '/')`. Adding a new app: just create the `saas.app` record — DNS wildcard `*.<base-host>` handles routing. Local dev: `*.localhost` works natively in modern browsers (no `/etc/hosts` edits). Reserved subdomains (`www`, `api`, `admin`, `web`, `static`, `longpolling`, `dashboard`, `portal`, ...) are rejected by `saas.app._check_app_key_valid` and also blocklisted in `app_resolver._RESERVED_SUBDOMAINS` as a runtime guard.
- **Vite dev server proxy preserves Host header** — `vite.config.js` sets `server.host = true` (binds 0.0.0.0) and uses default `changeOrigin: false`, so `posterra.localhost:3000` (Vite) proxying `/api/*` to `localhost:8069` (Odoo) keeps the `Host: posterra.localhost` header. Without this, Odoo would resolve to no app and 404.
- **Reverse proxy in production must forward Host header faithfully** — Azure Front Door, nginx, etc. need to send the original `Host` header (or `X-Forwarded-Host`) so `app_resolver.get_app_from_host` sees `<tenant>.<base-host>`. Set Odoo's `proxy_mode = True` so it trusts forwarded headers.
- **`hha_id` param removed from `app_dashboard()` signature** — all URL params now go to `**kw` for generic access. This was intentional to avoid Odoo capturing named params before `**kw`.
- **`provider_map` keys are Odoo record IDs** (not CCNs). Built at portal.py step 9 but NOT passed to React — only used in template context.
- **Hidden filters (`is_visible=False`)** are excluded from React state and URL by `FilterContext.jsx`. They are server-side SQL context only (e.g., hha_ccn, hha_name for widget SQL).
- **`dep_is_hha_provider_id` check in `_build_schema_where()`** — only `True` when source filter has `field_name='id'`. When `field_name='hha_ccn'`, falls through to direct column matching (correct behavior).
- **Cascade `resets_target` + auto-select** — when True: (a) exactly 1 option + no `include_all_option` → auto-select that option; (b) multi-select target + 2+ options + no `include_all_option` → auto-select ALL as CSV; (c) otherwise → reset to `''`. To suppress CSV auto-select, set `include_all_option=True` on the target filter.
- **`default_strategy` deferred resolution order matters** — non-static strategies use a `'__DEFERRED__'` sentinel. Root filters (no incoming dependency edges) are resolved early, BEFORE the main `filter_options` loop, so child filters get real constraint values. The sentinel must never leak into `constraint_values` — the options loop explicitly skips `'__DEFERRED__'` values when building constraints. Any remaining deferred filters are resolved after `filter_options` are built. The sentinel never reaches `filter_values_by_name`, `sql_params`, or React.
- **`auto_fill_from_hha` only works server-side** — runs on page load when `selected_provider` is resolved. Client-side auto-select is handled by the cascade auto-select logic in `handleGraphCascade()`.
- **`is_provider_selector` must be toggled ON** — admin must explicitly mark the Provider filter on each page. Without this, `selected_provider` will be `None` and auto-fill won't fire. Check this first when debugging "State shows All".
- **Seed data in `filters_data.xml`** may show `param_name=hha_id` but DB records may have been updated to `hha_ccn` by admin. DB state is authoritative.
- **`portal.py` filter_options must use `dashboard.filter.dependency` graph** — the options loop at step 11 uses `dep_records` (new multi-directional dependency system) to build `constraint_values` for each filter, NOT the legacy `depends_on_filter_id` field. Both `portal.py` and `widget_api.py` (`_build_portal_ctx`) must use the same pattern. If only legacy `depends_on_filter_id` is checked, filters whose dependencies are defined via the Filter Dependencies tab (new system) will get empty options on first page load. When a parent filter has no value (null/empty), the child filter should still show ALL available options (unfiltered), never empty.
- **Clear All must reset `dynamicOptions`** — clearing filter values alone is not enough. Without resetting `dynamicOptions`, dropdowns still show narrowed cascaded option lists instead of the full server-provided options. Both `setPendingFilter(key, '')` AND `setDynamicOptions({})` are required.
- **Cross-filter clicks (map `cross_filter`/`drill_cross_filter`) must cascade dependent options in ONE commit** — patching filter VALUES alone leaves dependent dropdowns with stale option lists (bug: clicking Pennsylvania on the map left County showing the previous state's counties), and committing values + cascade resets separately double-refetches every widget. Design: `WidgetGrid.onCrossFilter` → `FilterContext.applyCrossFilter(patch)` → pending updates instantly, then the resolver `FilterBar` registered on `crossFilterResolverRef` runs the batch cascade (`/api/v1/filters/resolve`), refreshes `dynamicOptions`, and RETURNS its value resets → `applyCrossFilter` commits `{...patch, ...resets}` to `filterValues` in one shot (one refetch wave; `drillJustFiredRef` alone protects the drilled map). No resolver mounted / resolver error → commits the click patch alone. `WidgetGrid.onCrossFilter` returns whether it fired: same-as-applied values no-op (zero refetches), and the renderer passes that bool as the drill-coupling arg (`onDrill(drill, crossFired)`) — arming the drill guard without a filterValues change leaves a stale flag.
- **Map click value must come from the CONFIGURED column or not fire at all** — `choropleth_click_filter_column` set but absent from the clicked region's popup props (no-data region, or a geo level whose SQL lacks the column) must NO-OP, never fall back to the region join key: the fallback sent county FIPS (`48143`) into `STATE_NAME`. Join-key fallback applies ONLY when no column is configured. Both renderers: `AlbersChoroplethMap.handleRegionClick` and `MapLibreMap` onClick.
- **County-level map clicks target their own filter via `choropleth_click_filter_param_county` / `_column_county`** — the base click param/column applies to state-level clicks; when the rendered `geo_level` is `county` AND the county param is set, clicks send that param instead (blank county column → join key = 5-digit FIPS GEOID, which matches a FIPS-valued County filter). Blank county param → county clicks fall back to the base param (pre-existing behavior). Flags live in both `MAP_FLAGS` and `ALBERS_CHOROPLETH_FLAGS` (chart_flags.py); renderer support is SVG-Albers only. A cross-filter fired FROM a drilled widget arms `drillJustFiredRef` in `WidgetGrid.onCrossFilter` so the county view survives the commit (only armed when the filter actually fires — applyCrossFilter always commits, so the flag is always consumed).
- **Auto-select-ALL-as-CSV is capped at `AUTO_SELECT_ALL_MAX_CHARS` (1500)** — an unconstrained multiselect cascade target with hundreds of options (Plan ID reached via an empty optional Plan Name hop → all 635 ids ≈ 4.7KB CSV) would otherwise blow up widget URLs and trip the 2000-char permalink threshold. Over the cap → reset to `''` (same "All" semantics). Two mirrors, keep in sync: `widget_api.py` (`api_filters_resolve`) and `FilterBar.jsx` (`handleGraphCascade`).
- **Schema-source filters have empty `model_name`/`field_name`** — these are `related` fields from `model_id`/`field_id`. When admin switches a filter to use schema sources, `model_id` is cleared → `model_name` becomes empty. Never use `model_name == 'hha.provider'` to identify filters. Use `is_provider_selector` for the Provider filter. For field lookups, use fallback chain: `field_name or param_name or schema_column_name`.
- **`%(param)s` in XML view placeholders** — Odoo's XML loader interprets `%(...)s` as Python string format refs, causing `External ID not found` errors. In XML `placeholder` or `help` attributes, use `%%(param)s` (doubled `%`) to escape, or rephrase without the `%(...)s` syntax.
- **Always syntax-check Python after refactoring** — Run `python -c "import ast; ast.parse(open('path/to/file.py').read())"` before committing large refactors. An orphaned `except` block (from a refactor that moved `try/except`) caused `SyntaxError` at module import time, preventing Odoo from loading.
- **CSS `::after` tooltips won't escape `overflow-y: auto` containers** — Use native HTML `title` attribute for tooltips inside scrollable containers (e.g., sidebar nav). CSS pseudo-element tooltips get clipped by any ancestor with `overflow: hidden/auto/scroll`.
- **EVERY widget/filter/section/badge/scope SQL path dispatches through `posterra_portal.utils.query_executors`** — never call `self.env.cr.execute()` directly from a runtime data path. The dispatch points are:
  - `dashboard_widget._execute_sql` (main SQL)
  - `dashboard_widget._execute_annotation_sql` (annotation overlay)
  - `dashboard_widget.get_scope_options` (scope-control schema-source dropdown)
  - `dashboard_widget` ranked-detail SQL
  - `dashboard_page_filter._get_schema_source_options` and `_get_schema_options_with_template`
  - `dashboard_page_section._execute_sql` and `get_scope_options`
  - `dashboard_page_badge.get_value` SQL
  - `dashboard_widget_scope_option.execute_option_sql`
  - `dashboard_builder.services.query_builder.QueryBuilder.execute_preview` — designer/builder preview path; takes optional `schema_source` param and dispatches via `get_executor()` when the source has a non-null `connection_id`. Phase 3 Path B added this; before, the wizard preview always ran against local PG and silently broke CH-backed widget previews. Callers (`designer_api.preview`, `builder_api.builder_preview`, `builder_api.drill_down`) MUST pass the source through, otherwise CH widgets fall back to PG dispatch.
  All call `get_executor(env, schema_source).execute(sql, params)`. Schema sources with `connection_id IS NULL` route to `PostgresLocalExecutor` (wraps `env.cr` inside a savepoint — identical to the pre-executor behaviour). Sources pointing at a `dashboard.connection` route to that engine's executor (e.g. `ClickHouseExecutor`). Adding a new SQL path? Use the executor — adding `env.cr.execute` will silently break CH-backed widgets without the test suite catching it.
- **`request.tenant_id` is the stable string `saas.app.app_key`** — set by `_get_api_user` for every JWT route, by `app_dashboard` / `_build_portal_ctx` for browser routes, and by `designer_api.preview` / `builder_api.builder_preview` for builder routes. The contract is the **string app_key** (e.g. `'posterra'`, `'inhome'`, `'mssp'`), not the integer `app.id`. Five callsites: `posterra_portal/controllers/portal.py`, `posterra_portal/controllers/widget_api.py` (×2), `dashboard_builder/controllers/designer_api.py`, `dashboard_builder/controllers/builder_api.py`. CH executor reads via `tenant_context.get_current_tenant_id`, casts via `str(tenant_id)` (no-op for strings). The fallback in `tenant_context.get_current_tenant_id` (no request, single-app user) returns `accessible.app_key` too. **Why the string, not the int**: stable across PG rebuilds (fresh Azure deploys won't break CH tenant tags), human-readable in `system.query_log`, and matches the DNS subdomain. `app_key` is now validated as a strict RFC 1035 DNS label (lowercase alphanumeric + hyphens, no underscores) by `saas.app._check_app_key_valid`, normalised via `.strip().lower()` in `create()`/`write()` overrides, and enforced unique at the DB level (`unique(app_key)` in `_sql_constraints`). New endpoints that bypass the helpers must set `request.tenant_id = app.app_key` themselves — without it, `requires_tenant_filter=True` raises a clear `ValueError` rather than silently leaking data.
- **`dashboard.connection` cache invalidation on write/unlink** — clickhouse-connect clients are cached per-process keyed by connection id. The model's `write()` and `unlink()` call `clickhouse._invalidate_client(id)` so password rotation / host changes take effect without an Odoo restart. If you add a new field that affects the client (host, port, TLS), invalidation is automatic; if you add a non-client field, the invalidation is harmless.
- **Secrets resolution priority — env var, then DB** — three secret families follow the same env-overrides-DB pattern: `_get_jwt_secret()` reads `POSTERRA_JWT_SECRET`; `clickhouse._get_password()` reads the env var **named after `connection.password_param_key`** (admin-supplied stable string, e.g. `POSTERRA_CH_PASSWORD_PROD` — NOT keyed by `connection.id` because IDs shift across fresh seeds); `AiSqlGenerator.__init__` reads `POSTERRA_AI_API_KEY`/`POSTERRA_AI_ENDPOINT`/`POSTERRA_AI_MODEL`. Each falls back to `ir.config_parameter` (or `connection.password` for CH) if the env var is unset. **Why env-first**: in multi-pod AKS, all replicas read the same Key-Vault-injected env var on cold boot — no race to generate or sync secrets through the DB. Dev / single-Odoo installs work unchanged because the fallback chain is preserved. Logs never print secret values — keep it that way.
- **`dashboard.schema.source.connection_id IS NULL` means "use local Postgres"** — every existing schema source has this null. The factory function `get_executor(env, source)` returns `PostgresLocalExecutor(env)` in that case. Don't add fallback code that special-cases NULL — the factory already handles it.
- **`_normalise_type` covers both Postgres and ClickHouse natives** — Postgres tokens (`character varying`, `numeric(10,2)`) and CH wrappers (`LowCardinality(String)`, `Nullable(Int64)`, `Array(...)`) all collapse to `text|integer|float|date|boolean`. CH wrappers are unwrapped up to 4 levels deep. Unknown types default to `text` — admins override in the column form if a guess is wrong.
- **CH tenant_id is a per-query setting, never a session SET** — `ClickHouseExecutor.execute()` ships `SQL_tenant_id` inside `client.query(settings={...})`, NOT via a separate `client.command('SET SQL_tenant_id = ...')`. The cached `clickhouse-connect` client is shared across threads; a session-state SET would race (thread A's value overwritten by thread B before A's query runs). Per-query settings are atomic with the query in the same HTTP request. CH-side row policies read via `getSetting('SQL_tenant_id')` and pick up the per-query value transparently. Don't reintroduce `SET`-style commands "for performance" — the race is real and silent.
- **`get_executor_for_connection` refuses inactive connections** — flipping `is_active=False` on a `dashboard.connection` makes every executor build raise a clear `ValueError` rather than silently running queries against a disabled cluster. Admins see per-widget error chips, not stale data.
- **Schema source uniqueness is per-connection** — `dashboard.schema.source` has no global SQL `UNIQUE(table_name)` constraint. Uniqueness is enforced via `@api.constrains` on `(connection_id, table_name)`, treating NULL `connection_id` (= local Postgres) as a single value. The same table name CAN exist across multiple connections (e.g. `fact_referrals` on a Production CH cluster and a Staging CH cluster), but not twice on the same connection. Don't add a SQL-level UNIQUE constraint back — Postgres treats NULL connection_ids as distinct and would let two PG sources share a table name, which is a regression from pre-CH behaviour.
- **Password rotation needs an explicit cache flush** — `clickhouse-connect` clients are cached per worker keyed by `connection.id`. Updating the password (env var, ICP row, or `connection.password` field) does NOT auto-trigger `connection.write()`, so cached clients keep using the old password. Refresh paths: (a) click **Test Connection** (auto-invalidates before testing); (b) click **Invalidate Cache** (drops the cached client without testing); (c) in production, `kubectl rollout restart deploy/odoo-http` after KV rotation — flushes every pod's cache atomically. Per-worker scope means clicking refresh only flushes the one worker that handled the click; other workers refresh lazily on their next query. The rollout-restart path is the canonical production rotation; admin-UI flush is for ad-hoc dev fixes.
- **Table names may be schema-qualified (`db.table`)** — `posterra_portal/utils/sql_idents.py` exposes `IDENT_RE` (single identifier, no dots) and `TABLE_RE` (optional one dot for `database.table`). Use `quote_table('gold.fact_referrals')` to emit `"gold"."fact_referrals"` (two quoted identifiers), NOT `f'"{table}"'` which would produce `"gold.fact_referrals"` (one identifier with a dot — broken in both PG and CH). All filter/widget/section/badge SQL emission paths now go through these helpers; new SQL should too.
- **CH connections require cluster-side bootstrap DDL + a server-config prereq** — the addon's executor depends on:
  1. **Cluster server config** declaring `<custom_settings_prefixes>SQL_</custom_settings_prefixes>` (in `users.xml` or a `config.d/*.xml` drop-in, then `SYSTEM RELOAD CONFIG;`). Without this, every `SQL_tenant_id` setting the addon sends is rejected with "Setting `SQL_tenant_id` is neither a built-in setting nor started with the prefix listed in custom_settings_prefixes." This is a **server-level** setting only — declaring it in a profile silently has no effect. ClickHouse Cloud / Aiven / Azure Database for ClickHouse may have `SQL_` pre-configured (varies by provider, tier, and region — verify with `SELECT getSetting('SQL_tenant_id') SETTINGS SQL_tenant_id='42'` returning `'42'`, not by assumption).
  2. **Bootstrap DDL** at `dashboard_builder/sql/clickhouse_bootstrap.sql` — creates `app_role`, `app_profile` (declaring `SQL_tenant_id` with `READONLY = 0`), and grants `SELECT ON shared.*`. The bootstrap does NOT create the `app_user` — user creation is a separate manual step done with a password atomically (`CREATE USER ... IDENTIFIED BY ...`) so there's no passwordless window where grants are exposed.
  3. **Per-table grant + row policy** for each tenant-scoped table — added together in one block, never separately. Bootstrap grants ONLY `shared.*` (cross-tenant reference data); `silver.*` and `gold.*` get per-table SELECT grants paired with row policies as Phase 3+ rolls out CH-backed widgets. Granting before the policy exists silently exposes all tenants' rows to any logged-in user. Audit query in section 4 of the bootstrap SQL lists tables granted without policies — should always be empty.
- **Wizard "Database Connection" dropdown drives source filtering + AI dialect** — Phase 3 Path C added a Connection picker at the top of the React Designer's Step 3 (Data Source). Default is `'local_pg'` (sentinel for sources with NULL `connection_id`); switching to a `dashboard.connection` filters the source list server-side via `?connection_id=X` on `/dashboard/designer/api/sources`. The dropdown is hidden entirely when only Local Postgres exists (no choice = no clutter). Switching connection clears `sources`, `joins`, and the custom-SQL `schemaSourceId` — sources from one engine are not portable to another. The connection's engine flows downstream: (a) the `Schema Source` dropdown lists only sources with that engine; (b) `QueryBuilder.execute_preview` dispatches via `get_executor()` for non-local engines; (c) `ai_sql_generator.assemble_context` reads `source.engine` and the AI prompt is built via `build_system_prompt(engine)` — `_PROMPT_BASE + _PROMPT_POSTGRES` for PG, `_PROMPT_BASE + _PROMPT_CLICKHOUSE` for CH. The dialect tail tells Claude to use `toStartOfMonth`/`toYYYYMM` instead of `date_trunc`, `positionCaseInsensitive` instead of `ILIKE`, and to expect `LowCardinality`/`Nullable`/`Array` type wrappers. **`SYSTEM_PROMPT` constant is now an alias for the PG-flavoured prompt** — every legacy importer that grabbed it directly continues to get PG dialect, no migration needed. Subsumes the master plan's Phase 6 dialect threading.

## Testing Checklist (Filter Changes)

### Core Filter Flow
1. Load with single provider: `posterra.localhost:8069/overview/command_center?hha_ccn=017014&year=2024,2023&ffs_ma=MA`
2. Verify State/County/City auto-populate from provider's geo data (not "All")
3. Load with multi-provider CSV: `hha_ccn=017014,047114` → geo auto-selects if all share same state, else "All"
4. Load without provider param (multi-provider user) → geo filters show "All"
5. Single-provider user → geo filters auto-populate regardless of URL
6. Change State dropdown → Provider/County/City cascade correctly (bidirectional)
7. Click Apply → URL updates with all filter values (including auto-selected geo)
8. Widget data reflects correct sql_params (check browser network tab)
9. Test on different pages (Overview, Hospitals, etc.) — each has its own filter set
10. Verify `is_provider_selector` is ON for Provider filter in admin (Settings → Pages → Context Filters)

### Cascade Multi-Select Auto-Select
11. Select 3 providers from different states → State filter shows CSV (e.g., `AR,IL,TX`), not "All"
12. Select 1 provider where county has 1 option → County auto-selects that single value (unchanged)
13. Multi-select filter with `include_all_option=True` → still resets to "All" on cascade (unchanged)
14. Single-select filter in cascade with 2+ options → resets to empty (unchanged)
15. Change Provider dropdown → multi-select child filters auto-select ALL cascaded values as CSV

### First Login / Deferred Resolution
16. First login (no URL params) with `default_strategy=all_values` on Provider → all providers selected AND State/County/City show cascaded options (not empty)
17. First login with URL params → child filters show options matching the URL-provided parent values

### Default Strategy
18. `default_strategy=static`, `default_value=2023` → page loads with Year=2023 (backward compat)
19. `default_strategy=first` on Provider → page loads with first provider selected
20. `default_strategy=latest` on Year → page loads with most recent year (e.g., 2024)
21. `default_strategy=all_values` on multi-select Provider → page loads with all providers as CSV
22. URL param `?year=2022` with `default_strategy=latest` → URL wins (loads 2022, not latest)
23. Single-provider user with `auto_fill_from_hha=True` → auto-fill wins over default_strategy
24. Admin UI: Default Strategy dropdown visible in Settings → Pages → Context Filters (4 options)

### Clear All + Apply
25. Click Clear All → all dropdowns reset to empty, option lists show full unfiltered options
26. After Clear All, click Apply → URL has no filter params (clean state)
27. After Clear All, select State=TX → cascade fills Provider/County/City → click Apply → URL has all 4 params
