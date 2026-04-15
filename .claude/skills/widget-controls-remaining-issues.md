# Widget-Scoped Controls — Remaining Issues

## Status: What WORKS

1. **Dashboard Builder** — Widget Controls step (Step 1) works: search toggle, scope mode, UI style, option list with label/value/icon
2. **Builder Data Source tabs** — FFS/MA/ALL tabs render, each with its own Custom SQL/AI editor
3. **Save & Place** — scope_mode, scope_ui, scope_query_mode saved to definition AND widget instance
4. **Scope Options** — child records (dashboard.widget.scope.option) created on widget instance with label, value, icon, query_sql
5. **Odoo Admin Controls tab** — shows scope_mode, scope_ui, scope_query_mode, scope options list
6. **Edit in Builder** — scope state restored: scopeMode, options, per-option SQL all visible

## Remaining Issues (3 bugs)

### Bug A: Widget renders but no data on portal

**Symptom:** Toggle buttons appear in widget card header but chart shows no data (or wrong data).

**Likely cause:** The portal's initial load uses the widget's main `query_sql` (which is the first option's FFS SQL). But the toggle buttons haven't been clicked, so the scope_option SQL doesn't execute. The issue may be:
- Missing schema_source_id on the widget (needed for {where_clause})
- The initial SQL works but filter params aren't available
- The API refresh on toggle click doesn't work because scope_option_id isn't found

**To investigate:**
1. Check browser Network tab — does the initial widget data API return data?
2. Click a toggle button — does it fire API call? What does the response look like?
3. Check Odoo server log for SQL execution errors

### Bug B: Odoo Admin doesn't show per-option SQL

**Symptom:** The Query tab in Odoo Admin shows only the FFS option's SQL (the first option). There's no way to see MA or ALL option SQL in the admin.

**This is by design** — the widget's `query_sql` field holds the first option's SQL (as a fallback/default). The per-option SQL is stored on `dashboard.widget.scope.option` child records. To see them, admin clicks into each scope option row in the Controls tab → opens the option form → SQL Query field is there.

**BUT** the option form in the Controls tab might not be showing the SQL clearly. The scope option form view in `widget_views.xml` has the SQL field but it may need better visibility.

**Fix needed:** Improve the scope option inline list to show a "has SQL" indicator, and ensure the option form view prominently displays the SQL editor.

### Bug C: Toggle Query Mode mismatch

**Symptom:** Builder doesn't show "Toggle Query Mode" field (it's implied by whether you write SQL per option). Odoo Admin shows it as "Same SQL, Different Parameter" vs "Different SQL Per Option".

**This is a UX inconsistency, not a data bug.** The builder always creates per-option configs (optionConfigs). Whether those configs have different SQL or the same SQL with different params is an admin choice.

**Opinion:** Keep both modes in Odoo Admin (they serve different use cases). The builder can optionally show this field too, or infer it based on whether option SQL fields are different.

## Key Files for Each Fix

### Bug A (data rendering):
- `posterra_portal/controllers/widget_api.py` — `api_widget_data()` scope override handler
- `posterra_portal/static/src/react/src/components/WidgetGrid.jsx` — toggle click handler, API call
- `posterra_portal/controllers/portal.py` — `_build_initial_widgets_json()` scope config

### Bug B (admin display):
- `posterra_portal/views/widget_views.xml` — scope option inline list columns + form view

### Bug C (mode mismatch):
- `dashboard_builder/static/src/designer/src/components/builder/WidgetControlsStep.jsx` — optionally add query mode selector

## Architecture Reference

### The TWO API controllers:
- **`designer_api.py`** — used by Dashboard Builder (`/dashboard/designer/api/...`)
- **`builder_api.py`** — used by portal widget API (`/api/v1/builder/...`) — NOT used by builder wizard
- **`widget_api.py`** — used by portal React for widget data refresh (`/api/v1/widget/<id>/data`)

### Data flow for toggle click on portal:
```
User clicks toggle → WidgetGrid.handleScopeChange()
  → builds URL: /api/v1/widget/<id>/data?...&_scope_option_id=<opt_id>
  → widget_api.py api_widget_data() 
    → checks widget.scope_query_mode == 'query' && _scope_option_id
    → loads scope_option record
    → calls opt.execute_option_sql(portal_ctx)
    → returns data to React
  → React renders chart with new data
```
