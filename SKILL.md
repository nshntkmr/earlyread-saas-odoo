# POSTERRA PORTAL — COMPLETE DEVELOPMENT SKILL

## LOAD THIS FILE AT THE START OF EVERY CODING SESSION

---

## ★ IMPLEMENTATION ORDER — READ THIS FIRST ★

Build these phases in strict sequence. Never start a phase until the
previous phase's milestone test passes. Each phase builds on the last.

```
PHASE 0  →  DB-Driven Pages, Tabs, Filters        ~8h   ← START HERE
PHASE 1  →  Widget Data Models                     ~4.5h
PHASE 2  →  CSV Upload Wizard                      ~2h
PHASE 3  →  Controller Data Fetching               ~4.5h
PHASE 4  →  Dynamic Template Rendering             ~4.5h
PHASE 5  →  Charts JS + Table Interactivity        ~3.5h
                                           TOTAL: ~27h
```

### What each phase unlocks

| Phase | You can do this after it's done |
|-------|----------------------------------|
| **0** | Admin can manage pages, tabs, filters from backend. Sidebar and filter bar read from DB. Portal still works exactly as before. |
| **1** | Admin can create sections and widget configs. Datasets exist. Nothing changes on portal yet — this is the DB foundation. |
| **2** | Admin can upload a CSV to a dataset and see rows in the DB. Data is live in the system. |
| **3** | Controller fetches real data for each widget. Verify via logs. Portal still shows old hardcoded HTML, but data is flowing. |
| **4** | Portal renders everything dynamically from DB records. Upload a new CSV → page updates immediately. |
| **5** | Charts (bar, line, donut, gauge, heatmap) actually draw using ApexCharts. Dashboard is fully functional. |

### The one Claude prompt to start each phase

Copy-paste the relevant line at the start of your session:

**Phase 0:**
> "Read /mnt/skills/user/SKILL.md, then build Phase 0 — create `dashboard.page`, `dashboard.page.tab`, and `dashboard.page.filter` models with their backend views and seed data for all 13 pages and their filters, then update `portal.py` to read pages and filters from DB, and update `dashboard_templates.xml` to loop over DB records for the sidebar and filter bar."

**Phase 1:**
> "Read /mnt/skills/user/SKILL.md, then build Phase 1 — create `dashboard.page.section`, `dashboard.widget.config`, `dashboard.widget.dataset`, and `dashboard.widget.data.row` models with their backend admin forms."

**Phase 2:**
> "Read /mnt/skills/user/SKILL.md, then build Phase 2 — create the `widget_data_import` CSV upload wizard linked to `dashboard.widget.dataset` with an Upload CSV button on the dataset form."

**Phase 3:**
> "Read /mnt/skills/user/SKILL.md, then build Phase 3 — add `_get_sections_for_page`, `_get_widget_rows`, `_transform_widget_data`, and `OdooJSONEncoder` to `portal.py`, and pass sections + widget_data to the template context."

**Phase 4:**
> "Read /mnt/skills/user/SKILL.md, then build Phase 4 — replace the hardcoded Strategic Identity and Market Leaders HTML in `dashboard_templates.xml` with the dynamic section/widget loop and all widget sub-templates."

**Phase 5:**
> "Read /mnt/skills/user/SKILL.md, then build Phase 5 — create `posterra_charts.js` with bar, line, donut, gauge, and heatmap renderers and `posterra_widgets.js` for table interactivity."

### Milestone checklist — tick before moving to the next phase

```
PHASE 0
  ☐ Go to Posterra → Configuration → Pages — all 13 pages visible
  ☐ Rename "Admits" to "Episodes" in backend → sidebar updates on portal
  ☐ Set State filter is_active=False on Overview → filter bar shows 4 items
  ☐ Restore both changes

PHASE 1
  ☐ Posterra → Configuration → Sections exists, no errors on load
  ☐ Create Section "Strategic Identity" linked to Overview / Command Center tab
  ☐ Create Widget Config "Profile Cards" (type=profile_card) inside that section
  ☐ Create Dataset "Test Dataset" — saves without error
  ☐ Portal Overview page still loads (no regressions)

PHASE 2
  ☐ Open "Test Dataset" → "Upload CSV" button exists
  ☐ Upload profile_card CSV (3 rows) → row count shows 3, hha_id_ref = "ALL"
  ☐ Upload ranked_table CSV (20 rows) → row count shows 20, hha_id_ref populated

PHASE 3
  ☐ Temporarily add _logger.info(widget_data) to the route
  ☐ Load /my/practice-vantage/overview → Odoo log shows correct JSON for both widgets
  ☐ No Python exceptions in the log
  ☐ Remove the _logger line

PHASE 4
  ☐ Overview renders Strategic Identity from DB (not hardcoded HTML)
  ☐ Change score_pct from 79 to 85 in CSV, re-upload → page shows 85
  ☐ Set a widget is_active=False → it disappears from portal
  ☐ Market Leaders shows "You" row highlighted

PHASE 5
  ☐ Add a bar chart widget config + CSV dataset → bar chart renders correctly
  ☐ Add a donut chart widget → renders correctly
  ☐ Add a gauge widget → renders correctly
  ☐ No JS console errors on any widget
```

---

## 1. PROJECT CONTEXT

**Platform:** Odoo 19 Community Edition, custom module `posterra_portal`
**What it is:** A healthcare analytics dashboard portal for Home Health Agencies (HHAs).
External HHA users log in and see their data. Internal admins configure everything
from the Odoo backend — no code changes needed for day-to-day configuration.

**Core stack:**
- Odoo QWeb templates (XML) for all portal HTML — **NO OWL on portal pages**
- Vanilla JS + Bootstrap 5 for interactivity
- ApexCharts 4.x via CDN for all charts
- PostgreSQL (claims data, materialized views)
- Redis for caching, PgBouncer for connection pooling

**What is already built and working:**
- Login system with email-domain → HHA matching
- Sidebar navigation (13 pages across 3 sections, currently hardcoded)
- HHA selector dropdown with multi-HHA / brand HHA support
- Filter bar (State → County → Locations cascading, Year, Payer — currently hardcoded)
- Overview page with Strategic Identity cards + Market Leaders table (currently hardcoded HTML)
- Tab bar navigation

**Goal of the widget system:** Replace every hardcoded thing above with
database-driven configuration. Admin creates records in the Odoo backend.
The portal template renders whatever those records say.

---

## 2. THE FIVE CRITICAL RULES

1. **NO OWL on portal pages.** QWeb templates + vanilla JS only.
2. **NO hardcoded data in templates.** Every value comes from the controller context.
3. **ApexCharts loads via CDN.** Script tag before the closing layout tag in the template.
4. **Chart data travels as JSON in `<script type="application/json">` tags.**
   JS reads from DOM. Never make an AJAX call on page load.
5. **Admin EDITS an existing widget rather than deleting and recreating.**
   When a widget needs to change type or look different, change its fields in-place.
   Only delete+recreate if you are moving it to a different section entirely.

---

## 3. THE COMPLETE DATA FLOW

```
Admin in backend
    ↓  creates dashboard.page  →  dashboard.page.tab
    ↓  creates dashboard.page.filter  (per page)
    ↓  creates dashboard.page.section  (linked to page + tab)
    ↓  creates dashboard.widget.config  (linked to section, type, data source)
    ↓  creates dashboard.widget.dataset  (named dataset)
    ↓  uploads CSV  →  creates dashboard.widget.data.row records

Portal user visits /my/practice-vantage/overview
    ↓  portal.py controller reads page config from DB
    ↓  reads active filters for this page from DB
    ↓  reads sections + widgets for active tab
    ↓  fetches data rows for each widget (filtered by user's HHA)
    ↓  transforms raw rows into chart-ready shape per widget type
    ↓  serialises to JSON, passes everything to QWeb template
    ↓  template renders HTML + embeds JSON in <script> tags
    ↓  JS reads JSON tags, calls ApexCharts.render()
    ↓  user sees live dashboard
```

---

## 4. MODULE FILE STRUCTURE

```
posterra_portal/
├── __manifest__.py                         ← EXISTING — add new files here
├── __init__.py                             ← EXISTING — add model imports here
├── models/
│   ├── hha_provider.py                     ← EXISTING
│   ├── res_partner.py                      ← EXISTING
│   ├── dashboard_page.py                   ← NEW (Phase 0)
│   ├── dashboard_page_filter.py            ← NEW (Phase 0)
│   ├── dashboard_page_section.py           ← NEW (Phase 1)
│   ├── dashboard_widget_config.py          ← NEW (Phase 1)
│   ├── dashboard_widget_dataset.py         ← NEW (Phase 1)
│   └── dashboard_widget_data_row.py        ← NEW (Phase 1)
├── wizard/
│   └── widget_data_import.py               ← NEW (Phase 2)
├── controllers/
│   └── portal.py                           ← EXISTING — add methods in Phase 3
├── views/
│   ├── dashboard_templates.xml             ← EXISTING — update in Phase 0 + Phase 4
│   ├── page_views.xml                      ← NEW (Phase 0) — backend forms for page/tab/filter
│   └── widget_config_views.xml             ← NEW (Phase 1) — backend forms for section/widget/dataset
├── data/
│   ├── pages_data.xml                      ← NEW (Phase 0) — seed 13 pages + tabs
│   └── filters_data.xml                    ← NEW (Phase 0) — seed filters per page
├── static/src/
│   ├── css/posterra.css                    ← EXISTING — add widget CSS at end
│   └── js/
│       ├── posterra_charts.js              ← NEW (Phase 5) — ApexCharts init
│       └── posterra_widgets.js             ← NEW (Phase 5) — table sort, interactions
└── security/
    └── ir.model.access.csv                 ← EXISTING — add rows for new models
```

**Import order in `models/__init__.py` (dependencies first):**
```python
from . import hha_provider
from . import res_partner
from . import dashboard_page          # no dependencies
from . import dashboard_page_filter   # depends on dashboard_page
from . import dashboard_page_section  # depends on dashboard_page + tab
from . import dashboard_widget_config  # depends on section
from . import dashboard_widget_dataset # no widget dependency
from . import dashboard_widget_data_row # depends on dataset
```

---

## 5. ALL DATA MODELS — IN DEPENDENCY ORDER

### 5.1  `dashboard.page`

Replaces the hardcoded `SIDEBAR_STRUCTURE` dict in `portal.py`.
One record per sidebar page (13 total).

```python
class DashboardPage(models.Model):
    _name = 'dashboard.page'
    _description = 'Dashboard Page'
    _order = 'sequence asc'

    name     = fields.Char(required=True)               # "Overview", "Hospitals"
    key      = fields.Char(required=True, index=True)   # "overview", "hospitals"
    section  = fields.Selection([
        ('my_hha',       'MY HHA'),
        ('portfolio',    'PORTFOLIO'),
        ('data_explorer','DATA EXPLORER'),
    ], required=True)
    icon       = fields.Char()          # "fa-home", "fa-hospital-o"
    sequence   = fields.Integer(default=10)
    is_active  = fields.Boolean(default=True)
    group_ids  = fields.Many2many('res.groups')
    tab_ids    = fields.One2many('dashboard.page.tab', 'page_id', string='Tabs')
    filter_ids = fields.One2many('dashboard.page.filter', 'page_id', string='Filters')
```

`dashboard.page.tab` — tabs within a page:
```python
class DashboardPageTab(models.Model):
    _name = 'dashboard.page.tab'
    _description = 'Dashboard Page Tab'
    _order = 'sequence asc'

    name     = fields.Char(required=True)               # "Command Center"
    key      = fields.Char(required=True, index=True)   # "command_center"
    page_id  = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
```

---

### 5.2  `dashboard.page.filter`

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

### 5.3  `dashboard.page.section`

A named group of widgets on a specific page + tab.
Examples: "Strategic Identity", "Market Leaders", "Demand", "Execution".

```python
class DashboardPageSection(models.Model):
    _name = 'dashboard.page.section'
    _description = 'Dashboard Page Section'
    _order = 'sequence asc'

    name        = fields.Char(required=True)    # "Strategic Identity"
    key         = fields.Char(index=True)       # "strategic_identity"

    # PAGE + TAB ASSIGNMENT — admin selects from dropdowns
    page_id     = fields.Many2one('dashboard.page', required=True,
                                  string='Page', ondelete='cascade')
    tab_id      = fields.Many2one('dashboard.page.tab', required=True,
                                  string='Tab',
                                  domain="[('page_id', '=', page_id)]",
                                  ondelete='cascade')

    sequence    = fields.Integer(default=10)
    section_tag = fields.Char()        # Top-right tag: "vs State HHAs"
    layout      = fields.Selection([
        ('cards',      'Cards (side by side)'),
        ('table',      'Full-width table'),
        ('mixed',      'Mixed'),
        ('full_width', 'Full width'),
    ], default='cards')
    is_active   = fields.Boolean(default=True)
    widget_ids  = fields.One2many('dashboard.widget.config', 'section_id')
```

**Admin workflow for page + tab assignment:**
1. Open Posterra → Sections → New
2. Select **Page** first (e.g. "Overview") — the Page dropdown shows all 13 pages
3. Select **Tab** — the Tab dropdown auto-filters to only tabs belonging to the selected page
4. Name the section, set layout, set sequence
5. Add widgets in the inline `widget_ids` list

This gives the clean hierarchy: **Page → Tab → Section → Widget**

---

### 5.4  `dashboard.widget.config`

The central model. One record = one widget on the dashboard.

```python
class DashboardWidgetConfig(models.Model):
    _name = 'dashboard.widget.config'
    _description = 'Dashboard Widget Config'
    _order = 'sequence asc'

    # IDENTITY
    name        = fields.Char(required=True)
    section_id  = fields.Many2one('dashboard.page.section', required=True,
                                   ondelete='cascade')
    sequence    = fields.Integer(default=10)
    is_active   = fields.Boolean(default=True)
    css_classes = fields.Char()

    # LAYOUT
    grid_col_span = fields.Integer(default=4)   # out of 12 Bootstrap columns
    grid_row_span = fields.Integer(default=1)

    # WIDGET TYPE — change this field when switching the widget
    widget_type = fields.Selection([
        ('kpi_card',      'KPI / Stat Tile'),
        ('profile_card',  'Profile Card (percentile + bar)'),
        ('ranked_table',  'Ranked Table'),
        ('bar',           'Bar Chart'),
        ('line',          'Line / Area Chart'),
        ('donut',         'Donut / Pie Chart'),
        ('gauge',         'Gauge (half-circle)'),
        ('heatmap',       'Heatmap'),
        ('funnel',        'Funnel Chart'),
        ('data_table',    'Data Table'),
        ('ai_insight',    'AI Insight Tile'),
    ], required=True)

    # DATA SOURCE — choose exactly ONE mode
    data_mode = fields.Selection([
        ('uploaded_data', 'Uploaded CSV Data'),
        ('raw_sql',       'Raw SQL Query'),
        ('odoo_model',    'Odoo Model + Domain'),
    ], default='uploaded_data')
    data_dataset_id  = fields.Many2one('dashboard.widget.dataset')
    raw_sql          = fields.Text()
    odoo_model_name  = fields.Char()
    odoo_domain_json = fields.Text()
    odoo_fields_json = fields.Text()
    order_by         = fields.Char()
    query_limit      = fields.Integer(default=100)

    # VISUAL CONFIG — one JSON blob per widget family; only the relevant one is used
    chart_config_json = fields.Text()  # bar, line, donut, gauge, heatmap, funnel
    table_config_json = fields.Text()  # ranked_table, data_table
    kpi_config_json   = fields.Text()  # kpi_card, profile_card, ai_insight

    # DRILLDOWN
    drilldown_type         = fields.Selection([
        ('none',          'No action'),
        ('internal_page', 'Navigate to page'),
        ('url',           'Open URL'),
        ('filter',        'Apply as filter'),
    ], default='none')
    drilldown_page_key     = fields.Char()
    drilldown_url          = fields.Char()
    drilldown_filter_field = fields.Char()
```

---

### 5.5  `dashboard.widget.dataset`

```python
class DashboardWidgetDataset(models.Model):
    _name = 'dashboard.widget.dataset'
    _description = 'Widget Dataset'

    name             = fields.Char(required=True)
    description      = fields.Text()
    year             = fields.Char()
    payer_type       = fields.Char()
    last_imported_at = fields.Datetime()
    row_count        = fields.Integer(compute='_compute_row_count', store=True)
    column_schema_json = fields.Text()
    row_ids          = fields.One2many('dashboard.widget.data.row', 'dataset_id')
    widget_ids       = fields.One2many('dashboard.widget.config', 'data_dataset_id')

    @api.depends('row_ids')
    def _compute_row_count(self):
        for rec in self:
            rec.row_count = len(rec.row_ids)
```

---

### 5.6  `dashboard.widget.data.row`

```python
class DashboardWidgetDataRow(models.Model):
    _name = 'dashboard.widget.data.row'
    _description = 'Widget Data Row'
    _order = 'sequence asc'

    dataset_id    = fields.Many2one('dashboard.widget.dataset', required=True,
                                    ondelete='cascade', index=True)
    sequence      = fields.Integer(default=10, index=True)
    hha_id_ref    = fields.Char(index=True)   # HHA CCN or "ALL"
    row_data_json = fields.Text()             # {"rank":1, "hha_name":"...", ...}
```

**Multi-tenancy rule:**
- `hha_id_ref = "ALL"` → visible to every portal user (market benchmark data)
- `hha_id_ref = "377502"` → only visible to users whose HHA CCN is 377502
- Controller always queries: `hha_id_ref IN ('ALL', *user_ccns)`

---

## 6. WIDGET SWITCHING — THE COMPLETE GUIDE

### Core rule: always edit in-place, never delete-recreate

When you want a widget to show something different or look different,
**edit the existing record**. You keep: section assignment, sequence order,
grid position, and data source link. Only delete+recreate if you want the
widget in a completely different section.

### Which JSON field each widget type uses

| widget_type | JSON field to fill | JSON fields to clear |
|-------------|-------------------|---------------------|
| `kpi_card` | `kpi_config_json` | `chart_config_json`, `table_config_json` |
| `profile_card` | `kpi_config_json` | `chart_config_json`, `table_config_json` |
| `ai_insight` | `kpi_config_json` | `chart_config_json`, `table_config_json` |
| `ranked_table` | `table_config_json` | `chart_config_json`, `kpi_config_json` |
| `data_table` | `table_config_json` | `chart_config_json`, `kpi_config_json` |
| `bar` | `chart_config_json` | `table_config_json`, `kpi_config_json` |
| `line` | `chart_config_json` | `table_config_json`, `kpi_config_json` |
| `donut` | `chart_config_json` | `table_config_json`, `kpi_config_json` |
| `gauge` | `chart_config_json` | `table_config_json`, `kpi_config_json` |
| `heatmap` | `chart_config_json` | `table_config_json`, `kpi_config_json` |
| `funnel` | `chart_config_json` | `table_config_json`, `kpi_config_json` |

### Scenario A — Switching within the chart family (simplest)

Example: bar → donut, or bar → line

Steps:
1. Edit the widget record
2. Change `widget_type` to the new type
3. Update `chart_config_json` — same field, different keys
4. Dataset stays the same — the same CSV columns work for most chart type switches

Example: bar chart with `{"category_field":"source_type","value_field":"referral_count"}`
switched to donut — the `chart_config_json` becomes:
`{"category_field":"source_type","value_field":"referral_count","height":280}`
The CSV does not change at all.

### Scenario B — Switching between chart and table

Example: ranked_table → bar chart

Steps:
1. Change `widget_type` to `bar`
2. Clear `table_config_json` (set to empty)
3. Fill `chart_config_json` with bar schema
4. Check if same dataset works — often yes, bar chart will just use two columns
   and ignore the others

### Scenario C — Switching between KPI/profile and chart

Example: kpi_card → bar chart

Steps:
1. Change `widget_type` to `bar`
2. Clear `kpi_config_json`
3. Fill `chart_config_json`
4. The dataset likely needs a new CSV — KPI data is single-row, bar needs multiple rows

### What happens with two charts in the same section?

Section A has:
- Widget 1 (sequence=10): bar chart — Source Mix
- Widget 2 (sequence=20): line chart — Trend over time

Switching Widget 1 from bar to donut:
- Edit Widget 1 only
- Change `widget_type` bar → donut
- Update `chart_config_json` for donut schema
- Widget 2 is completely unaffected

Adding a third chart:
- Create a new widget record, `section_id` = Section A, `sequence` = 30
- It renders after Widget 1 and Widget 2

Removing Widget 1:
- Set `is_active = False` on Widget 1 — it disappears from the portal
- OR delete the record entirely
- Widget 2 is unaffected

**The rule is simple: one widget record = one slot. Edit to change the slot.
Add a record to add a slot. Set `is_active=False` to hide a slot.**

---

## 7. JSON CONFIG SCHEMAS PER WIDGET TYPE

### `profile_card` — `kpi_config_json`
```json
{
  "value_field": "score_pct",
  "label_field": "profile_name",
  "sublabel_field": "primary_label",
  "description_field": "description_text",
  "bar_color_field": "bar_color",
  "strength_field": "strength_level",
  "strength_thresholds": {"strong": 70, "moderate": 40}
}
```

### `kpi_card` — `kpi_config_json`
```json
{
  "value_field": "total_admits",
  "comparison_field": "yoy_change_pct",
  "comparison_label": "vs LY",
  "value_format": "number",
  "lower_is_better": false
}
```

### `ranked_table` — `table_config_json`
```json
{
  "columns": [
    {"field": "rank",             "label": "#",            "type": "rank",         "width": "50px"},
    {"field": "hha_name",         "label": "HHA Name",     "type": "name_with_sub","sub_field": "owner_name"},
    {"field": "total_admits",     "label": "Admits",       "type": "number",       "align": "right"},
    {"field": "avg_daily_census", "label": "ADC",          "type": "number",       "align": "right"},
    {"field": "market_share_pct", "label": "Mkt Share",    "type": "percent",      "align": "right"},
    {"field": "timely_access_pct","label": "Timely Access","type": "colored_pct",
     "thresholds": {"good": 70, "warn": 50},               "align": "right"}
  ],
  "user_hha_field": "hha_ccn",
  "default_sort": "rank asc"
}
```

### `bar` — `chart_config_json`
```json
{
  "orientation": "horizontal",
  "category_field": "source_type",
  "value_field": "referral_count",
  "series_field": null,
  "colors": ["#3182ce", "#48bb78"],
  "show_data_labels": true,
  "stacked": false,
  "height": 280
}
```

### `line` — `chart_config_json`
```json
{
  "time_field": "period",
  "value_fields": ["admits", "adc"],
  "series_labels": ["Admits", "ADC"],
  "show_area": false,
  "stroke_width": 2,
  "colors": ["#3182ce", "#48bb78"],
  "height": 300
}
```

### `donut` — `chart_config_json`
```json
{
  "category_field": "source_type",
  "value_field": "referral_count",
  "colors": ["#3182ce", "#48bb78", "#ed8936", "#9f7aea"],
  "show_legend": true,
  "height": 280
}
```

### `gauge` — `chart_config_json`
```json
{
  "value_field": "timely_access_pct",
  "target_field": "target_pct",
  "gauge_label": "Timely Access",
  "color_ranges": [
    {"from": 0,  "to": 50, "color": "#e53e3e"},
    {"from": 50, "to": 70, "color": "#ed8936"},
    {"from": 70, "to": 100,"color": "#48bb78"}
  ],
  "height": 220
}
```

### `heatmap` — `chart_config_json`
```json
{
  "x_field": "month",
  "y_field": "metric_name",
  "value_field": "metric_value",
  "color_scale": "green_red",
  "height": 320
}
```

---

## 8. CSV FORMATS PER WIDGET TYPE

### `profile_card`
```
profile_name, score_pct, strength_level, primary_label, description_text, bar_color, hha_ccn
ACCESS DRIVEN VOLUME, 79, strong, Primary, Speed & volume-focused care model, blue, ALL
THERAPY CENTRIC STABILIZERS, 64, moderate, , Rehab & therapy-intensive approach, purple, ALL
```
`hha_ccn = ALL` → visible to all portal users

### `ranked_table`
```
rank, hha_name, hha_ccn, owner_name, total_admits, avg_daily_census, market_share_pct, timely_access_pct
1, MASS GENERAL BRIGHAM HOME CARE INC, 227207, MASS GENERAL BRIGHAM INC, 13126, 1401, 3.6, 74
20, ELARA CARING TEXAS, 377502, BW NHHC CO-INVEST L.P., 4477, 692, 1.2, 45
```
"You" row is identified at render time from `hha_ccn`. Do NOT flag it in the CSV.

### `kpi_card`
```
metric_name, value, yoy_change_pct, hha_ccn
total_admits, 4477, -26.3, 377502
```

### `bar` / `donut` (same format works for both)
```
category, value, series_name, hha_ccn
Physicians, 1200, Referrals, 377502
Hospitals, 850, Referrals, 377502
```

### `line`
```
period, admits, adc, hha_ccn
2025-01, 380, 52, 377502
2025-02, 410, 58, 377502
```

### `gauge`
```
metric_name, value, target, hha_ccn
timely_access_pct, 47.2, 75, 377502
```

---

## 9. BUILD PHASES — IN ORDER

### PHASE 0 — DB-Driven Pages, Tabs, and Filters (~8 hours)

**New files:** `models/dashboard_page.py`, `models/dashboard_page_filter.py`,
`views/page_views.xml`, `data/pages_data.xml`, `data/filters_data.xml`

**Existing files touched:** `controllers/portal.py` (replace SIDEBAR_STRUCTURE + hardcoded filter bar),
`views/dashboard_templates.xml` (sidebar loop + filter bar loop),
`__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`

**What it enables:** Admin can rename/hide pages, add tabs, change filter labels,
remove filters from specific pages — all from the backend, no code.

**Milestone:** Rename "Admits" to "Episodes" in backend → sidebar updates. Set State
filter `is_active=False` on Overview → filter bar shows 4 items not 5.

**Seed data pattern — use `noupdate="1"` so admin changes persist across upgrades:**
```xml
<data noupdate="1">
  <record id="page_overview" model="dashboard.page">
    <field name="name">Overview</field>
    <field name="key">overview</field>
    <field name="section">my_hha</field>
    <field name="icon">fa-home</field>
    <field name="sequence">10</field>
  </record>
  <!-- repeat for all 13 pages -->

  <record id="tab_overview_command_center" model="dashboard.page.tab">
    <field name="page_id" ref="page_overview"/>
    <field name="name">Command Center</field>
    <field name="key">command_center</field>
    <field name="sequence">10</field>
  </record>
  <!-- repeat for all tabs -->

  <record id="filter_overview_state" model="dashboard.page.filter">
    <field name="page_id" ref="page_overview"/>
    <field name="filter_type">state</field>
    <field name="label">State</field>
    <field name="sequence">10</field>
    <field name="is_active">True</field>
  </record>
  <!-- county(20), locations(30), year(40), payer(50) for overview -->
  <!-- year(10), payer(20) only for portfolio pages -->
</data>
```

**Controller changes in `portal.py`:**
```python
# Replace hardcoded SIDEBAR_STRUCTURE with:
pages = request.env['dashboard.page'].sudo().search(
    [('is_active','=',True)], order='sequence asc')

# Replace hardcoded filter bar context with:
page_filters = request.env['dashboard.page.filter'].sudo().search([
    ('page_id.key', '=', page_key),
    ('is_active', '=', True),
], order='sequence asc')
filter_values = {}
for f in page_filters:
    url_val = kw.get(f'ctx_{f.filter_type}', '').strip()
    filter_values[f.filter_type] = url_val or f.default_value or ''
```

**Template filter bar loop:**
```xml
<t t-if="page_filters">
  <div class="pv-ctx-filter-bar">
    <div class="d-flex align-items-end flex-wrap gap-3">
      <t t-foreach="page_filters" t-as="pf">

        <t t-if="pf.filter_type == 'state'">
          <div class="pv-ctx-filter-group">
            <label class="pv-ctx-group-label"><t t-esc="pf.label or 'State'"/></label>
            <select class="pv-ctx-select" id="ctx-state-select">
              <option value=""><t t-esc="pf.placeholder or 'All States'"/></option>
              <t t-foreach="all_states" t-as="st">
                <option t-att-value="st"
                        t-att-selected="filter_values.get('state') == st">
                  <t t-esc="st"/>
                </option>
              </t>
            </select>
          </div>
        </t>

        <t t-if="pf.filter_type == 'year'">
          <div class="pv-ctx-filter-group">
            <label class="pv-ctx-group-label"><t t-esc="pf.label or 'Year'"/></label>
            <select class="pv-ctx-select" id="ctx-year-select">
              <t t-set="year_opts" t-value="pf.get_options()"/>
              <t t-foreach="year_opts" t-as="opt">
                <option t-att-value="opt['value']"
                        t-att-selected="filter_values.get('year') == opt['value']">
                  <t t-esc="opt['label']"/>
                </option>
              </t>
            </select>
          </div>
        </t>

        <!-- county, locations, payer follow the same pattern -->

        <t t-if="pf.filter_type == 'custom_select'">
          <div class="pv-ctx-filter-group">
            <label class="pv-ctx-group-label" t-esc="pf.label"/>
            <select t-attf-class="pv-ctx-select"
                    t-attf-id="ctx-custom-#{pf.id}-select">
              <t t-set="custom_opts" t-value="pf.get_options()"/>
              <t t-foreach="custom_opts" t-as="opt">
                <option t-att-value="opt['value']"
                        t-att-selected="filter_values.get(pf.label) == opt['value']">
                  <t t-esc="opt['label']"/>
                </option>
              </t>
            </select>
          </div>
        </t>

      </t>

      <div class="pv-ctx-filter-group">
        <label class="pv-ctx-group-label">&#160;</label>
        <button type="button" class="btn btn-primary" id="ctx-apply-btn">
          <i class="fa fa-check me-1"/>Apply
        </button>
      </div>
    </div>
  </div>
</t>
```

---

### PHASE 1 — Widget Data Models (~4.5 hours)

**New files:** `models/dashboard_page_section.py`, `models/dashboard_widget_config.py`,
`models/dashboard_widget_dataset.py`, `models/dashboard_widget_data_row.py`,
`views/widget_config_views.xml`

**Existing files touched:** `__init__.py`, `__manifest__.py`, `ir.model.access.csv`

**What it enables:** Admin can create sections, widget configs, and datasets
in the backend. Nothing changes on the portal yet.

**Milestone:** Create section "Strategic Identity" linked to Overview / Command Center tab.
Create a profile_card widget config. Create a dataset. All save without errors.

**Backend form for widget config — use `invisible` to show only relevant JSON field:**
```xml
<group string="Visual Config"
       invisible="widget_type not in ('kpi_card','profile_card','ai_insight')">
  <field name="kpi_config_json" widget="code"/>
</group>
<group string="Visual Config"
       invisible="widget_type not in ('ranked_table','data_table')">
  <field name="table_config_json" widget="code"/>
</group>
<group string="Visual Config"
       invisible="widget_type not in ('bar','line','donut','gauge','heatmap','funnel')">
  <field name="chart_config_json" widget="code"/>
</group>
```

---

### PHASE 2 — CSV Upload Wizard (~2 hours)

**New files:** `wizard/widget_data_import.py`, wizard view XML

**Existing files touched:** `views/widget_config_views.xml` (add Upload CSV button),
`wizard/__init__.py`, `__manifest__.py`

**What it enables:** Admin uploads a CSV to a dataset and rows appear in the DB.

**Milestone:** Upload ranked_table CSV (20 rows) → row count shows 20,
`hha_id_ref` correctly populated on each row.

**Wizard core logic:**
```python
def action_import(self):
    import csv, io, json, base64
    from odoo import fields as ofields
    content = base64.b64decode(self.csv_file).decode('utf-8')
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if self.replace_existing:
        self.dataset_id.row_ids.unlink()
    for i, row in enumerate(rows):
        clean = {k.strip(): v.strip() for k, v in row.items()}
        self.env['dashboard.widget.data.row'].create({
            'dataset_id':    self.dataset_id.id,
            'sequence':      i + 1,
            'hha_id_ref':    clean.get('hha_ccn', 'ALL'),
            'row_data_json': json.dumps(clean),
        })
    self.dataset_id.last_imported_at = ofields.Datetime.now()
```

---

### PHASE 3 — Controller Data Fetching (~4.5 hours)

**Existing files touched:** `controllers/portal.py` only

**What it enables:** Controller reads widget configs from DB, fetches and transforms data,
passes it to templates. Portal still shows hardcoded HTML (Phase 4 replaces that),
but the context dict now carries the live data.

**Milestone:** Add `_logger.info(widget_data)` to the route. Load Overview → log shows
correct JSON for Strategic Identity + Market Leaders. No Python exceptions.

```python
class OdooJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        from decimal import Decimal
        if isinstance(obj, Decimal): return float(obj)
        if hasattr(obj, 'isoformat'): return obj.isoformat()
        return super().default(obj)

def _get_sections_for_page(self, page_key, tab_key):
    return request.env['dashboard.page.section'].sudo().search([
        ('page_id.key', '=', page_key),
        ('tab_id.key',  '=', tab_key),
        ('is_active',   '=', True),
    ], order='sequence asc')

def _get_widget_rows(self, widget, user_hha_ccns, filter_values):
    if widget.data_mode == 'uploaded_data':
        if not widget.data_dataset_id:
            return []
        rows = request.env['dashboard.widget.data.row'].sudo().search([
            ('dataset_id', '=', widget.data_dataset_id.id),
            '|',
            ('hha_id_ref', '=', 'ALL'),
            ('hha_id_ref', 'in', user_hha_ccns),
        ], order='sequence asc', limit=widget.query_limit or 500)
        return [json.loads(r.row_data_json) for r in rows]
    elif widget.data_mode == 'raw_sql':
        sql = (widget.raw_sql or '').strip()
        if not sql.lower().startswith('select'): return []
        forbidden = ['drop','delete','update','insert','truncate','alter']
        if any(kw in sql.lower() for kw in forbidden): return []
        params = {'hha_ids': tuple(user_hha_ccns) or (0,),
                  'year': filter_values.get('year','2025')}
        request.env.cr.execute(sql, params)
        cols = [d[0] for d in request.env.cr.description]
        return [dict(zip(cols, row)) for row in request.env.cr.fetchall()]
    elif widget.data_mode == 'odoo_model':
        domain = json.loads(widget.odoo_domain_json or '[]')
        fields_list = json.loads(widget.odoo_fields_json or '[]')
        return request.env[widget.odoo_model_name].sudo().search_read(
            domain, fields_list,
            limit=widget.query_limit, order=widget.order_by or None)
    return []

def _transform_widget_data(self, widget, raw_rows, user_hha_ccns):
    wtype     = widget.widget_type
    kpi_cfg   = json.loads(widget.kpi_config_json or '{}')
    chart_cfg = json.loads(widget.chart_config_json or '{}')
    table_cfg = json.loads(widget.table_config_json or '{}')

    if wtype == 'profile_card':
        return raw_rows

    elif wtype == 'ranked_table':
        for row in raw_rows:
            row['_is_you'] = row.get('hha_ccn') in user_hha_ccns
        return raw_rows

    elif wtype == 'kpi_card':
        row = raw_rows[0] if raw_rows else {}
        val = row.get(kpi_cfg.get('value_field','value'), 0)
        cmp = row.get(kpi_cfg.get('comparison_field',''), None)
        lower = kpi_cfg.get('lower_is_better', False)
        trend = 'neutral'
        if cmp is not None:
            cmp_f = float(cmp)
            trend = ('up' if cmp_f > 0 else 'down') if not lower \
                 else ('down' if cmp_f > 0 else 'up')
        return {'value': val, 'comparison_value': cmp,
                'comparison_label': kpi_cfg.get('comparison_label',''), 'trend': trend}

    elif wtype == 'bar':
        cat_f = chart_cfg.get('category_field','category')
        val_f = chart_cfg.get('value_field','value')
        ser_f = chart_cfg.get('series_field')
        if ser_f:
            series_map, categories = {}, []
            for row in raw_rows:
                s = row.get(ser_f,'Value'); c = row.get(cat_f,'')
                if c not in categories: categories.append(c)
                series_map.setdefault(s,[]).append(row.get(val_f,0))
            series = [{'name':k,'data':v} for k,v in series_map.items()]
        else:
            categories = [r.get(cat_f,'') for r in raw_rows]
            series = [{'name': widget.name,
                       'data': [r.get(val_f,0) for r in raw_rows]}]
        return {'chart_type':'bar','series':series,'categories':categories,
                'orientation':chart_cfg.get('orientation','vertical'),
                'colors':chart_cfg.get('colors',['#3182ce']),
                'height':chart_cfg.get('height',280)}

    elif wtype == 'donut':
        cat_f = chart_cfg.get('category_field','category')
        val_f = chart_cfg.get('value_field','value')
        return {'chart_type':'donut',
                'series':[float(r.get(val_f,0)) for r in raw_rows],
                'labels':[r.get(cat_f,'') for r in raw_rows],
                'colors':chart_cfg.get('colors',[]),
                'height':chart_cfg.get('height',280)}

    elif wtype == 'gauge':
        row = raw_rows[0] if raw_rows else {}
        return {'chart_type':'gauge',
                'value': float(row.get(chart_cfg.get('value_field','value'),0)),
                'target':float(row.get(chart_cfg.get('target_field','target'),0) or 0),
                'label': chart_cfg.get('gauge_label',''),
                'color_ranges':chart_cfg.get('color_ranges',[]),
                'height':chart_cfg.get('height',220)}

    elif wtype == 'line':
        time_f = chart_cfg.get('time_field','period')
        val_fs = chart_cfg.get('value_fields',[chart_cfg.get('value_field','value')])
        labels = chart_cfg.get('series_labels', val_fs)
        cats   = [r.get(time_f,'') for r in raw_rows]
        series = [{'name':labels[i] if i<len(labels) else vf,
                   'data':[r.get(vf,0) for r in raw_rows]}
                  for i,vf in enumerate(val_fs)]
        return {'chart_type':'line','series':series,'categories':cats,
                'show_area':chart_cfg.get('show_area',False),
                'colors':chart_cfg.get('colors',[]),
                'height':chart_cfg.get('height',300)}

    return raw_rows  # heatmap, funnel, data_table — template handles raw rows
```

**In the main route, add:**
```python
sections   = self._get_sections_for_page(page_key, active_tab_key)
widget_data = {}
for section in sections:
    for widget in section.widget_ids.filtered('is_active'):
        raw         = self._get_widget_rows(widget, user_hha_ccns, filter_values)
        transformed = self._transform_widget_data(widget, raw, user_hha_ccns)
        widget_data[widget.id] = json.dumps(transformed, cls=OdooJSONEncoder)
values.update({'sections': sections, 'widget_data': widget_data})
```

---

### PHASE 4 — Dynamic Template Rendering (~4.5 hours)

**Existing files touched:** `views/dashboard_templates.xml`, `static/src/css/posterra.css`

**What it enables:** Hardcoded Strategic Identity + Market Leaders HTML is replaced
with dynamic loops. Page now renders entirely from DB records.

**Milestone:** Change profile card score from 79 to 85 in the CSV, re-upload →
page shows 85. Set widget `is_active=False` → it disappears.

```xml
<!-- Add CDN before end of layout -->
<script src="https://cdn.jsdelivr.net/npm/apexcharts@latest/dist/apexcharts.min.js"/>

<!-- Replace hardcoded content with: -->
<t t-foreach="sections" t-as="section">
  <div t-attf-class="pv-section layout-#{section.layout}">
    <div class="pv-section-header">
      <i t-attf-class="fa #{section.icon or 'fa-star-o'} me-2"/>
      <span t-esc="section.name"/>
      <t t-if="section.section_tag">
        <span class="pv-section-tag" t-esc="section.section_tag"/>
      </t>
    </div>
    <div class="pv-widget-row">
      <t t-foreach="section.widget_ids.filtered(lambda w: w.is_active)" t-as="widget">
        <t t-call="posterra_portal.widget_profile_card"
           t-if="widget.widget_type == 'profile_card'"/>
        <t t-call="posterra_portal.widget_ranked_table"
           t-if="widget.widget_type == 'ranked_table'"/>
        <t t-call="posterra_portal.widget_kpi_card"
           t-if="widget.widget_type == 'kpi_card'"/>
        <t t-call="posterra_portal.widget_chart"
           t-if="widget.widget_type in ('bar','line','donut','gauge','heatmap','funnel')"/>
      </t>
    </div>
  </div>
</t>

<!-- profile_card sub-template -->
<t t-name="posterra_portal.widget_profile_card">
  <t t-set="cards" t-value="json.loads(widget_data.get(widget.id, '[]'))"/>
  <t t-foreach="cards" t-as="card">
    <div t-attf-class="pv-si-card #{card.get('primary_label') and 'pv-si-card-active' or ''}">
      <div class="pv-si-card-header">
        <span class="pv-si-card-label" t-esc="card.get('profile_name','')"/>
        <t t-set="strength" t-value="card.get('strength_level','moderate')"/>
        <span t-attf-class="pv-si-badge pv-si-badge-#{strength}"
              t-esc="strength.capitalize()"/>
      </div>
      <div class="pv-si-stat">
        <span class="pv-si-value"><t t-esc="card.get('score_pct',0)"/>%</span>
        <t t-if="card.get('primary_label')">
          <span class="pv-si-sublabel" t-esc="card.get('primary_label')"/>
        </t>
      </div>
      <div class="pv-si-bar-track">
        <div t-attf-class="pv-si-bar-fill pv-bar-#{card.get('bar_color','blue')}"
             t-attf-style="width:#{card.get('score_pct',0)}%"/>
      </div>
      <div class="pv-si-desc" t-esc="card.get('description_text','')"/>
    </div>
  </t>
</t>

<!-- chart sub-template (all ApexCharts types share this) -->
<t t-name="posterra_portal.widget_chart">
  <div class="pv-widget-card">
    <div class="pv-widget-header">
      <span class="pv-widget-title" t-esc="widget.name"/>
    </div>
    <div t-attf-id="chart-#{widget.id}"
         t-att-data-widget-id="widget.id"
         t-att-data-widget-type="widget.widget_type"
         class="pv-chart-container"
         style="min-height: 200px;"/>
    <script type="application/json" t-attf-id="chart-data-#{widget.id}">
      <t t-out="widget_data.get(widget.id, '{}')"/>
    </script>
  </div>
</t>
```

---

### PHASE 5 — Charts JS + Table Interactivity (~3.5 hours)

**New files:** `static/src/js/posterra_charts.js`, `static/src/js/posterra_widgets.js`
**Existing files touched:** `__manifest__.py`

**Milestone:** Bar chart, donut, and gauge all render correctly.
Market Leaders "You" row highlighted. No console errors.

```javascript
// posterra_charts.js
(function() {
  'use strict';

  function pvInitAllCharts() {
    document.querySelectorAll('[data-widget-id]').forEach(function(el) {
      var id     = el.dataset.widgetId;
      var dataEl = document.getElementById('chart-data-' + id);
      if (!dataEl) return;
      var data;
      try { data = JSON.parse(dataEl.textContent.trim()); } catch(e) { return; }
      if (!data || !data.chart_type) return;
      var opts = pvBuildOptions(data);
      if (opts) new ApexCharts(el, opts).render();
    });
  }

  function pvBuildOptions(d) {
    switch (d.chart_type) {
      case 'bar':     return pvBarOpts(d);
      case 'line':    return pvLineOpts(d);
      case 'donut':   return pvDonutOpts(d);
      case 'gauge':   return pvGaugeOpts(d);
      case 'heatmap': return pvHeatmapOpts(d);
      default: return null;
    }
  }

  function pvBarOpts(d) {
    return {
      chart: { type: 'bar', height: d.height || 280, toolbar: { show: false } },
      plotOptions: { bar: { horizontal: d.orientation === 'horizontal' } },
      series: d.series, xaxis: { categories: d.categories },
      colors: (d.colors && d.colors.length) ? d.colors : ['#3182ce'],
      dataLabels: { enabled: !!d.show_data_labels },
    };
  }

  function pvLineOpts(d) {
    return {
      chart: { type: d.show_area ? 'area' : 'line', height: d.height || 300,
               toolbar: { show: false } },
      series: d.series, xaxis: { categories: d.categories },
      colors: (d.colors && d.colors.length) ? d.colors : ['#3182ce'],
      stroke: { width: 2 },
      fill: { opacity: d.show_area ? 0.15 : 1 },
    };
  }

  function pvDonutOpts(d) {
    return {
      chart: { type: 'donut', height: d.height || 280 },
      series: d.series, labels: d.labels,
      colors: (d.colors && d.colors.length) ? d.colors : undefined,
    };
  }

  function pvGaugeOpts(d) {
    var color = '#3182ce';
    if (d.color_ranges) {
      d.color_ranges.forEach(function(r) {
        if (d.value >= r.from && d.value <= r.to) color = r.color;
      });
    }
    return {
      chart: { type: 'radialBar', height: d.height || 220 },
      plotOptions: {
        radialBar: {
          startAngle: -90, endAngle: 90,
          dataLabels: { value: { formatter: function(v) { return v + '%'; }, fontSize:'22px' } }
        }
      },
      series: [d.value], labels: [d.label || ''], colors: [color],
    };
  }

  function pvHeatmapOpts(d) {
    return { chart: { type: 'heatmap', height: d.height || 320,
                      toolbar: { show: false } }, series: d.series };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', pvInitAllCharts);
  } else {
    pvInitAllCharts();
  }
})();
```

---

## 10. SECURITY

**`ir.model.access.csv` — add one portal (read-only) and one admin (full) row per model:**
```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_page_portal,page portal,model_dashboard_page,posterra_portal.group_posterra_user,1,0,0,0
access_page_admin,page admin,model_dashboard_page,posterra_portal.group_posterra_admin,1,1,1,1
access_tab_portal,tab portal,model_dashboard_page_tab,posterra_portal.group_posterra_user,1,0,0,0
access_tab_admin,tab admin,model_dashboard_page_tab,posterra_portal.group_posterra_admin,1,1,1,1
access_filter_portal,filter portal,model_dashboard_page_filter,posterra_portal.group_posterra_user,1,0,0,0
access_filter_admin,filter admin,model_dashboard_page_filter,posterra_portal.group_posterra_admin,1,1,1,1
access_section_portal,section portal,model_dashboard_page_section,posterra_portal.group_posterra_user,1,0,0,0
access_section_admin,section admin,model_dashboard_page_section,posterra_portal.group_posterra_admin,1,1,1,1
access_wconfig_portal,wconfig portal,model_dashboard_widget_config,posterra_portal.group_posterra_user,1,0,0,0
access_wconfig_admin,wconfig admin,model_dashboard_widget_config,posterra_portal.group_posterra_admin,1,1,1,1
access_wdataset_portal,wdataset portal,model_dashboard_widget_dataset,posterra_portal.group_posterra_user,1,0,0,0
access_wdataset_admin,wdataset admin,model_dashboard_widget_dataset,posterra_portal.group_posterra_admin,1,1,1,1
access_wrow_portal,wrow portal,model_dashboard_widget_data_row,posterra_portal.group_posterra_user,1,0,0,0
access_wrow_admin,wrow admin,model_dashboard_widget_data_row,posterra_portal.group_posterra_admin,1,1,1,1
```

**Record rule for data rows (HHA data isolation):**
```xml
<record id="rule_widget_row_own_hha" model="ir.rule">
  <field name="name">Widget Data Row: own HHA only</field>
  <field name="model_id" ref="model_dashboard_widget_data_row"/>
  <field name="domain_force">[
    '|', ('hha_id_ref','=','ALL'),
    ('hha_id_ref','in',[p.hha_ccn for p in user.partner_id.hha_provider_ids])
  ]</field>
  <field name="groups" eval="[(4, ref('posterra_portal.group_posterra_user'))]"/>
</record>
```

---

## 11. COMMON PITFALLS

| Pitfall | Fix |
|---------|-----|
| ApexCharts not ready when JS runs | Use `document.readyState` check shown in Phase 5 |
| Chart renders at zero height | Set `min-height: 200px` on the container div |
| `Decimal`/`datetime` JSON error | Use `OdooJSONEncoder` from Phase 3 |
| `t-out` XSS risk | Only use `t-out` for pre-serialized server-side JSON |
| Two charts with the same DOM ID | Always use `widget.id` in the ID: `chart-#{widget.id}` |
| Tab dropdown shows all tabs not just page's tabs | Set `domain="[('page_id','=',page_id)]"` on `tab_id` |
| Switching widget type breaks rendering | Clear the OLD json field, fill the NEW one |
| Seed data gets overwritten on upgrade | Wrap `<data>` with `noupdate="1"` |
| `hha_id_ref` not set on rows | Wizard reads `hha_ccn` column from CSV, defaults to `"ALL"` |
| Filter bar shows on pages that don't want it | Set all that page's filter records `is_active=False` |

---

## 12. HOW TO START EACH CODING SESSION

See **★ IMPLEMENTATION ORDER** at the top of this file for the exact
copy-paste prompt for each phase and the milestone checklist to complete
before moving on.

The universal pattern is always:

> "Read /mnt/skills/user/SKILL.md, then build Phase N — [task description]."

Never skip a phase. Never start a phase before the previous milestone checklist is fully ticked.
