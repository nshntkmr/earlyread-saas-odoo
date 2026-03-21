# Bug Fix Report: Filter Cascade Scoping & Bidirectional Cascade

**Date:** 2026-03-20
**Module:** `posterra_portal`
**Files Modified:** 5

---

## Bug 1: Filter Options Not Scoped by All Active Selections

### Symptom
When a user selects a Provider (e.g., CCN 017014), the State filter correctly updates to show only the state where that provider operates. But the County filter shows ALL counties in that state, and City shows ALL cities — not just those where the selected provider operates.

### Root Cause (3 layers)

**Layer 1 — `filter_dependencies` never embedded in page HTML (`portal.py`)**
The `_build_page_config_json()` function serialized the page config into a `data-pageConfig` HTML attribute for the React app to read on mount. It included the legacy `filter_dep_map` but **never included `filter_dependencies`** (the new dependency graph array). The React always saw `filter_dependencies = []`, so `useNewDeps = false`, and it fell back to the legacy `handleLegacyCascade` path. The legacy cascade only uses `depends_on_field_name` (the old single-parent system), which only had State configured — not County or City.

**Layer 2 — Stale stored `source_param` / `target_param` on dependency records**
The `dashboard.filter.dependency` model has stored computed fields `source_param` and `target_param` that cache the source/target filter's `param_name`. If these stored values were empty or stale (never recomputed after the filter's `param_name` was set), the React would receive `source_param: ''`. The constraint builder then did `snapshot['']` which returned `undefined`, silently dropping the constraint.

**Layer 3 — API only applied dependency-edge constraints, not all active filter values**
The `/api/v1/filters/cascade/multi` endpoint only applied WHERE constraints from filters explicitly listed in the dependency graph edges. It did not consider other active filters on the same schema source table. So even if Provider was selected, County's query only used constraints from its direct dependency sources — missing any sibling filter values that could further narrow results.

### Fix

**`posterra_portal/controllers/portal.py` — `_build_page_config_json()`**
Added `filter_dependencies` to the serialized page config. Queries `dashboard.filter.dependency` records for the page and builds the dependency array with `source_param`/`target_param` fallbacks (same logic as the API endpoint).

**`posterra_portal/controllers/widget_api.py` — `api_page_config()` and `api_filters_cascade_multi()`**
- Serialization of dependency records now falls back to `src.param_name` or `src.field_name` if the stored `source_param` is empty.
- The `/cascade/multi` endpoint now accepts an `all_values` query parameter (JSON dict of `{param_name: value}`) representing the full current filter state, and passes it through to `get_options()`.

**`posterra_portal/models/dashboard_page_filter.py` — `get_options()` and `_build_schema_where()`**
- `get_options()` accepts a new `all_filter_values` parameter and passes it to the WHERE builders.
- `_build_schema_where()` has a new **section 1b** after the explicit dependency constraints: it searches for ALL filters on the same page sharing the same `schema_source_id` that have an active value in `all_filter_values`, and appends `AND "{column}" = %(param)s` for each. This is fully generic — no hardcoded column names.
- `_build_orm_domain_from_constraints()` has equivalent logic for ORM-based filters sharing the same `model_name`.
- The `dep_is_hha_provider_id` guard now includes `and not src_filter.schema_source_id` so that schema-based Provider filters (where the value is a CCN string, not an Odoo record ID) correctly use the same-source cascade path instead of the cross-type ORM resolution path.

**`posterra_portal/static/src/react/src/api/endpoints.js` — `cascadeMultiUrl()`**
Added `allValues` parameter. When provided, it is JSON-stringified and sent as the `all_values` query parameter.

**`posterra_portal/static/src/react/src/components/FilterBar.jsx` — `handleGraphCascade()`**
- Builds `allValues` from the snapshot (all current `param_name` -> `value` pairs) and passes it to `cascadeMultiUrl()` on every cascade API call.

---

## Bug 2: Reverse/Bidirectional Cascade Not Firing

### Symptom
When the user changes State, the dependency State -> Provider exists in the config but the Provider filter's options do NOT refresh. Downward cascades work (Provider -> State/County/City), but upward/reverse cascades are skipped.

### Root Cause
The original cascade engine used depth-first sequential processing. When processing Provider's targets, it would:
1. Process State (target), then immediately recurse into State's children
2. During recursion, if State -> County existed, County would be marked visited
3. Back at Provider's targets, Provider -> County would be SKIPPED (County already visited)

This meant recursive branches consumed visited-set slots before sibling targets (including reverse edges) were processed.

### Fix

**`posterra_portal/static/src/react/src/components/FilterBar.jsx` — `handleGraphCascade()`**
Restructured into two phases:

- **Phase 1**: Iterate ALL direct targets of the source filter. For each unvisited target: mark visited, fetch options, handle value reset/pruning. Collect into `processedTargets` list.
- **Phase 2**: Recurse into each processed target's children (with the shared visited set preventing infinite loops).

This ensures all sibling targets (including reverse edges like State -> Provider) are processed before any recursive branch can consume visited-set slots.

**Additional cascade improvements:**
- **`propagation: 'optional'`**: Skips refresh if the target already has an explicit user selection.
- **`resets_target: false`**: Keeps the current value but prunes any CSV values no longer in the refreshed options list (multi-select) or clears if the single value is no longer valid.
- **`sourceParam` / `targetParam` fallback resolution**: When building the dependency graph maps, falls back to `filter.param_name` or `filter.field_name` from `filtersById` if the dependency record's stored param is empty.

---

## Files Modified

| File | Changes |
|------|---------|
| `posterra_portal/controllers/portal.py` | Added `filter_dependencies` array to `_build_page_config_json()` |
| `posterra_portal/controllers/widget_api.py` | Added `all_values` param parsing; fallback `source_param`/`target_param` resolution in dependency serialization |
| `posterra_portal/models/dashboard_page_filter.py` | Added `all_filter_values` param to `get_options()`, `_build_schema_where()`, `_build_orm_domain_from_constraints()`, and both schema options methods; added section 1b same-table generic constraints; fixed `dep_is_hha_provider_id` guard for schema-based filters |
| `posterra_portal/static/src/react/src/api/endpoints.js` | Added `allValues` param to `cascadeMultiUrl()` |
| `posterra_portal/static/src/react/src/components/FilterBar.jsx` | Two-phase cascade; `sourceParam`/`targetParam` fallback resolution; `allValues` sent on every cascade call; `propagation` and `resets_target` handling |

---

## Verification Steps

1. Configure dependencies: Provider -> State, Provider -> County, Provider -> City
2. Select a Provider -> verify State, County, and City all scope to that provider's values only
3. Add reverse dependencies (State -> Provider) -> verify selecting State refreshes Provider options
4. Verify multi-select: select 3 providers -> verify 3 states, corresponding counties and cities appear
5. Check browser console for `[CASCADE]` debug logs confirming two-phase processing
6. Check Odoo server logs for `[CASCADE-SQL]` messages confirming correct WHERE clauses
