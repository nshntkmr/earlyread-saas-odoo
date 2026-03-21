# POSTERRA FRONTEND SKILL
## Maps to: SKILL.md — Phases 4, 7, 8

### LOAD THIS FILE AT THE START OF EVERY FRONTEND CODING SESSION

Also load the main SKILL.md at: `C:\Users\nisha\Odoo_Dev\posterra_portal\SKILL.md`

---

## ★ FRONTEND PHASE ORDER ★

```
PHASE 4  →  White-Label Login + Strip Odoo Chrome       ~4h   ← NEXT
PHASE 7  →  React Widget Grid + Filter Bar              ~8h
PHASE 8  →  Widget Click-Actions (drill + navigate)     ~6h
```

Phases 5 and 6 (saas.app model, JSON API) are backend prerequisites for Phase 7+.
Do NOT start Phase 7 until Phase 6 API endpoints are complete.

---

## 1. PROJECT CONTEXT

**Platform:** Odoo 19.0 Community Edition
**Module:** `posterra_portal` at `C:\Users\nisha\Odoo_Dev\posterra_portal\`
**Frontend repo:** `C:\Users\nisha\Odoo_Dev\posterra_frontend\`  (Phase 7+ React code lives here)

**Architecture (current → target):**

```
CURRENT (Phase 4):
  Odoo QWeb Shell  →  posterra_portal.base_layout (no Odoo chrome)
    ├── Sidebar (QWeb, DB-driven)
    ├── Context Filters Bar (QWeb, cascading dropdowns)
    ├── Tab Bar (QWeb)
    └── Widget Grid (QWeb + inline ECharts scripts)

TARGET (Phase 7+):
  Odoo QWeb Shell  →  posterra_portal.base_layout
    ├── Sidebar (QWeb — stays QWeb forever)
    └── <div id="app-root" data-page-config='{...}'>
              REACT OWNS THIS AREA
              ● Filter Bar
              ● Tab Bar
              ● Widget Grid (ECharts inside React components)
              ● Drill-down state
```

---

## 2. FRONTEND FILE MAP

### Odoo module files (QWeb + CSS)

| File | Purpose |
|------|---------|
| `views/dashboard_templates.xml` | Portal HTML shell — sidebar, base_layout, data-* attributes for React mount |
| `views/login_templates.xml` | Branded login page at `/my/<app_key>/login` + fallback overrides for `/web/login` |
| `views/error_templates.xml` | Branded 404/403/500 error pages |
| `static/src/css/posterra.css` | All portal CSS (dashboard, login, error pages) |
| `static/src/img/favicon.png` | 32×32 Posterra favicon |
| `controllers/portal.py` | Dashboard routes + custom login route |

### React app files (Phase 7+, lives in posterra_frontend/)

| File | Purpose |
|------|---------|
| `src/main.jsx` | React entry point — mounts onto `#app-root` |
| `src/components/FilterBar.jsx` | State → County → Locations cascade + Apply button |
| `src/components/TabBar.jsx` | Tab switching (no page reload) |
| `src/components/WidgetGrid.jsx` | Bootstrap grid of widget cards |
| `src/components/widgets/` | One component per chart_type (BarChart, DonutChart, KPICard, etc.) |
| `src/hooks/useWidgetData.js` | Fetches `/api/v1/widget/{id}/data` with filter params |
| `vite.config.js` | Vite build → outputs to `posterra_portal/static/src/js/bundle.js` |

---

## 3. CSS CONVENTIONS

**Namespace:** all Posterra CSS classes start with `pv-`

```
pv-dashboard          main dashboard wrapper (flex row)
pv-sidebar            left navigation sidebar
pv-sidebar-header     brand name + org name in sidebar header
pv-nav-section        nav group label (MY HHA, PORTFOLIO, etc.)
pv-content            main content flex column
pv-filter-bar         context filters bar (HHA selector + cascades)
pv-tab-bar            tab navigation row
pv-widget-*           widget-specific classes

pv-login-*            login page classes (Phase 4)
pv-error-*            error page classes (Phase 4)
```

**CSS Variables (defined in posterra.css `:root`):**
```css
--pv-primary         /* main brand blue */
--pv-bg-dark         /* dark sidebar/background color */
--pv-text-muted      /* secondary text */
```

**Framework:** Bootstrap 5 (loaded via `web.assets_frontend` — do NOT import Bootstrap separately)

**No SCSS** — plain CSS only. Odoo 19.0 asset pipeline does not compile SCSS without extra config.

**Asset registration:** All CSS goes in `web.assets_frontend` via `__manifest__.py`:
```python
'assets': {
    'web.assets_frontend': [
        'posterra_portal/static/src/css/posterra.css',
    ],
},
```

---

## 4. ODOO QWEB RULES (avoid breaking things)

These are non-negotiable constraints in Odoo 19.0:

```
❌ NEVER use <script type="application/json"> in QWeb — silently fails
✅ USE data-* attributes on div elements instead

❌ NEVER use type='json' in @route() decorators
✅ USE type='jsonrpc' or type='http'

❌ NEVER inherit website.layout or portal.frontend_layout in portal templates
✅ USE posterra_portal.base_layout (Phase 4) which calls web.frontend_layout

❌ NEVER omit website=False on login/dashboard routes (website=True injects Odoo navbar)
✅ DEFAULT is website=False — just omit the flag

❌ NEVER call Model.read_group() — deprecated in Odoo 19
✅ USE Model._read_group() — returns tuples, Many2one returns recordsets

✅ Portal reads always use .sudo() — access controlled by ACL/record rules
✅ base_layout passes no_header=True, no_footer=True, no_copyright=True to web.frontend_layout
```

---

## 5. PHASE 4 — White-Label Login + Strip Odoo Chrome (CURRENT)

**Maps to:** SKILL.md Phase 4 section + `C:\Users\nisha\.claude\plans\mellow-marinating-journal.md`

**Start prompt:**
> "Read SKILL.md and frontend_skill.md, then build Phase 4 — White-Label Login + Strip Odoo Chrome. Create posterra_portal.base_layout (minimal layout, no Odoo chrome). Add custom login at /my/<app_key>/login. Create branded error pages. Strip website=True from dashboard routes."

### Template hierarchy after Phase 4

```
web.layout
  └── web.frontend_layout  (assets: Bootstrap, FA, Odoo JS runtime)
        ├── posterra_portal.base_layout  ← NEW
        │     └── posterra_portal.dashboard (sidebar, filters, tabs, widgets)
        ├── posterra_portal.login  ← NEW standalone (no portal navbar)
        └── http_routing.404 → overridden by posterra_portal.posterra_404
```

### Login route

```
GET/POST /my/<app_key>/login
  auth='none', type='http'
  ensure_db() required
  On success: self._login_redirect(uid) → /my/posterra or /my/mssp
  On failure: re-render with error='Wrong email or password'
```

### Milestone (Phase 4 — tick before moving to Phase 5)

```
☐ Visit /my/posterra/login — branded login page, NO Odoo navbar/footer
☐ Visit /my/posterra/overview — NO "Your Logo", "Home", "Contact us" header
☐ Visit /my/posterra/overview — NO "Useful Links", "About us" footer
☐ Trigger 404 — branded error page, not Odoo default
☐ View page source — no "odoo" string in visible HTML/meta tags
```

---

## 6. PHASE 7 — React Widget Grid + Filter Bar (FUTURE — after Phase 6)

**Maps to:** SKILL.md Phase 7

**Start prompt (copy from SKILL.md Phase 7 section)**

**Prerequisites:**
- Phase 4 complete (base_layout installed — React mounts inside `#app-root` which is inside base_layout)
- Phase 5 complete (saas.app model — app branding available)
- Phase 6 complete (JSON API endpoints exist — React fetches widget data from API)

### Data flow (Phase 7)

```
QWeb renders:   <div id="app-root"
                     data-page-config='{"tabs":[...], "filters":[...], "widgets":[...]}'
                     data-initial-widgets='{"widget_1": {...}, "widget_2": {...}}'>

React reads:    const config = JSON.parse(el.dataset.pageConfig)
                const initial = JSON.parse(el.dataset.initialWidgets)

React mounts:   <FilterBar config={config.filters} initial={...} />
                <TabBar tabs={config.tabs} />
                <WidgetGrid widgets={config.widgets} initialData={initial} />
```

The `data-page-config` attribute is set by the QWeb template (server-rendered).
`data-initial-widgets` contains pre-fetched widget data (zero API calls on first load).
Filter changes trigger parallel `useWidgetData` hook calls to Phase 6 API.

### Vite build output

```
posterra_frontend/vite.config.js:
  build.outDir = '../posterra_portal/static/src/js/'
  build.rollupOptions.output.entryFileNames = 'posterra_app.js'

Registered in __manifest__.py assets:
  'posterra_portal/static/src/js/posterra_app.js'
```

### Widget type → React component map

| chart_type | React component |
|------------|----------------|
| bar | BarChart |
| line | LineChart |
| pie | PieChart |
| donut | DonutChart |
| gauge | GaugeChart |
| gauge_kpi | GaugeKpiCard |
| radar | RadarChart |
| kpi | KpiCard |
| status_kpi | StatusKpiCard |
| table | DataTable |
| scatter | ScatterChart |
| heatmap | HeatmapChart |
| battle_card | BattleCard |
| insight_panel | InsightPanel |

### Milestone (Phase 7)

```
☐ React mounts — filter bar renders from config JSON
☐ State filter change → County dropdown updates (no page reload)
☐ Apply → all widgets refetch and re-render (no page reload)
☐ Tab switch → widgets swap (no page reload)
☐ All 14 widget types render in React
☐ Initial page load: NO loading flash (data embedded in QWeb shell)
☐ Browser back/forward buttons work (URL reflects filter state)
```

---

## 7. PHASE 8 — Widget Click-Actions (FUTURE — after Phase 7)

**Maps to:** SKILL.md Phase 8

**Start prompt (copy from SKILL.md Phase 8 section)**

### Action types

| action_type | What it does |
|-------------|-------------|
| drill_filter | Click chart slice/table row → filter other widgets on same page |
| navigate_page | Click → go to another page with filter context |
| navigate_tab | Click → switch to another tab |

### Drill-filter state (React)

- "Filtered by: X ✕" chip appears in filter bar when drill active
- Clear button (✕) reverts all widgets to unfiltered state
- Auto-clears when context filter (State/County) changes

### Milestone (Phase 8)

```
☐ Admin creates drill_filter action on a widget
☐ Portal: click chart slice → other widgets update
☐ "Filtered by: X ✕" chip appears
☐ Click ✕ → widgets revert
☐ Context filter change → drill filter auto-clears
```

---

## 8. COMMON PATTERNS

### Adding a new CSS section

Always add a section header comment:
```css
/* ==========================================================================
   Phase X — Section Name
   ========================================================================== */
```

### Adding a new QWeb template

Always use the module namespace prefix:
```xml
<template id="my_template" name="Posterra My Template">
```
Not just `id="my_template"` — this avoids ID collisions with other Odoo modules.

### Passing data from Python controller to React (Phase 7+)

```python
# In controller, add to values dict:
import json
values['page_config_json'] = json.dumps(page_config_dict)
values['initial_widgets_json'] = json.dumps(widget_data_dict)
```

```xml
<!-- In QWeb template, on the React mount div: -->
<div id="app-root"
     t-att-data-page-config="page_config_json"
     t-att-data-initial-widgets="initial_widgets_json"/>
```

### Never do this in QWeb (broken in Odoo 19.0):

```xml
<!-- BROKEN: -->
<script type="application/json" id="page-config">
    <t t-out="page_config_json"/>
</script>

<!-- CORRECT: use data-* attribute on a div instead -->
```
