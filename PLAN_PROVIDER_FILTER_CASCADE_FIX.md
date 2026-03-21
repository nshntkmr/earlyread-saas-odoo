# Provider Filter Cascade Fix — Implementation Plan

## Relationship to Other Plans

This plan fixes the **immediate Provider → State cascade bug** using the existing `dashboard.page.filter` system. It can be shipped independently and does not require any architecture changes.

For the broader architectural changes (new `saas.app` scope fields, `saas.app.user.scope` model, DataService abstraction, audit log, `hha_id` → `entity_ids` SQL migration), see: [PLAN_ARCHITECTURE_CHANGES_HHA.md](./PLAN_ARCHITECTURE_CHANGES_HHA.md). Those changes build on top of this fix.

---

## Problem Statement

Two bugs in the Posterra portal filter bar:

**Bug 1 — State/County/City show unscoped data.** When John Wick (Elara Caring, 63 CCNs) opens the portal, the State dropdown shows every US state instead of only the ~15 states where Elara operates. The `scope_to_user_hha` mechanism exists and is turned ON for geo filters, but the Provider selection doesn't propagate into the cascade, so geo filters only scope to the user's full provider set — never to a single selected provider.

**Bug 2 — Provider selection doesn't cascade.** When John picks `197161 - Elara Caring` from the Provider dropdown, State/County/City should immediately narrow to where that one CCN operates. Currently the cascade chain is `State → County → City`. The Provider dropdown is hardcoded outside the filter system and doesn't participate in the cascade at all.

## Root Cause

The Provider dropdown (HHA selector) is **not a `dashboard.page.filter` record**. It is a separate, hardcoded construct:

- **Server-side** (`portal.py` lines 274–325): The controller builds `selector_options` from `_get_providers_for_user()` and embeds them into `page_config_json` under the `hha_selector` key — completely separate from the `filters` array.
- **React-side** (`FilterBar.jsx` lines 43–68): The HHA selector is rendered as its own `<select>` block with a dedicated `handleHhaChange` that only calls `setPendingFilter('hha_id', value)` — no cascade trigger, no child filter refresh.
- **Cascade logic** (`FilterBar.jsx` lines 24–41): The `handleFilterChange` function finds child filters via `depends_on_field_name` matching. Since Provider is not in the `filters` array, no filter has `depends_on_field_name === 'hha_id'`, so nothing cascades.

The admin has zero control over the Provider dropdown — can't change its label, sequence, cascade behavior, or turn it off.

## Solution: Make Provider a Real `dashboard.page.filter` Record

Promote the Provider dropdown from a hardcoded one-off into a standard filter record. The admin configures it from the same Page form → Context Filters tab, with the same cascade mechanism as State → County → City.

**After the fix, the cascade chain becomes:**
```
Provider (seq 5)  →  State (seq 10)  →  County (seq 20)  →  City (seq 30)
```

**Cascade vs Apply — the UX contract:**

| Action | What happens immediately | What requires Apply |
|--------|--------------------------|---------------------|
| Change Provider | State/County/City options repopulate | Widget data does NOT refresh |
| Change State | County/City options repopulate | Widget data does NOT refresh |
| Change County | City options repopulate | Widget data does NOT refresh |
| Change Year | Nothing cascades | Widget data does NOT refresh |
| Change Payer | Nothing cascades | Widget data does NOT refresh |
| Click Apply | Nothing cascades | ALL widgets refetch with full param set |

Cascade = instant, no Apply needed. Widget data refresh = only on Apply.

## Scope & Non-Scope

**In scope:**
- New fields on `dashboard.page.filter` model
- Changes to `get_options()` to support display templates
- Seed data for Provider filter records on every page
- Remove hardcoded `hha_selector` from `portal.py` and `_build_page_config_json()`
- Unify Provider into the React filter loop with cascade support
- Cascade endpoint supports the new Provider → State flow

**NOT in scope (unaffected):**
- Login flow (`posterra_login()`, `_login_redirect()`, `_has_posterra_access()`)
- `_get_providers_for_user()` function — unchanged
- `saas.app` model — no changes
- `hha.scope.group` model — no changes
- Widget models and rendering
- Dashboard Builder module
- Any provisioning or entity_type rework

---

## Phase 1: Model Changes (`dashboard_page_filter.py`)

### 1.1 New Fields

Add two fields to `DashboardPageFilter`:

```python
# ── Display template ──────────────────────────────────────────────────────
# When the filter's Column is 'id' (record primary key), the raw value
# is a numeric ID — not useful as a dropdown label.  display_template
# lets the admin format labels from other columns on the same table.
#
# Example: "{hha_ccn} - {hha_brand_name}" → "197161 - Elara Caring"
#
# When blank, labels come from the Column value itself (current behavior).
display_template = fields.Char(
    string='Display Template',
    help='Optional template for dropdown option labels.\n'
         'Use {field_name} placeholders to insert column values.\n'
         'Example: "{hha_ccn} - {hha_brand_name}"\n'
         'Only needed when Column = id and you want a human-readable label.',
)

# ── "All" option ──────────────────────────────────────────────────────────
# When ON, the dropdown prepends an "All" option (value='') at the top.
# For Provider: "All 63 HHAs".  For geo filters: already handled by
# React's hardcoded <option value="">All</option>.
include_all_option = fields.Boolean(
    string='Include "All" Option',
    default=False,
    help='When ON, the portal dropdown shows an "All" option at the top.\n'
         'The label is "All" followed by the option count (e.g. "All 63 HHAs").\n'
         'Use for the Provider filter or any filter where "no selection" = "all".',
)
```

### 1.2 Changes to `get_options()`

The method currently uses `_read_group()` which returns distinct values of a single column. This works for State/County/City (the distinct value IS the label). But for Provider where `field_name='id'`, we need composite labels from multiple columns.

**New logic branch — when `display_template` is set:**

```python
import re

def get_options(self, parent_value=None, provider_ids=None):
    self.ensure_one()
    if self.manual_options:
        return self.get_manual_options_list()

    if not self.model_name or not self.field_name:
        return []

    try:
        Model = self.env[self.model_name].sudo()
    except KeyError:
        return []

    # ── Build domain (unchanged) ─────────────────────────────────────
    domain = []
    dep = self.depends_on_filter_id
    if parent_value and dep:
        dep_model = (dep.model_id.model or dep.model_name or '').strip()
        dep_field = (dep.field_id.name or dep.field_name or '').strip()
        self_model = self.model_name or ''
        if dep_field and dep_model and dep_model == self_model:
            # When parent Column is 'id', cast parent_value to int
            if dep_field == 'id':
                try:
                    domain = [('id', '=', int(parent_value))]
                except (ValueError, TypeError):
                    pass
            else:
                domain = [(dep_field, '=', parent_value)]

    # ── HHA scoping (unchanged) ──────────────────────────────────────
    if (self.scope_to_user_hha
            and provider_ids
            and self.model_name == 'hha.provider'):
        domain = domain + [('id', 'in', provider_ids)]

    # ── NEW: display_template path ───────────────────────────────────
    if self.display_template:
        return self._get_options_with_template(Model, domain)

    # ── Existing _read_group path (unchanged) ────────────────────────
    try:
        groups = Model._read_group(
            domain=domain,
            groupby=[self.field_name],
            aggregates=[],
        )
        # ... (existing code unchanged)
    except Exception as exc:
        return []


def _get_options_with_template(self, Model, domain):
    """Fetch options using search_read + display_template formatting.

    Used when the filter value is a record ID but the label needs
    columns from the same record (e.g. "{hha_ccn} - {hha_brand_name}").
    """
    template = self.display_template
    # Extract {field_name} placeholders
    template_fields = re.findall(r'\{(\w+)\}', template)
    read_fields = list(set([self.field_name] + template_fields))

    try:
        records = Model.search_read(
            domain,
            fields=read_fields,
            order=template_fields[0] + ' asc' if template_fields else 'id asc',
        )
    except Exception as exc:
        _logger.warning(
            'dashboard.page.filter %s: search_read error: %s', self.id, exc)
        return []

    options = []
    for rec in records:
        raw_val = rec.get(self.field_name)
        if raw_val is None or raw_val is False:
            continue
        # Build label from template
        label = template
        for tf in template_fields:
            val = rec.get(tf, '') or ''
            label = label.replace('{' + tf + '}', str(val).strip())
        label = label.strip()
        # Value = string of the filter column value (typically 'id')
        value = str(raw_val).strip()
        if value and label:
            options.append({'value': value, 'label': label})

    return sorted(options, key=lambda o: o['label'].lower())
```

### 1.3 Domain builder — handle `id` as parent field

In `get_options()`, when the parent filter's `field_name` is `'id'`, the `parent_value` coming from the cascade endpoint is a string like `"12345"`. The current domain builder does `(dep_field, '=', parent_value)` which compares an integer column to a string. Odoo's ORM handles this for char fields but not for `id`.

**Fix:** Add an `int()` cast when `dep_field == 'id'`:

```python
# In the existing domain builder block:
if dep_field == 'id':
    try:
        domain = [('id', '=', int(parent_value))]
    except (ValueError, TypeError):
        pass  # skip — invalid parent value
else:
    domain = [(dep_field, '=', parent_value)]
```

### 1.4 Admin View Changes (`page_views.xml`)

Add the two new fields to the inline filter list in the Page form:

```xml
<!-- After the "Auto-fill from HHA" toggle -->
<field name="display_template"
       string="Display Template"
       placeholder='e.g. {hha_ccn} - {hha_brand_name}'
       optional="hide"/>
<field name="include_all_option"
       string='Include "All"'
       optional="hide"
       widget="boolean_toggle"/>
```

These are `optional="hide"` so they don't clutter the default view — admin expands them when needed.

---

## Phase 2: Seed Data Changes (`filters_data.xml`)

### 2.1 Add Provider Filter to Every Page That Has Geo Filters

For each page that currently has State/County/City filters, add a Provider filter at sequence 5 (before State at 10) and wire State's `depends_on_filter_id` to point at it.

**Overview page example:**

```xml
<!-- ── Provider filter (NEW) ──────────────────────────────────────── -->
<record id="filter_overview_provider" model="dashboard.page.filter">
    <field name="page_id" ref="page_overview"/>
    <field name="model_id" model="ir.model"
           search="[('model', '=', 'hha.provider')]"/>
    <field name="field_id" model="ir.model.fields"
           search="[('model', '=', 'hha.provider'), ('name', '=', 'id')]"/>
    <field name="label">Provider</field>
    <field name="param_name">hha_id</field>
    <field name="display_template">{hha_ccn} - {hha_brand_name}</field>
    <field name="include_all_option" eval="True"/>
    <field name="sequence">5</field>
    <field name="is_active">True</field>
    <field name="scope_to_user_hha" eval="True"/>
</record>

<!-- ── State filter (MODIFIED — now depends on Provider) ──────────── -->
<record id="filter_overview_state" model="dashboard.page.filter">
    <field name="page_id" ref="page_overview"/>
    <field name="model_id" model="ir.model"
           search="[('model', '=', 'hha.provider')]"/>
    <field name="field_id" model="ir.model.fields"
           search="[('model', '=', 'hha.provider'), ('name', '=', 'hha_state')]"/>
    <field name="label">State</field>
    <field name="sequence">10</field>
    <field name="is_active">True</field>
    <field name="scope_to_user_hha" eval="True"/>
    <field name="auto_fill_from_hha" eval="True"/>
    <!-- NEW: depends on Provider instead of being independent -->
    <field name="depends_on_filter_id" ref="filter_overview_provider"/>
</record>

<!-- County and City remain unchanged (County depends on State, City depends on County) -->
```

### 2.2 Pages That Need Provider Filters

Every page that currently has a State filter needs a Provider filter added:

| Page | State filter XML ID | New Provider filter XML ID | State `depends_on` changes to |
|------|--------------------|-----------------------------|-------------------------------|
| Overview | `filter_overview_state` | `filter_overview_provider` | `filter_overview_provider` |
| Hospitals | `filter_hospitals_state` | `filter_hospitals_provider` | `filter_hospitals_provider` |
| Physicians | `filter_physicians_state` | `filter_physicians_provider` | `filter_physicians_provider` |
| Competitive Intel | `filter_competitive_state` | `filter_competitive_provider` | `filter_competitive_provider` |
| Market Threats | `filter_mt_state` | `filter_mt_provider` | `filter_mt_provider` |
| Episodes | `filter_episodes_state` | `filter_episodes_provider` | `filter_episodes_provider` |
| Referral Sources | `filter_rs_state` | `filter_rs_provider` | `filter_rs_provider` |

All Provider filter records use the same configuration:
- Table: `hha.provider`
- Column: `id`
- Display Template: `{hha_ccn} - {hha_brand_name}`
- Include "All" Option: True
- Scope to User's HHAs: True
- URL Param: `hha_id`
- Sequence: 5

### 2.3 noupdate Consideration

The geo filters are seeded with `noupdate="0"` (always rewritten on upgrade). Provider filters should use the same block so they're always consistent. The `depends_on_filter_id` change on State filters also needs `noupdate="0"` to take effect on upgrade.

---

## Phase 3: Controller Changes (`portal.py`)

### 3.1 Remove Hardcoded `hha_selector` from `_build_page_config_json()`

**Current** (lines 48–92): The function builds an `hha_selector` key in the JSON with the provider options and current selection.

**After:** Remove the `hha_selector` key entirely. Provider is now in the `filters` array like any other filter. The JSON shape becomes:

```python
# REMOVE this block from _build_page_config_json():
'hha_selector': {
    'options':        selector_options,
    'current_hha_id': str(current_hha_id) if current_hha_id else 'all',
} if app.access_mode == 'hha_provider' else None,
```

### 3.2 Remove `selector_options` Construction from `app_dashboard()`

**Current** (lines 274–325): A 50-line block that builds `selector_options`, `org_display_name`, `current_hha_label`, `current_hha_id` from the provider recordset.

**After:** This block is replaced by the filter system. The Provider filter's `get_options()` with `display_template` handles option building. The controller still needs to:

1. Resolve `selected_provider` from `hha_id` URL param (for `auto_fill_from_hha`, geo data, sql_params) — this stays.
2. Pass `accessible_provider_ids` for HHA scoping — this stays.
3. Build `org_display_name` for the sidebar header — this stays (but simplified).

**Remove:** `selector_options` list building, `current_hha_label`, the `hha_selector` template context variable.

### 3.3 Provider Filter Options at Initial Load

The controller loop at lines 448–458 already calls `get_options()` for every active filter. Once the Provider filter record exists with `scope_to_user_hha=True`, it will automatically call `get_options()` with `provider_ids=accessible_provider_ids`, which will use `_get_options_with_template()` to return properly labeled options. No special code needed.

### 3.4 `include_all_option` Handling

When the filter has `include_all_option=True`, the controller (or `get_options()`) should prepend an "All N items" option. This can be done in `get_options()` itself:

```python
# At the end of get_options(), before return:
if self.include_all_option and options:
    all_label = f'All {len(options)} {self.label or "items"}'
    options.insert(0, {'value': '', 'label': all_label})
```

Or it can be done in the `_build_page_config_json()` serialization. The cleanest place is in `get_options()` so both initial load and cascade endpoint return consistent options.

**Important:** The "All" option value should be `''` (empty string), not `'all'`. This keeps it consistent with how other filters treat "no selection" and avoids needing special handling in the cascade endpoint. When `parent_value=''` or `None`, the cascade skips the parent domain — which means "show all states for all providers" — exactly right.

### 3.5 Template Context Cleanup

Remove from `values.update({...})`:
- `selector_options`
- `current_hha_label`
- `current_hha_id` (keep only if still needed for sidebar/URL building)

The `hha_selector` key disappears from `page_config_json`, and React reads Provider from the unified `filters` array.

---

## Phase 4: React Changes

### 4.1 `FilterBar.jsx` — Unify Provider into the Filter Loop

**Remove:**
- The dedicated `handleHhaChange` function (lines 43–46)
- The separate `hha_selector` rendering block (lines 53–68)
- The `hha_selector` destructuring from config (line 19)

**The Provider filter is now just another entry in the `filters` array.** It renders via the same `filters.map()` loop (lines 71–95) and uses the same `handleFilterChange` with cascade support.

**New FilterBar.jsx:**

```jsx
export default function FilterBar() {
  const { config, pendingValues, setPendingFilter, applyFilters, accessToken, apiBase } = useFilters()
  const { filters = [] } = config

  const [dynamicOptions, setDynamicOptions] = useState({})

  // ── Handle cascade when a filter value changes ─────────────────────
  const handleFilterChange = useCallback(async (filter, newValue) => {
    setPendingFilter(filter.field_name || filter.param_name, newValue)

    // Find any child filters that depend on this filter
    const myFieldName = filter.field_name || filter.param_name
    const childFilters = filters.filter(f => f.depends_on_field_name === myFieldName)

    for (const child of childFilters) {
      try {
        const url = cascadeUrl(apiBase, child.id, newValue)
        const data = await apiFetch(url, accessToken)
        setDynamicOptions(prev => ({ ...prev, [child.id]: data.options || [] }))
        // Reset child value when parent changes
        setPendingFilter(child.field_name || child.param_name, '')

        // Recursively reset grandchildren (County when Provider changes State)
        const grandchildren = filters.filter(f =>
          f.depends_on_field_name === (child.field_name || child.param_name)
        )
        for (const gc of grandchildren) {
          setPendingFilter(gc.field_name || gc.param_name, '')
          setDynamicOptions(prev => ({ ...prev, [gc.id]: [] }))
        }
      } catch (err) {
        console.warn('Cascade fetch failed for filter', child.id, err)
      }
    }
  }, [filters, setPendingFilter, apiBase, accessToken])

  if (!filters.length) return null

  return (
    <div className="pv-ctx-filter-bar">
      {filters.map(filter => {
        const options = dynamicOptions[filter.id] ?? filter.options ?? []
        const paramKey = filter.field_name || filter.param_name
        const currentValue = pendingValues[paramKey] || ''

        return (
          <div key={filter.id} className="pv-ctx-filter-group">
            <label className="pv-ctx-filter-label">
              {filter.name}
            </label>
            <select
              className="pv-ctx-select"
              value={currentValue}
              onChange={e => handleFilterChange(filter, e.target.value)}
            >
              {/* "All" option — either from server (include_all_option)
                  or hardcoded for backward compat */}
              {!filter.include_all_option && (
                <option value="">All</option>
              )}
              {options.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        )
      })}

      <div className="pv-ctx-filter-group pv-ctx-apply-group">
        <button type="button" className="btn btn-primary pv-ctx-apply-btn"
                onClick={applyFilters}>
          Apply
        </button>
      </div>
    </div>
  )
}
```

**Key changes:**
1. No separate HHA selector — Provider is in the `filters` array
2. Grandchild reset — when Provider changes, State resets AND County/City reset too
3. `include_all_option` — when the server sends the "All" option as part of `options`, React doesn't add its own

### 4.2 `FilterContext.jsx` — Remove `hha_selector` References

**Current** (line 25–27):
```jsx
if (pageConfig.hha_selector?.current_hha_id) {
  defaults['hha_id'] = pageConfig.hha_selector.current_hha_id
}
```

**After:** Remove this block. The Provider filter's default value comes from the `filters` array like any other filter (via `f.default_value`). The controller sets the default from the URL param or the first provider.

### 4.3 `_build_page_config_json()` — Include `include_all_option` in Filter JSON

The filter serialization in `_build_page_config_json()` (lines 72–86) needs to include the new field:

```python
{
    'id':                    pf.id,
    'field_name':            pf.field_name or pf.param_name or '',
    'param_name':            pf.param_name or pf.field_name or '',
    'name':                  pf.display_label or pf.field_name or '',
    'default_value':         pf.default_value or '',
    'depends_on_filter_id':  pf.depends_on_filter_id.id if pf.depends_on_filter_id else None,
    'depends_on_field_name': pf.depends_on_filter_id.field_name if pf.depends_on_filter_id else None,
    'scope_to_user_hha':     pf.scope_to_user_hha,
    'include_all_option':    pf.include_all_option,  # ← NEW
    'options':               filter_options.get(pf.id, []),
    'sequence':              pf.sequence,
}
```

### 4.4 `endpoints.js` — No Changes Needed

The `cascadeUrl()` function already passes `filter_id` and `parent_value` — works for Provider → State cascade as-is.

---

## Phase 5: Cascade Endpoint Changes (`widget_api.py`)

### 5.1 No Structural Changes Needed

The `/api/v1/filters/cascade` endpoint already:
1. Validates the JWT
2. Loads the filter record
3. Checks app-level access
4. Resolves `provider_ids` for HHA-scoped filters
5. Calls `f.get_options(parent_value=..., provider_ids=...)`

When State filter's `depends_on_filter_id` points to the Provider filter, and the cascade request comes in with `parent_value=12345` (a provider ID), `get_options()` builds `domain = [('id', '=', 12345), ('id', 'in', [user's 63 IDs])]` and groups by `hha_state` — returning only states for that one provider. This already works with the Phase 1 model changes.

### 5.2 The `depends_on_field_name` Resolution

The React cascade logic uses `f.depends_on_field_name` to find children. For the State filter, this stored field will be `'id'` (the Provider filter's `field_name`). But the Provider filter's param_name is `'hha_id'`.

**Important alignment:** The `_build_page_config_json()` function sends `depends_on_field_name` from the parent's `field_name`. React's `handleFilterChange` matches children by comparing `f.depends_on_field_name === filter.field_name`. This works as long as:
- Provider filter: `field_name = 'id'` (from ir.model.fields)
- State filter: `depends_on_field_name = 'id'` (stored from parent's field_name)
- When Provider changes, React looks for `f.depends_on_field_name === 'id'` → finds State ✓

BUT the `setPendingFilter` and `pendingValues` use `param_name` (which is `'hha_id'` for Provider). The matching in `handleFilterChange` needs to check the right key. This is why we use `filter.field_name || filter.param_name` in the new code — the cascade match uses `field_name` but the value storage uses `param_name`.

**Potential issue:** The `depends_on_field_name` for State will be `'id'` (from the Provider filter's `field_id.name`). But in `_build_page_config_json()`, the parent field_name is sent as-is. We need to make sure the React matching logic aligns.

**Resolution:** In `_build_page_config_json()`, change `depends_on_field_name` to send `param_name` instead of `field_name` when available, since that's what React uses for state keys:

```python
'depends_on_field_name': (
    pf.depends_on_filter_id.param_name
    or pf.depends_on_filter_id.field_name
) if pf.depends_on_filter_id else None,
```

And in the handleFilterChange matching:
```jsx
const myParamName = filter.param_name || filter.field_name
const childFilters = filters.filter(f => f.depends_on_field_name === myParamName)
```

This way:
- Provider filter has `param_name = 'hha_id'`
- State filter has `depends_on_field_name = 'hha_id'` (from parent's param_name)
- React matches on `'hha_id'` ✓
- State filter has `param_name = 'hha_state'`
- County filter has `depends_on_field_name = 'hha_state'` ✓

### 5.3 JSONRPC Endpoint (`posterra_filter_options`)

The old JSONRPC endpoint at `/posterra/filter_options` (portal.py lines 155–192) is a legacy endpoint from before the REST API. It works the same way as `/api/v1/filters/cascade`. **No changes needed** — React uses the REST endpoint.

---

## Phase 6: Provider Context for Widgets and Sections

### 6.1 `selected_provider` Resolution Stays

The controller still needs to know which provider is selected (for `auto_fill_from_hha`, geo data, `sql_params`). Currently this comes from `hha_id` URL param. After the fix, `hha_id` still comes as a URL param (from the Provider filter's `param_name`). The resolution logic at lines 256–294 stays:

```python
hha_id_str = (hha_id or kw.get('hha_id') or '').strip()
# ... resolve selected_provider from hha_id_str
```

**One change:** When hha_id is empty string (the "All" option), `selected_provider` is `None` — which is already handled correctly. The controller falls back to using all providers for geo data and leaves `hha_name` empty in sql_params.

### 6.2 `org_display_name` for Sidebar

The sidebar header shows the organization name (e.g. "ELARA CARING"). This comes from `org_display_name = providers[0].hha_dba`. This is unrelated to filters and stays as-is.

---

## Phase 7: Recursive Cascade Reset

### 7.1 The Problem

When Provider changes, State should reset and fetch new options. But County and City should ALSO reset (their options become stale). Currently the cascade only goes one level deep — `handleFilterChange` finds direct children only.

### 7.2 The Fix

In the new `handleFilterChange`, after resetting a child and fetching its new options, also reset all grandchildren:

```jsx
for (const child of childFilters) {
  // ... fetch child options, reset child value ...

  // Recursively reset grandchildren
  const resetDescendants = (parentFieldName) => {
    const descendants = filters.filter(f =>
      f.depends_on_field_name === parentFieldName
    )
    for (const desc of descendants) {
      setPendingFilter(desc.param_name || desc.field_name, '')
      setDynamicOptions(prev => ({ ...prev, [desc.id]: [] }))
      resetDescendants(desc.param_name || desc.field_name)
    }
  }
  resetDescendants(child.param_name || child.field_name)
}
```

This ensures:
- Provider changes → State, County, City all reset
- State changes → County, City reset
- County changes → City resets

---

## File Change Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `models/dashboard_page_filter.py` | MODIFY | Add `display_template`, `include_all_option` fields; add `_get_options_with_template()` method; handle `id` field in parent domain builder |
| `views/page_views.xml` | MODIFY | Add `display_template` and `include_all_option` to inline filter list |
| `data/filters_data.xml` | MODIFY | Add 7 Provider filter records; update 7 State filters to depend on Provider |
| `controllers/portal.py` | MODIFY | Remove hardcoded `selector_options`/`hha_selector` block; remove `hha_selector` from page_config_json; add `include_all_option` to filter serialization; fix `depends_on_field_name` to use `param_name` |
| `static/src/react/src/components/FilterBar.jsx` | REWRITE | Remove separate HHA selector; unify into filter loop; add recursive descendant reset |
| `static/src/react/src/state/FilterContext.jsx` | MODIFY | Remove `hha_selector` reference in `buildDefaults()` |
| `static/src/react/src/App.jsx` | NO CHANGE | - |
| `static/src/react/src/api/endpoints.js` | NO CHANGE | - |
| `controllers/widget_api.py` | NO CHANGE | Cascade endpoint already works |
| `controllers/main.py` | NO CHANGE | Login flow unaffected |
| `controllers/auth_api.py` | NO CHANGE | JWT auth unaffected |
| `models/saas_app.py` | NO CHANGE | - |
| `models/hha_scope_group.py` | NO CHANGE | - |
| `models/hha_provider.py` | NO CHANGE | - |

---

## Admin Experience After Implementation

### Configuring Provider Filter

1. Go to **Posterra → Configuration → Dashboard Pages**
2. Open any page (e.g. Overview)
3. Click **Context Filters** tab
4. The Provider filter is already seeded (from `filters_data.xml`):

| Seq | Table | Column | Label | URL Param | Display Template | Include "All" | HHA Scope | Depends On |
|-----|-------|--------|-------|-----------|------------------|---------------|-----------|------------|
| 5 | hha.provider | id | Provider | hha_id | {hha_ccn} - {hha_brand_name} | ✓ | ✓ | (none) |
| 10 | hha.provider | hha_state | State | hha_state | | | ✓ | **Provider** |
| 20 | hha.provider | hha_county | County | hha_county | | | ✓ | State |
| 30 | hha.provider | hha_city | Locations | hha_city | | | ✓ | County |

5. Admin can change any of these: rename "Provider" to "HHA", change sequence, disable, change display template to `{hha_name} ({hha_state})`, etc.
6. Admin can add Provider filters to new pages by creating a filter record with the same config.
7. Admin can remove the cascade by clearing the "Depends On" field on State.

### What The Portal User Sees

1. Filter bar shows: **Provider** | **State** | **County** | **Locations** | **Year** | **Payer** | [Apply]
2. Provider dropdown shows: `All 63 HHAs`, `197161 - Elara Caring`, `197162 - Elara Caring`, ...
3. User picks `197161 - Elara Caring` → State immediately repopulates to show only states where CCN 197161 operates → County and City reset
4. User picks State = "Ohio" → County repopulates for Ohio + CCN 197161 → City resets
5. User clicks Apply → all widgets refetch with `hha_id=197161&hha_state=Ohio&...`

---

## Testing Checklist

```
PROVIDER FILTER CASCADE FIX
  ☐ Admin: Open Overview page form → Context Filters tab → Provider filter visible
  ☐ Admin: Provider filter shows Table=hha.provider, Column=id, Display Template={hha_ccn} - {hha_brand_name}
  ☐ Admin: State filter shows Depends On = Provider
  ☐ Admin: Can change Provider label to "HHA" → portal shows "HHA"
  ☐ Admin: Can disable Provider filter → portal hides Provider dropdown
  ☐ Admin: Can change display template to "{hha_name}" → portal shows name-only labels

  ☐ Portal: Login as John Wick (Elara, 63 CCNs) → Provider shows "All 63 HHAs" + 63 individual options
  ☐ Portal: State dropdown shows ~15 states (Elara's states), NOT all US states
  ☐ Portal: Pick "197161 - Elara Caring" → State immediately narrows (no Apply needed)
  ☐ Portal: County and City reset to "All" when Provider changes
  ☐ Portal: Pick State = "Ohio" → County narrows to Ohio counties for CCN 197161
  ☐ Portal: Pick Provider = "All 63 HHAs" → State shows all Elara states again
  ☐ Portal: Click Apply → widgets refresh with correct params
  ☐ Portal: URL reflects hha_id param → shareable deep links work
  ☐ Portal: Browser back/forward restores filter state

  ☐ Login: Login flow unchanged — John redirected to /my/posterra as before
  ☐ Login: User without HHA access → redirected to /my as before
  ☐ Login: Branded login page at /my/posterra/login works as before

  ☐ Single-provider user: Login as user with 1 HHA → Provider dropdown still shows (with 1 option)
  ☐ Single-provider user: State auto-filled from that provider's state (auto_fill_from_hha)

  ☐ Admin-only: Dashboard admin sees all providers (superadmin bypass)
  ☐ Security: Cascade endpoint enforces JWT + app-level access
  ☐ Security: Provider IDs resolved server-side — client cannot spoof
```

---

## Migration Notes

- **No database migration needed.** The two new fields (`display_template`, `include_all_option`) are simple Char and Boolean — Odoo adds them automatically on module upgrade.
- **Seed data runs on upgrade** (`noupdate="0"` block). Provider filter records are created and State filters get their new `depends_on_filter_id` on `-u posterra_portal`.
- **React bundle must be rebuilt** after FilterBar.jsx and FilterContext.jsx changes (`cd static/src/react && npm run build`).
- **No breaking changes** for existing widgets or sections — they still receive the same `sql_params` dict.
