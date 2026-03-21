# POSTERRA PORTAL — COMPLETE DEVELOPMENT SKILL

## LOAD THIS FILE AT THE START OF EVERY CODING SESSION

---

## ★ IMPLEMENTATION ORDER — READ THIS FIRST ★

Build these phases in strict sequence. Never start a phase until the
previous phase's milestone test passes. Each phase builds on the last.

```
PHASE 0  →  DB-Driven Pages, Tabs, Filters             ~8h   ✅ COMPLETE
PHASE 1  →  Widget System (model + views + render)      ~6h   ✅ COMPLETE
PHASE 4  →  White-Label Login + Strip Odoo Chrome       ~4h   ← NEXT
PHASE 5  →  saas.app Model + Multi-App URL Routing      ~4h
PHASE 6  →  JSON API Endpoints (widget data + config)   ~6h
PHASE 7  →  React Widget Grid + Filter Bar              ~8h
PHASE 8  →  Widget Click-Actions (drill + navigate)     ~6h
PHASE 2  →  Seed Widgets + Validate All Types           ~2h
PHASE 3  →  Performance & Polish                        ~3h
```

### Why Phase 2/3 moved after Phase 8

Phase 2 seeds sample widgets and Phase 3 polishes rendering. After Phase 7,
widgets render via React instead of QWeb. Seeding and stress-testing widgets
against the old QWeb renderer and then redoing it for React would be double
work. Complete the React migration first, then seed and validate all 14
chart types against the final rendering pipeline.

### What each phase unlocks

| Phase | You can do this after it's done |
|-------|----------------------------------|
| **0** | Admin can manage pages, tabs, filters from backend. Sidebar and filter bar read from DB. Portal still works exactly as before. |
| **1** | Admin creates `dashboard.widget` records with SQL/ORM queries. Portal renders all 14 chart types (bar, line, pie, donut, gauge, gauge_kpi, radar, KPI, status_kpi, table, scatter, heatmap, battle_card, insight_panel) live with Apache ECharts. |
| **4** | Users see a fully branded login page per app. No Odoo header, footer, or chrome on any portal page. |
| **5** | Admin creates app records. Multiple apps (`/my/posterra`, `/my/aco-builder`) each with own branding, pages, widgets on the same Odoo instance. |
| **6** | Odoo exposes JSON API endpoints for page config, widget data, filter options. React (or any client) can fetch widget data without QWeb. |
| **7** | Portal content area (filters + tabs + widgets) renders via React. Filter changes and tab switches happen without page reloads. |
| **8** | Admin configures click-actions on widgets: click a table row → navigate to another page; click a chart slice → update other widgets on the same page. All admin-configurable, zero code. |
| **2** | All 14 chart types seeded and validated against the React rendering pipeline. Color palettes confirmed. |
| **3** | Performance: SQL timeouts, error cards, caching, no N+1 queries. |

### The one Claude prompt to start each phase

Copy-paste the relevant line at the start of your session:

**Phase 0:** ✅ COMPLETE

**Phase 1:** ✅ COMPLETE

**Phase 4:**
> "Read SKILL.md, then build Phase 4 — White-Label Login + Strip Odoo Chrome. Create a minimal portal base layout template that does NOT inherit from `website.layout`. Build custom login controllers and templates per app at `/my/<app_key>/login`. Remove all Odoo branding from portal pages — no header navbar, no footer, no 'Powered by Odoo'. The sidebar, header bar (user menu + HHA selector), and content area should be the only visible elements. Customize error pages (404/500) to match app branding."

**Phase 5:**
> "Read SKILL.md, then build Phase 5 — saas.app model + multi-app URL routing. Create the `saas.app` model with branding fields (logo, colors, login background, tagline). Add `app_id` Many2one to `dashboard.page`. Update `portal.py` to resolve the app from URL prefix and scope pages/widgets to the active app. Build admin views for saas.app under Configuration → Apps."

**Phase 6:**
> "Read SKILL.md, then build Phase 6 — JSON API endpoints. Create `/api/v1/page/<page_key>/config` (returns page structure, tabs, filter config, widget config including click-actions) and `/api/v1/widget/<int:widget_id>/data` (returns single widget data with filter params). Add JWT auth controller for API access. Extract existing Python widget data-building logic into the API — the computation stays the same, only the delivery changes from QWeb context to JSON response."

**Phase 7:**
> "Read SKILL.md, then build Phase 7 — React Widget Grid + Filter Bar. Set up a React app (Vite build) that mounts onto `<div id='app-root'>` inside the QWeb portal shell. Build React components for: FilterBar (all filter types including cascading State→County→Locations), TabBar, WidgetGrid, and one React component per widget type (BarChart, DonutChart, KPICard, Table, etc.). Initial page data is embedded as JSON in a `data-page-config` attribute on the mount div — zero API calls on first load. Filter changes trigger parallel widget data refetches via the Phase 6 API."

**Phase 8:**
> "Read SKILL.md, then build Phase 8 — Widget Click-Actions. Create the `dashboard.widget.action` model with admin views (inline on widget form). Implement three action types: `drill_filter` (click chart slice/table row → filter other widgets on same page), `navigate_page` (click → go to another page with filter context), `navigate_tab` (click → switch tab). React reads action config from page config JSON and wires ECharts click handlers + table row click handlers accordingly. Build the drill-filter state management: 'Filtered by: X ✕' chip, clear button, auto-clear on context filter change."

**Phase 2:**
> "Read SKILL.md, then seed one sample `dashboard.widget` record for each of the 14 chart types on the Overview page (use the `hha_provider` table for SQL queries where possible). After seeding, load the portal and fix any rendering errors found — React console errors, Python API exceptions, or blank widget cards."

**Phase 3:**
> "Read SKILL.md, then review the widget data pipeline for performance and robustness — add SQL query timeouts, cache the widget data JSON per widget+filter combination using a simple dict on the request, and improve error display on widget cards so admins can see what went wrong."

### Milestone checklist — tick before moving to the next phase

```
PHASE 0  ✅ COMPLETE
  ✅ Go to Posterra → Configuration → Pages — all 13 pages visible
  ✅ Rename a page in backend → sidebar updates on portal
  ✅ Set State filter is_active=False on Overview → filter bar shows 4 items
  ✅ Restore both changes

PHASE 1  ✅ COMPLETE
  ✅ Posterra → Configuration → Dashboard Widgets exists, no errors on load
  ✅ Create a bar chart widget with SQL → ECharts bar renders on portal
  ✅ Create a gauge widget → meter/gauge renders
  ✅ Create a status_kpi widget → dynamic icon + colour correct
  ✅ Create an insight_panel → narrative renders with active filter values
  ✅ Create a battle_card → WIN/TIE/LOSE badges visible
  ✅ col_span 6+6, 4+8, 12 all lay out correctly in Bootstrap grid

PHASE 4
  ☐ Visit /my/posterra/login — see branded login page, NO Odoo navbar/footer
  ☐ Visit /my/posterra/overview — NO "Your Logo", "Home", "Contact us" header
  ☐ Visit /my/posterra/overview — NO "Useful Links", "About us" footer
  ☐ Trigger a 404 error — see branded error page, not Odoo default
  ☐ View page source — no "odoo" string in visible HTML/meta tags

PHASE 5
  ☐ Create a saas.app record for "Posterra" with logo and colors
  ☐ Create a second saas.app record for "ACO Builder" with different branding
  ☐ Visit /my/posterra/login — see Posterra branding
  ☐ Visit /my/aco-builder/login — see ACO Builder branding
  ☐ Pages are scoped: Posterra pages don't appear in ACO Builder sidebar
  ☐ Admin views: Configuration → Apps shows both app records

PHASE 6
  ☐ GET /api/v1/page/overview/config returns JSON with tabs, filters, widgets
  ☐ GET /api/v1/widget/{id}/data?state=Arkansas returns widget data JSON
  ☐ GET /api/v1/filters/cascade?type=county&state=Arkansas returns county list
  ☐ API requires valid JWT token — unauthenticated requests return 401
  ☐ Response shape matches what React components expect (documented below)

PHASE 7
  ☐ Portal loads — React mounts, filter bar renders from config JSON
  ☐ Change State filter → County dropdown updates (cascade) without page reload
  ☐ Click Apply → all widgets refetch and re-render without page reload
  ☐ Tab switch → widgets swap without page reload
  ☐ All 14 widget types render in React (ECharts charts, KPI cards, tables, etc.)
  ☐ Initial page load has NO loading flash (data embedded in QWeb shell)
  ☐ Browser back/forward buttons work (URL reflects filter state)

PHASE 8
  ☐ Admin creates widget action: click Destination row in table → drill_filter
  ☐ Portal: click "HHA" in Actual Discharges → KPI cards + Intended Discharges update
  ☐ Portal: click "IP" on donut chart → KPI cards update
  ☐ Portal: click ACO Name in table → navigates to ACO page with name pre-filled
  ☐ "Filtered by: HHA ✕" chip appears when drill filter active
  ☐ Click ✕ → all widgets revert to unfiltered state
  ☐ Change context filter (State) → drill filter auto-clears
  ☐ Admin can create/edit/deactivate actions from widget form "Click Actions" tab

PHASE 2
  ☐ All 14 chart_type values render without React console errors
  ☐ Color palette switch healthcare → warm changes chart colours
  ☐ Deactivate a widget → disappears from portal immediately
  ☐ insight_panel: select HHA in portal → hha_name updates in narrative
  ☐ ECharts charts resize correctly on browser window resize

PHASE 3
  ☐ SQL query with bad syntax shows friendly error card, not a 500
  ☐ No N+1 queries — widget data loaded in one pass per page load
  ☐ Page load time under 2s with 10 active widgets
```

---

## 1. PROJECT CONTEXT

**Platform:** Odoo 19 Community Edition, custom module `posterra_portal`
**What it is:** A multi-app healthcare analytics SaaS platform.
Each "app" (Posterra, ACO Builder, etc.) serves a different client base with
separate branding, login pages, dashboards, and data. All apps are managed
from a single Odoo backend. External users never see Odoo.

**Architecture:**
```
┌──────────────────────────────────────────────────────────────┐
│  Odoo QWeb Shell (server-rendered once per page navigation)  │
│  ┌──────────┐ ┌────────────────────────────────────────────┐ │
│  │ Sidebar  │ │  <div id="app-root"                        │ │
│  │ (QWeb)   │ │       data-page-config='{...}'             │ │
│  │          │ │       data-initial-widgets='{...}'>         │ │
│  │ MY HHA   │ │                                            │ │
│  │ Overview │ │     ┌────────────────────────────────────┐ │ │
│  │ Cmd Ctr  │ │     │  REACT OWNS THIS AREA              │ │ │
│  │          │ │     │  ● Filter Bar (State, County, etc.) │ │ │
│  │ PORTFOLIO│ │     │  ● Tab Bar                          │ │ │
│  │ Hospitals│ │     │  ● Widget Grid (charts, KPIs, etc.) │ │ │
│  │ SNFs     │ │     │  ● Drill-down state management      │ │ │
│  │ ...      │ │     │  ● Click-action handlers             │ │ │
│  │          │ │     └────────────────────────────────────┘ │ │
│  └──────────┘ └────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Core stack:**
- Odoo QWeb templates (XML) for portal shell (sidebar, header, login) — **NO OWL on portal pages**
- **React** (via Vite build) for widget grid, filter bar, tab bar, and all interactivity
- **Apache ECharts 5** for all charts (used inside React via `echarts-for-react` or direct refs)
- PostgreSQL (claims data, materialized views)
- Redis for caching, PgBouncer for connection pooling
- JWT authentication for API endpoints

**What is already built and working (Phase 0 + 1):**
- Login system with admin-configured access (direct HHA assignment or Scope Group)
- Scope Group system — admin-configurable column+value matching to resolve HHA providers for groups of users (`hha.scope.group`)
- Sidebar navigation — 11 pages across DB-driven sections (`dashboard.nav.section`)
- Sidebar section labels (MY HHA / PORTFOLIO / DATA EXPLORER) — fully configurable via backend
- HHA selector integrated into the Context Filters bar (first item, before State/County/City)
- Filter bar (State → County → Locations cascading, Year, Payer — DB-driven via `dashboard.page.filter`)
- Tab bar navigation (DB-driven via `dashboard.page.tab`)
- Page sections above tab bar (Strategic Identity, Market Leaders) — DB-driven via `dashboard.page.section`
- Widget system — all 14 chart types including `gauge_kpi` (colored arc + sub-KPI cards)
- Portal user creation wizard with optional scope group assignment

**Goal of the platform:** Replace every hardcoded thing with database-driven configuration.
Admin creates records in the Odoo backend. The portal renders whatever those records say.
Multiple apps with full white-labeling — users never see Odoo.

---

## 2. THE FIVE CRITICAL RULES

1. **NO OWL on portal pages.** QWeb templates for shell + React for content area.
2. **NO hardcoded data in templates.** Every value comes from the DB via controller context or JSON API.
3. **Apache ECharts 5 for all charts.** Used inside React components via refs or `echarts-for-react`.
4. **Initial page data embedded as JSON attributes** on the React mount div. React reads `data-page-config` and `data-initial-widgets` on mount — zero API calls for first render. Subsequent interactions (filter change, drill-down) use the JSON API.
5. **Admin EDITS an existing widget rather than deleting and recreating.** Change `chart_type`, `query_sql`, or any field in-place. Only delete+recreate if moving to a different page entirely.

---

## 3. THE COMPLETE DATA FLOW

### Initial Page Load (server-rendered shell + React hydration)

```
Portal user visits /my/posterra/overview
    ↓  portal.py resolves saas.app from URL prefix "posterra"
    ↓  reads page config + active filters from DB (scoped to app)
    ↓  builds sql_params dict (filter values + hha context)
    ↓  reads active widgets for this page + default tab
    ↓  for each widget: executes SQL or ORM query
    ↓  builds ECharts option dict (or KPI/table/battle/insight dict)
    ↓  serialises everything as JSON
    ↓  QWeb template renders shell (sidebar, header)
    ↓  passes page config + widget data as data-* attributes on mount div
    ↓  React mounts, reads JSON, renders filter bar + tab bar + widget grid
    ↓  user sees full page — NO loading flash, NO extra API calls
```

### Subsequent Interactions (React → JSON API → React)

```
User changes State filter to "Oklahoma" and clicks Apply
    ↓  React updates filter state
    ↓  React fires parallel API calls for all visible widgets:
       GET /api/v1/widget/7/data?state=Oklahoma&year=2025&...
       GET /api/v1/widget/8/data?state=Oklahoma&year=2025&...
       ... (all in parallel)
    ↓  Each widget shows loading spinner independently
    ↓  As responses arrive, React re-renders each widget
    ↓  URL updates to reflect new filter state (shareable deep link)

User clicks "HHA" row in Actual Discharges table (drill-filter action)
    ↓  React reads widget action config: drill_filter, key=destination
    ↓  React dispatches state change: {drill_filters: {destination: 'HHA'}}
    ↓  Subscribed widgets (KPIs, Intended Discharges) fire parallel API calls
       with additional param: &destination=HHA
    ↓  "Filtered by: HHA ✕" chip appears above widget grid
    ↓  Click ✕ → drill state clears → widgets refetch unfiltered

User clicks ACO name in table (navigate-page action)
    ↓  React reads widget action config: navigate_page, target=aco page
    ↓  Browser navigates: /my/posterra/aco?aco_name=D0211
    ↓  New full page load → QWeb shell + React mount with pre-filtered data
```

---

## 4. MODULE FILE STRUCTURE

```
posterra_portal/
├── __manifest__.py                         ← EXISTING — updated through Scope Group phase
├── __init__.py                             ← EXISTING — updated through Scope Group phase
├── models/
│   ├── hha_provider.py                     ← EXISTING (domain_match_name cascade: DBA → Brand → Name)
│   ├── res_partner.py                      ← EXISTING (hha_scope_group_id added)
│   ├── hha_scope_group.py                  ← Scope Group ✅  admin-configurable HHA access groups
│   ├── res_config_settings.py              ← EXISTING (RLS field removed, scope group replaces it)
│   ├── saas_app.py                         ← Phase 5 — multi-app tenant registry
│   ├── dashboard_page.py                   ← Phase 0 ✅  (DashboardNavSection added mid-phase)
│   ├── dashboard_page_filter.py            ← Phase 0 ✅
│   ├── dashboard_page_section.py           ← mid-phase ✅  comparison_bar / leaderboard_table
│   ├── dashboard_widget.py                 ← Phase 1 ✅  (gauge_kpi added mid-phase)
│   └── dashboard_widget_action.py          ← Phase 8 — click-action configuration
├── controllers/
│   ├── main.py                             ← EXISTING — login redirect (uses _get_providers_for_user)
│   ├── portal.py                           ← EXISTING — Scope Group resolution + dashboard controller
│   ├── auth_api.py                         ← Phase 6 — JWT login/refresh endpoints
│   └── widget_api.py                       ← Phase 6 — JSON API for widget data + page config
├── views/
│   ├── dashboard_templates.xml             ← EXISTING — HHA selector moved into context filter bar
│   ├── login_templates.xml                 ← Phase 4 — custom branded login page templates
│   ├── hha_scope_group_views.xml           ← Scope Group ✅  backend admin views
│   ├── nav_section_views.xml               ← mid-phase ✅  admin views for dashboard.nav.section
│   ├── page_views.xml                      ← Phase 0 ✅  (+ Widgets tab Phase 1, nav_section_id mid-phase)
│   ├── section_views.xml                   ← mid-phase ✅  admin views for dashboard.page.section
│   ├── widget_views.xml                    ← Phase 1 ✅  (gauge_kpi fields added mid-phase)
│   ├── widget_action_views.xml             ← Phase 8 — inline actions on widget form
│   └── saas_app_views.xml                  ← Phase 5 — admin views for saas.app
├── wizard/
│   ├── create_portal_user.py               ← EXISTING — optional hha_scope_group_id assignment
│   ├── create_portal_user_views.xml        ← EXISTING
│   ├── hha_csv_import.py                   ← EXISTING
│   └── hha_csv_import_views.xml            ← EXISTING
├── data/
│   ├── nav_sections_data.xml               ← mid-phase ✅  seed MY HHA / PORTFOLIO / DATA EXPLORER
│   ├── pages_data.xml                      ← Phase 0 ✅  — seed 11 pages + tabs (nav_section_id refs)
│   ├── filters_data.xml                    ← Phase 0 ✅  — seed filters per page
│   └── sections_data.xml                   ← mid-phase ✅  seed Strategic Identity + Market Leaders
├── static/src/
│   ├── css/posterra.css                    ← EXISTING — widget + gauge_kpi CSS added
│   └── react/                              ← Phase 7 — React app (Vite build output)
│       ├── dist/                           ← built bundle (JS + CSS)
│       ├── src/
│       │   ├── App.jsx                     ← root component
│       │   ├── state/
│       │   │   ├── FilterContext.jsx        ← context filter state (State, County, Year, etc.)
│       │   │   └── DrillContext.jsx         ← drill-down filter state from click-actions
│       │   ├── components/
│       │   │   ├── FilterBar.jsx            ← all filter types + cascading + Apply
│       │   │   ├── TabBar.jsx               ← tab navigation
│       │   │   ├── WidgetGrid.jsx           ← responsive grid layout
│       │   │   ├── DrillChip.jsx            ← "Filtered by: X ✕" indicator
│       │   │   └── widgets/
│       │   │       ├── BarChart.jsx
│       │   │       ├── LineChart.jsx
│       │   │       ├── PieChart.jsx
│       │   │       ├── DonutChart.jsx
│       │   │       ├── GaugeChart.jsx
│       │   │       ├── GaugeKPI.jsx
│       │   │       ├── RadarChart.jsx
│       │   │       ├── KPICard.jsx
│       │   │       ├── StatusKPI.jsx
│       │   │       ├── DataTable.jsx
│       │   │       ├── ScatterChart.jsx
│       │   │       ├── HeatmapChart.jsx
│       │   │       ├── BattleCard.jsx
│       │   │       └── InsightPanel.jsx
│       │   └── api/
│       │       ├── client.js                ← fetch wrapper with JWT + error handling
│       │       └── endpoints.js             ← API URL builders
│       ├── vite.config.js
│       └── package.json
└── security/
    ├── posterra_security.xml               ← EXISTING — groups + scope group record rules
    ├── dashboard_access.xml                ← Phase 0 ✅  — ACLs for page/tab/filter/widget
    └── ir.model.access.csv                 ← EXISTING — updated through Scope Group phase
```

**Import order in `models/__init__.py` (dependencies first):**
```python
from . import res_partner
from . import hha_provider
from . import hha_scope_group            # scope group system  ← Scope Group ✅
from . import saas_app                   # multi-app tenant registry  ← Phase 5
from . import dashboard_page             # no dependencies (includes DashboardNavSection)
from . import dashboard_page_filter      # depends on dashboard_page
from . import dashboard_widget           # depends on dashboard_page + tab  ← Phase 1 ✅
from . import dashboard_widget_action    # depends on dashboard_widget  ← Phase 8
from . import dashboard_page_section     # depends on dashboard_page  ← mid-phase ✅
from . import res_config_settings
```

---

## 5. ALL DATA MODELS — IN DEPENDENCY ORDER

### 5.1  `saas.app`  ← Phase 5

Multi-app tenant registry. One record per app (Posterra, ACO Builder, etc.).
Controls branding, login page, URL routing.

```python
class SaaSApp(models.Model):
    _name = 'saas.app'
    _description = 'SaaS Application'
    _rec_name = 'name'

    # ── Identity ───────────────────────────────────────────────────────
    name          = fields.Char(required=True)              # "Posterra"
    app_key       = fields.Char(required=True, index=True)  # "posterra" — used in URL /my/<app_key>/
    is_active     = fields.Boolean(default=True)

    # ── Branding ───────────────────────────────────────────────────────
    logo          = fields.Binary(attachment=True)           # app logo for sidebar + login
    logo_filename = fields.Char()
    favicon       = fields.Binary(attachment=True)
    tagline       = fields.Char()                            # shown on login page
    primary_color = fields.Char(default='#0d9488')           # main brand color
    login_bg_image = fields.Binary(attachment=True)          # login page background
    login_bg_color = fields.Char(default='#f8fafc')          # fallback bg color
    custom_css    = fields.Text()                            # per-app CSS overrides

    # ── Relationships ──────────────────────────────────────────────────
    page_ids      = fields.One2many('dashboard.page', 'app_id', string='Pages')
    page_count    = fields.Integer(compute='_compute_page_count')

    # ── Defaults ───────────────────────────────────────────────────────
    default_page_key = fields.Char(default='overview')       # landing page after login
```

**Admin menu:** Configuration → **Apps** (sequence=1)

**URL routing pattern:**
- `/my/posterra/login` → login page with Posterra branding
- `/my/posterra/overview` → Posterra Overview page
- `/my/aco-builder/login` → login page with ACO Builder branding
- `/my/aco-builder/dashboard` → ACO Builder Dashboard page

**Controller resolution (`portal.py`):**
```python
app = request.env['saas.app'].sudo().search(
    [('app_key', '=', app_key), ('is_active', '=', True)], limit=1)
if not app:
    raise request.not_found()
# All subsequent page/widget queries scoped by app_id
pages = request.env['dashboard.page'].sudo().search([
    ('app_id', '=', app.id), ('is_active', '=', True)
], order='sequence asc')
```

---

### 5.2  `dashboard.page`

Replaces the hardcoded `SIDEBAR_STRUCTURE` dict in `portal.py`.
One record per sidebar page (13 total for Posterra).

```python
class DashboardPage(models.Model):
    _name = 'dashboard.page'
    _description = 'Dashboard Page'
    _order = 'sequence asc, id asc'

    name           = fields.Char(required=True)             # "Overview", "Hospitals"
    key            = fields.Char(required=True, index=True) # "overview", "hospitals"
    app_id         = fields.Many2one(                       # ← Phase 5 addition
        'saas.app',
        required=True,
        ondelete='cascade',
        string='Application',
    )
    nav_section_id = fields.Many2one(                       # ← replaces section Selection
        'dashboard.nav.section',
        required=True,
        ondelete='restrict',
        string='Sidebar Section',
    )
    icon       = fields.Char()          # "fa-home", "fa-hospital-o"
    sequence   = fields.Integer(default=10)
    is_active  = fields.Boolean(default=True)
    group_ids  = fields.Many2many('res.groups')
    tab_ids    = fields.One2many('dashboard.page.tab', 'page_id', string='Tabs')
    filter_ids = fields.One2many('dashboard.page.filter', 'page_id', string='Filters')

    @api.model
    def default_get(self, fields_list):
        """New pages always append to the end of the sidebar (not position 10)."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            last = self.search([], order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res
```

`dashboard.page.tab` — tabs within a page:
```python
class DashboardPageTab(models.Model):
    _name = 'dashboard.page.tab'
    _description = 'Dashboard Page Tab'
    _order = 'sequence asc, id asc'

    name     = fields.Char(required=True)               # "Command Center"
    key      = fields.Char(required=True, index=True)   # "command_center"
    page_id  = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    @api.model
    def default_get(self, fields_list):
        """New tabs append after the last tab on the same page."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            page_id = self.env.context.get('default_page_id')
            domain = [('page_id', '=', page_id)] if page_id else []
            last = self.search(domain, order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res
```

---

### 5.3  `dashboard.nav.section`  ← mid-phase ✅

Replaces the hardcoded `SECTIONS` constant in `portal.py` and the old
`section = Selection(...)` field on `dashboard.page`.
Admin creates/renames/reorders/deactivates sidebar group headers from
**Configuration → Nav Sections**.

```python
class DashboardNavSection(models.Model):
    _name        = 'dashboard.nav.section'
    _description = 'Sidebar Navigation Section'
    _order       = 'sequence asc, id asc'

    name      = fields.Char(required=True, string='Label')       # "MY HHA"
    key       = fields.Char(required=True, index=True)           # "my_hha" (legacy slug)
    sequence  = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
    page_ids  = fields.One2many('dashboard.page', 'nav_section_id', string='Pages')

    @api.model
    def default_get(self, fields_list):
        """New sections land at the end of the sidebar group list."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            last = self.search([], order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res
```

**Controller (`portal.py`) — replaces `SECTIONS` constant:**
```python
nav_sections = request.env['dashboard.nav.section'].sudo().search(
    [('is_active', '=', True)], order='sequence asc'
)
sections_with_pages = []
for ns in nav_sections:
    ns_pages = pages.filtered(lambda p: p.nav_section_id.id == ns.id)
    if ns_pages:
        sections_with_pages.append({'section': ns, 'pages': ns_pages})
# Pass 'sections_with_pages' to template (replaces old 'sections': SECTIONS)
```

**Sidebar template loop:**
```xml
<t t-foreach="sections_with_pages" t-as="sp">
    <div class="pv-sidebar-section-label"><t t-esc="sp['section'].name"/></div>
    <t t-foreach="sp['pages']" t-as="page">
        <a t-attf-href="/my/#{app.app_key}/#{page.key}?hha_id=#{current_hha_id}"
           t-attf-class="pv-sidebar-item #{current_page_key == page.key and 'active' or ''}">
            <i t-attf-class="fa #{page.icon} pv-sidebar-icon"/>
            <span t-esc="page.name"/>
        </a>
    </t>
</t>
```

**Seed data XML IDs:**
- `posterra_portal.nav_section_my_hha`
- `posterra_portal.nav_section_portfolio`
- `posterra_portal.nav_section_data_explorer`

**Pages seed data pattern (use `ref=` not the old varchar value):**
```xml
<field name="nav_section_id" ref="posterra_portal.nav_section_my_hha"/>
```

---

### 5.4  `dashboard.page.section`  ← mid-phase ✅

DB-driven sections that appear **above the tab bar** on any page
(replaces hardcoded Strategic Identity + Market Leaders HTML on Overview).

```python
class DashboardPageSection(models.Model):
    _name  = 'dashboard.page.section'
    _order = 'sequence asc, id asc'

    # Placement
    page_id   = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    sequence  = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    # Identity
    name         = fields.Char(required=True)           # "Strategic Identity"
    icon         = fields.Char(default='fa-star-o')
    action_label = fields.Char()                        # static badge, e.g. "vs State HHAs"
    section_type = fields.Selection([
        ('comparison_bar',    'Comparison Bar (KPI cards + progress bars)'),
        ('leaderboard_table', 'Leaderboard Table (ranked rows)'),
    ], required=True, default='comparison_bar')

    # SQL query (same safety rules as dashboard.widget)
    query_sql = fields.Text()

    # Comparison bar column mapping
    cb_label_col    = fields.Char()   # card title
    cb_value_col    = fields.Char()   # numeric % value + bar width
    cb_status_col   = fields.Char()   # Strong/Moderate/Weak/Neutral
    cb_desc_col     = fields.Char()   # small description text
    cb_sublabel_col = fields.Char()   # optional sub-label next to value

    # Leaderboard column mapping
    lt_rank_col       = fields.Char()
    lt_name_col       = fields.Char()
    lt_sub_name_cols  = fields.Char()   # comma-sep — shown smaller below name
    lt_display_cols   = fields.Char()   # comma-sep metric column names
    lt_display_labels = fields.Char()   # comma-sep column headers
    lt_you_col        = fields.Char()   # column returning 1 for highlighted row
    lt_color_col      = fields.Char()   # last column — color-coded by thresholds
    lt_good_threshold = fields.Float(default=70)
    lt_warn_threshold = fields.Float(default=50)

    @api.model
    def default_get(self, fields_list):
        """New sections append after the last section on the same page."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            page_id = self.env.context.get('default_page_id')
            domain = [('page_id', '=', page_id)] if page_id else []
            last = self.search(domain, order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res
```

**Status class mapping for `comparison_bar`:**
```python
_STATUS_CLASS = {
    'strong': 'strong', 'good': 'strong',
    'moderate': 'moderate', 'warning': 'moderate',
    'weak': 'weak', 'bad': 'weak',
    'neutral': 'neutral', 'stable': 'neutral',
}
```
Bar colors cycle by row index: `['pv-bar-blue', 'pv-bar-purple', 'pv-bar-orange', 'pv-bar-teal']`

**Portal context:**
```python
page_sections = env['dashboard.page.section'].sudo().search([
    ('page_id.key', '=', page_key), ('is_active', '=', True)
], order='sequence asc')
section_data = {sec.id: sec.get_portal_data(portal_ctx) for sec in page_sections}
# Pass 'page_sections' and 'section_data' to template
```

**Template position:** after filter bar `<div>`, before tab bar. Guarded by `t-if="page_sections"`.

**Admin menu:** Configuration → **Page Sections** (sequence=5)
**Seed data:** `data/sections_data.xml` (`noupdate="1"`)

---

### 5.5  `hha.scope.group`  ← Scope Group ✅

Admin-configurable access groups that determine which HHA providers a portal
user can see. Configure a column + value + match mode once, assign the group
to many users.

```python
class HHAScopeGroup(models.Model):
    _name = 'hha.scope.group'
    _description = 'HHA Scope Group'
    _rec_name = 'name'

    name          = fields.Char(required=True)              # "Elara Caring"
    match_column  = fields.Selection([
        ('domain_match_name', 'Auto (DBA → Brand → Name)'),
        ('hha_dba', 'DBA'),
        ('hha_brand_name', 'Brand Name'),
        ('hha_name', 'HHA Name'),
    ], default='domain_match_name', required=True, string='Match Column')
    match_value   = fields.Char(string='Match Value')       # "Elara Caring"
    match_mode    = fields.Selection([
        ('exact', 'Exact Match'),
        ('starts_with', 'Starts With'),
        ('contains', 'Contains'),
    ], default='exact', required=True, string='Match Mode')
    auto_resolve  = fields.Boolean(default=True)
    provider_ids  = fields.Many2many('hha.provider',
        'hha_scope_group_provider_rel', 'scope_group_id', 'provider_id',
        string='Matched Providers')
    provider_count = fields.Integer(compute='_compute_provider_count', store=True)
    partner_ids   = fields.One2many('res.partner', 'hha_scope_group_id',
        string='Assigned Users')
    user_count    = fields.Integer(compute='_compute_user_count')
```

**Key behaviors:**
- `_resolve_providers()` — ORM search using `match_column` + `match_value` + `match_mode`
  - `exact` → `=ilike` operator (case-insensitive exact)
  - `starts_with` → `=ilike` with `%` suffix
  - `contains` → `ilike` operator
- `action_resolve_providers()` — button action to manually re-resolve
- `@api.onchange('match_column', 'match_value', 'match_mode', 'auto_resolve')` — live preview of matched providers in form
- `@api.model_create_multi` / `write()` overrides — auto-resolve on save when `auto_resolve=True` and match config fields change
- `action_view_users()` — stat button to show assigned partners

**View note:** `provider_ids` uses `readonly="auto_resolve"` + `force_save="1"` in the XML view.
The `force_save="1"` is **required** because Odoo does not send readonly field values back to the
server on save — without it, onchange-populated Many2many values are discarded on save.

**Partner integration (`res_partner.py`):**
```python
hha_scope_group_id = fields.Many2one('hha.scope.group', string='HHA Scope Group')

@api.depends('hha_provider_id', 'hha_scope_group_id')
def _compute_is_posterra_user(self):
    for partner in self:
        partner.is_posterra_user = bool(
            partner.hha_provider_id or partner.hha_scope_group_id
        )
```

**Provider resolution (`controllers/portal.py` → `_get_providers_for_user()`):**
```
Stage 1 — Direct assignment:  partner.hha_provider_id → single HHA
Stage 2 — Scope Group:        partner.hha_scope_group_id.provider_ids → multiple HHAs
No fallback — empty recordset if neither configured (user sees /my, not portal)
```

```python
def _get_providers_for_user(user):
    partner = user.partner_id.sudo()
    if partner.hha_provider_id:
        return request.env['hha.provider'].sudo().browse(partner.hha_provider_id.id)
    if partner.hha_scope_group_id and partner.hha_scope_group_id.provider_ids:
        return partner.hha_scope_group_id.sudo().provider_ids
    return request.env['hha.provider'].browse()  # empty recordset
```

**Login redirect (`controllers/main.py`):**
```python
from .portal import _get_providers_for_user

class PosterraHome(Home):

    def _has_posterra_access(self, uid):
        user = request.env['res.users'].sudo().browse(uid)
        return bool(_get_providers_for_user(user))

    def login_successful_external_user(self, **kwargs):
        if request.session.uid and self._has_posterra_access(request.session.uid):
            return request.redirect('/my/posterra')
        return super().login_successful_external_user(**kwargs)

    def _login_redirect(self, uid, redirect=None):
        if not is_user_internal(uid) and self._has_posterra_access(uid):
            return '/my/posterra'
        return super()._login_redirect(uid, redirect=redirect)
```

**Admin menu:** Configuration → **Scope Groups** (sequence=15)

**Wizard integration:** `wizard/create_portal_user.py` has optional `hha_scope_group_id`
field — admin can bulk-assign scope group during portal user creation.

---

### 5.6  `dashboard.page.filter`

Controls which filters appear on each page's filter bar.
Defined per PAGE (all tabs on a page share the same filter bar).

```python
class DashboardPageFilter(models.Model):
    _name = 'dashboard.page.filter'
    _description = 'Dashboard Page Filter'
    _order = 'sequence asc'

    page_id       = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    filter_type   = fields.Selection([
        ('state',         'State'),
        ('county',        'County'),
        ('locations',     'Locations'),
        ('year',          'Year'),
        ('payer',         'Payer'),
        ('custom_select', 'Custom Dropdown'),
    ], required=True)
    label         = fields.Char()          # Override label e.g. "Region" instead of "State"
    sequence      = fields.Integer(default=10)
    is_active     = fields.Boolean(default=True)
    default_value = fields.Char()          # "2025", "ffs", "Oklahoma"
    is_required   = fields.Boolean(default=False)
    options_json  = fields.Text()          # JSON [{value, label}] for year/payer/custom
    placeholder   = fields.Char()          # "All States", "Select Year"

    def get_options(self):
        self.ensure_one()
        import json
        if self.filter_type == 'year':
            if self.options_json:
                try: return json.loads(self.options_json)
                except: pass
            return [
                {'value': '2023', 'label': '2023'},
                {'value': '2024', 'label': '2024'},
                {'value': '2025', 'label': '2025 (Current)'},
            ]
        elif self.filter_type == 'payer':
            if self.options_json:
                try: return json.loads(self.options_json)
                except: pass
            return [
                {'value': 'all', 'label': 'All Payers'},
                {'value': 'ffs', 'label': 'Fee-for-Service'},
                {'value': 'ma',  'label': 'Medicare Advantage'},
            ]
        elif self.filter_type == 'custom_select' and self.options_json:
            try: return json.loads(self.options_json)
            except: pass
        return []
```

**What admin can do with filters (zero code):**

| Action | How |
|--------|-----|
| Remove State filter from Hospitals page | Set `is_active = False` |
| Rename "Payer" → "Insurance Type" | Edit the `label` field |
| Change Year default to 2024 | Edit `default_value` to "2024" |
| Reorder filters left-to-right | Change `sequence` numbers |
| Add a Quarter filter | New record, `filter_type = custom_select`, set `options_json` |
| Remove filter bar entirely from a page | Set all this page's filters `is_active = False` |
| Make Year required (no blank) | Set `is_required = True` |

**Recommended filters per page:**

| Page | Filters |
|------|---------|
| Overview | State, County, Locations, Year, Payer |
| Hospitals | State, Year, Payer |
| SNFs | State, Year, Payer |
| Physicians | State, Year, Payer |
| Competitive Intel | State, Year |
| Case Mix | Year, Payer |
| Command Center | Year, Payer |
| Leaderboard | Year, Payer |
| Market Threats | State, Year |
| Strategy | Year |
| Reports | Year, Payer |
| Admits | State, Year, Payer |
| Referral Sources | State, Year, Payer |

---

### 5.7  `dashboard.widget`  ← Phase 1 ✅

One record = one widget on the dashboard. Central model.

```python
class DashboardWidget(models.Model):
    _name = 'dashboard.widget'
    _description = 'Dashboard Widget'
    _order = 'sequence asc, id asc'

    # ── Placement ─────────────────────────────────────────────────────────
    page_id  = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    tab_id   = fields.Many2one('dashboard.page.tab',
                                domain="[('page_id','=',page_id)]",
                                ondelete='set null',
                                help='Leave empty → widget shows on ALL tabs of the page')
    sequence  = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    # ── Display ───────────────────────────────────────────────────────────
    name         = fields.Char(string='Title', required=True)
    col_span     = fields.Selection([('3','25%'),('4','33%'),('6','50%'),
                                     ('8','67%'),('12','100%')], default='6')
    chart_height = fields.Integer(default=350, string='Height (px)')
    chart_type   = fields.Selection([
        ('bar','Bar'), ('line','Line'), ('pie','Pie'), ('donut','Donut'),
        ('gauge','Gauge / Meter'), ('gauge_kpi','Gauge + KPI Breakdown'),
        ('radar','Radar / Spider'),
        ('kpi','KPI Card'), ('status_kpi','KPI Card — Dynamic Icon'),
        ('table','Data Table'), ('scatter','Scatter'), ('heatmap','Heatmap'),
        ('battle_card','Battle Card (You vs Them)'),
        ('insight_panel','Insight Panel'),
    ], required=True, default='bar')

    # ── Color palette ─────────────────────────────────────────────────────
    color_palette = fields.Selection([
        ('default','Default (ECharts)'),
        ('healthcare','Healthcare (teal/green)'),
        ('ocean','Ocean (blue tones)'),
        ('warm','Warm (orange/red/amber)'),
        ('mono','Monochrome (grey)'),
        ('custom','Custom (use echart_override)'),
    ], default='healthcare')

    # ── Query mode ────────────────────────────────────────────────────────
    query_type = fields.Selection([('sql','Raw SQL'),('orm','Model + Domain')],
                                   required=True, default='sql')

    # ── SQL branch ────────────────────────────────────────────────────────
    query_sql     = fields.Text()   # SELECT … Use %(field_name)s for filter params
    x_column      = fields.Char()   # Result column for X axis / labels
    y_columns     = fields.Char()   # Comma-separated result columns for values
    series_column = fields.Char()   # Result column to split into multiple series

    # ── ORM branch ────────────────────────────────────────────────────────
    orm_model_id      = fields.Many2one('ir.model')
    orm_model_name    = fields.Char(related='orm_model_id.model', store=True)
    orm_domain        = fields.Char(default='[]')
    orm_groupby_field = fields.Many2one('ir.model.fields',
                                         domain="[('model_id','=',orm_model_id)]")
    orm_measure_field = fields.Many2one('ir.model.fields',
                                         domain="[('model_id','=',orm_model_id)]")
    orm_agg_func      = fields.Selection([('count','Count'),('sum','Sum'),
                                           ('avg','Avg'),('min','Min'),('max','Max')],
                                          default='count')
    orm_series_field  = fields.Many2one('ir.model.fields',
                                         domain="[('model_id','=',orm_model_id)]")

    # ── KPI fields ────────────────────────────────────────────────────────
    kpi_format = fields.Selection([('number','Number'),('currency','$'),
                                    ('percent','%'),('decimal','0.00')], default='number')
    kpi_prefix = fields.Char()
    kpi_suffix = fields.Char()

    # ── status_kpi ────────────────────────────────────────────────────────
    status_column = fields.Char()   # SQL column: up / down / retreated / neutral / warning

    # ── battle_card ───────────────────────────────────────────────────────
    label_column    = fields.Char()   # SQL column for metric row label
    you_column      = fields.Char()   # SQL column for YOUR value
    them_column     = fields.Char()   # SQL column for THEIR value
    competitor_name = fields.Char()   # Label for "Them" column
    win_threshold   = fields.Selection([('higher','Higher is better'),
                                         ('lower','Lower is better')], default='higher')

    # ── Gauge options (gauge + gauge_kpi) ────────────────────────────────
    gauge_min            = fields.Float(default=0)
    gauge_max            = fields.Float(default=100)
    gauge_color_mode     = fields.Selection([
        ('traffic_light', 'Traffic Light (red/amber/green)'),
        ('palette',        'Use Color Palette'),
    ], default='traffic_light')
    gauge_warn_threshold = fields.Float(default=50)   # below → red; between → amber
    gauge_good_threshold = fields.Float(default=75)   # at or above → green

    # ── Gauge KPI Breakdown (gauge_kpi only) ──────────────────────────────
    gauge_sub_kpi_columns   = fields.Char()  # comma-sep columns for sub-KPI values
    gauge_sub_kpi_labels    = fields.Char()  # comma-sep display labels
    gauge_sub_label_columns = fields.Char()  # comma-sep sub-labels below value
    gauge_alert_column      = fields.Char()  # column for optional alert text

    # ── insight_panel ─────────────────────────────────────────────────────
    metric1_label      = fields.Char()   # e.g. "Pre-PDGM Avg (2017-19)"
    metric2_label      = fields.Char()   # e.g. "Post-COVID Avg (2023-25)"
    metric3_label      = fields.Char()   # e.g. "Drift"
    narrative_template = fields.Text()   # Template with %(key)s placeholders

    # ── Click Actions ─────────────────────────────────────────────────────
    action_ids = fields.One2many('dashboard.widget.action', 'widget_id',
                                  string='Click Actions')   # ← Phase 8 addition

    # ── Advanced ──────────────────────────────────────────────────────────
    echart_override = fields.Text()      # JSON deep-merged into ECharts option
```

**Hierarchy:** `App → Page → Tab → Widget` (+ optional click-actions)

**Admin workflow:**
1. Posterra → Configuration → Dashboard Widgets → New
2. Select Page, optionally select Tab (leave empty = show on all tabs)
3. Choose chart_type, set col_span (width), color_palette
4. Query tab: choose SQL or ORM, write the query
5. Widget Options tab: fill type-specific fields
6. Click Actions tab: configure interactivity (Phase 8)
7. Advanced tab: optional `echart_override` JSON

---

### 5.8  `dashboard.widget.action`  ← Phase 8

Admin-configurable click-actions on widgets. One record = one interaction rule.
Shown as an inline list on the widget form under "Click Actions" tab.

```python
class DashboardWidgetAction(models.Model):
    _name = 'dashboard.widget.action'
    _description = 'Widget Click Action'
    _order = 'sequence asc, id asc'

    # ── Source (what triggers this action) ─────────────────────────────
    widget_id     = fields.Many2one('dashboard.widget', required=True, ondelete='cascade')
    click_column  = fields.Char(required=True,
        help='Column name or chart dimension that triggers the action. '
             'For tables: the SQL column name (e.g. "physician_name"). '
             'For charts: the category/series dimension (e.g. "destination", "source_type").')
    click_style   = fields.Selection([
        ('link', 'Clickable Name (renders as link)'),
        ('button', 'Row Button (Go → icon)'),
        ('slice', 'Chart Slice / Bar Click'),
    ], required=True, default='link',
        help='How the clickable element appears to the user.')

    # ── Action Type ────────────────────────────────────────────────────
    action_type   = fields.Selection([
        ('drill_filter',   'Filter Other Widgets (same page)'),
        ('navigate_page',  'Navigate to Another Page'),
        ('navigate_tab',   'Switch to Another Tab'),
    ], required=True, default='drill_filter')

    # ── drill_filter: which widgets react to the click ─────────────────
    drill_key     = fields.Char(
        help='Filter parameter name passed to target widgets. '
             'E.g. "destination" → target widget SQL gets &destination=HHA')
    target_widget_ids = fields.Many2many('dashboard.widget',
        'widget_action_target_rel', 'action_id', 'widget_id',
        string='Target Widgets',
        help='Widgets that re-render when this action fires. '
             'Leave empty → ALL other widgets on the same page react.')

    # ── navigate_page / navigate_tab: where to go ─────────────────────
    target_page_id    = fields.Many2one('dashboard.page',
        help='Destination page for navigate_page action')
    target_tab_id     = fields.Many2one('dashboard.page.tab',
        help='Destination tab for navigate_tab action')
    target_filter_key = fields.Char(
        help='Query param on destination page that receives the clicked value. '
             'E.g. "physician_name" → destination URL gets ?physician_name=Dr.Smith')

    # ── General ────────────────────────────────────────────────────────
    sequence  = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
```

**Example configurations:**

| Source Widget | click_column | click_style | action_type | drill_key / target | Effect |
|---------------|-------------|-------------|-------------|-------------------|--------|
| Actual Discharges (table) | destination | link | drill_filter | drill_key=destination, targets=KPIs + Intended Discharges | Click "HHA" → KPIs + other table update |
| HHA Admits By Source (donut) | source_type | slice | drill_filter | drill_key=admit_source, targets=KPI cards | Click "IP" slice → KPIs recalculate for IP |
| ACO REACH (table) | aco_name | link | navigate_page | target_page=ACO, target_filter_key=aco_name | Click ACO name → go to ACO page |
| Physician Table | physician_name | link | navigate_page | target_page=Physicians, target_filter_key=physician_name | Click Dr. Smith → Physicians page filtered |
| Hospital Table | hospital_name | button | navigate_page | target_page=Hospitals, target_filter_key=hospital_name | Click Go → → Hospitals page filtered |

**Admin view:** Inline tree on widget form, "Click Actions" tab:
```xml
<page string="Click Actions">
    <field name="action_ids">
        <tree editable="bottom">
            <field name="click_column"/>
            <field name="click_style"/>
            <field name="action_type"/>
            <field name="drill_key" attrs="{'invisible': [('action_type','!=','drill_filter')]}"/>
            <field name="target_widget_ids" widget="many2many_tags"
                   attrs="{'invisible': [('action_type','!=','drill_filter')]}"/>
            <field name="target_page_id"
                   attrs="{'invisible': [('action_type','not in',['navigate_page'])]}"/>
            <field name="target_tab_id"
                   attrs="{'invisible': [('action_type','!=','navigate_tab')]}"/>
            <field name="target_filter_key"
                   attrs="{'invisible': [('action_type','==','drill_filter')]}"/>
            <field name="sequence"/>
            <field name="is_active"/>
        </tree>
    </field>
</page>
```

**How React consumes this:** The page config JSON includes each widget's actions:
```json
{
  "widget_id": 42,
  "name": "Actual Discharges",
  "chart_type": "table",
  "actions": [
    {
      "click_column": "destination",
      "click_style": "link",
      "action_type": "drill_filter",
      "drill_key": "destination",
      "target_widget_ids": [43, 44, 45, 46, 47, 48]
    }
  ]
}
```

React reads `actions`, attaches click handlers to the relevant column/slice, and
dispatches state changes or navigations accordingly.

---

### 5.9  SQL Safety Rules (`_execute_sql`)

1. Strip leading SQL comments (`--` lines and `/* */` blocks)
2. Validate first keyword is `SELECT` or `WITH`
3. Block DML/DDL: `INSERT UPDATE DELETE DROP TRUNCATE ALTER CREATE GRANT REVOKE COPY EXECUTE`
4. Execute via `env.cr.execute(sql, params)` — psycopg2 named params, SQL-injection-safe
5. `params` dict = all active filter `field_name` values + geo context + `hha_name` + `hha_id`
6. **Phase 8 addition:** drill filter params are merged into the params dict, allowing widget SQL to include `WHERE (%(destination)s = '' OR destination = %(destination)s)` guards

---

### 5.10  Color Palettes (`_PALETTES`)

```python
_PALETTES = {
    'healthcare': ['#0d9488','#14b8a6','#2dd4bf','#6ee7b7','#34d399','#059669'],
    'ocean':      ['#1d4ed8','#3b82f6','#60a5fa','#93c5fd','#0ea5e9','#38bdf8'],
    'warm':       ['#ea580c','#f97316','#fb923c','#fbbf24','#f59e0b','#d97706'],
    'mono':       ['#374151','#6b7280','#9ca3af','#d1d5db','#e5e7eb','#f3f4f6'],
}
```
`default` → no `color` key injected (ECharts built-in)
`custom` → no override; `echart_override` JSON takes full control

---

### 5.11  Status KPI Map (`_STATUS_MAP`)

| SQL `status_column` value | Icon class | CSS modifier |
|--------------------------|-----------|-------------|
| `up` / `disciplined` / `growing` | `fa-arrow-up` | `status-up` (green) |
| `down` / `retreated` | `fa-arrow-down` | `status-down` (red) |
| `neutral` / `stable` | `fa-minus` | `status-neutral` (grey) |
| `warning` | `fa-exclamation-triangle` | `status-warning` (amber) |

---

### 5.12  Narrative Template Injection (`_build_narrative`)

Three-layer variable merge for `insight_panel`:

```python
# Layer 1: all SQL result columns (classification, metric1, metric2, …)
template_vars = dict(sql_row)
# Layer 2: all active page filter values keyed by field_name
template_vars.update(portal_ctx.get('filter_values_by_name', {}))
# Layer 3: HHA context
template_vars['hha_name']   = hha.name if hha else ''
template_vars['hha_state']  = portal_ctx.get('ctx_state', '')
template_vars['hha_county'] = portal_ctx.get('ctx_county', '')
return self.narrative_template % template_vars
```

Example template:
```
%(hha_name)s in %(hha_state)s decreased their therapy mix after PDGM.
This "%(classification)s" trajectory indicates a shift toward nursing-heavy models.
```

If the portal user selects "BMR HOME HEALTH LLC" + State "TX", renders as:
```
BMR HOME HEALTH LLC in TX decreased their therapy mix after PDGM.
This "Retreated" trajectory indicates a shift toward nursing-heavy models.
```

---

### 5.13  Battle Card Logic (`_compute_battle_rows`)

For each SQL row: compare `you_column` vs `them_column` using `win_threshold`:
- `higher`: `you > them` → WIN, equal → TIE, `you < them` → LOSE
- `lower`:  `you < them` → WIN, equal → TIE, `you > them` → LOSE

Returns `[{label, you, them, result, advantage}]` for template rendering.

---

## 6. WIDGET SWITCHING — THE COMPLETE GUIDE

### Core rule: always edit in-place, never delete-recreate

When you want a widget to show something different or look different,
**edit the existing record**. Change `chart_type`, `query_sql`, or any field in-place.
Only delete+recreate if you want the widget on a completely different page.

### Which fields each chart_type uses

| `chart_type` | Key fields |
|-------------|-----------|
| `bar` / `line` | `query_sql`, `x_column`, `y_columns`, optional `series_column` |
| `pie` / `donut` | `query_sql`, `x_column` (labels), `y_columns` (values) |
| `gauge` | `query_sql`, `x_column` (single numeric), `gauge_min`, `gauge_max`, `gauge_warn_threshold`, `gauge_good_threshold`, `gauge_color_mode` |
| `gauge_kpi` | same as gauge + `gauge_sub_kpi_columns`, `gauge_sub_kpi_labels`, `gauge_sub_label_columns`, `gauge_alert_column` |
| `radar` | `query_sql`, `x_column` (categories), `y_columns` (values) |
| `scatter` | `query_sql`, `x_column`, `y_columns` |
| `heatmap` | `query_sql`, `x_column`, `y_columns` (value) |
| `kpi` | `query_sql`, `x_column` (value), `kpi_format`, `kpi_prefix`, `kpi_suffix` |
| `status_kpi` | same as kpi + `status_column` |
| `table` | `query_sql` (all columns shown as-is) |
| `battle_card` | `query_sql`, `label_column`, `you_column`, `them_column`, `win_threshold`, `competitor_name` |
| `insight_panel` | `query_sql`, `metric1/2/3_label`, `narrative_template` |

### Scenario A — Switching within chart family (simplest)

Example: `bar` → `donut`

1. Edit the widget record
2. Change `chart_type` to `donut`
3. `x_column` becomes the label column, `y_columns` the value column
4. SQL does not change

### Scenario B — Switching to a different widget family

Example: `bar` → `kpi`

1. Change `chart_type` to `kpi`
2. Update `x_column` to the column containing the single numeric value
3. Optionally set `kpi_format`, `kpi_prefix`, `kpi_suffix`
4. SQL may need updating — KPI needs a single-row result

### Scenario C — Switching to battle_card or insight_panel

1. Change `chart_type`
2. Fill the type-specific fields (label/you/them columns, or metric labels + narrative)
3. Update SQL to return required columns

### Two widgets side-by-side

```
Page: Overview | Tab: Command Center
  Widget 1 (sequence=10, col_span=6): gauge — Timely Access
  Widget 2 (sequence=20, col_span=6): kpi   — Total Admits
```

Switching Widget 1 from gauge to bar chart:
- Edit Widget 1 only, change `chart_type` to `bar`, update `query_sql`, `x_column`, `y_columns`
- Widget 2 is completely unaffected

**One widget record = one slot. Edit to change the slot. Set `is_active=False` to hide it.**

---

## 7. WIDGET CONFIG REFERENCE

### `echart_override` field

Optional JSON deep-merged **on top of** the generated ECharts option. Use to tweak titles,
axis labels, colors, and any ECharts property without changing the model.

```json
{
  "title": {"text": "Timely Access Rate", "subtext": "vs National Avg"},
  "yAxis": {"name": "Count"},
  "color": ["#dc2626", "#16a34a"]
}
```

If `color` is set in `echart_override` it overrides the `color_palette` selection.

---

### `narrative_template` variable reference

Available `%(key)s` placeholders inside an `insight_panel` narrative:

| Variable | Source |
|----------|--------|
| `%(hha_name)s` | Display name of the HHA selected in the portal HHA picker |
| `%(hha_state)s` | Current State filter value |
| `%(hha_county)s` | Current County filter value |
| `%(classification)s` | SQL result column named `classification` |
| `%(metric1)s` | SQL result column named `metric1` |
| `%(metric2)s` | SQL result column named `metric2` |
| `%(metric3)s` | SQL result column named `metric3` |
| `%(field_name)s` | Any active page filter with `field_name = field_name` |
| any SQL column | Any column returned by the widget's `query_sql` |

---

### `battle_card` field reference

| Field | Purpose |
|-------|---------|
| `label_column` | SQL column for metric row label (e.g. `metric_name`) |
| `you_column` | SQL column for YOUR value (e.g. `you_val`) |
| `them_column` | SQL column for THEIR value (e.g. `them_val`) |
| `competitor_name` | Label for the "Them" header (e.g. `UNITEDHEALTH`) |
| `win_threshold` | `higher` = higher you wins; `lower` = lower you wins |

SQL must return one row per metric (multiple rows = multiple battle rows in the card).

---

### `status_kpi` field reference

| Field | Purpose |
|-------|---------|
| `x_column` | SQL column for the numeric KPI value |
| `status_column` | SQL column returning: `up`, `down`, `retreated`, `neutral`, `stable`, `warning`, `disciplined`, `growing` |
| `kpi_format` | `number`, `currency`, `percent`, `decimal` |
| `kpi_prefix` / `kpi_suffix` | Optional prefix (`$`) or suffix (`%`) |

---

## 8. SQL-FIRST APPROACH — QUERY REFERENCE

Widgets execute SQL **live** against the PostgreSQL database — no CSV upload needed.
The controller builds a `params` dict and passes it to `env.cr.execute(sql, params)`.

### Available `%(key)s` SQL parameters

| Parameter | Value |
|-----------|-------|
| `%(hha_state)s` | Current `ctx_state` filter value (e.g. `'TX'`) |
| `%(hha_county)s` | Current `ctx_county` filter value |
| `%(hha_city)s` | Current locations filter value |
| `%(hha_name)s` | Display name of selected HHA provider |
| `%(hha_id)s` | Database ID of selected HHA provider (string) |
| `%(field_name)s` | Any active page filter where `field_name` = the key |
| `%(drill_key)s` | Any active drill filter from click-actions (Phase 8) |

All values are strings. Cast in SQL as needed: `%(hha_id)s::int`

**Drill filter pattern in SQL:** When a widget is a target of a drill_filter action,
its SQL should include a guard clause:
```sql
WHERE (%(destination)s = '' OR destination = %(destination)s)
```
When no drill is active, `%(destination)s` is empty string → no filter applied.
When drill is active (user clicked "HHA"), `%(destination)s = 'HHA'` → rows filtered.

---

### Example SQL per chart type

**bar** — state distribution:
```sql
SELECT hha_state AS state, COUNT(*) AS providers
FROM hha_provider
WHERE (%(hha_state)s = '' OR hha_state = %(hha_state)s)
GROUP BY hha_state ORDER BY providers DESC LIMIT 15
```
`x_column = state`, `y_columns = providers`

**gauge** — single metric:
```sql
SELECT ROUND(AVG(timely_access_pct)::numeric, 1) AS score
FROM hha_provider
WHERE (%(hha_state)s = '' OR hha_state = %(hha_state)s)
```
`x_column = score`, `chart_height = 220`

**kpi** — single number:
```sql
SELECT COUNT(*) AS total FROM hha_provider
WHERE (%(hha_state)s = '' OR hha_state = %(hha_state)s)
```
`x_column = total`, `kpi_format = number`

**status_kpi** — value + status flag:
```sql
SELECT ROUND(AVG(therapy_pct)::numeric,1) AS pct,
       CASE WHEN AVG(therapy_pct) > 35 THEN 'up' ELSE 'retreated' END AS status
FROM hha_provider WHERE hha_state = %(hha_state)s
```
`x_column = pct`, `status_column = status`

**battle_card** — you vs competitor:
```sql
SELECT 'Timely Access' AS metric, 47.2 AS you_val, 61.8 AS them_val
UNION ALL
SELECT 'ADC', 52, 88
```
`label_column = metric`, `you_column = you_val`, `them_column = them_val`

**insight_panel** — narrative-driven:
```sql
SELECT 'Retreated' AS classification,
       38.5 AS metric1, 22.1 AS metric2, -16.4 AS metric3
FROM hha_provider WHERE hha_id = %(hha_id)s::int LIMIT 1
```
`narrative_template`:
```
%(hha_name)s in %(hha_state)s decreased their therapy mix after PDGM.
This "%(classification)s" trajectory may indicate a shift toward nursing-heavy models.
```

---

## 9. BUILD PHASES — IN ORDER

### PHASE 0 — DB-Driven Pages, Tabs, and Filters  ✅ COMPLETE (~8 hours)

**New files:** `models/dashboard_page.py`, `models/dashboard_page_filter.py`,
`views/page_views.xml`, `data/pages_data.xml`, `data/filters_data.xml`

**Existing files touched:** `controllers/portal.py` (replace SIDEBAR_STRUCTURE + hardcoded filter bar),
`views/dashboard_templates.xml` (sidebar loop + filter bar loop),
`__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`

**What it enables:** Admin can rename/hide pages, add tabs, change filter labels,
remove filters from specific pages — all from the backend, no code.

**Milestone:** Rename "Admits" to "Episodes" in backend → sidebar updates. Set State
filter `is_active=False` on Overview → filter bar shows 4 items not 5.

---

### PHASE 1 — Widget System  ✅ COMPLETE (~6 hours)

**New files:** `models/dashboard_widget.py`, `views/widget_views.xml`

**Existing files touched:** `models/__init__.py`, `models/dashboard_page.py` (widget_ids O2M),
`views/page_views.xml` (Widgets tab), `security/dashboard_access.xml` (ACLs),
`controllers/portal.py` (widget loading + sql_params), `views/dashboard_templates.xml`
(widget grid + ECharts init JS), `static/src/css/posterra.css` (widget card CSS),
`__manifest__.py`

**What it enables:** Admin creates `dashboard.widget` records in backend.
Portal renders all 14 chart types live using Apache ECharts 5.
Narrative templates inject active filter values dynamically.

---

### MID-PHASE ADDITIONS (built between Phase 1 and Phase 4)

The following were built outside the phase plan in response to UX needs.
They are fully complete and tested.

1. **`gauge_kpi` widget type** — colored arc gauge + sub-KPI cards + optional alert text
   Files: `dashboard_widget.py`, `widget_views.xml`, `dashboard_templates.xml`, `posterra.css`

2. **`dashboard.page.section`** — DB-driven sections above the tab bar on any page
   Files: `models/dashboard_page_section.py`, `views/section_views.xml`,
   `data/sections_data.xml`, `controllers/portal.py`,
   `security/ir.model.access.csv`, `dashboard_templates.xml`, `__manifest__.py`

3. **`dashboard.nav.section`** — DB-driven sidebar group labels
   Files: `models/dashboard_page.py`, `views/nav_section_views.xml`,
   `data/nav_sections_data.xml`, `data/pages_data.xml`,
   `security/ir.model.access.csv`, `controllers/portal.py`,
   `dashboard_templates.xml`, `__manifest__.py`

4. **Smart `default_get`** on all sequence-bearing models — new records always
   append to the end (`max(existing.sequence) + 10`) instead of landing at position 10.

5. **Scope Group system** (`hha.scope.group`) — admin-configurable column+value matching
   to resolve HHA providers for groups of users. Replaces email domain matching.
   Files: `models/hha_scope_group.py`, `models/res_partner.py`, `models/hha_provider.py`,
   `controllers/portal.py`, `controllers/main.py`, `views/hha_scope_group_views.xml`,
   `views/res_partner_views.xml`, `views/res_config_settings_views.xml`,
   `views/dashboard_templates.xml`, `views/menuitems.xml`,
   `wizard/create_portal_user.py`, `wizard/create_portal_user_views.xml`,
   `security/ir.model.access.csv`, `security/posterra_security.xml`, `__manifest__.py`

6. **HHA selector repositioned** — moved from standalone top-level bar into
   the Context Filters bar as the first item (before State/County/City).
   Only shown for non-MSSP portal users (`t-if="portal_type != 'mssp'"`).

7. **Email domain matching removed** — all access is now admin-configured via
   direct HHA assignment or scope group. No fallback.

---

### PHASE 4 — White-Label Login + Strip Odoo Chrome (~4 hours)

**New files:** `views/login_templates.xml`, `views/error_templates.xml`

**Existing files touched:** `views/dashboard_templates.xml` (replace portal layout inheritance),
`controllers/portal.py` (custom login route), `static/src/css/posterra.css` (login page styles)

**What it enables:** Users see a fully branded login page per app. No Odoo header,
footer, or branding anywhere on the portal.

**Key implementation details:**
- Create a minimal base layout template that does NOT inherit from `website.layout`
- Custom login controller at `/my/<app_key>/login` rendering a brand-new QWeb template
- Login template pulls branding from future `saas.app` model (hardcode Posterra for now)
- Override 404/500 error page templates to match app branding
- Remove all references to Odoo in HTML source, meta tags, CSS class names
- Custom session cookie name (optional, for extra de-branding)

**Milestone:** See Phase 4 checklist above.

---

### PHASE 5 — saas.app Model + Multi-App URL Routing (~4 hours)

**New files:** `models/saas_app.py`, `views/saas_app_views.xml`

**Existing files touched:** `models/dashboard_page.py` (add `app_id` field),
`views/page_views.xml` (add `app_id` to form), `controllers/portal.py` (URL routing),
`controllers/main.py` (login redirect per app), `views/login_templates.xml` (dynamic branding),
`data/pages_data.xml` (add `app_id` refs), `security/ir.model.access.csv`,
`__init__.py`, `__manifest__.py`

**What it enables:** Multiple apps on the same Odoo instance. Each app has its own
URL prefix, branding, login page, sidebar, and widget configuration.

**Milestone:** See Phase 5 checklist above.

---

### PHASE 6 — JSON API Endpoints (~6 hours)

**New files:** `controllers/widget_api.py`, `controllers/auth_api.py`

**Existing files touched:** `controllers/__init__.py`, `models/dashboard_widget.py`
(extract `get_portal_data` into reusable method), `__manifest__.py`

**What it enables:** React (or any HTTP client) can fetch page config and widget data
via JSON API. This is the bridge between the Odoo backend and the React frontend.

**Endpoints:**

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/v1/auth/login` | POST | JWT access token + refresh token |
| `/api/v1/auth/refresh` | POST | New access token |
| `/api/v1/page/<page_key>/config` | GET | Page structure: tabs, filters (with options), widget metadata (including click-actions), page sections |
| `/api/v1/widget/<int:widget_id>/data` | GET | Single widget data (ECharts option / KPI dict / table rows / etc.) with filter + drill params |
| `/api/v1/filters/cascade` | GET | Dynamic filter options (counties for a state, locations for a county) |

**Auth flow:**
- Login endpoint validates credentials against `res.users`
- Checks user belongs to the correct `saas.app` (via scope group or direct assignment)
- Returns JWT with `user_id`, `app_id`, `exp`
- All API endpoints validate JWT via a decorator
- Initial page load uses Odoo session (QWeb renders the shell); React uses JWT for subsequent API calls

**Key principle:** The Python computation logic (SQL execution, ECharts option building,
narrative templating) does NOT change. The API endpoints call the same `get_portal_data()`
methods. Only the transport changes: Python dict → JSON response instead of Python dict → QWeb context.

**Milestone:** See Phase 6 checklist above.

---

### PHASE 7 — React Widget Grid + Filter Bar (~8 hours)

**New files:** `static/src/react/` (entire React app)

**Existing files touched:** `views/dashboard_templates.xml` (replace widget grid + filter bar
HTML with `<div id="app-root">`), `__manifest__.py` (include React build output in assets)

**What it enables:** Filter changes, tab switches, and widget rendering happen without
page reloads. React manages all interactivity within the content area.

**Key implementation details:**
- React app built with Vite, output to `static/src/react/dist/`
- QWeb template includes the built JS/CSS bundle
- Initial data embedded as `data-page-config` and `data-initial-widgets` JSON attributes
- React reads these on mount → zero API calls for first render → no loading flash
- FilterBar component: all filter types, cascading dropdowns, Apply button
- TabBar component: tab switching updates widget grid
- WidgetGrid component: responsive Bootstrap grid, renders widget components by type
- Each widget type is a React component (BarChart, DonutChart, KPICard, DataTable, etc.)
- ECharts used via direct refs (not `echarts-for-react` to avoid extra dependency)
- Filter state managed via React Context (FilterContext)
- URL sync: filter changes update URL query params (shareable deep links)
- Browser back/forward respects filter state via popstate listener

**QWeb shell after Phase 7:**
```xml
<div class="pv-portal-container">
    <!-- Sidebar: still QWeb -->
    <div class="pv-sidebar">...</div>

    <!-- Content: React takes over -->
    <div class="pv-content-area">
        <div class="pv-page-header">
            <h2><t t-esc="current_page.name"/></h2>
        </div>
        <div id="app-root"
             t-att-data-page-config="page_config_json"
             t-att-data-initial-widgets="initial_widget_data_json"
             t-att-data-api-base="'/api/v1'"
             t-att-data-csrf-token="request.csrf_token()"/>
    </div>
</div>
```

**Milestone:** See Phase 7 checklist above.

---

### PHASE 8 — Widget Click-Actions (~6 hours)

**New files:** `models/dashboard_widget_action.py`, `views/widget_action_views.xml`

**Existing files touched:** `models/dashboard_widget.py` (add `action_ids` O2M),
`models/__init__.py`, `views/widget_views.xml` (Click Actions tab),
`controllers/widget_api.py` (include actions in page config + accept drill params),
`security/ir.model.access.csv`, `__manifest__.py`

**React files touched:** All widget components (add click handlers), new DrillContext
and DrillChip components, WidgetGrid (parallel refetch on drill change)

**What it enables:** Admin configures click-actions from the Odoo backend.
Portal users click chart slices, table rows, or buttons → widgets update or
pages navigate. All without any code changes.

**React state management for drill filters:**
```
FilterContext (context filters: State, County, Year, Payer)
    ↓
DrillContext (drill filters from click-actions: {destination: 'HHA', admit_source: 'IP'})
    ↓
Widget components read both contexts
    ↓
API calls include both: ?state=Arkansas&year=2025&destination=HHA&admit_source=IP
    ↓
Clear drill → widgets refetch without drill params
    ↓
Change context filter → drill auto-clears (one source of truth)
```

**Milestone:** See Phase 8 checklist above.

---

### PHASE 2 — Seed Widgets + Validate All Types (~2 hours)

**Files touched:** seed data XML (new file) or manual backend creation

**What it enables:** All 14 chart types verified working end-to-end against
the React rendering pipeline. Color palettes confirmed. Filter-driven
narratives tested.

**Milestone:** See Phase 2 checklist above.

---

### PHASE 3 — Performance & Polish (~3 hours)

**Files touched:** `controllers/widget_api.py`, `models/dashboard_widget.py`

**What it enables:** Better error display for bad SQL, faster API responses,
optional per-widget caching.

**Key improvements:**
- Catch SQL exceptions per-widget, return `{'error': str(e)}` instead of 500
- React shows error card for widgets with `data.error`
- SQL timeout: set `SET LOCAL statement_timeout = '5s'` before executing
- Log slow widgets: compare time before/after `_execute_sql()`

**Milestone:** See Phase 3 checklist above.

---

## 10. SECURITY

**ACL pattern (one portal read-only row + one admin full-CRUD row per model):**
```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_page_portal,page portal,model_dashboard_page,posterra_portal.group_posterra_user,1,0,0,0
access_page_admin,page admin,model_dashboard_page,posterra_portal.group_posterra_admin,1,1,1,1
access_tab_portal,tab portal,model_dashboard_page_tab,posterra_portal.group_posterra_user,1,0,0,0
access_tab_admin,tab admin,model_dashboard_page_tab,posterra_portal.group_posterra_admin,1,1,1,1
access_filter_portal,filter portal,model_dashboard_page_filter,posterra_portal.group_posterra_user,1,0,0,0
access_filter_admin,filter admin,model_dashboard_page_filter,posterra_portal.group_posterra_admin,1,1,1,1
access_widget_portal,widget portal,model_dashboard_widget,posterra_portal.group_posterra_user,1,0,0,0
access_widget_admin,widget admin,model_dashboard_widget,posterra_portal.group_posterra_admin,1,1,1,1
access_widget_action_portal,widget action portal,model_dashboard_widget_action,posterra_portal.group_posterra_user,1,0,0,0
access_widget_action_admin,widget action admin,model_dashboard_widget_action,posterra_portal.group_posterra_admin,1,1,1,1
access_saas_app_portal,saas app portal,model_saas_app,posterra_portal.group_posterra_user,1,0,0,0
access_saas_app_admin,saas app admin,model_saas_app,posterra_portal.group_posterra_admin,1,1,1,1
access_hha_scope_group_portal,hha.scope.group portal,model_hha_scope_group,posterra_portal.group_posterra_user,1,0,0,0
access_hha_scope_group_admin,hha.scope.group admin,model_hha_scope_group,posterra_portal.group_posterra_admin,1,1,1,1
```

Portal users access all models via `.sudo()` — ACL rows are belt-and-suspenders for
direct ORM access. The SQL executed by `dashboard.widget` runs under the `env.cr`
cursor, not filtered by record rules, so HHA data isolation must be enforced in
the SQL `WHERE` clause (e.g. `WHERE hha_id = %(hha_id)s::int`).

**Record rules for `hha.scope.group`** (`security/posterra_security.xml`):
- Portal users: unrestricted read-only access (same pattern as `hha.provider`)
- Admin: full CRUD

**JWT API security:**
- All `/api/v1/` endpoints require a valid JWT token in the `Authorization: Bearer <token>` header
- Token contains `user_id`, `app_id`, `exp` (expiration)
- API middleware validates token, resolves user, checks app access
- Invalid/expired tokens return 401 Unauthorized
- Refresh tokens have longer expiry and are stored server-side for revocation

---

## 11. COMMON PITFALLS

| Pitfall | Fix |
|---------|-----|
| `%(key)s` in XML `placeholder` attribute causes upgrade error | Odoo's `convert.py` interprets `%(...)s` as External ID references — use `{key}` notation in placeholder text instead |
| ECharts not defined when JS runs | In React: import echarts directly. In QWeb shell (if any remain): add `if (typeof echarts === 'undefined') return;` check |
| Chart renders at zero height | Set explicit `height` via `style` attribute on the chart div. In React: pass `style={{height: widget.chart_height}}` |
| `Decimal`/`datetime` JSON serialisation error | Handled in `get_portal_data()` via `OdooJSONEncoder` — ensure it's used wherever `json.dumps` is called, including API endpoints |
| `t-out` XSS risk | Only use `t-out` for pre-serialised server-side JSON (never for user-supplied strings) |
| Two widgets share the same DOM ID | Always use `w.id` in the element ID: `'pv-widget-' + str(w.id)` |
| Tab dropdown in widget form shows all pages' tabs | `domain="[('page_id','=',page_id)]"` must be on the `tab_id` field |
| Widget appears on wrong tab | Check `tab_id` — leave it empty to show on ALL tabs; set it to restrict to one |
| Seed data overwritten on upgrade | Wrap `<data>` with `noupdate="1"` |
| Filter bar shows on pages that don't want it | Set all that page's `dashboard.page.filter` records `is_active=False` |
| SQL runs on every page load with no HHA filter | Always include a `WHERE hha_id = %(hha_id)s::int` guard in per-HHA queries |
| `<select>` tags in inline JS break Odoo XML parser | Use `lxml`-safe alternatives — avoid raw HTML tags inside `<script>` blocks in QWeb XML |
| New records always appear at the **top** of a sequence list | Override `default_get` to compute `max(existing.sequence) + 10`; scope to `default_page_id` context for child models (tabs, page sections) |
| `dashboard_nav_section` table not found in migration SQL | Run `odoo-bin -u posterra_portal` first — the table is created during upgrade; the migration SQL must run after, not before |
| Gauge shows 0% / overlapping title label inside dial | Ensure `x_column` is set to the value column name; add `'title': {'show': False}` and `'detail': {'offsetCenter': [0, '60%']}` to the ECharts gauge option |
| `page.section` field reference errors after mid-phase migration | The `section` Selection field was replaced by `nav_section_id` Many2one — update any code/views/seed data that still references `page.section` |
| `'res.groups' has no attribute 'users'` | Odoo 19 removed `users` from `res.groups`. Use `user.has_group('module.xml_id')` instead of `group in user.groups_id` or `user in group.users` |
| `'res.users' has no attribute 'groups_id'` | Odoo 19 removed `groups_id` from `res.users`. Use `user.has_group('module.xml_id')` — the only reliable group membership check |
| Scope Group `provider_ids` not saved (count=0 after save) | `provider_ids` has `readonly="auto_resolve"` — Odoo doesn't send readonly values on save. Fix: add `force_save="1"` on the field in the view + `create`/`write` overrides that call `_resolve_providers()` server-side |
| Module upgrade fails from Odoo UI with UndefinedColumn | Upgrade via CLI: `"C:\Program Files\Odoo 19.0.20251113\python\python.exe" "C:\Program Files\Odoo 19.0.20251113\server\odoo-bin" -c "C:\Program Files\Odoo 19.0.20251113\server\odoo.conf" -d odoo_db -u posterra_portal --stop-after-init` |
| CLI module upgrade fails with `No module named 'babel'` | Use Odoo's **bundled** Python, not the system Python — path: `C:\Program Files\Odoo 19.0.20251113\python\python.exe` |
| React build not loading in Odoo portal | Ensure Vite `base` config points to `/posterra_portal/static/src/react/dist/`. Add built files to `__manifest__.py` assets |
| CORS errors on API calls from React | API endpoints should use the same origin (Odoo serves both shell and API). If testing locally with separate Vite dev server, add CORS headers to Odoo API controller |
| JWT token expired mid-session | React API client should intercept 401 responses, call `/api/v1/auth/refresh`, retry the original request. If refresh also fails, redirect to login |
| Drill filter params not reaching widget SQL | Ensure `widget_api.py` merges drill params into `sql_params` dict before calling `get_portal_data()`. Widget SQL must have guard clauses: `WHERE (%(drill_key)s = '' OR column = %(drill_key)s)` |

---

## 12. ODOO 19 API NOTES

Key Odoo 19 API differences from Odoo 16/17 encountered during development:

| Topic | Odoo 19 Way | Old Way (deprecated/removed) |
|-------|-------------|------------------------------|
| Group membership check | `user.has_group('module.xml_id')` | `group.users`, `user.groups_id` — both removed |
| `read_group` | `Model._read_group()` | `Model.read_group()` — deprecated |
| `_read_group` return format | Returns tuples; Many2one fields return recordsets | Many2one returned `(id, name)` tuples |
| Route type for JSON-RPC | `type='jsonrpc'` | `type='json'` — deprecated |
| Inline JSON in QWeb | Use `data-*` attributes on HTML elements | `<script type="application/json">` — does NOT work in Odoo QWeb |

---

## 13. HOW TO START EACH CODING SESSION

See **★ IMPLEMENTATION ORDER** at the top of this file for the exact
copy-paste prompt for each phase and the milestone checklist to complete
before moving on.

The universal pattern is always:

> "Read SKILL.md, then build Phase N — [task description]."

Never skip a phase. Never start a phase before the previous milestone checklist is fully ticked.

---

## 14. WHAT PHASE 0/1 BUILT vs WHAT CHANGES IN LATER PHASES

This section clarifies what from Phase 0 and Phase 1 stays, what gets modified,
and what gets replaced as Phases 4-8 are built.

### Phase 0/1 models — STAY AS-IS (with minor additions)
- `dashboard.page` → add `app_id` Many2one in Phase 5 (one field)
- `dashboard.page.tab` → no changes
- `dashboard.page.filter` → no changes
- `dashboard.nav.section` → no changes
- `dashboard.page.section` → no changes
- `dashboard.widget` → add `action_ids` One2many in Phase 8 (one field)
- `hha.scope.group` → no changes

### Phase 0/1 admin views — STAY AS-IS (with minor additions)
- `page_views.xml` → add `app_id` field to form in Phase 5
- `widget_views.xml` → add "Click Actions" tab in Phase 8
- All other admin views → no changes

### Phase 0/1 Python logic — REUSED (not rewritten)
- `_execute_sql()` → same function, called from API endpoint instead of controller
- `get_portal_data()` → same function, returns dict consumed by API instead of QWeb
- `_build_narrative()` → no changes
- `_compute_battle_rows()` → no changes
- Color palette logic → no changes
- SQL parameter building → reused, with drill params merged in Phase 8

### Phase 0/1 QWeb templates — TRIMMED (not deleted)
- Sidebar rendering → STAYS in QWeb (sidebar is part of the shell)
- Page header → STAYS in QWeb
- Filter bar rendering → REPLACED by React component in Phase 7
- Tab bar rendering → REPLACED by React component in Phase 7
- Widget grid rendering → REPLACED by React component in Phase 7
- ECharts init JS → REPLACED by React widget components in Phase 7

### Phase 0/1 controller — REFACTORED
- `portal.py` main route → STAYS (serves QWeb shell + embeds JSON for React)
- Widget data loading → EXTRACTED into `widget_api.py` as JSON endpoint
- Filter cascade logic → EXTRACTED into `widget_api.py` as JSON endpoint
- Login handling → MOVED to custom routes per app in Phase 4
