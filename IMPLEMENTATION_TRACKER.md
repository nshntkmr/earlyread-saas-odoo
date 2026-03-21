# Filter State Management — Implementation Tracker

## Problem 2: "All Means Omit" — Dynamic SQL Generation
**Status: COMPLETE ✓**

### What Was Done
- **Finding:** DashboardFilterBuilder already implements "All means omit" for Category A/B widgets (`{where_clause}`)
- **Bug fix:** `widget_api.py` `_build_portal_ctx()` was missing `('__all__',)` sentinel tuple creation — now matches portal.py
- **New feature:** `[[...]]` optional clause syntax (Metabase-style) for Category C manual SQL
  - `resolve_optional_clauses()` in `filter_builder.py` (shared utility, no Odoo imports)
  - Integrated into `dashboard_widget.py._execute_sql()` and `dashboard_page_section.py._execute_sql()`
- **Docs:** Updated `SQL_QUERY_PATTERNS.md` with `[[...]]` syntax, updated Category C examples, updated Bug 7

### Files Changed
- `controllers/widget_api.py` — Bug fix: added `('__all__',)` sentinel + `_single`/`_prior` helpers
- `utils/filter_builder.py` — New: `resolve_optional_clauses()` function
- `models/dashboard_widget.py` — Added `[[...]]` processing before SQL execution
- `models/dashboard_page_section.py` — Same `[[...]]` support
- `docs/SQL_QUERY_PATTERNS.md` — Documented new syntax and updated examples

---

## Problem 3: Multi-Select SQL — ANY() Over IN
**Status: COMPLETE ✓ (No changes needed)**

### What Was Found
- psycopg2 adapts Python tuples to SQL tuple syntax `('a', 'b')`, NOT PG arrays `{'a','b'}`
- `IN %(param)s` with tuples is **correct** for psycopg2; `ANY()` would break
- The codebase already standardized on `IN` everywhere — `SQL_QUERY_PATTERNS.md` Bug 1 warns against ANY
- Only fix: corrected stale help text in `dashboard_page_filter.py` field that incorrectly said "use ANY()"

### Files Changed
- `models/dashboard_page_filter.py` — Fixed `is_multiselect` field help text

---

## Problem 4: Cascade Resolution — DAG-Based Batch API
**Status: COMPLETE ✓**

### What Was Done
- **New endpoint:** `POST /api/v1/filters/resolve` — single batch call resolves entire cascade DAG
  - BFS graph traversal with visited-set cycle prevention
  - Builds constraints from ALL sources of each target (multi-directional)
  - Handles `resets_target` auto-select logic (same as FilterBar.jsx)
  - Handles `propagation=optional` skip logic
  - Returns all updated filters with options + new values
- **Cycle detection:** `_check_no_cycle` constraint on `dashboard.filter.dependency`
  - DFS-based cycle detection runs on every edge create/update
  - Validates full page DAG remains acyclic
- **React:** `handleBatchCascade()` in FilterBar.jsx
  - Single POST call replaces N sequential GET calls
  - Graceful fallback to `handleGraphCascade` on failure
  - Unified handler now prefers batch → graph → legacy

### Files Changed
- `controllers/widget_api.py` — New `api_filters_resolve()` endpoint
- `models/dashboard_filter_dependency.py` — New `_check_no_cycle` constraint
- `static/src/react/src/api/endpoints.js` — New `filtersResolveUrl()` builder
- `static/src/react/src/components/FilterBar.jsx` — New `handleBatchCascade()`, updated unified handler

---

## Problem 1: URL State — Server-Side Permalink Tokens
**Status: COMPLETE ✓**

### What Was Done
- **New model:** `dashboard.filter.state` with JSONB storage + UUID key
  - `save_state()` → creates record, returns 12-char hex key
  - `load_state()` → finds by key, respects expiry
  - `cleanup_expired()` → cron-ready method for TTL cleanup
  - 7-day default TTL
- **API endpoints:**
  - `POST /api/v1/filter-state/save` — saves config, returns key
  - `GET /api/v1/filter-state/load?key=<token>` — loads config
- **React (FilterContext.jsx):**
  - On mount: detects `?state=<key>`, loads config from server
  - On Apply: if URL would exceed 2000 chars, saves server-side and uses `?state=<key>` URL
  - Graceful fallback to direct URL params if save fails
  - Extracted `_pushUrlParams()` helper for reuse
- **Portal (portal.py):** Step 7b resolves permalink key into `kw` before filter processing
- **Security:** ACL records for portal (read+create) and admin (full CRUD)

### Files Created
- `models/dashboard_filter_state.py` — New model

### Files Changed
- `models/__init__.py` — Registered new model
- `controllers/widget_api.py` — New save/load endpoints
- `controllers/portal.py` — Permalink resolution in step 7b
- `static/src/react/src/api/endpoints.js` — New URL builders
- `static/src/react/src/state/FilterContext.jsx` — Permalink load/save logic
- `security/dashboard_access.xml` — ACL for new model

---

## Testing Checklist

### Problem 2
- [ ] Widget with `{where_clause}` + "All" selected → WHERE 1=1 (no filtering)
- [ ] Widget with `[[AND col IN %(param)s]]` + "All" → clause removed
- [ ] Widget with `[[...]]` + specific value → clause present
- [ ] API refresh path (widget_api.py) produces same sql_params as portal.py

### Problem 4
- [ ] Change State dropdown → single POST to /filters/resolve
- [ ] Response includes all downstream filter options
- [ ] Auto-select works (1 option + resets_target + no include_all_option)
- [ ] Cycle detection rejects A→B→A dependency creation
- [ ] Batch fallback to graph cascade on error

### Problem 1
- [ ] Select 7+ multi-select values → Apply → URL uses ?state=<key>
- [ ] Reload page with ?state=<key> → filters restored
- [ ] Simple filters (< 2000 chars) → direct URL params (no permalink)
- [ ] Expired permalink key → empty config (graceful degradation)
