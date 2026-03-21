# Filter State Management — Change Document

**Branch:** `claude/busy-mirzakhani`
**Commits:** 4 (feature + security fix + docs + geo_role removal)
**Total:** 18 files changed, +1,217 / -90 lines

---

## What This PR Does

Four production-grade improvements to the dashboard filter system:

| # | Feature | One-Line Summary |
|---|---------|-----------------|
| 1 | **Dynamic SQL** | `[[...]]` bracket syntax — WHERE clauses auto-removed when filter = "All" |
| 2 | **Batch Cascade API** | Single `POST /filters/resolve` replaces N sequential HTTP calls |
| 3 | **Server-Side Permalinks** | Complex filter state stored server-side; URL becomes `?state=<12-char-key>` |
| 4 | **Multi-Tenant Security** | App-scoped permalinks, removed hardcoded field/model names |

---

## Admin Configuration Required

### Only 1 thing needs admin verification:

**`is_provider_selector`** — verify it's ON for exactly 1 filter per page.
- **Where:** Settings → Dashboard → Pages → select page → Context Filters tab
- **Why:** The batch cascade and permalink systems rely on this to identify the Provider filter
- **Note:** This was already required before this PR — just verify it's set

### Everything else is automatic (zero config):

| Feature | How It Activates |
|---------|-----------------|
| `[[...]]` clause omission | Any widget SQL using bracket syntax |
| `__all__` bug fix in API refresh | Always active — fixes existing sentinel handling |
| Batch cascade (1 call vs N) | React auto-uses new endpoint, falls back if unavailable |
| Permalink tokens | Auto-triggers when URL > 2000 chars |
| Cycle detection | Validates every dependency create/update |
| App-scoped state isolation | Automatically uses JWT's app_id |
| Geo values in annotations | Flow through `filter_values_by_name` via param_name — no special setup |

### Optional: Migrate widget SQL to `[[...]]` syntax

Old sentinel checks still work. But bracket syntax gives better PostgreSQL query plan optimization:

```sql
-- OLD (still works, but suboptimal):
WHERE ('__all__' IN %(hha_state)s OR hha_state IN %(hha_state)s)
  AND (%(ffs_ma)s = '' OR ffs_ma = %(ffs_ma)s)

-- NEW (clause disappears when param is "All"/empty):
WHERE TRUE
  [[ AND hha_state IN %(hha_state)s ]]
  [[ AND ffs_ma = %(ffs_ma)s ]]
```

**Where:** Settings → Dashboard → Widgets → select widget → SQL Query field
**Rule:** Every `[[...]]` clause must reference at least one `%(param)s`

---

## Detailed Changes

### 1. Dynamic SQL — "All Means Omit" (`[[...]]` Syntax)

**Problem:** When user selects "All", widget SQL received `('__all__',)` sentinel and each query had to manually check for it. This prevents PostgreSQL from optimizing query plans.

**Solution:**
- New `resolve_optional_clauses(sql, params)` utility in `filter_builder.py`
- Regex `\[\[(.*?)\]\]` matches bracketed clauses
- For each clause, checks all `%(param)s` references — if ANY param is `None`, `''`, `'all'`, or `('__all__',)` sentinel, the clause is removed entirely
- Each unique filter combination produces a different SQL shape → PostgreSQL optimizes each independently

**Bug fix:** `widget_api.py` `_build_portal_ctx()` was missing the `('__all__',)` sentinel tuple for multiselect filters with "All" selected. API refresh calls would break when user selected "All" on the page. Now fixed — `_build_portal_ctx()` mirrors portal.py's sentinel logic.

**Files:**
| File | Change |
|------|--------|
| `utils/filter_builder.py` | **NEW** `resolve_optional_clauses()` + regex constants |
| `models/dashboard_widget.py` | `[[...]]` processing in `_execute_sql()` |
| `models/dashboard_page_section.py` | Same `[[...]]` processing |
| `controllers/widget_api.py` | Bug fix: sentinel tuple + helper params in `_build_portal_ctx()` |
| `docs/SQL_QUERY_PATTERNS.md` | Documented syntax, updated examples |

---

### 2. Batch Cascade API (DAG-Based Resolution)

**Problem:** Changing one filter (e.g., State) triggered N sequential HTTP calls — one per cascade tier (County, City, Provider, etc.). Slow on complex pages.

**Solution:**
- New `POST /api/v1/filters/resolve` endpoint
- Server does BFS walk of the dependency DAG in a single request
- Returns all downstream filter options + auto-selected values in one response
- React applies all updates in one sweep

**Request/Response:**
```
POST /api/v1/filters/resolve
Body: {
  page_id: 42,
  changed_filter_id: 101,
  changed_value: "OH",
  current_values: {hha_state: "OH", year: "2024", ...}
}

Response: {
  updated_filters: {
    "102": {param_name: "hha_county", options: [...], new_value: "", value_changed: true},
    "103": {param_name: "hha_city",   options: [...], new_value: "", value_changed: true}
  }
}
```

**Cycle detection:** New `_check_no_cycle` constraint on `dashboard.filter.dependency`. Uses DFS with WHITE/GRAY/BLACK coloring — GRAY→GRAY = back edge = cycle → raises `ValidationError`. Scoped to page_id.

**Graceful fallback:** If batch endpoint fails (network/server error), React falls back to existing per-target `handleGraphCascade` — zero user-visible impact.

**Files:**
| File | Change |
|------|--------|
| `controllers/widget_api.py` | New `api_filters_resolve()` with BFS DAG traversal |
| `models/dashboard_filter_dependency.py` | `_check_no_cycle` DFS constraint (+50 lines) |
| `static/src/react/src/components/FilterBar.jsx` | `handleBatchCascade()` + fallback |
| `static/src/react/src/api/endpoints.js` | `filtersResolveUrl()` |

---

### 3. Server-Side Permalinks

**Problem:** URLs exceed ~2000 character browser/server limit with 7+ multi-select filters.

**Solution:**
- New `dashboard.filter.state` model stores filter configs as JSONB
- When Apply produces URL > 2000 chars, React POSTs config to `/api/v1/filter-state/save`
- Server returns 12-char hex key → URL becomes `?state=aE6zJGOJK3k&tab=overview`
- On page load with `?state=<key>`, server/React resolves stored config
- 7-day TTL with cron cleanup
- Backward compatible: simple filters still use direct URL params

**New Model: `dashboard.filter.state`**

| Field | Type | Purpose |
|-------|------|---------|
| `key` | Char (unique, indexed) | 12-char hex token for URL |
| `app_id` | Many2one → saas.app | Multi-tenant isolation — prevents cross-app leakage |
| `page_id` | Many2one → dashboard.page | Which page this state belongs to |
| `user_id` | Many2one → res.users | Who created it (nullable for shared links) |
| `filter_config` | Json | `{param_name: value, ...}` |
| `expires_at` | Datetime | 7-day TTL |

**Resolution priority:** permalink key → URL query params → user's last saved → dashboard defaults

**Files:**
| File | Change |
|------|--------|
| `models/dashboard_filter_state.py` | **NEW** model with save/load/cleanup methods |
| `models/__init__.py` | Registered new model |
| `controllers/widget_api.py` | `POST /filter-state/save` and `GET /filter-state/load` endpoints |
| `controllers/portal.py` | Step 7b: resolve `?state=<key>` before filter processing |
| `security/dashboard_access.xml` | ACL: portal=read+create, admin=full |
| `static/src/react/src/state/FilterContext.jsx` | Permalink load on mount, save on Apply |
| `static/src/react/src/api/endpoints.js` | `filterStateSaveUrl()`, `filterStateLoadUrl()` |

---

### 4. Multi-Tenant Security Fixes

**Issues found and fixed:**

| Issue | Severity | Fix |
|-------|----------|-----|
| `load_state()` had no app scoping | CRITICAL | Added `app_id` field + parameter to `load_state()` |
| `api_filter_state_load` no app check | CRITICAL | Now passes `app_id=app.id` from JWT |
| Portal permalink no app check | CRITICAL | Now passes `app_id=app.id` |
| `model_name == 'hha.provider'` hardcoded in widget_api | MEDIUM | Replaced with `is_provider_selector` flag |
| Geo context extracted via hardcoded param names | MEDIUM | Removed entirely (see below) |

**Geo context simplification:**
Previously, `ctx_state`/`ctx_county`/`ctx_cities` were extracted in a separate loop matching hardcoded param names (`hha_state`, `hha_county`, `hha_city`) and passed to widget annotations.

This was **redundant** — `filter_values_by_name` already contains ALL filter values keyed by their `param_name`. Widget annotations like `%(hha_state)s` work because `hha_state` IS the param_name and it's already in `filter_values_by_name` (Layer 2 in annotation interpolation).

**Removed:** `ctx_state`, `ctx_county`, `ctx_cities` extraction blocks, template value passing, and the initially-added `geo_role` field (deemed unnecessary since filter values already flow automatically).

**Files:**
| File | Change |
|------|--------|
| `models/dashboard_filter_state.py` | `app_id` field, scoped `save_state()`/`load_state()` |
| `controllers/widget_api.py` | App-scoped load, `is_provider_selector` lookup |
| `controllers/portal.py` | App-scoped permalink, removed geo extraction |
| `models/dashboard_widget.py` | Removed redundant geo Layer 4 in annotation interpolation |
| `data/filters_data.xml` | Cleaned up seed data |

---

## Complete File Index (18 files)

| # | File | Status | Description |
|---|------|--------|-------------|
| 1 | `models/dashboard_filter_state.py` | **NEW** | Permalink storage model (JSONB + UUID key, 7-day TTL) |
| 2 | `utils/filter_builder.py` | **NEW** | `resolve_optional_clauses()` for `[[...]]` syntax |
| 3 | `controllers/widget_api.py` | Modified | 4 new endpoints + bug fix + removed hardcoding |
| 4 | `controllers/portal.py` | Modified | Permalink resolution + removed geo extraction |
| 5 | `models/dashboard_widget.py` | Modified | `[[...]]` processing + simplified annotation layers |
| 6 | `models/dashboard_page_section.py` | Modified | `[[...]]` processing |
| 7 | `models/dashboard_page_filter.py` | Modified | Fixed `is_multiselect` help text |
| 8 | `models/dashboard_filter_dependency.py` | Modified | Cycle detection constraint |
| 9 | `models/__init__.py` | Modified | Registered new model |
| 10 | `security/dashboard_access.xml` | Modified | ACL for `dashboard.filter.state` |
| 11 | `data/filters_data.xml` | Modified | Cleaned seed data |
| 12 | `docs/SQL_QUERY_PATTERNS.md` | Modified | `[[...]]` syntax docs + Bug 7 |
| 13 | `static/src/react/src/components/FilterBar.jsx` | Modified | Batch cascade handler |
| 14 | `static/src/react/src/state/FilterContext.jsx` | Modified | Permalink load/save |
| 15 | `static/src/react/src/api/endpoints.js` | Modified | 3 new URL builders |
| 16 | `SKILL.md` | Modified | Updated annotation docs |
| 17 | `CHANGES.md` | **NEW** | This document |
| 18 | `IMPLEMENTATION_TRACKER.md` | **NEW** | Implementation tracking |

---

## How Filter Values Flow (After This PR)

```
Admin creates filter with param_name = "hha_state"
    ↓
User selects "OH" (or "All")
    ↓
portal.py / widget_api.py:
    filter_values_by_name = {"hha_state": "OH", "year": "2024", ...}
    sql_params = {"hha_state": ("OH",), "year": ("2024", "2023"), ...}
    (If "All" → sql_params["hha_state"] = ("__all__",))
    ↓
Widget SQL:  SELECT ... WHERE TRUE [[ AND hha_state IN %(hha_state)s ]]
    → "OH" selected: WHERE TRUE AND hha_state IN ('OH')
    → "All" selected: WHERE TRUE  (clause removed)
    ↓
Widget annotations:  "Agencies in %(hha_state)s"
    → Gets "OH" from filter_values_by_name (Layer 2)
    → No special geo extraction needed
```

---

## Pre-Existing Issues (Out of Scope)

These hardcoded patterns existed before this PR and need separate refactoring:

1. **`hha.provider` field reads** in portal.py: `read(['id', 'hha_state', 'hha_county', 'hha_city'])` — hardcodes provider model field names for geo data extraction. Fixing requires making the provider model configurable per-app.

2. **Provider display fields** in portal.py: `providers[0].hha_dba or providers[0].hha_name` — hardcodes display field selection.

3. **`hha_name` in widget annotations** in dashboard_widget.py: `hha.hha_brand_name or hha.hha_dba or hha.hha_name` — hardcodes HHA-specific field names for the provider display name variable.

---

## Testing Checklist

### Dynamic SQL
- [ ] Widget with `{where_clause}` + "All" selected → generates `WHERE 1=1`
- [ ] Widget with `[[AND col IN %(param)s]]` + "All" → clause removed entirely
- [ ] Widget with `[[...]]` + specific value → clause present in SQL
- [ ] API refresh (widget_api) produces same sql_params as portal.py page load

### Batch Cascade
- [ ] Change State dropdown → single POST to `/api/v1/filters/resolve`
- [ ] Response includes all downstream options + auto-selections
- [ ] Auto-select fires when: 1 option + `resets_target=True` + no `include_all_option`
- [ ] Create circular dependency A→B→A → `ValidationError` on save
- [ ] Batch endpoint failure → graceful fallback to per-target cascade

### Permalinks
- [ ] Select 7+ multi-select values → Apply → URL uses `?state=<key>`
- [ ] Reload page with `?state=<key>` → all filters restored correctly
- [ ] Simple filters (< 2000 chars) → standard URL params (backward compatible)
- [ ] Expired permalink key → empty config, graceful degradation

### Multi-Tenant Isolation
- [ ] Load permalink key from App B while in App A → returns empty config
- [ ] JWT from App A cannot access App B's filter state
- [ ] Widget annotations show correct geo values via `filter_values_by_name`
- [ ] `is_provider_selector` identifies provider filter (not hardcoded `model_name`)
