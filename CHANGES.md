# Filter State Management — Complete Change Document

## Branch: `claude/busy-mirzakhani`
## Commits: 2

---

## Problem 1: URL State Breaks Down Past 6-7 Complex Filters

### What Changed
When a dashboard has 7+ multi-select filters with many selected values, URL query params exceed the ~2000 character browser/server limit. This implementation adds server-side filter state storage with short permalink tokens.

### Architecture
```
User clicks Apply with complex filters
    → FilterContext.jsx checks: URL params > 2000 chars?
        → YES: POST /api/v1/filter-state/save → stores JSONB, returns 12-char key
                URL becomes ?state=aE6zJGOJK3k&tab=overview
        → NO:  Standard URL params (backward compatible)

User loads page with ?state=<key>
    → Server (portal.py step 7b): load_state(key, app_id=app.id)
    → React (FilterContext.jsx): apiFetch(filterStateLoadUrl) → merge into state
    → Resolution priority: permalink → URL params → defaults
```

### New Model: `dashboard.filter.state`

| Field | Type | Purpose |
|-------|------|---------|
| `key` | Char (unique, indexed) | 12-char hex token for URL |
| `app_id` | Many2one → saas.app | **Multi-tenant isolation** |
| `page_id` | Many2one → dashboard.page | Which page this state belongs to |
| `user_id` | Many2one → res.users | Who created it (nullable for shared links) |
| `filter_config` | Json | `{param_name: value, ...}` |
| `expires_at` | Datetime | 7-day TTL, cron-cleanable |

### Multi-Tenant Safety
- `save_state()` requires `app_id` — stored on every record
- `load_state()` accepts `app_id` parameter — filters results to prevent cross-app leakage
- `api_filter_state_load` endpoint passes JWT user's `app.id` to `load_state()`
- Portal permalink resolution passes current `app.id`
- A user from App A **cannot** load filter state created in App B

### Files
| File | What Changed |
|------|-------------|
| `models/dashboard_filter_state.py` | **NEW** — model with save/load/cleanup methods |
| `models/__init__.py` | Registered new model |
| `controllers/widget_api.py` | New `POST /filter-state/save` and `GET /filter-state/load` endpoints |
| `controllers/portal.py` | Step 7b: resolve `?state=<key>` into filter params before processing |
| `security/dashboard_access.xml` | ACL: portal=read+create, admin=full |
| `static/src/react/src/state/FilterContext.jsx` | Permalink load on mount, save on Apply when complex |
| `static/src/react/src/api/endpoints.js` | `filterStateSaveUrl()`, `filterStateLoadUrl()` |

---

## Problem 2: "All Means Omit" — Dynamic SQL Generation

### What Changed
When a user selects "All" for a filter, the WHERE clause for that filter should be **omitted entirely** (not pass all values). The `DashboardFilterBuilder` already handled this for Category A/B widgets using `{where_clause}`. This implementation adds:

1. **Bug fix**: `widget_api.py` was missing the `('__all__',)` sentinel tuple in `_build_portal_ctx()`, causing API refresh calls to break for "All" selections.

2. **`[[...]]` bracket syntax**: Category C manual SQL can now use optional clauses that auto-disappear when the referenced param is empty/all.

### How `[[...]]` Works
```sql
-- Before (anti-pattern — sentinel check in every query):
WHERE ('__all__' IN %(hha_state)s OR hha_state IN %(hha_state)s)
  AND (%(ffs_ma)s = '' OR ffs_ma = %(ffs_ma)s)

-- After (clause disappears when param is __all__/empty/null):
WHERE TRUE
  [[ AND hha_state IN %(hha_state)s ]]
  [[ AND ffs_ma = %(ffs_ma)s ]]
```

When `hha_state = ('__all__',)`, the first clause is removed entirely. When `ffs_ma = 'MA'`, the second clause stays. Result: each unique filter combination produces a different SQL shape → PostgreSQL optimizes each independently.

### Implementation
- `resolve_optional_clauses(sql, params)` in `filter_builder.py` — shared utility, no Odoo imports
- Regex `\[\[(.*?)\]\]` matches bracketed clauses
- For each clause, checks all `%(param)s` references — if ANY param is meaningless (None, '', 'all', `__all__` sentinel), the clause is removed
- Integrated into both `dashboard_widget.py._execute_sql()` and `dashboard_page_section.py._execute_sql()` before SQL validation

### Files
| File | What Changed |
|------|-------------|
| `utils/filter_builder.py` | New `resolve_optional_clauses()` function + regex constants |
| `models/dashboard_widget.py` | `[[...]]` processing before SQL execution |
| `models/dashboard_page_section.py` | Same `[[...]]` processing |
| `controllers/widget_api.py` | Bug fix: `_build_portal_ctx()` now creates `('__all__',)` + helper params |
| `docs/SQL_QUERY_PATTERNS.md` | Documented `[[...]]` syntax, updated Category C examples, Bug 7 |

---

## Problem 3: Multi-Select SQL — ANY() vs IN

### What Changed
**No code changes needed.** The research doc recommended `ANY()` over `IN`, but this doesn't apply to our stack:

- psycopg2 adapts Python tuples to SQL tuple syntax `('a', 'b')` — works with `IN`
- `ANY()` needs PostgreSQL array syntax `{'a','b'}` — psycopg2 only produces this from lists
- The codebase already correctly standardized on `IN %(param)s` everywhere
- `SQL_QUERY_PATTERNS.md` Bug 1 explicitly warns against `ANY()`

Only fix: corrected stale help text on `is_multiselect` field that incorrectly said "use ANY()".

### Files
| File | What Changed |
|------|-------------|
| `models/dashboard_page_filter.py` | Fixed `is_multiselect` help text: "ANY()" → "IN" |

---

## Problem 4: Cascade Resolution — DAG-Based Batch API

### What Changed
Previously, changing a filter triggered N sequential HTTP calls (one per cascade tier). Now a single `POST /api/v1/filters/resolve` call resolves the entire dependency graph server-side.

### Architecture
```
User changes State dropdown
    → React: POST /api/v1/filters/resolve
        Body: {
          page_id: 42,
          changed_filter_id: 101,
          changed_value: "OH",
          current_values: {hha_state: "OH", year: "2024", ...}
        }
    → Server: BFS walk of dependency DAG
        Level 0: State (changed)
        Level 1: County, Provider (targets of State)
        Level 2: City (target of County)
        For each: get_options() → determine new value → update snapshot
    → Response: {
          updated_filters: {
            "102": {param_name: "hha_county", options: [...], new_value: "", value_changed: true},
            "103": {param_name: "hha_city",   options: [...], new_value: "", value_changed: true},
            ...
          }
        }
    → React: Apply all option updates + value changes in one sweep
```

### Cycle Detection
New `_check_no_cycle` constraint on `dashboard.filter.dependency`:
- Runs DFS on the full page's dependency graph on every edge create/update
- Uses WHITE/GRAY/BLACK coloring — GRAY → GRAY = back edge = cycle
- Raises `ValidationError` if cycle detected
- Scoped to `page_id` — edges from different pages don't interfere

### Graceful Fallback
If the batch endpoint fails (network error, server error), React falls back to the existing per-target `handleGraphCascade` — zero user-visible impact.

### Files
| File | What Changed |
|------|-------------|
| `controllers/widget_api.py` | New `POST /api/v1/filters/resolve` with BFS DAG traversal |
| `models/dashboard_filter_dependency.py` | `_check_no_cycle` DFS constraint |
| `static/src/react/src/components/FilterBar.jsx` | `handleBatchCascade()`, updated unified handler |
| `static/src/react/src/api/endpoints.js` | `filtersResolveUrl()` |

---

## Multi-Tenant Security Audit Fixes

### What Changed
Audit revealed cross-app isolation gaps and hardcoded field names. All fixed:

| Issue | Severity | Fix |
|-------|----------|-----|
| `load_state()` had no app scoping | CRITICAL | Added `app_id` field + parameter to `load_state()` |
| `api_filter_state_load` no app check | CRITICAL | Now passes `app_id=app.id` |
| Portal permalink no app check | CRITICAL | Now passes `app_id=app.id` |
| `model_name == 'hha.provider'` hardcoded | MEDIUM | Replaced with `is_provider_selector` flag |
| Geo context extraction hardcoded | MEDIUM | **Removed entirely** — geo values flow through `filter_values_by_name` via param_name |

### Geo Context Simplification

Previously, `ctx_state`/`ctx_county`/`ctx_cities` were extracted in a separate loop and passed to widget annotations.
This was redundant — `filter_values_by_name` already contains all filter values keyed by `param_name`.
Widget annotation templates like `%(hha_state)s` work because `hha_state` IS the param_name, and it's already in `filter_values_by_name`.

**Removed:** `geo_role` field, `ctx_state`/`ctx_county`/`ctx_cities` extraction blocks, template value passing.
**No admin configuration needed** — geo filter values flow automatically through the standard filter→sql_params pipeline.

### Files
| File | What Changed |
|------|-------------|
| `models/dashboard_filter_state.py` | Added `app_id` field, updated `save_state()`/`load_state()` |
| `controllers/widget_api.py` | App-scoped load, `is_provider_selector` lookup, removed geo extraction |
| `controllers/portal.py` | App-scoped permalink, removed geo extraction |
| `models/dashboard_page_filter.py` | Removed `geo_role` field (unnecessary) |
| `data/filters_data.xml` | Removed `geo_role` values from seed data |

---

## Complete File Index

| # | File | Status | Lines Changed |
|---|------|--------|---------------|
| 1 | `models/dashboard_filter_state.py` | **NEW** | +126 |
| 2 | `IMPLEMENTATION_TRACKER.md` | **NEW** | +95 |
| 3 | `controllers/widget_api.py` | Modified | +360, -18 |
| 4 | `controllers/portal.py` | Modified | +20, -8 |
| 5 | `utils/filter_builder.py` | Modified | +40 |
| 6 | `models/dashboard_widget.py` | Modified | +5 |
| 7 | `models/dashboard_page_section.py` | Modified | +5 |
| 8 | `models/dashboard_page_filter.py` | Modified | +10, -2 |
| 9 | `models/dashboard_filter_dependency.py` | Modified | +50 |
| 10 | `models/__init__.py` | Modified | +1 |
| 11 | `security/dashboard_access.xml` | Modified | +20 |
| 12 | `data/filters_data.xml` | Modified | +3 |
| 13 | `docs/SQL_QUERY_PATTERNS.md` | Modified | +55, -25 |
| 14 | `static/src/react/src/components/FilterBar.jsx` | Modified | +62, -6 |
| 15 | `static/src/react/src/state/FilterContext.jsx` | Modified | +86, -10 |
| 16 | `static/src/react/src/api/endpoints.js` | Modified | +31 |

---

## Pre-Existing Issues Not Addressed (Out of Scope)

These hardcoded patterns existed before this PR and require deeper refactoring:

1. **`hha.provider` field reads** in portal.py (lines 490-517): `geo_records = request.env['hha.provider'].sudo().browse(...).read(['id', 'hha_state', 'hha_county', 'hha_city'])` — hardcodes provider model field names for geo data extraction. Fixing requires making the provider model itself configurable per-app.

2. **`hha_dba` / `hha_name` display fields** in portal.py (line 471): `providers[0].hha_dba or providers[0].hha_name` — hardcodes provider display field selection.

These should be addressed in a separate PR focused on making the provider model generic across apps.

---

## Testing Checklist

### Problem 2 — Dynamic SQL
- [ ] Widget with `{where_clause}` + "All" → WHERE 1=1
- [ ] Widget with `[[AND col IN %(param)s]]` + "All" → clause removed
- [ ] Widget with `[[...]]` + specific value → clause present
- [ ] API refresh (widget_api) produces same sql_params as portal.py

### Problem 4 — Batch Cascade
- [ ] Change State → single POST to /filters/resolve
- [ ] Response includes all downstream options + auto-selections
- [ ] Auto-select fires when 1 option + resets_target + no include_all_option
- [ ] Create A→B→A dependency → ValidationError
- [ ] Batch failure → graceful fallback to graph cascade

### Problem 1 — Permalinks
- [ ] 7+ multi-select values → Apply → URL uses `?state=<key>`
- [ ] Reload with `?state=<key>` → filters restored
- [ ] Simple filters (< 2000 chars) → direct URL params
- [ ] Expired key → empty config (graceful degradation)

### Multi-Tenant Isolation
- [ ] Cross-app permalink key → empty config
- [ ] JWT from App A cannot load App B's filter state
- [ ] Widget annotations get geo values via `filter_values_by_name` (no special extraction)
- [ ] `is_provider_selector` identifies provider filter (not `model_name`)
