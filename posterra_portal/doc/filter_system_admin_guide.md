# Filter System — Admin Guide

## Overview

The Posterra filter system powers all dashboard dropdowns (Provider, State, County, City, Year, Payer, etc.) across every app and page. Everything is admin-configurable — no code changes needed to add filters, change cascade behavior, or set up new apps.

This guide covers how filters work, how to configure them, and how to troubleshoot common issues.

---

## How Filters Work

### Page Load Flow

When a user visits a dashboard page (e.g., `/my/posterra?hha_ccn=017014&year=2024`):

1. **Provider Resolution**: The system finds the filter marked as "Provider Selector" and reads the URL parameter (e.g., `hha_ccn=017014`) to identify which provider the user selected.

2. **Auto-Fill**: If a provider is identified, all filters with "Auto-fill from HHA" enabled are pre-populated with that provider's data (e.g., State = "Alabama", County = "CULLMAN").

3. **Auto-Select**: For any filter where the cascade produces exactly 1 valid option and the filter does NOT have "Include All" enabled, that option is automatically selected.

4. **Options Fetching**: Each filter's dropdown options are fetched from the configured data source (schema source table or ORM model), constrained by parent filter values.

5. **Widget Data**: All filter values are passed as SQL parameters to widget queries.

### Interactive Cascade Flow

When a user changes a filter dropdown (before clicking Apply):

1. The system looks up all **Filter Dependencies** for that filter.
2. For each dependent filter, new options are fetched from the server with the new constraint.
3. If the dependency has **Reset Value = ON**:
   - If exactly **1 option** exists and "Include All" is OFF → **auto-select** that option
   - If **0 or 2+ options** exist → reset to "All" (user must choose)
4. If the dependency has **Reset Value = OFF**: keep the current value if it's still valid in the new options.
5. The cascade recurses into children of children (e.g., Provider → State → County → City).

---

## Filter Configuration

### Context Filters Tab (Per Page)

Navigate to **Settings → Dashboard → Pages → [Page Name] → Context Filters**.

Each row defines one dropdown in the portal filter bar:

| Column | What It Does |
|--------|-------------|
| **Table** | The schema source (materialized view) this filter pulls options from |
| **Column** | Which column in that table provides the filter values |
| **Source Column** | The column name used for URL params and SQL (e.g., `hha_ccn`, `hha_state`) |
| **Label** | Display name shown in the portal (e.g., "Provider", "State") |
| **Default Value** | Pre-selected value when no URL param is present |
| **Placeholder** | Hint text shown when no value is selected |
| **URL Param** | The query parameter name in the URL (e.g., `hha_ccn`, `year`) |
| **Manual Options** | Hardcoded options (one per line) — overrides database lookup |
| **HHA Scope** | Restrict options to the logged-in user's accessible providers |
| **HHA Scope Column** | Which column in the schema source contains HHA CCN values for scoping |
| **Auto-fill from HHA** | Pre-populate this filter from the selected provider's record on page load |
| **Provider Selector** | **Mark this filter as THE provider selector** (see below) |
| **Visible** | Show in portal filter bar (OFF = hidden SQL context param only) |
| **Display Template** | Composite label format (e.g., `{hha_ccn} - {hha_brand_name}`) |
| **Include "All"** | Prepend an "All N items" option at top of dropdown |
| **Multi-select** | Allow selecting multiple values (CSV in URL) |
| **Searchable** | Enable search box in dropdown |

### Provider Selector Flag

**Critical**: Exactly ONE filter per page must have **Provider Selector = ON**. This tells the system which filter represents the HHA provider for:

- Resolving the selected provider from URL parameters
- Auto-filling geo filters (State, County, City) from provider data
- Building geo data context for widgets

**Without this flag**: `selected_provider` will be `None`, auto-fill won't fire, and State/County/City will show "All" even when a provider is selected.

**How to set it**:
1. Go to **Settings → Dashboard → Pages → [Page Name] → Context Filters**
2. Find the Provider filter row
3. Toggle **Provider Selector** to ON (green)
4. Ensure no other filter on the same page has this toggle ON

### Auto-Fill from HHA

Enable this on geo filters (State, County, City) that should be pre-populated from the selected provider's record.

**How it works**: When a single provider is selected (via URL or single-provider user), the system reads the provider's `hha_state`, `hha_county`, `hha_city` fields and sets the corresponding filter values.

**Requirements**:
- The filter's **URL Param** must match the `hha.provider` field name (e.g., `hha_state` for State)
- **Provider Selector** must be ON for the Provider filter (so `selected_provider` is resolved)

### Auto-Select Behavior

Filters are automatically selected when:
1. The cascade from a parent filter produces **exactly 1 valid option**
2. The filter does **NOT** have **Include "All"** enabled
3. The filter's current value is empty

**Example**: Provider "047114 - JORDAN HOME HEALTH CARE" is in Arkansas. When selected:
- State cascade returns `[Arkansas]` (1 option) → auto-selected
- County cascade returns `[MILLER]` (1 option) → auto-selected
- City cascade returns `[TEXARKANA]` (1 option) → auto-selected

If the provider has offices in 2 states, State returns `[Arkansas, Ohio]` (2 options) → stays "All", user must choose.

**Why Provider is NOT auto-selected**: The Provider filter has **Include "All"** enabled, which disables auto-select. Even if only 1 provider matches a state, the user should still see "All 63 Provider" as a valid choice.

---

## Filter Dependencies Tab

Navigate to **Settings → Dashboard → Pages → [Page Name] → Filter Dependencies**.

Each row defines a cascade relationship: "When [source] changes, refresh [target]'s options."

| Column | What It Does |
|--------|-------------|
| **When this changes...** | The source filter that triggers the cascade |
| **...refresh this** | The target filter whose options are refreshed |
| **Propagation** | `Required` = always cascade; `Optional` = skip if target already has a value |
| **Reset Value** | ON = clear target value on source change; OFF = keep if still valid |

### Bidirectional Dependencies

For fully-connected filters (Provider ↔ State ↔ County ↔ City), create edges in **both** directions:

```
Provider → State    (Required, Reset Value ON)
Provider → County   (Required, Reset Value ON)
Provider → City     (Required, Reset Value ON)
State → Provider    (Required, Reset Value ON)
State → County      (Required, Reset Value ON)
State → City        (Required, Reset Value ON)
County → Provider   (Required, Reset Value ON)
County → State      (Required, Reset Value ON)
County → City       (Required, Reset Value ON)
```

This means: changing ANY geo filter refreshes ALL others. The cascade handler prevents infinite loops via a visited-set pattern.

---

## Setting Up a New App's Filters

### Step 1: Create Schema Source

1. Go to **Settings → Dashboard → Schema Sources**
2. Create a new record pointing to your materialized view (e.g., `total_admits`)
3. Add columns: `hha_ccn`, `hha_state`, `hha_county`, `hha_city`, `year`, `ffs_ma`, etc.

### Step 2: Create Filters

On the Page form, go to **Context Filters** tab and add filters:

| Filter | Source Column | URL Param | Key Flags |
|--------|-------------|-----------|-----------|
| Provider | `hha_ccn` | `hha_ccn` | HHA Scope ON, **Provider Selector ON**, Display Template: `{hha_ccn} - {hha_brand_name}` |
| State | `hha_state` | `hha_state` | HHA Scope ON, Auto-fill from HHA ON, Multi-select ON |
| County | `hha_county` | `hha_county` | HHA Scope ON, Auto-fill from HHA ON |
| City | `hha_city` | `hha_city` | HHA Scope ON, Auto-fill from HHA ON |
| Year | `year` | `year` | Default Value: `2024` |
| Payer | `ffs_ma` | `ffs_ma` | Default Value: `MA` |

### Step 3: Create Dependencies

On the Page form, go to **Filter Dependencies** tab and add cascade edges (see Bidirectional Dependencies above).

### Step 4: Set HHA Scope Column

For each filter with **HHA Scope = ON**, set **HHA Scope Column** to the column containing HHA CCN values (typically `hha_ccn`). This restricts dropdown options to the user's accessible providers.

---

## Troubleshooting

### State/County/City show "All" when a Provider is selected

**Check**: Is **Provider Selector** toggled ON for the Provider filter?
- Go to **Context Filters** tab on the page
- Find the Provider row
- Ensure the "Provider Selector" toggle is green

**Check**: Is **Auto-fill from HHA** toggled ON for State/County/City filters?

**Check**: Does the URL contain the correct param? (e.g., `hha_ccn=017014`, not `hha_id=123`)

### Cascade doesn't refresh options when changing a filter

**Check**: Are **Filter Dependencies** configured for that direction?
- If you want State → County cascade, you need a row: Source=State, Target=County

### Provider dropdown shows wrong format

**Check**: Is **Display Template** set correctly? (e.g., `{hha_ccn} - {hha_brand_name}`)
- Template Source should be "Schema Source" if using schema sources

### Filter options include providers from other users

**Check**: Is **HHA Scope** toggled ON for the filter?
**Check**: Is **HHA Scope Column** set to the correct CCN column?

### Multi-CCN URL doesn't auto-select State

The system auto-selects State only when all selected providers share the same state. If `hha_ccn=A,B` where A is in Arkansas and B is in Ohio, State stays "All" because 2 options exist.

### Widgets show wrong data after filter change

Ensure you click **Apply** after changing filters. Filter changes are pending until Apply is clicked. Check the browser network tab for the widget API call to verify `sql_params` contain the expected values.

---

## Bug Fix History

### Fix: State/County/City Not Auto-Populating (March 2026)

**Problem**: When a Provider was selected (via URL or dropdown), State/County/City filters remained "All" instead of auto-populating with the provider's geo data.

**Root Causes**:
1. **Provider identification used `include_all_option`** — a flag that defaults to `False` and was hidden in the admin UI. The system couldn't find the Provider filter, so `selected_provider` was always `None`.
2. **Cascade always reset values to empty** — even when only 1 option was available, the React cascade handler cleared the value instead of auto-selecting.

**Fix**:
1. Added `is_provider_selector` boolean field — an explicit, admin-configurable toggle replacing the unreliable `include_all_option` check.
2. Added cascade auto-select logic — when exactly 1 option exists and `include_all_option` is OFF, the value is auto-selected (both server-side for page load and client-side for interactive changes).

**Action Required**: Toggle **Provider Selector = ON** for the Provider filter on each page.
