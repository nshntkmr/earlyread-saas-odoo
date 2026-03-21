# DASHBOARD BUILDER — COMPLETE DEVELOPMENT SKILL

## LOAD THIS FILE AT THE START OF EVERY CODING SESSION

---

## IMPLEMENTATION ORDER — READ THIS FIRST

Build these phases in strict sequence. Never start a phase until the
previous phase's milestone test passes. Each phase builds on the last.

```
PHASE WB-1  →  Schema Registry (tables, columns, JOINs)       ~6h   ✅ COMPLETE
PHASE WB-2  →  Widget Action Mixin (click presets)             ~4h   ✅ COMPLETE
PHASE WB-3  →  Query Builder Service                           ~6h   ✅ COMPLETE
PHASE WB-4  →  Builder REST API Endpoints                      ~4h   ✅ COMPLETE
PHASE WB-5  →  React Widget Builder UI (6-step wizard)         ~12h  ✅ COMPLETE
PHASE WB-6  →  Template Library + Healthcare Templates         ~6h   ✅ COMPLETE
PHASE DD-1  →  Designer API + Session-Auth Controllers         ~4h   ✅ COMPLETE
PHASE DD-2  →  Designer React App (standalone page)            ~8h   ✅ COMPLETE
PHASE DD-3  →  Decouple Builder from Portal                    ~3h   ✅ COMPLETE
PHASE DD-4  →  Widget Edit/Update + End-to-End Test            ~4h   ☐ IN PROGRESS
PHASE AZ-S  →  Track B Stubs (Azure AI provisioning)           ~2h   ⏭ SKIPPED (deferred)
```

### What each phase unlocks

| Phase | You can do this after it's done |
|-------|----------------------------------|
| **WB-1** | Admin registers database tables, discovers columns automatically, configures JOIN relationships between tables. Schema metadata is queryable from Python. |
| **WB-2** | Admin configures click behavior on widgets: filter this page, navigate to another page, show detail table, open URL. Column-level links for table widgets. |
| **WB-3** | Python service generates safe SQL from structured config: multi-table JOINs, aggregation, filtering, sorting, limiting. Drill-down queries auto-generated. |
| **WB-4** | React (or any client) can list schema sources, preview queries, create/update widgets, execute drill-downs, and use templates via REST API. |
| **WB-5** | Admin opens Widget Builder on the portal dashboard, walks through 6 steps (chart type → data source → columns → filters/actions → appearance → preview), and creates a widget without writing any SQL. |
| **WB-6** | Admin picks from pre-built healthcare templates (Executive KPI Row, Payer Mix Trend, Market Position Radar, Peer Profile Table, etc.) to create widgets instantly. |
| **DD-1** | Session-authenticated Designer API endpoints mirror the JWT builder API. Standalone designer controller serves `/dashboard/designer` page. No JWT tokens needed — uses Odoo session cookies. |
| **DD-2** | Standalone React app at `/dashboard/designer` with sidebar navigation (Widget Library, Create Widget, Templates). 6-step wizard runs inline (not modal). Modern polished UI with card-based chart picker. |
| **DD-3** | Builder UI removed from portal. Portal is customer-only (no admin controls). Widget placement happens via Odoo backend admin (Dashboard Widgets form), not from the portal. Designer creates definitions → Odoo backend places instances on pages. |
| **DD-4** | Edit/update existing widget definitions from Designer. End-to-end test: create in Designer → place via Odoo backend → view on portal. |
| **AZ-S** | File structure, models, settings, and stubs for Azure AI Foundry integration are in place. Track B can be implemented by filling in the service layer. |

### The one Claude prompt to start each phase

**Phase WB-1:**
> "Read SKILL.md, then build Phase WB-1 — Schema Registry. Create the `dashboard.schema.source`, `dashboard.schema.column`, and `dashboard.schema.relation` models. Add auto-discover functionality that reads `information_schema.columns` and populates column records. Build admin tree + form views with columns tab, relations tab, and 'Discover Columns' button. Add menu under Dashboard Builder → Configuration → Schema Sources. Create security groups and ACL rules."

**Phase WB-2:**
> "Read SKILL.md, then build Phase WB-2 — Widget Action Mixin. Create the `dashboard.widget.action.mixin` abstract model with click_action presets (none, filter_page, go_to_page, show_details, open_url) and column_link_config. In posterra_portal, inherit the mixin into `dashboard.widget`. Add an Actions tab to the widget form view with conditional field visibility based on click_action selection."

**Phase WB-3:**
> "Read SKILL.md, then build Phase WB-3 — Query Builder Service. Create `services/query_builder.py` with the `QueryBuilder` class. Implement `build_select_query()` that generates SQL from structured config (multi-table JOINs, aggregation, GROUP BY, ORDER BY, LIMIT). Implement `build_drill_query()` that auto-generates detail queries by removing aggregation and adding WHERE on clicked value. Reuse `_BLOCKED_KEYWORDS` regex for SQL validation. Add `SET TRANSACTION READ ONLY` and `statement_timeout` safety wrappers."

**Phase WB-4:**
> "Read SKILL.md, then build Phase WB-4 — Builder REST API. Create `controllers/builder_api.py` with JWT-authenticated endpoints: GET sources, GET columns, GET relations, POST preview, POST create, PUT update, POST drill, GET pages, GET templates, POST template/use. Follow the exact JWT auth pattern from posterra_portal's `widget_api.py` (import `_verify_token`, `_json_response`, `_json_error` from `auth_api.py`). Admin-only except drill endpoint."

**Phase WB-5:**
> "Read SKILL.md, then build Phase WB-5 — React Widget Builder UI. Create the 6-step modal wizard: ChartTypePicker (14 types), TableJoinBuilder (multi-table with visual JOIN display), ColumnMapper (x/y/series/sort/limit + column links), FilterActionConfig (WHERE conditions + click action presets), AppearanceConfig (palette/width/height/legend), LivePreview (real chart + generated SQL). Add DrillDownModal component. Wire EChartWidget onClick for click_action dispatch. Wire DataTable column links. Add 'Add Widget' button to WidgetGrid toolbar (admin-only)."

**Phase WB-6:**
> "Read SKILL.md, then build Phase WB-6 — Template Library. Create the `dashboard.widget.template` model with name, category, widget_configs (JSON), preview_image. In posterra_portal, create seed data XML for 6 healthcare templates matching the Ariv-style screenshots: Executive KPI Row, Payer Mix Trend, Market Position Radar, Peer Profile Table, Market Operating Profile, Insights Banner. Add 'Start from Template' option in Widget Builder Step 1."

**Phase DD-1:** ✅ COMPLETE
> "Read SKILL.md, then build Phase DD-1 — Designer API + Session-Auth Controllers. Create `controllers/designer_api.py` with session-authenticated endpoints that mirror the JWT builder API (sources, preview, library CRUD, templates). Create `controllers/designer_page.py` serving `/dashboard/designer` as a standalone QWeb page (no Odoo chrome). Use `auth='user'` + admin group check instead of JWT Bearer tokens."

**Phase DD-2:** ✅ COMPLETE
> "Read SKILL.md, then build Phase DD-2 — Designer React App. Create a standalone React app in `static/src/designer/` with Vite build. Components: App.jsx (root layout), Sidebar.jsx (navigation), WidgetLibrary.jsx (browsable grid with search/filter), WidgetBuilder.jsx (6-step inline wizard, NOT modal), TemplateGallery.jsx (browse/use templates), AppPagePicker.jsx (widget placement tree). Copy builder components from WB-5 and adapt: replace `apiFetch`→`designerFetch` (session cookies, no JWT), remove `accessToken` params. Build outputs to `dist/designer.js` + `dist/main.css`."

**Phase DD-3:** ✅ COMPLETE
> "Read SKILL.md, then build Phase DD-3 — Decouple Builder from Portal. Remove LibraryPicker, 'Add from Library' button, and all admin builder controls from posterra_portal React app. Remove `isAdmin` prop from WidgetGrid. Portal is customer-only. Widget placement is done via Odoo backend admin: admin creates `dashboard.widget` records in the backend form, selecting a definition from the library. The Designer creates definitions → Odoo backend admin places instances."

**Phase DD-4:** ☐ IN PROGRESS
> "Read SKILL.md, then build Phase DD-4 — Widget Edit/Update + End-to-End Test. Add edit capability in the Designer: click a widget definition in the library → opens the 6-step wizard pre-filled with existing config → save updates the definition. Add delete with confirmation. End-to-end test: create 'Total Admits' KPI in Designer → place on Posterra Overview page via Odoo backend → verify it renders on the portal."

**Phase AZ-S:**
> "Read SKILL.md, then build Phase AZ-S — Track B Stubs. Create `ai_conversation.py` model, `ai_service.py` stub class, `ai_api.py` stub controller, and AI settings fields in `res_config_settings.py` (ai_provider, ai_endpoint_url, ai_api_key, ai_deployment_name). Settings page shows 'AI features coming soon' when provider is 'disabled'. All AI API endpoints return 501 Not Implemented."

### Milestone checklist — tick before moving to the next phase

```
PHASE WB-1  ✅ COMPLETE
  ✅ Dashboard Builder → Configuration → Schema Sources menu exists
  ✅ Create schema source for "hha_provider" → "Discover Columns" → columns auto-populated
  ✅ Column data types auto-detected (text, integer, float, etc.)
  ✅ is_measure auto-set to True for integer/float columns
  ✅ is_dimension auto-set to True for text/date columns
  ✅ Create second source for "hha_metrics"
  ✅ Create relation: hha_provider → hha_metrics (LEFT JOIN on hha_id)
  ✅ Relation shows in form view Relations tab with correct column mapping

PHASE WB-2  ✅ COMPLETE
  ✅ dashboard.widget now has click_action, action_page_key, drill_detail_columns fields
  ✅ Widget form → Actions tab shows fields based on click_action selection
  ✅ Select click_action='go_to_page' → action_page_key and action_pass_value_as appear
  ✅ Select click_action='show_details' → drill_detail_columns appears
  ✅ Select click_action='open_url' → action_url_template appears
  ✅ column_link_config field accessible on widget form

PHASE WB-3  ✅ COMPLETE
  ✅ From Python shell: QueryBuilder(env).build_select_query({...}) returns valid SQL
  ✅ Single-table query: SELECT x, SUM(y) FROM table WHERE ... GROUP BY x
  ✅ Multi-table query: includes LEFT JOIN with correct ON clause from relation
  ✅ Query with multiple value columns: SUM(a), COUNT(b) in same SELECT
  ✅ All 5 aggregation functions work: SUM, COUNT, AVG, MIN, MAX
  ✅ build_drill_query() removes GROUP BY, adds WHERE click_column = %(click_value)s
  ✅ validate_query() blocks INSERT/UPDATE/DELETE keywords
  ✅ Missing relation between tables → returns clear error
  ✅ Custom SQL mode: validate_query() accepts valid SELECT, blocks DML/DDL

PHASE WB-4  ✅ COMPLETE
  ✅ GET /api/v1/builder/sources → returns table list with column counts
  ✅ GET /api/v1/builder/sources/1 → returns columns with types and flags
  ✅ GET /api/v1/builder/sources/1/relations → returns available JOINs
  ✅ POST /api/v1/builder/preview → returns data rows + ECharts option
  ✅ POST /api/v1/builder/create → creates dashboard.widget.definition record
  ✅ GET /api/v1/builder/library → returns definition list with instance counts
  ✅ POST /api/v1/builder/library/1/place → creates dashboard.widget on target page
  ✅ POST /api/v1/builder/reorder → updates widget sequence on a page
  ✅ POST /api/v1/builder/widget/1/drill → returns detail rows
  ✅ All endpoints require valid JWT Bearer token
  ✅ Non-admin user gets 403 on create/update/library endpoints
  ✅ Non-admin user can access drill endpoint

PHASE WB-5  ✅ COMPLETE
  ✅ Portal → "Add Widget" button visible for admin, hidden for non-admin
  ✅ Click "Add Widget" → 6-step modal opens
  ✅ Step 1: all 14 chart types displayed with icons
  ✅ Step 2: mode toggle [Visual Builder] [Custom SQL] visible
  ✅ Step 2 (Visual): select primary table → columns load. "+ Add Table" → join config appears
  ✅ Step 2 (Custom SQL): SQL textarea, filter param pills, "Test Query" button works
  ✅ Step 2 (Custom SQL): x_column, y_columns, series_column inputs visible
  ✅ Step 3 (Visual): X/Y column dropdowns populated. Multiple Y-axis columns supported
  ✅ Step 3 (Visual): each Y column has aggregation function selector (SUM/COUNT/AVG/MIN/MAX)
  ✅ Step 3 (Visual): "Display As" label input per Y column
  ☐ Step 3 (table widget): column link toggle → page + filter dropdowns appear
  ✅ Step 4 (Visual): WHERE condition builder works with filter parameters
  ✅ Step 4 (Custom SQL): WHERE builder hidden, only click action section shown
  ✅ Step 4: click action radio buttons, conditional fields show/hide correctly
  ✅ Step 5: color palette visual picker, width selector, height slider
  ✅ Step 6: live chart preview renders with real data (both modes)
  ✅ Step 6 (Visual): shows auto-generated SQL (read-only)
  ✅ Step 6 (Custom SQL): shows admin's SQL (read-only)
  ✅ Step 6: "Save to Library" → definition created in widget library
  ☐ "Add Widget from Library" on page → library picker modal opens
  ☐ Pick definition from library → widget instance created on page
  ☐ Same definition placed on two different pages → both work independently
  ☐ Drag-and-drop reorder → widget sequence updates persist
  ✅ Click bar chart with go_to_page → navigates to target page with filter
  ✅ Click chart with show_details → drill-down modal opens with detail rows
  ✅ Click linked column in table → navigates to target page with filter
  ✅ Drill-down modal: sortable columns, close button works

PHASE WB-6  ✅ COMPLETE
  ✅ dashboard.widget.template model exists with admin views
  ✅ Healthcare templates seeded: 6 templates visible in admin
  ☐ Widget Builder Step 1 → "Start from Template" shows template cards
  ✅ Select "Executive KPI Row" → creates 5 KPI widgets on target page
  ✅ Select "Peer Profile Table" → creates table widget with linkable HHA Name
  ✅ Templates have preview images in admin view

PHASE DD-1  ✅ COMPLETE
  ✅ controllers/designer_api.py exists with session-auth endpoints
  ✅ controllers/designer_page.py serves /dashboard/designer with QWeb template
  ✅ GET /dashboard/api/sources → returns schema sources (session-auth)
  ✅ GET /dashboard/api/sources/<id> → returns columns
  ✅ POST /dashboard/api/preview → returns preview data
  ✅ POST /dashboard/api/library/create → creates widget definition
  ✅ GET /dashboard/api/library → lists definitions
  ✅ GET /dashboard/api/templates → lists templates
  ✅ All endpoints use auth='user' + admin group check (no JWT)

PHASE DD-2  ✅ COMPLETE
  ✅ React app in static/src/designer/src/ with Vite build
  ✅ App.jsx with view routing (library, create, templates)
  ✅ Sidebar.jsx with navigation links
  ✅ WidgetLibrary.jsx with search, category filter, widget cards
  ✅ WidgetBuilder.jsx — 6-step inline wizard (not modal)
  ✅ TemplateGallery.jsx — browse and use templates
  ✅ All 9 builder sub-components adapted (designerFetch, no JWT)
  ✅ Vite outputs dist/designer.js + dist/main.css
  ✅ QWeb template loads CSS + JS, renders full-page designer
  ✅ Modern polished UI: card-based chart picker, underline tabs, clean spacing

PHASE DD-3  ✅ COMPLETE
  ✅ LibraryPicker removed from posterra_portal React app
  ✅ "Add from Library" button removed from WidgetGrid
  ✅ isAdmin prop removed from WidgetGrid
  ✅ Portal is customer-only — no admin builder controls
  ✅ Widget placement done via Odoo backend (dashboard.widget form)
  ✅ Architecture: Designer (definitions) → Odoo Backend (placement) → Portal (rendering)

PHASE DD-4  ☐ IN PROGRESS
  ☐ Click widget card in library → opens wizard pre-filled with existing config
  ☐ Edit wizard saves updates to existing definition (PUT, not POST)
  ☐ Delete widget definition with confirmation dialog
  ☐ End-to-end: create "Total Admits" in Designer → place via Odoo backend → renders on portal
  ☐ Preview endpoint works (Config must be a non-empty dict error fixed)

PHASE AZ-S  ⏭ SKIPPED (deferred)
  ☐ ai.conversation model exists (no data yet)
  ☐ AI settings visible in Settings → Dashboard Builder section
  ☐ ai_provider='disabled' shows "AI features coming soon" message
  ☐ POST /api/v1/ai/generate-widget → returns 501 Not Implemented
  ☐ AiService().generate_widget() → raises NotImplementedError
```

---

## 1. PROJECT CONTEXT

**Platform:** Odoo 19 Community Edition, separate module `dashboard_builder`
**What it is:** A generic, reusable dashboard widget builder module. It provides schema discovery, visual widget creation, and action configuration that any Odoo dashboard module can use.

**Relationship to `posterra_portal`:**
```
dashboard_builder (generic)         posterra_portal (healthcare-specific)
├── Schema Registry                 ├── depends: ['dashboard_builder', ...]
├── Query Builder                   ├── Inherits widget action mixin
├── Widget Action Mixin             ├── Healthcare templates (seed data)
├── Builder API (JWT)               ├── HHA scoping + scope groups
├── Designer API (session-auth)     ├── Portal rendering (React + QWeb)
├── Designer React App              ├── JWT auth (auth_api.py)
├── Widget Templates (model)        └── Customer-only portal (no admin controls)
├── AI Stubs (Track B)
└── Widget Definitions (library)
```

**Three-tier architecture:**
```
┌──────────────────────────────────────────────────────────────────────┐
│  DASHBOARD DESIGNER (/dashboard/designer)                             │
│  Admin-only standalone React app (session-auth)                       │
│  → Create/edit/delete widget definitions in the library               │
│  → Browse and use templates                                           │
│  → NO page/tab assignment here                                        │
├──────────────────────────────────────────────────────────────────────┤
│  ODOO BACKEND ADMIN (Settings → Dashboard Widgets)                    │
│  Standard Odoo tree/form views                                        │
│  → Create dashboard.widget instance on a specific page/tab            │
│  → Select definition_id from library → inherits SQL, chart config     │
│  → Admin controls: sequence, page, tab, override title                │
├──────────────────────────────────────────────────────────────────────┤
│  PORTAL (/my/posterra, /my/mssp, etc.)                                │
│  Customer-facing React app (JWT-auth)                                 │
│  → Renders widgets assigned to the page                               │
│  → NO admin controls, NO builder, NO library picker                   │
│  → Filters, drill-down, click-actions only                            │
└──────────────────────────────────────────────────────────────────────┘
```

**Core principle: Widget Library pattern.** Dashboard Builder creates reusable **widget definitions** (not tied to any page). The consuming app (Posterra) picks from the library and places instances on pages/tabs. Rendering is the consuming app's responsibility.

**Two ways to create widgets (both coexist):**
1. **Dashboard Designer** (`/dashboard/designer`) → creates `dashboard.widget.definition` (reusable in library) → admin places on page via **Odoo backend** (Dashboard Widgets form) → creates `dashboard.widget` instance
2. **Direct Odoo form** → admin creates `dashboard.widget` directly with raw SQL in Odoo backend (existing approach, unchanged)

**Widget flow:**
```
Dashboard Designer              Odoo Backend Admin              Portal
(/dashboard/designer)           (Settings → Dashboard Widgets)  (/my/posterra)
┌─────────────────┐             ┌─────────────────────┐         ┌──────────────┐
│ 6-step wizard   │             │ dashboard.widget    │         │ React renders│
│ → definition    │──library──→ │ form view           │──page──→│ widget data  │
│   (library)     │             │ → select definition │         │ from SQL     │
│                 │             │ → assign page/tab   │         │              │
│ Templates       │             │ → set sequence      │         │ Filters →    │
│ → quick-start   │             └─────────────────────┘         │ SQL params → │
└─────────────────┘                                             │ chart render │
                                                                └──────────────┘
```

**SQL Safety — Absolute Write Protection:**
Even admins CANNOT write, drop, delete, or modify any table, column, or schema. Every SQL query (whether from Visual Builder, Custom SQL, or AI) goes through multiple safety layers:
1. `_BLOCKED_KEYWORDS` regex blocks: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `GRANT`, `REVOKE`, `COPY`, `EXECUTE`
2. `SET TRANSACTION READ ONLY` — PostgreSQL enforces read-only at transaction level
3. `SET LOCAL statement_timeout = '10s'` — prevents runaway queries
4. Only `SELECT` and `WITH` (CTE) statements are allowed
5. No `;` allowed (prevents statement chaining/injection)
6. Schema registry limits which tables are queryable (admin must register tables first)

---

## 2. CRITICAL RULES

1. **This module does NOT render widgets.** It creates `dashboard.widget` records. Rendering is handled by the consuming module (posterra_portal → React + ECharts).
2. **The QueryBuilder generates SELECT-only SQL.** All DML/DDL is blocked by `_BLOCKED_KEYWORDS` regex. SQL runs with `SET TRANSACTION READ ONLY` + `statement_timeout = '10s'`.
3. **Schema context is admin-curated.** Only tables/columns explicitly registered in `dashboard.schema.source` are available. The builder cannot query arbitrary database tables.
4. **The mixin pattern for widget actions.** This module provides `dashboard.widget.action.mixin` (abstract). The consuming module inherits it into their widget model. This keeps the builder module independent of any specific widget model.
5. **No external Python dependencies.** API calls (for Track B AI) use `urllib.request`. No `pip install` needed.
6. **Designer React app is self-contained.** The designer has its own Vite build at `static/src/designer/` with `dist/designer.js` + `dist/main.css`. It does NOT share a bundle with the portal. The designer uses session-auth (`designerFetch`), the portal uses JWT-auth (`apiFetch`).
7. **Portal is customer-only.** No admin builder controls, no LibraryPicker, no "Add Widget" button on the portal. All widget management is done via the Dashboard Designer (`/dashboard/designer`) and Odoo backend admin (Dashboard Widgets form views).
8. **Two auth patterns coexist.** Designer API uses `auth='user'` (Odoo session cookies). Builder API uses `auth='none'` + JWT Bearer tokens for portal consumption. Both share the same backend models.

---

## 3. MODULE FILE STRUCTURE

```
dashboard_builder/
├── __init__.py
├── __manifest__.py
├── SKILL.md                              ← this file
├── models/
│   ├── __init__.py
│   ├── dashboard_schema.py               ← WB-1: schema source, column, relation
│   ├── dashboard_widget_definition.py    ← WB-2: widget definition (library)
│   ├── dashboard_widget_mixin.py         ← WB-2: action fields (abstract mixin)
│   ├── dashboard_widget_template.py      ← WB-6: widget template model
│   ├── ai_conversation.py               ← AZ-S: AI conversation audit (stub)
│   └── res_config_settings.py           ← AZ-S: AI settings (stub)
├── services/
│   ├── __init__.py
│   ├── query_builder.py                  ← WB-3: safe SQL generation
│   └── ai_service.py                    ← AZ-S: Azure AI stub
├── controllers/
│   ├── __init__.py
│   ├── builder_api.py                   ← WB-4: builder REST endpoints (JWT-auth)
│   ├── designer_api.py                  ← DD-1: designer REST endpoints (session-auth)
│   ├── designer_page.py                 ← DD-1: /dashboard/designer page controller
│   └── ai_api.py                        ← AZ-S: AI endpoints (stub)
├── views/
│   ├── dashboard_schema_views.xml       ← WB-1: schema source admin views
│   ├── widget_template_views.xml        ← WB-6: template admin views
│   ├── designer_templates.xml           ← DD-1: QWeb template for designer page
│   ├── res_config_settings_views.xml    ← AZ-S: AI settings page
│   └── menuitems.xml                    ← menu structure
├── security/
│   ├── builder_security.xml              ← groups: group_dashboard_builder_admin
│   └── ir.model.access.csv             ← ACL for all models
├── data/
│   └── (empty — healthcare templates live in posterra_portal)
└── static/
    └── src/
        ├── designer/                     ← DD-2: standalone React app
        │   ├── package.json
        │   ├── vite.config.js            ← output: dist/designer.js, dev port 3001
        │   ├── dist/
        │   │   ├── designer.js           ← compiled bundle
        │   │   └── main.css              ← extracted styles (Vite)
        │   ├── styles/
        │   │   └── designer.css          ← dd-* layout + wb-* builder styles
        │   └── src/
        │       ├── main.jsx              ← entry point, parses data-* attributes
        │       ├── App.jsx               ← root layout, view routing
        │       ├── api/
        │       │   ├── client.js          ← designerFetch() with session cookies
        │       │   └── endpoints.js       ← URL builders for /dashboard/api/*
        │       └── components/
        │           ├── Sidebar.jsx        ← left navigation
        │           ├── WidgetLibrary.jsx  ← browsable widget grid + search/filter
        │           ├── TemplateGallery.jsx ← browse/use templates
        │           ├── AppPagePicker.jsx  ← tree picker for placement
        │           └── builder/           ← 6-step wizard components
        │               ├── WidgetBuilder.jsx      ← wizard orchestrator (inline, not modal)
        │               ├── ChartTypePicker.jsx     ← 14 chart type cards
        │               ├── TableJoinBuilder.jsx    ← multi-table visual JOIN
        │               ├── CustomSqlEditor.jsx     ← raw SQL mode
        │               ├── ColumnMapper.jsx        ← x/y/series mapping
        │               ├── FilterActionConfig.jsx  ← WHERE + click actions
        │               ├── AppearanceConfig.jsx    ← palette/width/height
        │               ├── LivePreview.jsx         ← real chart preview
        │               └── DrillDownModal.jsx      ← drill-down detail view
        └── js/
            └── builder/                  ← WB-5: original React source (legacy)
                ├── WidgetBuilder.jsx
                ├── ChartTypePicker.jsx
                ├── TableJoinBuilder.jsx
                ├── ColumnMapper.jsx
                ├── FilterActionConfig.jsx
                ├── AppearanceConfig.jsx
                ├── LivePreview.jsx
                └── builder_endpoints.js
```

**Import order in `models/__init__.py`:**
```python
from . import dashboard_schema              # WB-1: no dependencies
from . import dashboard_widget_definition   # WB-2: depends on schema (for builder_config)
from . import dashboard_widget_mixin        # WB-2: abstract, no dependencies
from . import dashboard_widget_template     # WB-6: no dependencies
from . import ai_conversation              # AZ-S: no dependencies
from . import res_config_settings           # AZ-S: depends on base
```

---

## 4. ALL DATA MODELS

### 4.1 `dashboard.schema.source` ← WB-1

Represents a database table that the widget builder can query.

```python
class DashboardSchemaSource(models.Model):
    _name = 'dashboard.schema.source'
    _description = 'Schema Source (Database Table)'
    _order = 'name asc'

    name          = fields.Char(required=True, string='Display Name')       # "HHA Providers"
    table_name    = fields.Char(required=True, string='Table Name')         # "hha_provider"
    table_alias   = fields.Char(string='SQL Alias', size=5)                 # "p"
    description   = fields.Text(string='Description')                       # "Home Health Agency..."
    app_ids       = fields.Many2many('saas.app', string='Available in Apps')
    column_ids    = fields.One2many('dashboard.schema.column', 'source_id', string='Columns')
    relation_ids  = fields.One2many('dashboard.schema.relation', 'source_id', string='Outgoing Relations')
    is_active     = fields.Boolean(default=True)
    column_count  = fields.Integer(compute='_compute_column_count', string='# Columns')

    def action_discover_columns(self):
        """Button action: reads information_schema.columns for self.table_name,
        creates dashboard.schema.column records for each column found.
        Auto-maps data types: varchar/text→text, int/bigint→integer,
        numeric/float/double→float, date/timestamp→date, bool→boolean.
        Sets is_measure=True for integer/float, is_dimension=True for text/date.
        Skips columns that already exist (matched by column_name)."""
```

### 4.2 `dashboard.schema.column` ← WB-1

Represents a column within a schema source table.

```python
class DashboardSchemaColumn(models.Model):
    _name = 'dashboard.schema.column'
    _description = 'Schema Column'
    _order = 'source_id, column_name'

    source_id     = fields.Many2one('dashboard.schema.source', required=True, ondelete='cascade')
    column_name   = fields.Char(required=True)                  # "total_admits"
    display_name  = fields.Char(required=True)                  # "Total Admits"
    data_type     = fields.Selection([
        ('text',    'Text'),
        ('integer', 'Integer'),
        ('float',   'Float / Decimal'),
        ('date',    'Date / Timestamp'),
        ('boolean', 'Boolean'),
    ], required=True, default='text')
    is_measure    = fields.Boolean(default=False,
        help='Can be used as Y-axis value (aggregated). Auto-set for int/float.')
    is_dimension  = fields.Boolean(default=False,
        help='Can be used as X-axis / group-by. Auto-set for text/date.')
    is_filterable = fields.Boolean(default=False,
        help='Available in WHERE conditions.')
```

### 4.3 `dashboard.schema.relation` ← WB-1

Represents a JOIN relationship between two schema source tables.

```python
class DashboardSchemaRelation(models.Model):
    _name = 'dashboard.schema.relation'
    _description = 'Schema Relation (JOIN)'
    _order = 'source_id, target_source_id'

    name             = fields.Char(string='Label')              # "Provider → Metrics"
    source_id        = fields.Many2one('dashboard.schema.source',
        required=True, ondelete='cascade', string='From Table')
    target_source_id = fields.Many2one('dashboard.schema.source',
        required=True, ondelete='cascade', string='To Table')
    join_type        = fields.Selection([
        ('inner', 'INNER JOIN'),
        ('left',  'LEFT JOIN'),
        ('right', 'RIGHT JOIN'),
    ], required=True, default='left')
    source_column    = fields.Char(required=True, string='From Column')   # "hha_id"
    target_column    = fields.Char(required=True, string='To Column')     # "hha_id"

    @api.model
    def create(self, vals):
        """Auto-generate name if not provided."""
        if not vals.get('name'):
            src = self.env['dashboard.schema.source'].browse(vals.get('source_id'))
            tgt = self.env['dashboard.schema.source'].browse(vals.get('target_source_id'))
            vals['name'] = f"{src.name} → {tgt.name}"
        return super().create(vals)
```

### 4.4 `dashboard.widget.definition` ← WB-2

**The core of the Widget Library.** A reusable widget design not tied to any page.

```python
class DashboardWidgetDefinition(models.Model):
    _name = 'dashboard.widget.definition'
    _description = 'Widget Definition (Library)'
    _order = 'category, name'

    # ── Identity ──────────────────────────────────────────────
    name           = fields.Char(required=True, string='Widget Name')
    description    = fields.Text(string='Description')
    category       = fields.Selection([
        ('kpi',         'KPI Cards'),
        ('chart',       'Charts'),
        ('table',       'Tables'),
        ('comparison',  'Comparisons'),
        ('profile',     'Profiles'),
        ('insight',     'Insights'),
    ], default='chart')
    preview_image  = fields.Binary(attachment=True, string='Preview Thumbnail')
    app_ids        = fields.Many2many('saas.app', string='Available in Apps')
    is_active      = fields.Boolean(default=True)

    # ── Chart / Display ──────────────────────────────────────
    chart_type     = fields.Selection([
        ('bar', 'Bar'), ('line', 'Line'), ('pie', 'Pie'), ('donut', 'Donut'),
        ('gauge', 'Gauge'), ('radar', 'Radar'), ('kpi', 'KPI Card'),
        ('status_kpi', 'Status KPI'), ('table', 'Data Table'),
        ('scatter', 'Scatter'), ('heatmap', 'Heatmap'),
        ('battle_card', 'Battle Card'), ('insight_panel', 'Insight Panel'),
        ('gauge_kpi', 'Gauge + KPI'),
    ], required=True, default='bar')
    chart_height   = fields.Integer(default=350, string='Default Height (px)')
    color_palette  = fields.Selection([
        ('default', 'Default'), ('healthcare', 'Healthcare'),
        ('ocean', 'Ocean'), ('warm', 'Warm'), ('mono', 'Monochrome'),
        ('custom', 'Custom'),
    ], default='healthcare')
    color_custom_json = fields.Char(string='Custom Colors (JSON)')
    default_col_span  = fields.Selection([
        ('3', '25%'), ('4', '33%'), ('6', '50%'), ('8', '67%'), ('12', '100%'),
    ], default='6', string='Default Width')

    # ── Data Source ───────────────────────────────────────────
    data_mode      = fields.Selection([
        ('visual', 'Visual Builder'),
        ('custom_sql', 'Custom SQL'),
    ], default='visual', string='Data Source Mode')

    # Visual mode: structured config (stored as JSON)
    builder_config = fields.Text(string='Builder Config (JSON)',
        help='Structured config from the visual builder: '
             'tables, columns, joins, filters, group_by, order_by, limit')

    # Custom SQL mode: raw query
    query_sql      = fields.Text(string='SQL Query',
        help='SELECT only. Use %(param)s for filter values.')
    x_column       = fields.Char(string='X / Label Column')
    y_columns      = fields.Char(string='Y / Value Column(s)',
        help='Comma-separated result column names')
    series_column  = fields.Char(string='Series Column')

    # ── Generated SQL (for visual mode) ──────────────────────
    generated_sql  = fields.Text(string='Generated SQL (read-only)',
        help='Auto-generated by QueryBuilder from builder_config. '
             'Stored so the widget instance can use it directly.')

    # ── Click Actions ────────────────────────────────────────
    click_action = fields.Selection([
        ('none', 'No action'), ('filter_page', 'Filter this page'),
        ('go_to_page', 'Go to another page'), ('show_details', 'Show detail table'),
        ('open_url', 'Open URL'),
    ], default='none')
    action_page_key      = fields.Char(string='Target Page Key')
    action_tab_key       = fields.Char(string='Target Tab Key')
    action_pass_value_as = fields.Char(string='Pass Clicked Value As')
    drill_detail_columns = fields.Char(string='Detail Columns')
    action_url_template  = fields.Char(string='URL Template')
    column_link_config   = fields.Text(string='Column Links (JSON)')

    # ── KPI-specific fields (same as dashboard.widget) ───────
    kpi_format     = fields.Selection([
        ('number', 'Number'), ('currency', 'Currency'),
        ('percent', 'Percent'), ('decimal', 'Decimal'),
    ], default='number')
    kpi_prefix     = fields.Char()
    kpi_suffix     = fields.Char()

    # ── Gauge fields ─────────────────────────────────────────
    gauge_min      = fields.Float(default=0)
    gauge_max      = fields.Float(default=100)
    gauge_color_mode = fields.Selection([
        ('single', 'Single'), ('traffic_light', 'Traffic Light'),
    ], default='single')

    # ── Advanced ─────────────────────────────────────────────
    echart_override = fields.Text(string='ECharts Override (JSON)')

    # ── Tracking ─────────────────────────────────────────────
    instance_count = fields.Integer(compute='_compute_instance_count',
        string='Times Used')
    instance_ids   = fields.One2many('dashboard.widget', 'definition_id',
        string='Widget Instances')

    def get_effective_sql(self):
        """Returns the SQL to use: generated_sql for visual mode, query_sql for custom."""
        if self.data_mode == 'custom_sql':
            return self.query_sql
        return self.generated_sql

    def action_regenerate_sql(self):
        """Re-run QueryBuilder on builder_config to update generated_sql."""
        from ..services.query_builder import QueryBuilder
        qb = QueryBuilder(self.env)
        config = json.loads(self.builder_config or '{}')
        self.generated_sql = qb.build_select_query(config)
```

**Key design: Definition holds the complete widget design. When placed on a page, a `dashboard.widget` instance is created that references the definition and inherits all its fields.**

---

### 4.5 `dashboard.widget.action.mixin` ← WB-2

Abstract mixin that the consuming module inherits into their widget model.

```python
class DashboardWidgetActionMixin(models.AbstractModel):
    _name = 'dashboard.widget.action.mixin'
    _description = 'Widget Action Mixin'

    # ── Click Action Preset ──────────────────────────────────────
    click_action = fields.Selection([
        ('none',           'No action'),
        ('filter_page',    'Filter this page'),
        ('go_to_page',     'Go to another page'),
        ('show_details',   'Show detail table'),
        ('open_url',       'Open URL'),
    ], default='none', string='When Clicked')

    # For 'go_to_page': navigate to another page with filter pre-set
    action_page_key = fields.Char(string='Target Page Key',
        help='Page key to navigate to (e.g., "physicians")')
    action_tab_key = fields.Char(string='Target Tab Key',
        help='Optional tab key on the target page')
    action_pass_value_as = fields.Char(string='Pass Clicked Value As',
        help='URL parameter name for clicked value (e.g., "physician_name")')

    # For 'show_details': auto-generate drill-down query
    drill_detail_columns = fields.Char(string='Detail Columns',
        help='Comma-separated columns to show in drill-down modal. '
             'Leave empty = show all columns from the base query.')

    # For 'open_url': URL template with placeholder
    action_url_template = fields.Char(string='URL Template',
        help='URL with {value} placeholder. E.g.: /my/posterra/hha/{value}')

    # ── Column Links (for table-type widgets) ────────────────────
    column_link_config = fields.Text(string='Column Links (JSON)',
        help='Auto-generated by builder. Format: '
             '[{"column": "physician_name", "page_key": "physicians", '
             '"filter_param": "physician_name"}]')

    # ── Builder Config (stored for edit/rebuild) ─────────────────
    builder_config = fields.Text(string='Builder Config (JSON)',
        help='Stores the full widget builder config so the widget can be '
             'edited in the builder later. Auto-populated by builder API.')
```

**How click actions work:**

| Preset | Admin Config | User Experience | React Implementation |
|--------|-------------|-----------------|---------------------|
| `none` | Nothing | Static chart | No onClick handler |
| `filter_page` | Nothing (auto-detected) | Click "Illinois" bar → page filters to Illinois | `EChartWidget` onClick → update FilterContext with x_value matched to page filter `field_name` |
| `go_to_page` | Pick page key + filter param | Click "Dr. Smith" → navigate to `/my/posterra/physicians?physician_name=Dr.+Smith` | `EChartWidget` onClick → `window.location.href` with page key + filter param |
| `show_details` | Pick detail columns | Click bar → modal opens with detail table | `EChartWidget` onClick → open `DrillDownModal` → call drill API |
| `open_url` | Enter URL template | Click → open URL with value substituted | `EChartWidget` onClick → `window.open(url.replace('{value}', clicked))` |
| Column links | Toggle per column in builder | "Dr. Smith" in table is a link → click navigates | `DataTable` renders `<a>` for linkable columns |

### 4.5 `dashboard.widget.template` ← WB-6

Pre-built widget configurations that admins can use as starting points.

```python
class DashboardWidgetTemplate(models.Model):
    _name = 'dashboard.widget.template'
    _description = 'Widget Template'
    _order = 'category, name'

    name           = fields.Char(required=True)                  # "Executive KPI Row"
    description    = fields.Text()                               # "5 KPI cards showing..."
    category       = fields.Selection([
        ('kpi',         'KPI Cards'),
        ('trend',       'Trends & Time Series'),
        ('comparison',  'Comparisons'),
        ('ranking',     'Rankings & Tables'),
        ('profile',     'Profiles & Scorecards'),
        ('overview',    'Overview / Layout'),
    ], required=True, default='kpi')
    preview_image  = fields.Binary(attachment=True, string='Preview')
    widget_configs = fields.Text(required=True, string='Widget Configs (JSON)',
        help='JSON array of builder config objects. Each object maps to one '
             'dashboard.widget record when the template is used.')
    creates_count  = fields.Integer(compute='_compute_creates_count',
        string='Widgets Created')
    app_ids        = fields.Many2many('saas.app', string='Available in Apps')

    def action_use_template(self, page_id, tab_id=None):
        """Creates dashboard.widget records from widget_configs JSON.
        Uses QueryBuilder to generate SQL for each widget config.
        Returns list of created widget IDs."""
```

### 4.6 `ai.conversation` ← AZ-S (stub)

```python
class AiConversation(models.Model):
    _name = 'ai.conversation'
    _description = 'AI Conversation'
    _order = 'create_date desc'

    user_id             = fields.Many2one('res.users', required=True, default=lambda s: s.env.user)
    app_id              = fields.Many2one('saas.app')
    page_id             = fields.Many2one('dashboard.page')
    messages            = fields.Text(string='Messages (JSON)',
        help='JSON array of {role, content} message objects')
    status              = fields.Selection([
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('completed',  'Completed'),
        ('failed',     'Failed'),
    ], default='pending')
    error_message       = fields.Text()
    generated_widget_ids = fields.Many2many('dashboard.widget',
        string='Generated Widgets')
```

---

## 5. SERVICES

### 5.1 `QueryBuilder` ← WB-3

File: `services/query_builder.py`

```python
class QueryBuilder:
    """Generates safe SQL from structured widget builder config.

    Usage:
        qb = QueryBuilder(env)
        sql = qb.build_select_query(config)
        rows = qb.execute_preview(sql, params)
    """

    def __init__(self, env):
        self.env = env
        # Reuse from posterra_portal or define locally
        self._BLOCKED = re.compile(
            r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|EXECUTE)\b',
            re.IGNORECASE)

    def build_select_query(self, config):
        """
        config schema:
        {
            "source_ids": [1, 2],
            "columns": [
                {"source_id": 1, "column": "hha_state", "alias": "state"},
                {"source_id": 2, "column": "total_admits", "agg": "sum", "alias": "admits"}
            ],
            "filters": [
                {"source_id": 1, "column": "hha_state", "op": "=", "param": "hha_state"}
            ],
            "group_by": [{"source_id": 1, "column": "hha_state"}],
            "order_by": [{"alias": "admits", "dir": "DESC"}],
            "limit": 10
        }

        Returns: SQL string with %(param)s placeholders.
        Raises: ValueError if columns/tables invalid or no relation between tables.
        """

    def build_drill_query(self, widget, click_column, detail_columns=None):
        """Auto-generates drill-down query from widget's builder_config.

        1. Reads widget.builder_config JSON
        2. Keeps the same FROM + JOIN clauses
        3. Removes aggregation and GROUP BY
        4. Selects detail_columns (or all columns if not specified)
        5. Adds WHERE click_column = %(click_value)s
        6. Adds LIMIT 50

        Returns: SQL string with %(click_value)s + original filter params.
        """

    def validate_query(self, sql):
        """Checks SQL against _BLOCKED keywords.
        Returns: (is_valid: bool, error_message: str or None)"""

    def execute_preview(self, sql, params, limit=25):
        """Executes SQL in read-only transaction with timeout.

        SET TRANSACTION READ ONLY;
        SET LOCAL statement_timeout = '10s';
        {sql}

        Returns: (columns: list[str], rows: list[tuple])
        """
```

**JOIN resolution logic:**
1. Read `dashboard.schema.relation` records for the given `source_ids`
2. Build a JOIN chain: source → target via relation's `source_column`/`target_column`
3. If multiple tables have no relation path → raise ValueError with helpful message
4. If a table is used but has no alias → auto-assign alphabetical alias (a, b, c, ...)

**Column validation:**
- Every column referenced in config must exist in `dashboard.schema.column` for the given source
- Aggregation functions limited to: `sum`, `count`, `avg`, `min`, `max`
- Filter operators limited to: `=`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`, `LIKE`, `ILIKE`

### 5.2 `AiService` ← AZ-S (stub)

File: `services/ai_service.py`

```python
class AiService:
    """Azure AI Foundry integration — Track B.

    When implemented, this class will:
    1. Read schema context from dashboard.schema.source
    2. Build a system prompt with table schemas + widget type catalog
    3. Call Azure AI Foundry endpoint via urllib.request
    4. Parse response JSON into widget builder configs
    5. Create dashboard.widget records via QueryBuilder

    Current status: STUB — raises NotImplementedError.
    """

    def __init__(self, env):
        self.env = env

    def generate_widget(self, prompt, page_id, app_id):
        raise NotImplementedError("Track B: Azure AI Foundry not yet implemented. "
                                  "Use the Visual Widget Builder (Track A) instead.")

    def generate_dashboard(self, prompt, app_id):
        raise NotImplementedError("Track B: Azure AI Foundry not yet implemented.")

    def refine_widget(self, conversation_id, prompt):
        raise NotImplementedError("Track B: Azure AI Foundry not yet implemented.")
```

---

## 6. REST API ENDPOINTS ← WB-4

File: `controllers/builder_api.py`

All endpoints use JWT Bearer token authentication. The builder imports auth helpers from `posterra_portal.controllers.auth_api` (`_verify_token`, `_json_response`, `_json_error`).

### Schema Endpoints

| Endpoint | Method | Auth | Response |
|----------|--------|------|----------|
| `/api/v1/builder/sources` | GET | Admin | `[{id, name, table_name, alias, column_count, description}]` |
| `/api/v1/builder/sources/<int:id>` | GET | Admin | `{id, name, table_name, alias, columns: [{column_name, display_name, data_type, is_measure, is_dimension, is_filterable}]}` |
| `/api/v1/builder/sources/<int:id>/relations` | GET | Admin | `[{id, name, target: {id, name, table_name, alias}, join_type, source_column, target_column}]` |

### Widget Builder Endpoints

| Endpoint | Method | Auth | Input | Response |
|----------|--------|------|-------|----------|
| `/api/v1/builder/preview` | POST | Admin | Builder config JSON (visual mode) OR `{mode: "custom_sql", sql: "SELECT...", x_column, y_columns}` | `{sql, columns: [...], rows: [...], echart_option: {...}}` |
| `/api/v1/builder/create` | POST | Admin | `{mode, config, page_id, tab_id, name, chart_type, col_span, chart_height, color_palette, click_action, ...}` — mode: `visual` or `custom_sql` | `{widget_id, name}` |
| `/api/v1/builder/widget/<int:id>` | PUT | Admin | Updated config fields | `{widget_id, name}` |
| `/api/v1/builder/widget/<int:id>/drill` | POST | Any authenticated | `{click_column, click_value, ...filter_params}` | `{columns: [...], rows: [...]}` |

### Navigation Endpoints (for builder dropdowns)

| Endpoint | Method | Auth | Response |
|----------|--------|------|----------|
| `/api/v1/builder/pages` | GET | Admin | `[{key, name, filters: [{field_name, label}]}]` — for action_page_key + action_pass_value_as dropdowns |

### Widget Library Endpoints

| Endpoint | Method | Auth | Input | Response |
|----------|--------|------|-------|----------|
| `/api/v1/builder/library` | GET | Admin | `?app_id=1&category=chart` | `[{id, name, description, category, chart_type, preview_image_url, instance_count}]` |
| `/api/v1/builder/library/<int:id>` | GET | Admin | — | Full definition detail |
| `/api/v1/builder/library/<int:id>/place` | POST | Admin | `{page_id, tab_id, col_span, title_override}` | Creates `dashboard.widget` instance → `{widget_id}` |

### Widget Reorder Endpoint

| Endpoint | Method | Auth | Input | Response |
|----------|--------|------|-------|----------|
| `/api/v1/builder/reorder` | POST | Admin | `{widget_ids: [5, 3, 8, 1]}` (ordered list) | Updates `sequence` field for each widget → `{ok: true}` |

### Template Endpoints

| Endpoint | Method | Auth | Response |
|----------|--------|------|----------|
| `/api/v1/builder/templates` | GET | Admin | `[{id, name, description, category, creates_count, preview_image_url}]` |
| `/api/v1/builder/templates/<int:id>/use` | POST | Admin | `{page_id, tab_id}` → creates definitions + instances → `{widget_ids: [...]}` |

---

## 7. REACT COMPONENTS ← WB-5

### Two Data Source Modes

The Widget Builder supports two modes for defining data:

| Mode | Who it's for | Steps shown | How data is defined |
|------|-------------|-------------|---------------------|
| **Visual Builder** | Non-technical admins | Steps 1-6 (all) | Pick tables → pick columns → pick aggregation → pick filters (all dropdowns) |
| **Custom SQL** | Technical admins / power users | Steps 1, SQL Editor, 5, 6 (skips 2-4) | Write raw SQL with `%(param)s` placeholders + specify x_column/y_columns |

Admin toggles between modes in **Step 2** via a tab: `[Visual Builder] [Custom SQL]`

### Component Architecture

```
WidgetBuilder.jsx (modal, 6 steps — or 4 in SQL mode)
├── Step 1: ChartTypePicker.jsx
│   └── 14 chart type cards (icon + label + description)
│   └── "Start from Template" button → TemplatePicker sub-component
│
├── Step 2: DataSourceStep.jsx (MODE TOGGLE)
│   ├── Tab: [Visual Builder] [Custom SQL]
│   │
│   ├── Visual Builder Mode:
│   │   └── TableJoinBuilder.jsx
│   │       └── Primary table dropdown
│   │       └── "+ Add Table" → secondary table + join display
│   │       └── Visual join diagram: [Table A] ←JOIN→ [Table B]
│   │
│   └── Custom SQL Mode:
│       └── CustomSqlEditor.jsx
│           └── SQL textarea with syntax hints
│           └── Available filter params shown as pills: %(hha_state)s, %(hha_county)s
│           └── Available tables/columns reference panel (from schema registry)
│           └── "Test Query" button (calls /api/v1/builder/preview)
│           └── x_column input: which result column is the X-axis
│           └── y_columns input: which result columns are values
│           └── series_column input: optional grouping column
│
├── Step 3: ColumnMapper.jsx (Visual mode only — skipped in SQL mode)
│   └── X-axis dropdown (dimension columns from all tables)
│   └── Y-axis: multi-add with explicit aggregation function per column
│   │   ┌──────────────────────────────────────────────┐
│   │   │ Column: [Total Admits ▾]  Function: [SUM ▾]  │
│   │   │ Column: [Episodes     ▾]  Function: [COUNT▾] │
│   │   │ [+ Add Value Column]                         │
│   │   └──────────────────────────────────────────────┘
│   │   Available functions: SUM, COUNT, AVG, MIN, MAX
│   └── Series/Group By dropdown
│   └── Sort + Limit controls
│   └── Column Links section (for table type): clickable toggle per column
│
├── Step 4: FilterActionConfig.jsx (Visual mode: WHERE + actions. SQL mode: actions only)
│   └── WHERE condition builder (Visual mode only — SQL mode handles WHERE in the query)
│   └── Click action radio group with conditional config
│
├── Step 5: AppearanceConfig.jsx
│   └── Color palette visual picker (4 palettes with swatches)
│   └── Width selector (5 options)
│   └── Height slider
│   └── Title input
│   └── Legend/axis/data label toggles
│
└── Step 6: LivePreview.jsx
    └── ECharts preview (calls /api/v1/builder/preview)
    └── Generated SQL display (Visual mode: auto-generated. SQL mode: the admin's query)
    └── Page + Tab target dropdowns
    └── "Save to Dashboard" button

DrillDownModal.jsx (separate from builder)
├── Title bar with close button
├── Sortable data table
└── Row count display
```

### Custom SQL Mode — Step 2 Detail

```
┌─────────────────────────────────────────────────┐
│  Data Source                                    │
│                                                 │
│  [Visual Builder]  [Custom SQL ✓]               │
│                                                 │
│  SQL Query:                                     │
│  ┌──────────────────────────────────────────┐   │
│  │ SELECT p.hha_state AS state,             │   │
│  │        SUM(m.total_admits) AS admits,     │   │
│  │        COUNT(m.episode_id) AS episodes    │   │
│  │ FROM hha_provider p                      │   │
│  │ LEFT JOIN hha_metrics m                  │   │
│  │   ON p.hha_id = m.hha_id                │   │
│  │ WHERE p.hha_state = %(hha_state)s        │   │
│  │ GROUP BY p.hha_state                     │   │
│  │ ORDER BY admits DESC LIMIT 10            │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  Available Params: [%(hha_state)s] [%(hha_county)s] │
│                    [%(hha_city)s]  [%(hha_id)s]     │
│                                                 │
│  [Test Query ▶]  Result: 10 rows, 3 columns     │
│                                                 │
│  Column Mapping:                                │
│  X-axis column:   [state      ]                 │
│  Y-axis columns:  [admits, episodes]            │
│  Series column:   [(none)     ]                 │
│                                                 │
│                         [← Back] [Cancel] [→]   │
│  (Next goes to Step 4: Actions, skipping Step 3)│
└─────────────────────────────────────────────────┘
```

**Custom SQL safety:** Same validation as Visual mode:
- `_BLOCKED_KEYWORDS` regex blocks INSERT/UPDATE/DELETE/DROP/etc.
- `SET TRANSACTION READ ONLY` wrapper
- `statement_timeout = '10s'`
- Admin sees the blocked keywords list if validation fails

### Aggregation Functions — Step 3 Detail (Visual Mode)

```
┌─────────────────────────────────────────────────┐
│  Columns                                        │
│                                                 │
│  X-Axis / Labels:  [HHA State (p.hha_state) ▾]  │
│                                                 │
│  Y-Axis / Values:                               │
│  ┌──────────────────────────────────────────┐   │
│  │ #1  Column: [Total Admits      ▾]        │   │
│  │     Function: [○SUM ●COUNT ○AVG ○MIN ○MAX]│   │
│  │     Display As: [Total Admits        ]    │   │
│  ├──────────────────────────────────────────┤   │
│  │ #2  Column: [Revenue per Visit  ▾]        │   │
│  │     Function: [○SUM ○COUNT ○AVG ○MIN ○MAX]│   │
│  │                        ●                  │   │
│  │     Display As: [Avg Revenue         ]    │   │
│  ├──────────────────────────────────────────┤   │
│  │ [+ Add Value Column]                      │   │
│  └──────────────────────────────────────────┘   │
│                                                 │
│  Group By (series): [(none)              ▾]     │
│  Sort By:           [Total Admits DESC   ▾]     │
│  Limit:             [10                   ]     │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Aggregation functions available:**

| Function | Label | Description | SQL Generated |
|----------|-------|-------------|--------------|
| `sum` | SUM | Total of all values | `SUM(column)` |
| `count` | COUNT | Number of records | `COUNT(column)` |
| `avg` | AVG | Average value | `AVG(column)` |
| `min` | MIN | Minimum value | `MIN(column)` |
| `max` | MAX | Maximum value | `MAX(column)` |

Each Y-axis column gets its own aggregation function selector. This maps to the `agg` field in the builder config:
```json
{"source_id": 2, "column": "total_admits", "agg": "sum", "alias": "admits"}
```

### Key React Implementation Notes

**WidgetBuilder state management:**
```jsx
// Builder state (managed by useReducer in WidgetBuilder.jsx)
{
  step: 1,                    // current step (1-6)
  chartType: 'bar',           // selected chart type

  // ── Data Source Mode ──────────────────────────────
  dataSourceMode: 'visual',   // 'visual' or 'custom_sql'

  // Visual mode fields:
  sources: [],                // selected schema sources [{id, name, alias, columns}]
  joins: [],                  // selected joins [{relation_id, ...}]
  columns: {
    x: null,                  // {source_id, column, alias}
    y: [],                    // [{source_id, column, agg, alias, displayName}]
                              //   agg: 'sum' | 'count' | 'avg' | 'min' | 'max'
    series: null,             // {source_id, column, alias}
  },
  filters: [],                // [{source_id, column, op, param}]
  groupBy: [],                // [{source_id, column}]
  orderBy: [],                // [{alias, dir}]
  limit: 10,

  // Custom SQL mode fields:
  customSql: '',              // raw SQL text
  customXColumn: '',          // which result column is X-axis
  customYColumns: '',         // comma-separated result columns for Y values
  customSeriesColumn: '',     // optional grouping column
  sqlTestResult: null,        // {columns, rows, error} from Test Query

  // ── Actions (both modes) ──────────────────────────
  clickAction: 'none',
  actionPageKey: '',
  actionTabKey: '',
  actionPassValueAs: '',
  drillDetailColumns: '',
  actionUrlTemplate: '',
  columnLinks: [],            // [{column, page_key, filter_param}]

  // ── Appearance (both modes) ───────────────────────
  appearance: {
    title: '',
    colorPalette: 'healthcare',
    colSpan: '6',
    chartHeight: 350,
    showLegend: true,
    showAxisLabels: true,
    showDataLabels: false,
  },
  previewData: null,          // result from /api/v1/builder/preview
  targetPageId: null,
  targetTabId: null,
}
```

**Step flow based on mode:**
- **Visual mode:** Step 1 → 2 (tables) → 3 (columns + aggregation) → 4 (filters + actions) → 5 (appearance) → 6 (preview)
- **Custom SQL mode:** Step 1 → 2 (SQL editor) → 4 (actions only, no WHERE builder) → 5 (appearance) → 6 (preview)

**DrillDownModal:**
```jsx
// Props:
// - isOpen: boolean
// - widgetId: number
// - clickColumn: string
// - clickValue: string
// - onClose: function
// - apiBase: string
// - accessToken: string

// On open: POST /api/v1/builder/widget/{widgetId}/drill
//          with {click_column, click_value, ...currentFilterValues}
// Renders: sortable table with columns + rows from response
```

**EChartWidget.jsx modifications (WB-5):**
```jsx
// Add onClick handler based on widget.click_action
useEffect(() => {
  if (!chartRef.current || widget.click_action === 'none') return;
  const instance = chartRef.current;
  instance.on('click', (params) => {
    const clickedValue = params.name || params.data?.name;
    switch (widget.click_action) {
      case 'filter_page':
        // Find matching filter field_name from page config
        // Update filterValues in FilterContext
        break;
      case 'go_to_page':
        // Navigate: /my/{app}/{action_page_key}?{action_pass_value_as}={clickedValue}
        window.location.href = buildActionUrl(widget, clickedValue);
        break;
      case 'show_details':
        // Open DrillDownModal
        setDrillDown({widgetId: widget.id, clickColumn: widget.x_column, clickValue: clickedValue});
        break;
      case 'open_url':
        window.open(widget.action_url_template.replace('{value}', clickedValue));
        break;
    }
  });
}, [widget.click_action]);
```

**DataTable.jsx modifications (WB-5):**
```jsx
// Parse column_link_config JSON
const columnLinks = JSON.parse(widget.column_link_config || '[]');
const linkMap = Object.fromEntries(columnLinks.map(l => [l.column, l]));

// In render: check each cell
{cols.map((col, ci) => {
  const link = linkMap[col];
  const cellValue = row[ci];
  return (
    <td key={ci}>
      {link ? (
        <a href={`/my/${appKey}/${link.page_key}?${link.filter_param}=${encodeURIComponent(cellValue)}`}
           className="text-teal-600 hover:underline">
          {cellValue}
        </a>
      ) : cellValue}
    </td>
  );
})}
```

---

## 8. TEMPLATE LIBRARY ← WB-6

### Healthcare Templates (seeded in `posterra_portal/data/widget_templates_data.xml`)

Each template stores a `widget_configs` JSON array. When "Use Template" is clicked, each config object creates one `dashboard.widget` record.

**Template 1: Executive KPI Row**
```json
[
  {"chart_type": "kpi", "name": "Total Admits", "col_span": "3",
   "columns": {"y": [{"column": "total_admits", "agg": "sum"}]},
   "appearance": {"kpi_format": "number", "kpi_suffix": ""}},
  {"chart_type": "kpi", "name": "Avg Daily Census", "col_span": "3",
   "columns": {"y": [{"column": "adc", "agg": "avg"}]},
   "appearance": {"kpi_format": "decimal"}},
  {"chart_type": "kpi", "name": "Visits/Admit", "col_span": "3",
   "columns": {"y": [{"column": "visits_per_admit", "agg": "avg"}]},
   "appearance": {"kpi_format": "decimal"}},
  {"chart_type": "kpi", "name": "Revenue/Visit", "col_span": "3",
   "columns": {"y": [{"column": "revenue_per_visit", "agg": "avg"}]},
   "appearance": {"kpi_format": "currency", "kpi_prefix": "$"}},
  {"chart_type": "kpi", "name": "Quality Rating", "col_span": "3",
   "columns": {"y": [{"column": "quality_rating", "agg": "avg"}]},
   "appearance": {"kpi_format": "decimal", "kpi_suffix": "★"}}
]
```

**Template 2: Payer Mix Trend** — 1x stacked bar with series_column = payer_type, x = year

**Template 3: Market Position Radar** — 1x radar, 5 dimensions (Quality, Revenue, Outcomes, Timely Access, Volume), 2 series (Your Portfolio, State Median)

**Template 4: Peer Profile Table** — 1x table with columns: Rank, HHA Name (linkable), Admits, Mkt Share %, ADV %ile, TCS %ile

**Template 5: Market Operating Profile** — 3x gauge_kpi widgets (Access Driven Volume, Therapy Centric Stabilizer, High Acuity Specialist)

**Template 6: Insights Banner** — 1x insight_panel with narrative template

### Template Usage Flow

1. Admin opens Widget Builder → Step 1 → clicks "Start from Template"
2. Template picker shows cards with preview image, name, description, creates_count
3. Admin selects a template → builder pre-fills Steps 2-5 with template config
4. Admin adjusts data source (picks their actual table/columns)
5. Preview shows → Save creates all widgets at once

---

## 9. `__manifest__.py`

```python
{
    'name': 'Dashboard Builder',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'Visual widget builder with schema registry and query generation',
    'description': """
        Dashboard Builder
        =================
        - Schema Registry: register database tables, columns, and JOIN relationships
        - Query Builder: auto-generate safe SQL from structured configuration
        - Widget Action System: click presets (filter, navigate, drill-down, URL)
        - Builder API: REST endpoints for preview, create, update widgets
        - Widget Templates: pre-built widget patterns for rapid dashboard creation
        - AI Integration: Azure AI Foundry stub (Track B provisioning)
    """,
    'author': 'Posterra',
    'website': 'https://posterra.com',
    'depends': ['base'],
    'data': [
        'security/builder_security.xml',
        'security/ir.model.access.csv',
        'views/dashboard_schema_views.xml',
        'views/widget_template_views.xml',
        'views/res_config_settings_views.xml',
        'views/menuitems.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
```

**Note on dependencies:** The module depends only on `base`. It does NOT depend on `posterra_portal`. The consuming module (`posterra_portal`) depends on `dashboard_builder`, not the other way around.

---

## 10. SECURITY

### Groups (`security/builder_security.xml`)

```xml
<record id="module_category_dashboard_builder" model="ir.module.category">
    <field name="name">Dashboard Builder</field>
    <field name="sequence">100</field>
</record>

<record id="group_dashboard_builder_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_dashboard_builder"/>
</record>

<record id="group_dashboard_builder_admin" model="res.groups">
    <field name="name">Administrator</field>
    <field name="category_id" ref="module_category_dashboard_builder"/>
    <field name="implied_ids" eval="[(4, ref('group_dashboard_builder_user'))]"/>
</record>
```

### ACL (`security/ir.model.access.csv`)

| Model | User Read | User Write | Admin Read | Admin Write |
|-------|-----------|------------|------------|-------------|
| dashboard.schema.source | ✓ | ✗ | ✓ | ✓ |
| dashboard.schema.column | ✓ | ✗ | ✓ | ✓ |
| dashboard.schema.relation | ✓ | ✗ | ✓ | ✓ |
| dashboard.widget.template | ✓ | ✗ | ✓ | ✓ |
| ai.conversation | ✗ | ✗ | ✓ | ✓ |

---

## 11. INTEGRATION WITH `posterra_portal`

### How It All Connects (The Full Picture)

```
┌─ DASHBOARD BUILDER MODULE ──────────────────────────────────┐
│                                                              │
│  dashboard.schema.source     → Tables admin can query        │
│  dashboard.schema.column     → Columns with types            │
│  dashboard.schema.relation   → JOIN relationships            │
│  dashboard.widget.definition → Reusable widget designs       │
│  dashboard.widget.template   → Pre-built template bundles    │
│  QueryBuilder service        → Generates safe SQL            │
│  Builder API                 → REST endpoints                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                              ↕ depends
┌─ POSTERRA PORTAL MODULE ────────────────────────────────────┐
│                                                              │
│  dashboard.widget (EXISTING) → NOW has optional              │
│    definition_id → Many2one to widget.definition             │
│    + action mixin fields (click_action, etc.)                │
│                                                              │
│  Widget can be created TWO ways:                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ WAY 1: Direct (existing, unchanged)                   │   │
│  │   Admin → Odoo backend → Dashboard Widgets → Create   │   │
│  │   Writes raw SQL, picks chart type, saves              │   │
│  │   definition_id = None (no library link)               │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ WAY 2: From Library (new)                             │   │
│  │   Admin → Page settings → "Add from Library"          │   │
│  │   Picks a widget.definition → widget instance created │   │
│  │   Inherits SQL, chart_type, colors, actions            │   │
│  │   Can override: title, col_span, sequence              │   │
│  │   definition_id = the selected definition              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Page filters flow automatically:                            │
│    Page has filters: State, County, City                     │
│    Widget SQL uses: %(hha_state)s, %(hha_county)s            │
│    portal.py passes filter values as sql_params              │
│    → Widget automatically filters by page context            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Changes to `posterra_portal/__manifest__.py`

```python
'depends': ['base', 'portal', 'auth_signup', 'hha_crm_integration', 'dashboard_builder'],
```

### Changes to `posterra_portal/models/dashboard_widget.py`

```python
class DashboardWidget(models.Model):
    _name = 'dashboard.widget'
    _inherit = ['dashboard.widget', 'dashboard.widget.action.mixin']

    # ── Link to Widget Library (optional) ────────────────────
    definition_id = fields.Many2one(
        'dashboard.widget.definition', string='From Library',
        ondelete='set null',
        help='If set, this widget was created from a library definition. '
             'Fields are populated from the definition but can be overridden.')

    # Mixin adds: click_action, action_page_key, action_pass_value_as,
    #             drill_detail_columns, action_url_template, column_link_config

    def action_create_from_definition(self, definition_id, page_id, tab_id=None):
        """Creates a widget instance from a library definition.
        Copies all relevant fields from the definition to the widget.
        Admin can then override title, col_span, sequence."""
        defn = self.env['dashboard.widget.definition'].browse(definition_id)
        vals = {
            'definition_id': defn.id,
            'page_id': page_id,
            'tab_id': tab_id,
            'name': defn.name,
            'chart_type': defn.chart_type,
            'query_type': 'sql',
            'query_sql': defn.get_effective_sql(),
            'x_column': defn.x_column,
            'y_columns': defn.y_columns,
            'series_column': defn.series_column,
            'col_span': defn.default_col_span,
            'chart_height': defn.chart_height,
            'color_palette': defn.color_palette,
            'color_custom_json': defn.color_custom_json,
            'click_action': defn.click_action,
            'action_page_key': defn.action_page_key,
            'action_tab_key': defn.action_tab_key,
            'action_pass_value_as': defn.action_pass_value_as,
            'drill_detail_columns': defn.drill_detail_columns,
            'action_url_template': defn.action_url_template,
            'column_link_config': defn.column_link_config,
            'kpi_format': defn.kpi_format,
            'kpi_prefix': defn.kpi_prefix,
            'kpi_suffix': defn.kpi_suffix,
            'echart_override': defn.echart_override,
        }
        return self.create(vals)
```

### Changes to `posterra_portal/views/widget_views.xml`

Add "Library" info + "Actions" tab to the widget form:
```xml
<!-- Library reference (top of form) -->
<field name="definition_id" readonly="1"
       help="This widget was created from a library definition"/>

<!-- Actions tab -->
<page string="Actions">
    <group>
        <field name="click_action"/>
        <field name="action_page_key"
               attrs="{'invisible': [('click_action', '!=', 'go_to_page')]}"/>
        <field name="action_tab_key"
               attrs="{'invisible': [('click_action', '!=', 'go_to_page')]}"/>
        <field name="action_pass_value_as"
               attrs="{'invisible': [('click_action', '!=', 'go_to_page')]}"/>
        <field name="drill_detail_columns"
               attrs="{'invisible': [('click_action', '!=', 'show_details')]}"/>
        <field name="action_url_template"
               attrs="{'invisible': [('click_action', '!=', 'open_url')]}"/>
    </group>
    <group string="Column Links (Table Widgets)">
        <field name="column_link_config"/>
    </group>
</page>
```

### How Page Filters Integrate with Builder Widgets

Filters are already handled — no extra work needed:

1. Each page has `dashboard.page.filter` records (State, County, City, Year, etc.)
2. Each filter has a `field_name` (e.g., `hha_state`)
3. `portal.py` collects filter values from URL params → builds `sql_params` dict
4. Widget SQL uses `%(hha_state)s` → `portal.py` substitutes the value
5. **Builder-created widgets use the same `%(param)s` placeholders** in their SQL

The Widget Builder shows available filter params as clickable pills:
`[%(hha_state)s] [%(hha_county)s] [%(hha_city)s] [%(hha_id)s] [%(hha_name)s]`
Admin clicks a pill to insert it into their SQL (Custom mode) or selects it in the WHERE builder (Visual mode).

**If a page has different filters than what the widget expects:**
- Missing params gracefully become empty strings (existing behavior in `portal.py`)
- The widget still renders — it just shows unfiltered data for that dimension

### React Changes for Widget Library Integration

**WidgetGrid.jsx additions:**
- "Add Widget" button (admin-only) → opens library picker (not the full builder)
- "..." menu on each widget → Edit, Remove, Change Order

**New component: `WidgetLibraryPicker.jsx`**
- Modal showing all `dashboard.widget.definition` records for the current app
- Grid of cards: preview image, name, description, chart type icon
- Search/filter by category
- Click "Add to Page" → calls API to create widget instance
- Can also launch full Widget Builder to create a new definition

**Drag-and-drop reordering** within a page:
- Admin clicks "Edit Layout" → widgets become draggable
- Drag to reorder → updates `sequence` field
- Save → API call updates sequence values
- Uses simple drag handles (no `react-grid-layout` needed for sequence-only reordering)

### React Component Integration

The builder React components live in `dashboard_builder/static/src/js/builder/` as source files. They are imported by posterra_portal's React app:

```jsx
// In posterra_portal/static/src/react/src/App.jsx
import WidgetBuilder from './components/WidgetBuilder';
import WidgetLibraryPicker from './components/WidgetLibraryPicker';
import DrillDownModal from './components/widgets/DrillDownModal';
```

For simplicity, builder components are developed in dashboard_builder but compiled as part of posterra_portal's Vite build (shared source directory).

---

## 12. TRACK B — AZURE AI FOUNDRY (FUTURE)

When Track B is implemented, fill in these stubs:

1. **`services/ai_service.py`** — Replace `NotImplementedError` with actual Azure API calls:
   - `_build_schema_context()` reads `dashboard.schema.source` records
   - `_call_azure_api()` calls `https://{endpoint}/openai/deployments/{deployment}/chat/completions`
   - `_parse_widget_config()` extracts JSON from AI response
   - `_create_widget_records()` uses `QueryBuilder` to validate and create

2. **`controllers/ai_api.py`** — Replace 501 responses with actual endpoints:
   - `POST /api/v1/ai/generate-widget` — natural language → widget(s)
   - `POST /api/v1/ai/generate-dashboard` — natural language → page + widgets
   - `POST /api/v1/ai/refine` — continue conversation

3. **`models/res_config_settings.py`** — Enable the settings form fields

4. **React AI components** (new):
   - `AiAssistant.jsx` — slide-in chat panel
   - `AiFab.jsx` — floating sparkle button
   - `AiContext.jsx` — AI state management

**Azure AI Foundry API pattern:**
```python
import json
import urllib.request

url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={version}"
headers = {'Content-Type': 'application/json', 'api-key': api_key}
body = json.dumps({'messages': messages, 'temperature': 0.3}).encode()
req = urllib.request.Request(url, data=body, headers=headers)
resp = urllib.request.urlopen(req, timeout=30)
result = json.loads(resp.read())
```
