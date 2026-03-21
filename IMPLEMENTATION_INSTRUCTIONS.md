# Posterra Filter Architecture — Implementation Instructions

> **IMPORTANT**: Read this entire document before starting. Implement in the exact phase order below. Each phase must pass its tests before moving to the next. Reference `CLAUDE.md` for architecture context.

---

## What We Are Building

A three-layer filter architecture upgrade that fixes three critical problems:

1. **P1**: URL not constructed correctly — "All" selections omitted from URL, causing wrong server defaults
2. **P2**: "All" = empty string breaks SQL — `('__all__',)` sentinel matches nothing in database
3. **P3**: Multi-value selections create URLs exceeding browser limits (2,000-8,192 chars)

The solution uses these proven patterns (used by Looker, Superset, Innovaccer):

- **Layer 1**: Smart SQL Parameters with Dual Scope (Omit = All)
- **Layer 2**: Hybrid URL + Backend State ID
- **Layer 3**: Batch Cascade API with Source Tracking

---

## Architecture Rules

1. **"All" in a filter = that filter's WHERE condition is REMOVED from SQL entirely** (not set to empty or sentinel). The query becomes LESS restrictive, not more.
2. **Two scopes exist**: Provider scope (user's own CCNs, for their metrics) and Geo scope (all providers in user's states, for benchmarks).
3. **Security scope is always server-computed** from the user's provider assignments. Never overridable from client.
4. **Backward compatibility**: Existing widgets with hardcoded WHERE clauses must still work during migration via the COALESCE pattern.
5. **No hardcoding**: Everything config-driven per the existing CLAUDE.md principles.

---

## PHASE 1: Smart SQL Parameters with Dual Scope

**Goal**: Fix P2 (SQL correctness). Make "All" work correctly. Add dual-scope support.
**Estimated effort**: 3-4 days
**Files to modify**: `portal.py`, `widget_api.py`, `dashboard_widget.py`, `dashboard_page_filter.py`

### Step 1.1: Add `is_security_scope` field to `dashboard.page.filter`

**File**: `posterra_portal/models/dashboard_page_filter.py`

Add a new Boolean field to the `dashboard.page.filter` model:

```python
is_security_scope = fields.Boolean(
    string='Security Scope Filter',
    default=False,
    help='If True, this filter\'s user-scoped values are always included in '
         '_user_* sql_params for security scoping, regardless of user selection.'
)
```

**Purpose**: Admin marks filters whose values define the user's data security boundary (e.g., the Provider/CCN filter). The server always computes the user's accessible values for these filters and passes them as `_user_*` params.

### Step 1.2: Handle None constraints in `get_options()`

**File**: `posterra_portal/models/dashboard_page_filter.py`

In both `_build_orm_domain_from_constraints()` and `_build_schema_where()`, add early-continue for None constraint values:

```python
# In _build_orm_domain_from_constraints():
for src_filter, value in constraints.items():
    if value is None or value == '':  # "All" = skip this constraint
        continue
    # ... rest of existing logic unchanged

# In _build_schema_where():
for src_filter, value in constraints.items():
    if value is None or value == '':  # "All" = skip this constraint
        continue
    # ... rest of existing logic unchanged
```

**Why**: When a parent filter is on "All", its constraint should not restrict the child's options. Currently passing '' or `('__all__',)` causes incorrect WHERE clauses.

### Step 1.3: Add `scope_mode` field to `dashboard.widget`

**File**: `posterra_portal/models/dashboard_widget.py`

Add a Selection field to the `DashboardWidget` class:

```python
scope_mode = fields.Selection([
    ('provider', 'Provider Scope'),      # Default: auto-add hha_ccn = ANY(_user_ccns) to WHERE
    ('benchmark', 'Benchmark Scope'),    # No CCN restriction; use geo scope only
    ('comparison', 'Comparison Scope'),  # Both _user_ccns and geo params available
    ('custom', 'Custom SQL'),            # Widget SQL handles all scoping manually
], default='custom', string='Data Scope',
   help='Controls how the auto WHERE builder applies security scoping. '
        '"custom" means the widget SQL handles everything itself.')
```

**Note**: Default is `'custom'` so all existing widgets continue working unchanged. New widgets can opt into `'provider'`, `'benchmark'`, or `'comparison'` mode.

### Step 1.4: Modify `DashboardFilterBuilder.build()` to skip None params

**File**: `posterra_portal/models/dashboard_widget.py`

Find the `DashboardFilterBuilder` class and its `build()` method. Modify it to:

1. **Skip WHERE conditions when the parameter value is None** (meaning "All" selected)
2. **Append security scope based on `scope_mode`** when the widget uses `{where_clause}`

```python
def build(self):
    where_parts = []
    params = {}

    for fdef in self.filter_defs:
        param = fdef.get('param_name')
        if param in self.exclude_params:
            continue
        val = self.user_params.get(param)

        # NEW: Skip filter if value is None (user selected "All")
        if val is None:
            continue

        col = fdef.get('schema_column_name') or fdef.get('column_name') or param
        if isinstance(val, tuple):
            where_parts.append(f'"{col}" = ANY(%({param})s)')
        else:
            where_parts.append(f'"{col}" = %({param})s')
        params[param] = val

    # NEW: Append security scope based on widget's scope_mode
    scope_mode = getattr(self, 'scope_mode', 'custom')
    if scope_mode == 'provider' and self.user_params.get('_user_ccns'):
        ccn_col = self._get_ccn_column()  # Helper to find the CCN column name
        where_parts.append(f'"{ccn_col}" = ANY(%(_user_ccns)s)')
        params['_user_ccns'] = self.user_params['_user_ccns']
    elif scope_mode == 'comparison' and self.user_params.get('_user_ccns'):
        # Include _user_ccns in params but don't add to WHERE (widget SQL decides)
        params['_user_ccns'] = self.user_params['_user_ccns']
    # 'benchmark' and 'custom': no CCN restriction added

    where_sql = ' AND '.join(where_parts) if where_parts else '1=1'
    return where_sql, params
```

**Important**: The `scope_mode` needs to be passed to the builder. Check how `DashboardFilterBuilder` is instantiated in `get_portal_data()` and pass the widget's `scope_mode` to it.

### Step 1.5: Revise sql_params builder in `portal.py`

**File**: `posterra_portal/controllers/portal.py`

Find the section where `sql_params` is built (approximately lines 589-613 in the `app_dashboard` method). This is the critical change.

**Before** (current logic — DO NOT keep this):
```python
# Current broken logic:
if val and val not in ('', 'all'):
    parts = tuple(v.strip() for v in val.split(',') if v.strip())
    sql_params[key] = parts
else:
    sql_params[key] = ('__all__',)  # <-- THIS IS THE BUG
```

**After** (new logic):
```python
sql_params = {}
for key, val in filter_values_by_name.items():
    if key in multiselect_params:
        if val and val not in ('', 'all'):
            parts = tuple(v.strip() for v in val.split(',') if v.strip())
            sql_params[key] = parts
            sql_params[f'_{key}_is_all'] = False
            # Keep existing YoY helper logic
            if len(parts) == 1 and parts[0].isdigit():
                sql_params[f'_{key}_single'] = int(parts[0])
                sql_params[f'_{key}_prior'] = int(parts[0]) - 1
        else:
            sql_params[key] = None              # NEW: None instead of ('__all__',)
            sql_params[f'_{key}_is_all'] = True
    else:
        if val and val not in ('', 'all'):
            sql_params[key] = val
            sql_params[f'_{key}_is_all'] = False
        else:
            sql_params[key] = None              # NEW: None instead of ''
            sql_params[f'_{key}_is_all'] = True

# NEW: Always compute and add user security scope params
# These are derived from the user's provider assignments (from 'providers' variable
# which is already computed earlier in app_dashboard)
user_provider_ccns = tuple(providers.mapped('hha_ccn')) if providers else ()
user_provider_states = tuple(set(providers.mapped('hha_state'))) if providers else ()
user_provider_counties = tuple(set(providers.mapped('hha_county'))) if providers else ()
user_provider_cities = tuple(set(providers.mapped('hha_city'))) if providers else ()

sql_params['_user_ccns'] = user_provider_ccns or None
sql_params['_user_states'] = user_provider_states or None
sql_params['_user_counties'] = user_provider_counties or None
sql_params['_user_cities'] = user_provider_cities or None
```

### Step 1.6: Mirror sql_params changes in `widget_api.py`

**File**: `posterra_portal/controllers/widget_api.py`

Find the `_build_portal_ctx()` method which builds `sql_params` for API-driven widget refreshes. Apply the **exact same logic** from Step 1.5.

**Recommendation**: Extract the sql_params builder into a shared utility function to avoid duplication. Create a helper:

```python
# In a shared location (e.g., models/dashboard_page_filter.py or a new utils.py):
def build_sql_params(filter_values_by_name, multiselect_params, providers):
    """Build sql_params dict from filter values with None-based 'All' encoding."""
    sql_params = {}
    # ... (the logic from Step 1.5)
    return sql_params
```

Then call it from both `portal.py` and `widget_api.py`.

### Step 1.7: Migrate existing widget SQL for backward compatibility

**IMPORTANT**: Existing widget SQL in the database uses patterns like:
```sql
WHERE hha_state = ANY(%(hha_state)s)
```

With the new None-based encoding, `%(hha_state)s` will be `None` when "All" is selected. In PostgreSQL, `ANY(NULL)` returns no rows, which is WRONG.

**Two migration options — choose based on widget count**:

**Option A (Per-widget, recommended for < 50 widgets)**: Update each widget's SQL to use the COALESCE pattern:
```sql
-- Before:
WHERE hha_state = ANY(%(hha_state)s)

-- After:
WHERE (%(hha_state)s IS NULL OR hha_state = ANY(%(hha_state)s))
```

**Option B (Auto-conversion in _execute_sql)**: Add a compatibility shim in `dashboard_widget.py._execute_sql()` that auto-replaces None params with a "match all" equivalent:
```python
def _execute_sql(self, params):
    sql = self.query_sql
    # Compatibility: for params that are None, remove their WHERE clauses
    # This is a temporary shim — migrate widget SQL to {where_clause} over time
    for key, val in list(params.items()):
        if val is None and not key.startswith('_'):
            # Replace "col = ANY(%(key)s)" with "TRUE" in SQL
            # or: skip the param and let {where_clause} handle it
            pass  # Decide approach based on your SQL patterns
    # ... rest of existing logic
```

**Option A is cleaner and safer. Recommend Option A first, then migrate to `{where_clause}` auto-generation over time.**

### Phase 1 Testing Checklist

After completing Steps 1.1–1.7, test these scenarios:

1. ✅ Load `/my/posterra?hha_ccn=017014&year=2023&ffs_ma=FFS` — KPI widgets show data (not empty)
2. ✅ Load `/my/posterra?year=2023&ffs_ma=FFS` (no hha_ccn) — widgets show data for ALL user's providers
3. ✅ Load with `hha_state=Illinois,Indiana` — widgets filter to those states only
4. ✅ Check `sql_params` in debug: `hha_state` should be `('Illinois', 'Indiana')`, not `('__all__',)`
5. ✅ Check `sql_params` when State is "All": `hha_state` should be `None`, not `('__all__',)` or `''`
6. ✅ `_user_ccns` should always be populated with the user's provider CCNs
7. ✅ `_user_states` should always contain the states where user's providers operate
8. ✅ Existing widgets with hardcoded WHERE clauses still work (after COALESCE migration)

---

## PHASE 2: Hybrid URL + Backend State ID

**Goal**: Fix P1 (URL incompleteness) and P3 (URL too long).
**Estimated effort**: 3-4 days
**Files to create**: `dashboard_filter_state.py`, `filter_state_cron.xml`
**Files to modify**: `widget_api.py`, `portal.py`, `FilterContext.jsx`, `endpoints.js`, `__manifest__.py`, `models/__init__.py`, `ir.model.access.csv`

### Step 2.1: Create new model `dashboard.filter.state`

**Create file**: `posterra_portal/models/dashboard_filter_state.py`

```python
import json
from uuid import uuid4
from datetime import timedelta
from odoo import models, fields, api

class DashboardFilterState(models.Model):
    _name = 'dashboard.filter.state'
    _description = 'Ephemeral Filter State Snapshot'

    state_id = fields.Char(
        string='State ID', index=True, required=True,
        default=lambda self: str(uuid4()).replace('-', '')[:12]
    )
    app_id = fields.Many2one('saas.app', required=True, ondelete='cascade')
    page_id = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    user_id = fields.Many2one(
        'res.users', default=lambda self: self.env.uid, ondelete='set null'
    )
    filter_json = fields.Text(required=True)
    created_at = fields.Datetime(default=fields.Datetime.now)
    expires_at = fields.Datetime()

    _sql_constraints = [
        ('state_id_unique', 'unique(state_id)', 'State ID must be unique.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('expires_at'):
                now = fields.Datetime.now()
                vals['expires_at'] = now + timedelta(days=30)
        return super().create(vals_list)

    @api.model
    def save_state(self, app_id, page_id, filter_values):
        """Save filter state and return the state_id."""
        state = self.create({
            'app_id': int(app_id),
            'page_id': int(page_id),
            'filter_json': json.dumps(filter_values),
        })
        return state.state_id

    @api.model
    def load_state(self, state_id, app_id):
        """Load filter state by state_id. Returns dict or None."""
        state = self.search([
            ('state_id', '=', str(state_id)),
            ('app_id', '=', int(app_id)),
            ('expires_at', '>', fields.Datetime.now()),
        ], limit=1)
        if not state:
            return None
        return json.loads(state.filter_json)

    @api.model
    def cleanup_expired(self):
        """Remove expired filter states. Called by ir.cron."""
        expired = self.search([('expires_at', '<', fields.Datetime.now())])
        count = len(expired)
        expired.unlink()
        return count
```

### Step 2.2: Register the new model

**File**: `posterra_portal/models/__init__.py`
- Add: `from . import dashboard_filter_state`

**File**: `posterra_portal/__manifest__.py`
- Add `'data/filter_state_cron.xml'` to the `'data'` list

**File**: `posterra_portal/security/ir.model.access.csv`
- Add access rights for the new model:
```csv
access_dashboard_filter_state_user,dashboard.filter.state.user,model_dashboard_filter_state,base.group_user,1,1,0,0
access_dashboard_filter_state_admin,dashboard.filter.state.admin,model_dashboard_filter_state,base.group_system,1,1,1,1
```

### Step 2.3: Create the cleanup cron job

**Create file**: `posterra_portal/data/filter_state_cron.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="ir_cron_cleanup_filter_states" model="ir.cron">
        <field name="name">Dashboard: Cleanup Expired Filter States</field>
        <field name="model_id" ref="model_dashboard_filter_state"/>
        <field name="state">code</field>
        <field name="code">model.cleanup_expired()</field>
        <field name="interval_number">1</field>
        <field name="interval_type">days</field>
        <field name="numbercall">-1</field>
        <field name="active">True</field>
    </record>
</odoo>
```

### Step 2.4: Add API endpoints for state save/load

**File**: `posterra_portal/controllers/widget_api.py`

Add two new endpoints:

```python
@http.route('/api/v1/filters/state/save', type='json', auth='user', methods=['POST'])
def api_save_filter_state(self, app_id, page_id, filter_values, **kw):
    """Save filter state server-side, return short state_id."""
    state_id = request.env['dashboard.filter.state'].sudo().save_state(
        app_id=int(app_id),
        page_id=int(page_id),
        filter_values=filter_values,
    )
    return {'state_id': state_id}

@http.route('/api/v1/filters/state/load', type='json', auth='user', methods=['POST'])
def api_load_filter_state(self, state_id, app_id, **kw):
    """Load filter state by state_id."""
    values = request.env['dashboard.filter.state'].sudo().load_state(
        state_id=str(state_id),
        app_id=int(app_id),
    )
    if not values:
        return {'error': 'State not found or expired'}
    return {'filter_values': values}
```

### Step 2.5: Add state URL handling in `portal.py`

**File**: `posterra_portal/controllers/portal.py`

At the beginning of `app_dashboard()`, before filter resolution, check for state_id in URL params:

```python
# Near the top of app_dashboard(), after app/page resolution:
state_id = kw.pop('s', None)  # Remove from kw so it doesn't interfere with filters
if state_id:
    saved_state = request.env['dashboard.filter.state'].sudo().load_state(
        state_id=state_id, app_id=app.id
    )
    if saved_state:
        # Inject saved filter values into kw (URL params)
        kw.update(saved_state)
```

This way the rest of the flow works exactly as if the user had those params in the URL.

### Step 2.6: Update React FilterContext.jsx for state ID support

**File**: `posterra_portal/static/src/react/src/state/FilterContext.jsx`

**Change the URL sync effect** (the `useEffect` that pushes filter values to the URL):

```javascript
const URL_LENGTH_THRESHOLD = 2000;

// In the URL sync useEffect:
useEffect(() => {
    if (!isMounted.current) return;

    const params = new URLSearchParams();

    // Build URL with explicit (non-All) selections only
    Object.entries(filterValues).forEach(([k, v]) => {
        if (!hiddenKeys.has(k) && v && v !== '') {
            params.set(k, v);
        }
    });
    if (currentTabKey) params.set('tab', currentTabKey);

    const candidateQs = params.toString();
    const candidateUrl = candidateQs ? '?' + candidateQs : window.location.pathname;

    if (candidateUrl.length > URL_LENGTH_THRESHOLD) {
        // URL too long → save state server-side
        saveFilterState(pageConfig.appId, pageConfig.pageId, filterValues)
            .then(resp => {
                if (resp && resp.state_id) {
                    const stateParams = new URLSearchParams();
                    stateParams.set('s', resp.state_id);
                    if (currentTabKey) stateParams.set('tab', currentTabKey);
                    window.history.pushState(
                        { filterValues, currentTabKey },
                        '',
                        '?' + stateParams.toString()
                    );
                }
            })
            .catch(err => {
                // Fallback: use long URL anyway
                window.history.pushState({ filterValues, currentTabKey }, '', candidateUrl);
            });
    } else {
        window.history.pushState({ filterValues, currentTabKey }, '', candidateUrl);
    }
}, [filterValues, currentTabKey, hiddenKeys]);
```

### Step 2.7: Add API functions in `endpoints.js`

**File**: `posterra_portal/static/src/react/src/api/endpoints.js`

Add these two functions:

```javascript
export async function saveFilterState(appId, pageId, filterValues, accessToken) {
    const resp = await fetch('/api/v1/filters/state/save', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'call',
            params: { app_id: appId, page_id: pageId, filter_values: filterValues },
        }),
    });
    const data = await resp.json();
    return data.result;
}

export async function loadFilterState(stateId, appId, accessToken) {
    const resp = await fetch('/api/v1/filters/state/load', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'call',
            params: { state_id: stateId, app_id: appId },
        }),
    });
    const data = await resp.json();
    return data.result;
}
```

### Phase 2 Testing Checklist

1. ✅ Select few filters → URL uses normal params (no `?s=`)
2. ✅ Select many values in multiple filters (force URL > 2000 chars) → URL auto-switches to `?s=abc123`
3. ✅ Reload page with `?s=abc123` → filters restore correctly from server state
4. ✅ Share `?s=abc123` URL with another authorized user → they see same filters
5. ✅ Use `?s=abc123` from a different app → returns error, does not load
6. ✅ After 30 days (or manual expiry in DB) → graceful fallback, loads defaults
7. ✅ Cron job runs → expired records cleaned up (verify in DB)

---

## PHASE 3: Batch Cascade API with Source Tracking

**Goal**: Performance optimization — reduce cascade API calls from O(n) to O(1).
**Estimated effort**: 2-3 days
**Files to modify**: `widget_api.py`, `FilterBar.jsx`, `endpoints.js`

### Step 3.1: Create batch cascade endpoint

**File**: `posterra_portal/controllers/widget_api.py`

Add a new endpoint that resolves all dependent filters in one server round-trip:

```python
@http.route('/api/v1/filters/cascade/batch', type='json', auth='user', methods=['POST'])
def api_cascade_batch(self, changed_filter_id, changed_value, current_state, page_id, **kw):
    """
    Resolve all dependent filter options in one server round-trip.
    Uses BFS traversal of the filter dependency graph.

    Args:
        changed_filter_id: ID of the filter that changed
        changed_value: New value of the changed filter
        current_state: dict of {param_name: value} for all filters
        page_id: ID of the current dashboard page

    Returns:
        filter_updates: dict of {filter_id: {options, auto_selected, param_name}}
    """
    page = request.env['dashboard.page'].browse(int(page_id))
    page_filters = page.filter_ids

    # Resolve user's providers for scoping
    user = request.env.user
    providers = self._get_user_providers(user, page.app_id)
    provider_ids = providers.ids if providers else []

    # Load all dependencies for this page
    deps = request.env['dashboard.filter.dependency'].search([
        ('source_filter_id.page_id', '=', page.id)
    ])

    # Build adjacency list: source_id -> [edge_info]
    graph = {}
    reverse_graph = {}  # target_id -> [source_info]
    for dep in deps:
        src_id = dep.source_filter_id.id
        tgt_id = dep.target_filter_id.id
        edge = {
            'target_id': tgt_id,
            'source_id': src_id,
            'resets_target': dep.resets_target,
            'propagation': dep.propagation,
        }
        graph.setdefault(src_id, []).append(edge)
        reverse_graph.setdefault(tgt_id, []).append({
            'source_id': src_id,
            'source_filter': dep.source_filter_id,
        })

    # Mutable state copy
    state = dict(current_state or {})
    changed_id = int(changed_filter_id)
    changed_filter = page_filters.filtered(lambda f: f.id == changed_id)
    if changed_filter:
        state[changed_filter.param_name or changed_filter.field_name] = changed_value

    # BFS from changed filter
    visited = {changed_id}
    queue = [changed_id]
    results = {}

    while queue:
        src_id = queue.pop(0)
        for edge in graph.get(src_id, []):
            tgt_id = edge['target_id']
            if tgt_id in visited:
                continue
            visited.add(tgt_id)

            tgt_filter = page_filters.filtered(lambda f: f.id == tgt_id)
            if not tgt_filter:
                continue
            tgt_filter = tgt_filter[0]

            # Build constraints from ALL sources of this target
            constraints = {}
            for src_info in reverse_graph.get(tgt_id, []):
                src_f = src_info['source_filter']
                src_param = src_f.param_name or src_f.field_name
                src_val = state.get(src_param, '')
                if src_val:
                    constraints[src_f] = src_val

            # Fetch options with constraints
            try:
                options = tgt_filter.get_options(
                    constraint_values=constraints if constraints else None,
                    provider_ids=provider_ids,
                    all_filter_values=state,
                )
            except Exception:
                options = []

            # Auto-select logic
            auto_val = None
            if (edge['resets_target']
                    and len(options) == 1
                    and not tgt_filter.include_all_option):
                auto_val = options[0].get('value', '')
                tgt_param = tgt_filter.param_name or tgt_filter.field_name
                state[tgt_param] = auto_val
                queue.append(tgt_id)  # Propagate auto-selection
            elif edge['resets_target']:
                tgt_param = tgt_filter.param_name or tgt_filter.field_name
                state[tgt_param] = ''  # Reset

            results[str(tgt_id)] = {
                'options': options,
                'auto_selected': auto_val,
                'param_name': tgt_filter.param_name or tgt_filter.field_name,
            }

    return {'filter_updates': results}
```

**Note**: You'll need to adapt `_get_user_providers()` — this should use the same provider resolution logic that exists in `portal.py` and `widget_api.py`. Check existing helper methods.

### Step 3.2: Add batch cascade URL in `endpoints.js`

**File**: `posterra_portal/static/src/react/src/api/endpoints.js`

```javascript
export function cascadeBatchUrl(apiBase) {
    return `${apiBase}/api/v1/filters/cascade/batch`;
}

export async function fetchCascadeBatch(apiBase, changedFilterId, changedValue, currentState, pageId, accessToken) {
    const resp = await fetch(cascadeBatchUrl(apiBase), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(accessToken ? { 'Authorization': `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
            jsonrpc: '2.0',
            method: 'call',
            params: {
                changed_filter_id: changedFilterId,
                changed_value: changedValue,
                current_state: currentState,
                page_id: pageId,
            },
        }),
    });
    const data = await resp.json();
    return data.result;
}
```

### Step 3.3: Replace sequential cascade with batch call in `FilterBar.jsx`

**File**: `posterra_portal/static/src/react/src/components/FilterBar.jsx`

Replace the `handleGraphCascade()` function with a simpler batch approach:

```javascript
async function handleFilterChange(filterMeta, newValue) {
    // 1. Update this filter immediately in pending state
    setPendingFilter(filterMeta.param_name, newValue);

    // 2. Build current state snapshot
    const currentState = { ...pendingValues };
    currentState[filterMeta.param_name] = newValue;

    // 3. Check if this filter has any dependents
    const hasDependents = filterDeps.some(
        dep => dep.source_filter_id === filterMeta.id
    );
    if (!hasDependents) return;

    // 4. Single batch cascade call
    try {
        const response = await fetchCascadeBatch(
            apiBase,
            filterMeta.id,
            newValue,
            currentState,
            pageConfig.pageId,
            accessToken
        );

        // 5. Apply all updates atomically
        if (response && response.filter_updates) {
            for (const [filterId, update] of Object.entries(response.filter_updates)) {
                // Update options for this filter in state
                setFilterOptions(prev => ({
                    ...prev,
                    [filterId]: update.options,
                }));

                // Set auto-selected value or reset
                if (update.auto_selected !== null && update.auto_selected !== undefined) {
                    setPendingFilter(update.param_name, update.auto_selected);
                } else if (update.auto_selected === null) {
                    // Filter was reset — check if it currently has a value and clear it
                    // (only if resets_target was true, which the server already handled)
                }
            }
        }
    } catch (err) {
        console.error('Batch cascade failed, falling back to individual calls', err);
        // Fallback: use existing handleGraphCascade if available
        // Or just skip cascade and let user click Apply to refresh
    }
}
```

**Important**: Keep the existing `handleGraphCascade()` as a fallback. The batch endpoint is an optimization. If it fails, the old sequential approach should still work.

### Phase 3 Testing Checklist

1. ✅ Change State dropdown → all dependent filters (Provider, County, City) update in ONE network call
2. ✅ Check Network tab: only 1 request to `/api/v1/filters/cascade/batch` (not 3-6 individual calls)
3. ✅ Bidirectional cascade: State → Provider → County works correctly
4. ✅ No infinite loops: changing State cascades to Provider/County/City, stops there (visited set prevents re-processing)
5. ✅ Auto-select: if changing State leaves exactly 1 provider, it's auto-selected
6. ✅ Reset: if changing State leaves multiple providers, Provider resets to empty (user must choose)
7. ✅ Cascade performance: < 500ms for full cascade chain (measure in Network tab)
8. ✅ Fallback: if batch endpoint errors, UI doesn't break

---

## PHASE 4: Final Testing & Migration

### Widget SQL Migration

For each existing widget record in the database (`dashboard.widget` table), update the `query_sql` field:

**Pattern: Replace direct ANY() with null-safe version**:
```sql
-- Find all occurrences of:
column_name = ANY(%(param)s)

-- Replace with:
(%(param)s IS NULL OR column_name = ANY(%(param)s))
```

**OR**: Migrate widgets to use `{where_clause}` auto-generation (preferred for new widgets).

### Full Regression Test

Run the complete 11-point testing checklist from `CLAUDE.md`:

1. Load with single provider: `/my/posterra?hha_ccn=017014&year=2024,2023&ffs_ma=MA&tab=command_center`
2. Verify State/County/City auto-populate from provider's geo data (not "All")
3. Load with multi-provider CSV: `hha_ccn=017014,047114` → geo auto-selects if all share same state
4. Load without provider param (multi-provider user) → geo filters show "All", data shows for all providers
5. Single-provider user → geo filters auto-populate regardless of URL
6. Change Provider dropdown → child filters auto-select if 1 option, reset if 2+
7. Change State dropdown → Provider/County/City cascade correctly (single batch API call)
8. Click Apply → URL updates with all filter values (or state ID if > 2000 chars)
9. Widget data reflects correct sql_params (check browser network tab)
10. Test on different pages (Overview, Hospitals, etc.) — each has its own filter set
11. Verify `is_provider_selector` is ON for Provider filter in admin

### Build React

After all React changes:
```bash
cd posterra_portal/static/src/react && npm run build
```

### Restart Odoo

After all Python changes:
```bash
# Stop Odoo
# Upgrade module to apply new model + cron
python odoo-bin -c odoo.conf -u posterra_portal
# Start Odoo normally
python odoo-bin -c odoo.conf
```

---

## Files Summary

| File | Action | Phase |
|------|--------|-------|
| `models/dashboard_page_filter.py` | Modify (add field + None handling) | 1 |
| `models/dashboard_widget.py` | Modify (scope_mode + builder fix) | 1 |
| `controllers/portal.py` | Modify (sql_params + state ID check) | 1 + 2 |
| `controllers/widget_api.py` | Modify (sql_params + new endpoints) | 1 + 2 + 3 |
| `models/dashboard_filter_state.py` | **NEW** | 2 |
| `models/__init__.py` | Modify (import new model) | 2 |
| `__manifest__.py` | Modify (add cron data file) | 2 |
| `data/filter_state_cron.xml` | **NEW** | 2 |
| `security/ir.model.access.csv` | Modify (add access rights) | 2 |
| `static/.../state/FilterContext.jsx` | Modify (URL sync + state ID) | 2 |
| `static/.../api/endpoints.js` | Modify (add state + cascade APIs) | 2 + 3 |
| `static/.../components/FilterBar.jsx` | Modify (batch cascade) | 3 |
| Widget SQL records in DB | Migrate (COALESCE pattern) | 4 |
