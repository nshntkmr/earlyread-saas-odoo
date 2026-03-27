# AG Grid Table Column Configuration — Dashboard Builder Skill

## When This Applies

Use this skill when working on:
- Table widget column configuration in the Dashboard Builder
- The `TableConfigurator` split-pane component (replaces Steps 3/4/5 for tables)
- `DataTable.jsx` component (replacing Bootstrap HTML table with AG Grid)
- `_build_table_data()` in `dashboard_widget.py`
- Any AG Grid `columnDefs` generation or cell renderer work
- The `table_column_config` JSON field on widget models
- Preview API changes for table widgets
- Odoo admin form view changes for table widget type (`widget_views.xml`)

---

## Architecture Overview

### Wizard Flow: Charts vs Tables

```
Charts (bar, line, pie, etc.):
  Step 1 (Chart Type) → Step 2 (Data Source) → Step 3 (Columns) → Step 4 (Filters & Actions) → Step 5 (Preview & Save)

Tables (data_table):
  Step 1 (Chart Type) → Step 2 (Data Source) → Step 3 (TableConfigurator — split-pane)
```

When `chartType === 'table'`, Steps 3/4/5 merge into a single **split-pane TableConfigurator** that shows column config on the left and a live preview on the right. This eliminates the back-and-forth between config and preview steps.

### Split-Pane Layout

```
Step 3 for table widgets:
+-------------------------------+----------------------------------+
|  LEFT: Column Config          |  RIGHT: Live Preview             |
|                               |                                  |
|  Widget Name: [_____________] |  +------------------------------+|
|                               |  | #  | HHA Name   | Admits |..|||
|  [+ Add Column] [+ Group]    |  | 1  | ABC Home   | 1,374  |  |||
|                               |  | 2  | First Care |   892  |  |||
|  1. Rank (#)     [pin] [gear]|  | 3  | Quality HH |   547  |  |||
|  2. HHA Name     [pin] [gear]|  |... |            |        |  |||
|  3. Admits        [desc][gear]|  +------------------------------+|
|  4. Timely %     [pct] [gear]|                                  |
|                               |  Page Filters:                   |
|  -- Settings for: Admits --   |  [Year: 2024 v] [State: All v]  |
|  Header: [Admits        ]     |                                  |
|  Type: [Numeric        v]     |  Showing 20 of 761 rows          |
|  Width: [110]                 |                                  |
|  Renderer: [Number     v]     |  [Refresh Preview]               |
|  Sort: [DESC v]               |                                  |
|  Click Action: [Go to page v] |  [Save to Library] [Save & Place]|
|  ...                          |                                  |
+-------------------------------+----------------------------------+
```

### Data Flow

```
Admin (Builder TableConfigurator)
  -> Configures columns with AG Grid properties per-column
  -> Click actions configured per-column (not separate step)
  -> WHERE filters configured in left panel below columns
  -> Live preview updates on right panel via preview API
  -> Saved as `table_column_config` JSON on widget definition/instance
  -> Server passes columnDefs + rowData to React portal
  -> AG Grid Community renders with full config
```

---

## Key Integration Points

| Layer | File | What Changes |
|-------|------|--------------|
| **Wizard orchestrator** | `dashboard_builder/static/src/designer/src/components/builder/WidgetBuilder.jsx` | When `chartType === 'table'` and `step >= 2`, render `TableConfigurator` instead of separate Steps 3/4/5. Step tabs show 3 steps for tables, 5 for charts. Footer hides Next/Back on Step 3 (TableConfigurator has its own save). |
| **NEW: Table config UI** | `dashboard_builder/static/src/designer/src/components/builder/TableConfigurator.jsx` | Split-pane component: left = column list + settings + WHERE filters; right = AG Grid preview + page filters + save buttons |
| **NEW: Column settings** | `dashboard_builder/static/src/designer/src/components/builder/TableColumnSettings.jsx` | Expandable settings panel for one column (all 20 AG Grid props + click action) |
| **Builder save** | `WidgetBuilder.jsx` → `buildCreatePayload()` | Include `table_column_config` JSON in payload when `chartType === 'table'` |
| **Widget definition model** | `dashboard_builder/models/dashboard_widget_definition.py` | New `table_column_config` Text field |
| **Widget mixin** | `dashboard_builder/models/dashboard_widget_mixin.py` | `table_column_config` propagates to instances |
| **Widget data builder** | `posterra_portal/models/dashboard_widget.py` → `_build_table_data()` | Returns `{type, columnDefs, rowData}` instead of `{type, cols, rows}` |
| **React table component** | `posterra_portal/static/src/react/src/components/widgets/DataTable.jsx` | AG Grid Community replaces Bootstrap HTML table |
| **Dependencies** | `posterra_portal/static/src/react/package.json` | Add `ag-grid-community`, `ag-grid-react` |
| **Preview API** | `dashboard_builder/controllers/builder_api.py` | Preview endpoint returns AG Grid-compatible `{columnDefs, rowData}` for table type |
| **Admin form view** | `posterra_portal/views/widget_views.xml` | Hide irrelevant tabs/fields for `chart_type == 'table'`, add `table_column_config` read-only field |

---

## Odoo Admin Form — What Shows for Table Widgets

### Design Principle

The builder owns all table column configuration. The Odoo admin handles **placement** (which page, which tab, what size) and **instance overrides** (annotations, subtitle/footnote). The admin form conditionally hides sections that are irrelevant or would conflict with builder-managed config.

### Admin Layout for `chart_type == 'table'`

```
Header:
  [Widget Title]

  LIBRARY & PLACEMENT              DISPLAY
  From Library: [dropdown]         Chart Type: Data Table (read-only when builder_config set)
  Page: [dropdown]  (required)     Width (preset): [50%]
  Tab: [dropdown]                  Width (%): [0]
  Sequence: [10]                   Max Width (%): [0]
  Is Active: [x]                   Height (px): [350]

  (Typography group: HIDDEN — per-column styling in builder)
  (Color Palette: HIDDEN — no ECharts palette for tables)

Tabs:
  [Query]         → HIDDEN when builder_config is set
  [Widget Opts]   → HIDDEN (no KPI/gauge/battle card options for tables)
  [Actions]       → HIDDEN (per-column click actions live in builder)
  [Annotations]   → VISIBLE (subtitle, footnote, badge only)
  [Advanced]      → VISIBLE (table_column_config read-only, builder_config read-only)
```

### Header Section: Library & Placement — KEEP

These are per-instance placement fields, not configuration. They must stay in admin because the same definition can be placed on different pages at different sizes.

| Field | Verdict | Reason |
|-------|---------|--------|
| `definition_id` | **Keep** | Pick from library to auto-fill. Core workflow. |
| `page_id` | **Keep** | Which page. Placement. |
| `tab_id` | **Keep** | Which tab. Placement. |
| `sequence` | **Keep** | Sort order. Placement. |
| `is_active` | **Keep** | Toggle on/off. Admin concern. |

### Display Section — KEEP Sizing Only

| Field | Verdict | Reason |
|-------|---------|--------|
| `chart_type` | **Keep (read-only)** | Shows "Data Table" for reference. Not editable when `builder_config` is set. |
| `col_span` / `width_pct` / `max_width_pct` | **Keep** | Width is placement — same table might be 50% on Overview but 100% on Detail page. |
| `chart_height` | **Keep** | Height varies per placement. Summary page = shorter table. |
| `color_palette` / `color_custom_json` | **Hide** | Tables don't use ECharts color palettes. AG Grid styling is per-column via columnDefs. |
| `bar_stack`, `display_mode`, `kpi_layout`, etc. | **Already hidden** | Conditional `invisible` already hides these for non-matching chart types. |

### Typography Section — HIDE for Tables

| Field | Verdict | Reason |
|-------|---------|--------|
| `label_font_weight`, `label_color` | **Hide** | These control KPI label text. For tables, header styling is per-column via `headerClass` in AG Grid config. |
| `value_font_weight`, `value_color` | **Hide** | These control KPI value text. For tables, cell styling is per-column via `cellStyle` and `cellClassRules`. |

Typography for tables is inherently per-column — "Admits" might be bold + right-aligned while "HHA Name" is normal + left-aligned. A single widget-level setting is meaningless. The builder handles this per-column.

### Tab 1: Query — HIDE When Builder-Managed

| Field | Verdict | Reason |
|-------|---------|--------|
| `query_sql`, `schema_source_id`, `x_column`, `y_columns`, `series_column`, `where_clause_exclude` | **Hide when `builder_config` is set** | SQL is configured in builder Step 2. Editing here would desync from `builder_config`. |

**Exception:** For manually-created widgets (no `definition_id`, no `builder_config`), the Query tab stays visible. This preserves backward compat for power users who hand-configure widgets in admin.

**XML invisible condition:** `invisible="chart_type == 'table' and builder_config != False"`

### Tab 2: Widget Options — HIDE for Tables

All fields in this tab (KPI format, Gauge thresholds, Battle Card columns, Insight Panel templates) are for other chart types. None apply to tables. The existing `invisible` conditions already hide most of these, but the entire tab should be hidden when `chart_type == 'table'`.

### Tab 3: Actions — HIDE for Tables

| Field | Verdict | Reason |
|-------|---------|--------|
| `click_action` | **Hide** | For tables, click actions are per-column. Widget-level click action is meaningless — clicking "HHA Name" should navigate, but clicking "Admits" shouldn't. |
| `column_link_config` | **Hide** | Replaced by per-column `clickAction` in `table_column_config`. Legacy widgets without `table_column_config` still use it via the old DataTable path. |
| `builder_config` (read-only) | **Move to Advanced tab** | Useful for debugging but doesn't belong in Actions. |

### Tab 4: Annotations — KEEP (Modified for Tables)

Annotations are universally useful — every widget type benefits from subtitles, footnotes, and badges.

| Field | Verdict | Reason |
|-------|---------|--------|
| `subtitle` | **Keep** | "Data as of Q1 2025" under table title. Supports `%(column)s` interpolation. |
| `footnote` | **Keep** | "Source: CMS OASIS data" below table. Same interpolation. |
| `annotation_type` | **Keep (restricted)** | Only show `None` and `Badge` options for tables. Hide `Reference Line` and `Text Overlay` — those are ECharts-only concepts. |
| `annotation_text` | **Keep** | Badge text like "761 providers". Shown when `annotation_type == 'badge'`. |
| `annotation_query_sql` | **Keep** | Separate SQL for subtitle/footnote interpolation. E.g., returns `report_period`, `total_count` for templates. |
| `annotation_value`, `annotation_value_column` | **Hide** | Reference line-specific fields. Not applicable to tables. |
| `annotation_position`, `annotation_x`, `annotation_y`, `annotation_align`, `annotation_font_size`, `annotation_color` | **Hide** | Positioning is for ECharts text overlays. Not applicable to tables (badge position is fixed in widget header). |

**XML change:** Add `invisible="chart_type == 'table'"` to reference_line and text_overlay radio options, and to all positioning fields.

### Tab 5: Patterns — HIDE for Tables

Already conditionally hidden for `chart_type == 'table'` (ECharts decal patterns don't apply to AG Grid).

### Tab 6: Advanced — KEEP (Enhanced for Tables)

| Field | Verdict | Reason |
|-------|---------|--------|
| `echart_override` | **Hide** | ECharts-specific JSON override. Not applicable to tables. |
| `visual_config` | **Keep (read-only)** | Builder flags for debugging. |
| `builder_config` | **Keep (read-only)** | Full builder state JSON. Moved here from Actions tab for tables. |
| `table_column_config` | **NEW — Add** | Read-only monospace JSON view of the AG Grid columnDefs. Power users can inspect/debug the full column configuration. |

### XML Changes Summary

All changes go in `posterra_portal/views/widget_views.xml`:

```xml
<!-- 1. Hide Typography group for tables -->
<group string="TYPOGRAPHY"
       invisible="chart_type in ('table',)">
  <!-- existing typography fields -->
</group>

<!-- 2. Hide color_palette for tables -->
<field name="color_palette"
       invisible="chart_type in ('table',)" />

<!-- 3. Hide Query tab when builder-managed table -->
<page string="Query"
      invisible="chart_type == 'table' and builder_config != False">
  <!-- existing query fields -->
</page>

<!-- 4. Hide Widget Options tab for tables -->
<page string="Widget Options"
      invisible="chart_type == 'table'">
  <!-- existing KPI/gauge/battle card fields -->
</page>

<!-- 5. Hide Actions tab for tables -->
<page string="Actions"
      invisible="chart_type == 'table'">
  <!-- existing click action fields -->
</page>

<!-- 6. Annotations tab: restrict annotation_type for tables -->
<!-- In annotation_type radio, hide reference_line and text_overlay for tables -->
<!-- Only None and Badge remain for chart_type == 'table' -->

<!-- 7. Hide Patterns tab for tables (likely already done) -->
<page string="Patterns"
      invisible="chart_type in ('kpi','status_kpi','table','battle_card','insight_panel','kpi_strip')">
</page>

<!-- 8. Advanced tab: add table_column_config -->
<field name="table_column_config"
       widget="text"
       readonly="1"
       invisible="not table_column_config"
       style="font-family: monospace; min-height: 120px;"
       string="Table Column Config (JSON)" />
```

---

## TableConfigurator Component Design

### Props (from WidgetBuilder)

```javascript
<TableConfigurator
  sources={state.sources}           // from Step 2
  joins={state.joins}               // from Step 2
  dataMode={state.dataMode}         // 'visual' or 'custom_sql'
  customSql={state.customSql}       // custom SQL state
  filters={state.filters}           // WHERE conditions
  visualFlags={state.visualFlags}   // table-level flags
  appearance={state.appearance}     // title, width, height
  builderState={state}              // full state for preview API
  onUpdate={dispatch}               // reducer dispatch
  onSave={handleSave}               // save handler
  saving={saving}                   // save in progress
  apiBase={apiBase}                 // API base URL
  appContext={appContext}            // page context for filters
/>
```

### Internal State

```javascript
const [tableColumns, setTableColumns] = useState([])      // column list with AG Grid config
const [columnGroups, setColumnGroups] = useState([])       // column group definitions
const [selectedColumnIdx, setSelectedColumnIdx] = useState(null)  // which column's settings are open
const [previewData, setPreviewData] = useState(null)       // preview API response
const [previewLoading, setPreviewLoading] = useState(false)
const [filterValues, setFilterValues] = useState({})       // page filter values for preview
```

### Column Object Shape

Each column in `tableColumns[]`:

```javascript
{
  // Data source (from Step 2 sources)
  source_id: 5,
  column: 'admits',
  alias: 'admits',
  data_type: 'numeric',           // from schema metadata

  // AG Grid columnDef properties
  field: 'admits',                // = alias
  headerName: 'Admits',           // display label
  width: 110,
  minWidth: 80,
  flex: null,                     // null = use width, 1 = auto-flex
  pinned: null,                   // null | 'left' | 'right'
  sortable: true,
  sort: 'desc',                   // null | 'asc' | 'desc'
  sortIndex: 0,                   // multi-sort priority
  filter: 'agNumberColumnFilter', // false | 'agTextColumnFilter' | 'agNumberColumnFilter' | 'agDateColumnFilter'
  resizable: true,
  cellRenderer: null,             // null | renderer key from registry
  cellRendererParams: {},         // renderer-specific params
  valueFormatter: 'number',       // null | formatter key
  cellStyle: { textAlign: 'right' },
  cellClassRules: {},             // { 'cell-good': 'x >= 70', 'cell-bad': 'x < 50' }
  headerClass: null,
  hide: false,
  tooltipField: null,
  wrapText: false,
  type: 'numericColumn',          // column type preset

  // Click action (per-column, replaces separate column_link_config)
  clickAction: 'none',            // 'none' | 'go_to_page' | 'filter_page' | 'open_url'
  actionPageKey: '',
  actionTabKey: '',
  actionFilterParam: '',          // param name to pass clicked value as
  actionUrlTemplate: '',
}
```

### Column Group Object Shape

```javascript
{
  headerName: 'ALOS',
  headerClass: null,
  childColumnIndices: [5, 6],     // indices into tableColumns[]
}
```

---

## Builder UI — Column Settings Panel

When admin clicks the gear icon on a column, the settings panel expands below it. Settings are organized into collapsible sections to avoid overwhelming the admin:

### Section 1: Basic (always visible)

| Control | Type | Default | Notes |
|---------|------|---------|-------|
| Header Label | text input | `display_name` from schema | `headerName` |
| Column Type | dropdown | auto-detect from `data_type` | `type` — pre-fills width, alignment, formatter, filter |
| Width (px) | number input | from type preset | `width` |
| Auto-flex | toggle | off | when on, sets `flex: 1` and hides width |

### Section 2: Display (collapsible, open by default)

| Control | Type | Default | Notes |
|---------|------|---------|-------|
| Formatter | dropdown | from type preset | `valueFormatter` — None, Number, Currency, Percentage, Decimal, Date |
| Renderer | dropdown | None | `cellRenderer` — shows dynamic params below when selected |
| Renderer Params | dynamic inputs | — | `cellRendererParams` — appears based on renderer selection |
| Alignment | 3-button toggle | from type | Left / Center / Right → `cellStyle.textAlign` |
| Bold | toggle | off | `cellStyle.fontWeight` |

### Section 3: Behavior (collapsible, closed by default)

| Control | Type | Default | Notes |
|---------|------|---------|-------|
| Sortable | toggle | on | `sortable` |
| Default Sort | dropdown | None | `sort` — None / ASC / DESC |
| Filterable | dropdown | from type | `filter` — None / Text / Number / Date |
| Pinned | dropdown | None | `pinned` — None / Left / Right |
| Resizable | toggle | on | `resizable` |
| Visible | toggle | on | `hide` (inverted) |
| Wrap Text | toggle | off | `wrapText` + `autoHeight` |
| Tooltip Field | dropdown | None | `tooltipField` — populated from source columns |

### Section 4: Conditional Formatting (collapsible, closed by default)

| Control | Type | Default | Notes |
|---------|------|---------|-------|
| Rule 1: Class | dropdown | — | CSS class: `cell-good`, `cell-bad`, `cell-warn`, `cell-muted` |
| Rule 1: Condition | text input | — | Expression: `x >= 70` (AG Grid native string expression) |
| [+ Add Rule] | button | — | Add more cellClassRules entries |

### Section 5: Click Action (collapsible, closed by default)

| Control | Type | Default | Notes |
|---------|------|---------|-------|
| On Click | dropdown | None | `clickAction` — None / Go to Page / Filter Page / Open URL |
| Target Page | dropdown | — | `actionPageKey` — populated from app pages (visible when Go to Page) |
| Target Tab | dropdown | — | `actionTabKey` — populated from page tabs |
| Pass Value As | text input | — | `actionFilterParam` — URL param name |
| URL Template | text input | — | `actionUrlTemplate` — visible when Open URL |

### Smart Defaults from Column Type

When admin selects a Column Type, auto-fill related settings:

| Type | Width | Align | Formatter | Filter | AG Grid type |
|------|-------|-------|-----------|--------|--------------|
| Text | 200 | left | none | agTextColumnFilter | — |
| Numeric | 110 | right | number | agNumberColumnFilter | numericColumn |
| Currency | 120 | right | currency | agNumberColumnFilter | currency (custom) |
| Percentage | 100 | right | percentage | agNumberColumnFilter | percentage (custom) |
| Date | 120 | left | date | agDateColumnFilter | — |

Admin can override any auto-filled value afterward. The type just sets sensible starting points.

---

## AG Grid Column Properties Reference

### 1. `field` — Database Column
Maps to a key in `rowData[]`. Populated from selected MV schema.
Config: `{ "field": "admits" }`

### 2. `headerName` — Column Header Label
Display label. Defaults to `field` if omitted.
Config: `{ "field": "hospitalization_flag_rate", "headerName": "Bounce %" }`

### 3. `width` / `minWidth` / `maxWidth` / `flex` — Column Sizing
Width in px or proportional flex.
Config: `{ "field": "hha_name", "width": 280, "minWidth": 150 }`

### 4. `pinned` — Freeze Column Left/Right
Stays visible during horizontal scroll.
Config: `{ "field": "hha_name", "pinned": "left" }`

### 5. `sortable` — Client-Side Header Sort
Header click cycles asc/desc/none.
Config: `{ "field": "admits", "sortable": true }`

### 6. `sort` / `sortIndex` — Default Sort
Default sort direction and multi-sort priority.
Config: `{ "field": "admits", "sort": "desc", "sortIndex": 0 }`

### 7. `filter` — Column Filter Type
Built-in text/number/date filters in header.
Config: `{ "field": "admits", "filter": "agNumberColumnFilter" }`

Filter mapping: Text → `agTextColumnFilter`, Number → `agNumberColumnFilter`, Date → `agDateColumnFilter`, None → `false`

### 8. `resizable` — Drag Column Edges
Users drag header border to resize.
Config: `{ "field": "hha_name", "resizable": true }`

### 9. `cellRenderer` — Custom Visual Component
Replaces text with React component (sparklines, badges, etc.).
Config: `{ "field": "admits_trend", "cellRenderer": "sparkline" }`

**Renderer Registry:**

| Key | Name | Renders | Params |
|-----|------|---------|--------|
| `text` | Text (default) | Plain text | — |
| `number` | Number | Formatted with commas | `{ decimals }` |
| `currency` | Currency | Dollar-formatted | `{ decimals, symbol }` |
| `percentage` | Percentage | Percent with % suffix | `{ decimals, multiply }` |
| `sparkline` | Sparkline | Tiny inline line chart | `{ color, height, width }` |
| `starRating` | Star Rating | Star icon(s) + value | `{ maxStars, color }` |
| `badge` | Badge | Bootstrap badge | `{ colorMap }` |
| `pctColored` | Colored % | Percent with threshold color | `{ goodAbove, badBelow, goodColor, badColor }` |
| `barInline` | Inline Bar | Mini horizontal bar | `{ maxValue, color }` |
| `link` | Link | Clickable cell (from click action config) | `{ pageKey, filterParam }` |

### 10. `cellRendererParams` — Renderer Settings
Extra config for the renderer. Dynamic UI based on renderer selection.

### 11. `valueFormatter` — Display Format
Transforms display without changing sort/filter value.
Mapping: `number` → `26,000`, `currency` → `$26,001`, `percentage` → `44.1%`, `decimal` → `0.94`, `date` → locale

### 12. `valueGetter` — Computed Column
Derives value from multiple fields. Rarely needed (MVs pre-compute).
Config: `{ "headerName": "$/Visit", "valueGetter": "revenue_per_visit" }`

### 13. `cellStyle` — Inline CSS
Static CSS on every cell. Builder exposes alignment + bold only.
Config: `{ "field": "admits", "cellStyle": { "textAlign": "right", "fontWeight": "bold" } }`

### 14. `cellClassRules` — Conditional CSS Classes
AG Grid supports string expressions where `x` = cell value.
Config: `{ "cellClassRules": { "cell-good": "x >= 70", "cell-bad": "x < 50" } }`

Required CSS classes in `posterra.css`:
```css
.cell-good { color: #10b981; font-weight: 600; }
.cell-bad  { color: #ef4444; font-weight: 600; }
.cell-warn { color: #f59e0b; font-weight: 600; }
.cell-muted { color: #9ca3af; }
```

### 15. `headerClass` — Header CSS Class
Styles the header cell for visual grouping.
Config: `{ "field": "timely_pct", "headerClass": "header-quality" }`

### 16. `hide` — Hidden Column
In data but not shown. Used for drill-down linking.
Config: `{ "field": "hha_ccn", "hide": true }`

### 17. `children` — Nested Column Groups
Two-level header structure (parent spans children).
Config: `{ "headerName": "ALOS", "children": [{ "field": "alos_yours" }, { "field": "alos_mkt" }] }`

### 18. `tooltipField` / `tooltipValueGetter` — Hover Tooltip
Shows extra info on hover.
Config: `{ "field": "hha_name", "tooltipField": "hha_full_description" }`

### 19. `wrapText` / `autoHeight` — Multi-Line Cells
Wraps instead of truncating. Breaks uniform row height — use sparingly.
Config: `{ "field": "notes", "wrapText": true, "autoHeight": true }`

### 20. `type` — Column Type Template
Bundles common settings into one selection.
Config: `{ "field": "admits", "type": "numericColumn" }`

Custom types registered in AG Grid setup:
```javascript
columnTypes: {
  currency:   { width: 110, type: 'rightAligned', valueFormatter: currencyFormatter, filter: 'agNumberColumnFilter' },
  percentage: { width: 100, type: 'rightAligned', valueFormatter: pctFormatter, filter: 'agNumberColumnFilter' },
}
```

---

## Wizard Integration in WidgetBuilder.jsx

### Modified STEPS Logic

```javascript
// Dynamic steps based on chart type
const getSteps = (chartType) => {
  if (chartType === 'table') {
    return [
      { key: 'chart_type',  label: 'Chart Type' },
      { key: 'data_source', label: 'Data Source' },
      { key: 'configure',   label: 'Configure Table' },  // merged step
    ]
  }
  return [
    { key: 'chart_type',  label: 'Chart Type' },
    { key: 'data_source', label: 'Data Source' },
    { key: 'columns',     label: 'Columns' },
    { key: 'filters',     label: 'Filters & Actions' },
    { key: 'preview',     label: 'Preview & Save' },
  ]
}
```

### Step 3 Rendering (table branch)

```jsx
{/* Step 3: Configure Table (merged Steps 3+4+5 for tables) */}
{state.step === 2 && state.chartType === 'table' && (
  <TableConfigurator
    sources={state.sources}
    joins={state.joins}
    dataMode={state.dataMode}
    customSql={state.customSql}
    filters={state.filters}
    visualFlags={state.visualFlags}
    appearance={state.appearance}
    builderState={state}
    onUpdate={dispatch}
    onSave={handleSave}
    saving={saving}
    apiBase={apiBase}
    appContext={appContext}
  />
)}

{/* Step 3: Columns (charts only — existing ColumnMapper) */}
{state.step === 2 && state.chartType !== 'table' && (
  // ... existing ColumnMapper code
)}
```

### Footer Behavior

For tables on Step 3, hide the Next button (save lives inside TableConfigurator). Back button still works to go to Step 2.

### buildCreatePayload Changes

```javascript
function buildCreatePayload(state) {
  const base = { /* ... existing base ... */ }

  // Table-specific: include column config JSON
  if (state.chartType === 'table' && state.tableColumnConfig) {
    base.table_column_config = JSON.stringify(state.tableColumnConfig)
  }

  // ... rest of existing payload logic
}
```

---

## `table_column_config` JSON — Stored on Widget Model

### Field Definition

Add to `dashboard_widget_definition.py`, `dashboard_widget_mixin.py`, and `dashboard_widget.py`:

```python
table_column_config = fields.Text(
    string='Table Column Config (JSON)',
    help='AG Grid columnDefs JSON. Stores full column configuration '
         'including renderers, formatters, sorting, pinning, '
         'conditional formatting, and click actions.')
```

### Resolved columnDefs Example

This is what gets stored and passed to React:

```json
[
  {
    "field": "rank",
    "headerName": "#",
    "width": 60,
    "pinned": "left",
    "sortable": true,
    "type": "numericColumn"
  },
  {
    "field": "hha_name",
    "headerName": "HHA Name",
    "width": 280,
    "pinned": "left",
    "filter": "agTextColumnFilter",
    "tooltipField": "hha_full_description",
    "cellRenderer": "link",
    "cellRendererParams": {
      "pageKey": "hha_detail",
      "filterParam": "hha_ccn",
      "valueField": "hha_ccn"
    }
  },
  {
    "field": "timely_pct",
    "headerName": "Timely %",
    "cellRenderer": "pctColored",
    "cellRendererParams": {
      "goodAbove": 70,
      "badBelow": 50,
      "goodColor": "#10b981",
      "badColor": "#ef4444"
    },
    "valueFormatter": "percentage",
    "type": "percentage"
  },
  {
    "headerName": "ALOS",
    "children": [
      { "field": "alos_yours", "headerName": "Yours", "type": "numericColumn" },
      { "field": "alos_mkt", "headerName": "Mkt Avg", "type": "numericColumn" }
    ]
  }
]
```

---

## Backend Data Flow

### Current `_build_table_data()` (dashboard_widget.py line 1477)

```python
def _build_table_data(self, cols, rows):
    result = {
        'type': 'table',
        'cols': cols,
        'rows': [[str(cell) if cell is not None else '' for cell in r] for r in rows],
    }
    result.update(self._get_typography_overrides())
    return result
```

### Target `_build_table_data()` with AG Grid

```python
def _build_table_data(self, cols, rows):
    column_config = json.loads(self.table_column_config or '[]')
    if column_config:
        # AG Grid mode: columnDefs + rowData (list of dicts)
        row_data = [dict(zip(cols, r)) for r in rows]
        return {
            'type': 'table',
            'columnDefs': column_config,
            'rowData': row_data,
            'row_count': len(rows),
        }
    # Fallback: legacy cols/rows for backward compat
    result = {
        'type': 'table',
        'cols': cols,
        'rows': [[str(cell) if cell is not None else '' for cell in r] for r in rows],
    }
    result.update(self._get_typography_overrides())
    return result
```

### Preview API Changes (builder_api.py)

The preview endpoint must return AG Grid-compatible format for table type:

```python
# In preview() handler, after SQL execution:
if chart_type == 'table':
    # Return raw column names + dict rows for AG Grid preview
    row_data = [dict(zip(cols, r)) for r in rows[:50]]  # limit preview to 50 rows
    return {'columns': cols, 'rowData': row_data, 'row_count': len(rows)}
```

The TableConfigurator builds columnDefs client-side from the admin's config, and feeds them along with rowData to an AG Grid instance for live preview.

---

## React DataTable.jsx — AG Grid Integration

### Dual-Mode Detection

```jsx
export default function DataTable({ data = {}, columnLinkConfig, onCellClick }) {
  // AG Grid mode: has columnDefs
  if (data.columnDefs) {
    return <AGGridTable data={data} onCellClick={onCellClick} />
  }
  // Legacy mode: plain cols/rows (backward compat)
  return <LegacyTable data={data} columnLinkConfig={columnLinkConfig} onCellClick={onCellClick} />
}
```

### AG Grid Component

```jsx
function AGGridTable({ data, onCellClick }) {
  const { columnDefs, rowData, row_count } = data

  // Resolve renderer keys to actual React components
  const resolvedColDefs = useMemo(() =>
    resolveRenderers(columnDefs), [columnDefs]
  )

  return (
    <div className="pv-widget-table-wrap ag-theme-alpine">
      <AgGridReact
        columnDefs={resolvedColDefs}
        rowData={rowData}
        defaultColDef={{
          resizable: true,
          sortable: true,
        }}
        columnTypes={CUSTOM_COLUMN_TYPES}
        domLayout="autoHeight"
        suppressCellFocus={true}
        onCellClicked={handleCellClick}
      />
      {row_count != null && (
        <div className="pv-table-meta text-muted small mt-1">
          Showing {rowData.length} of {row_count} rows
        </div>
      )}
    </div>
  )
}
```

---

## Gotchas

- **Column groups (`children`) have no `field`** — they are header-only wrappers. The builder must handle groups as a separate entity from data columns.
- **`cellClassRules` uses string expressions** like `"x >= 70"` — AG Grid natively supports this. Store as strings in JSON config, no function serialization needed.
- **`valueFormatter` and `cellRenderer` are mutually exclusive in practice** — if a custom renderer handles formatting (like `pctColored`), don't also set a valueFormatter. The builder UI should grey out one when the other is selected.
- **`type` pre-sets multiple properties** — when admin picks a column type, auto-fill width, alignment, formatter, and filter. Allow override of individual properties afterward.
- **Backward compatibility** — existing table widgets with no `table_column_config` must continue working with the legacy `cols/rows` format. `DataTable.jsx` must detect which format it receives and render accordingly (AG Grid vs legacy Bootstrap table).
- **Row data must be dicts for AG Grid** — AG Grid expects `[{field: value, ...}]`, not nested arrays. `_build_table_data()` converts SQL tuples to dicts using `dict(zip(cols, row))`.
- **`column_link_config` merges into columnDefs** — existing column link config becomes `cellRenderer: 'link'` entries in columnDefs, not a separate config. Legacy widgets with `column_link_config` but no `table_column_config` still use the old DataTable path.
- **Preview in builder uses the same preview API** — TableConfigurator calls `/dashboard/designer/api/preview` and renders the response in an AG Grid instance on the right panel. The columnDefs are built client-side from the admin's column config state.
- **WHERE filters stay in TableConfigurator** — the left panel has a collapsible "WHERE Conditions" section below the column list. Same UI as current `FilterActionConfig` Part A, but embedded in the split-pane instead of a separate step.
- **Page filters in preview** — reuses existing `PageFilterPanel.jsx` component in the right panel. Only shown when `appContext.page` is set (building within a page context).
- **Step count is dynamic** — `WidgetBuilder.jsx` must compute steps from `state.chartType`. The tab bar, dots, and Next/Back buttons all adapt. When switching from table to bar chart type in Step 1, step count changes from 3 to 5.
- **Custom SQL mode tables** — TableConfigurator still works. Columns come from the SQL result column names (detected via test execution in Step 2). Admin configures AG Grid properties per column. The only difference is no WHERE conditions section (custom SQL handles its own filtering).
- **Annotation SQL interpolation still works** — `subtitle` and `footnote` use `%(column)s` syntax populated from `annotation_query_sql` results. This runs server-side in `_interpolate_annotations()` and is independent of the AG Grid column config. No changes needed to the annotation pipeline.
- **Admin form `invisible` conditions must use Odoo 19 syntax** — Odoo 19 CE uses Python-style domain expressions in `invisible` attributes, not legacy `attrs`. Example: `invisible="chart_type == 'table'"` not `attrs="{'invisible': [('chart_type','=','table')]}"`.
- **`definition_id` auto-fill must include `table_column_config`** — the existing `onchange_definition_id` method that auto-populates widget fields from a library definition must also copy `table_column_config`. Without this, placing a library definition onto a page would lose the AG Grid column config.

---

## Safety Audit: Non-Table Chart Type Isolation

### Dispatch Is Hermetically Sealed

Every chart type routes through strict `if/elif/else` branching in `get_portal_data()` (dashboard_widget.py lines 606-620). The table branch (`chart_type == 'table'`) calls `_build_table_data()` exclusively. No other chart type can accidentally trigger it. The same isolation exists in:

- **WidgetGrid.jsx** — `resolveWidget()` uses `ECHART_TYPES` Set + switch statement. Table maps to `DataTable`, all others map to their own components.
- **buildCreatePayload()** — chart-type-specific fields already have `state.chartType === 'bar'` guards (e.g., `bar_stack`). Adding `table_column_config` with a `state.chartType === 'table'` guard follows the same pattern.
- **Admin form XML** — all table-specific visibility uses `invisible="chart_type == 'table'"` which does NOT affect other chart types.

### Risk Matrix — Zero Impact on Other Chart Types

| Chart Type | Dispatch Path | AG Grid Risk |
|-----------|---------------|--------------|
| bar, line, pie, donut, gauge, radar, scatter, heatmap | `ECHART_TYPES` → `_build_echart_option()` → EChartWidget | **None** — completely separate rendering pipeline |
| kpi, status_kpi, kpi_strip | `_build_kpi_data()` → KPICard/StatusKPI/KPIStrip | **None** — different model builder, different component |
| gauge_kpi | `_build_gauge_kpi_data()` → GaugeKPI | **None** — no overlap with table data format |
| battle_card | `_build_battle_data()` → BattleCard | **None** — separate builder and component |
| insight_panel | `_build_insight_data()` → InsightPanel | **None** — narrative template system, unrelated |

### Pre-Existing Gaps (Fix Before or Alongside AG Grid Work)

These are bugs in the CURRENT codebase that affect table widgets today, not introduced by AG Grid changes. They must be fixed to ensure table widgets work correctly:

#### Gap 1: `column_link_config` not copied in `_onchange_definition_id()`

**File:** `posterra_portal/models/dashboard_widget.py` → `_onchange_definition_id()` (around line 500-544)
**Problem:** When admin picks a library definition to auto-fill a widget instance, `column_link_config` is NOT in the copy list. Table widget column links are lost.
**Fix:**
```python
# Add after the existing field copies (around line 544):
self.column_link_config = defn.column_link_config
```
**Also add for new field:**
```python
self.table_column_config = defn.table_column_config
```

#### Gap 2: `LOAD_DEFINITION` reducer doesn't restore `tableColumnConfig`

**File:** `dashboard_builder/static/src/designer/src/components/builder/WidgetBuilder.jsx` → reducer `LOAD_DEFINITION` case (lines 117-175)
**Problem:** When editing an existing table widget in the builder, the `table_column_config` is not restored into state. The column config would appear empty.
**Fix:**
```javascript
// Add to the LOAD_DEFINITION return object (around line 173):
tableColumnConfig: (() => {
  try {
    return d.table_column_config
      ? (typeof d.table_column_config === 'string'
          ? JSON.parse(d.table_column_config)
          : d.table_column_config)
      : []
  } catch { return [] }
})(),
```
**Also add `tableColumnConfig: []` to `initialState` (around line 23-75).**

#### Gap 3: `column_link_config` not in initial widgets JSON

**File:** `posterra_portal/controllers/portal.py` → `_build_initial_widgets_json()` (lines 123-163)
**Problem:** `column_link_config` is not included in the widget metadata JSON embedded in the page HTML. WidgetGrid.jsx reads `w.column_link_config` (line 237) but it's currently passed via a separate template context path, not the JSON.
**Status:** Verify current behavior — if column links work today, this may be passed through a different mechanism. If broken, add:
```python
# Add to the widget dict (around line 162):
'column_link_config': json.loads(w.column_link_config or '{}') if w.chart_type == 'table' else None,
```

### Implementation Safety Checklist

Before deploying AG Grid table changes, verify these non-table chart types still work:

```
[ ] Bar chart renders with correct ECharts options
[ ] Line chart renders with correct ECharts options
[ ] Pie/Donut chart renders correctly
[ ] KPI Card displays formatted value, icon, label
[ ] Status KPI shows up/down arrow correctly
[ ] Gauge renders with min/max/thresholds
[ ] Gauge + KPI shows gauge with sub-KPI breakdown
[ ] Battle Card shows You vs Them comparison
[ ] Insight Panel renders narrative template
[ ] Heatmap renders color-coded matrix
[ ] Scatter plot renders X-Y correlation
[ ] Radar chart renders multi-axis comparison
[ ] KPI Strip renders compact inline KPIs
[ ] Widget click actions work (go_to_page, filter_page, show_details, open_url)
[ ] Annotations render (subtitle, footnote, badge, reference line, text overlay)
[ ] Filter cascade refreshes widgets correctly
[ ] Widget API (/api/v1/widget/<id>/data) returns correct format for each type
[ ] Builder wizard creates/edits bar, kpi, table widgets without errors
[ ] Existing table widgets (no table_column_config) render with legacy Bootstrap table
```
