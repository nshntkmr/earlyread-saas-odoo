# Line Chart Configuration — Dashboard Builder Skill

## When This Applies

Use this skill when working on:
- Line chart variants in the Dashboard Builder
- `_build_echart_option()` line section in `dashboard_widget.py`
- `_build_echart_preview()` line section in `preview_formatter.py`
- `LineStylePicker.jsx` component (variant selection sub-panel with SVG icons)
- Chart flags for line in `chart_flags.py`
- `visual_config` JSON for line widgets
- Custom SQL help text for line variants in `CustomSqlEditor.jsx`
- Any new line variant or flag additions

---

## Architecture Overview

### The 7 Variants

All variants use ECharts `type: 'line'` (except waterfall which uses `type: 'bar'` internally and combo which mixes both). The `chart_type` field stays `'line'` — variants are selected via `line_style` flag in `visual_config` JSON.

| # | Key | Name | ECharts Config | SQL Shape | Best For |
|---|-----|------|----------------|-----------|----------|
| 1 | `basic` | Basic Line | `type:'line'` (default) | X=time, Y=val1,val2 | Comparing multiple metrics over time |
| 2 | `area` | Area Chart | `areaStyle:{opacity}` + optional gradient | Same as basic | Volume trends, emphasizing magnitude |
| 3 | `stacked_line` | Stacked Line | `stack:'total'` | X=time, Y=metric, Series=category | Cumulative trends by category |
| 4 | `stacked_area` | Stacked Area | `stack:'total'` + `areaStyle` | Same as stacked_line | Composition over time (part-to-whole) |
| 5 | `waterfall` | Waterfall/Bridge | Invisible base + colored bar segments | X=step_name, Y=delta_value | Sequential +/- changes, YoY deltas |
| 6 | `combo` | Combo (Bar+Line) | Some series `type:'bar'`, others `type:'line'` | X=category, Y=bar_col,line_col | Two different scales (volume + rate) |
| 7 | `benchmark` | Trend+Benchmark | `markLine` (static) or dashed series (column) | X=time, Y=actual[,target] | Actual vs target comparison |

---

## Variant Details & Usage Guide

### 1. Basic Line (`basic`)

**Purpose:** Straight lines connecting data points. Best for comparing multiple metrics on the same scale.

**Column Mapping (Visual Builder):**
| Field | Value | Notes |
|-------|-------|-------|
| X-axis | `year` | Time dimension |
| Y-axis | `total_admits, episode_count` (SUM) | One line per Y-column |
| Series | (empty) | Leave empty for wide-format data |

**When to use Series column:** Only for "long format" data where metric names are in a column:
```sql
-- Long format: use Series = metric_name, Y = metric_value
SELECT year, metric_name, metric_value FROM some_view
```

**Sample Custom SQL:**
```sql
SELECT year,
       SUM(total_admits) AS total_admits,
       SUM(episode_count) AS episodes
FROM mv_hha_kpi_summary
WHERE TRUE
  [[AND hha_ccn IN %(hha_ccn)s]]
  [[AND year::text IN %(year)s]]
  [[AND ffs_ma IN %(ffs_ma)s]]
GROUP BY year
ORDER BY year
```

---

### 2. Area Chart (`area`)

**Purpose:** Line with filled area underneath. Emphasizes volume/magnitude.

**Column Mapping:** Same as Basic Line.

**Variant Settings:**
- **Area Opacity (0-1):** Controls fill transparency. Default `0.3`, increase to `0.6-0.7` for more vivid fills.
- **Gradient Fill:** Toggle for top-to-transparent vertical gradient effect.

**When to use:** Volume metrics (total_admits, episode_count) where you want to emphasize magnitude. NOT suitable for rate metrics.

---

### 3. Stacked Line (`stacked_line`)

**Purpose:** Multiple cumulative lines stacked vertically. Each line's Y-position = sum of all series below it + own value.

**Column Mapping:**
| Field | Value | Notes |
|-------|-------|-------|
| X-axis | `year` | Time dimension |
| Y-axis | `total_admits` (SUM) | **Single** additive metric |
| Series | `ffs_ma` or `source` | One stacked line per category |

**Important:** Y-axis values are cumulative. The tooltip shows individual values, but line positions show running totals. Use only with **additive metrics** (counts, amounts). Never stack rates or percentages.

**Sample Custom SQL:**
```sql
SELECT year, source, SUM(total_admits) AS total_admits
FROM mv_referral_velocity
WHERE TRUE
  [[AND hha_ccn IN %(hha_ccn)s]]
  [[AND year::text IN %(year)s]]
  [[AND ffs_ma IN %(ffs_ma)s]]
GROUP BY year, source
ORDER BY year, source
```

---

### 4. Stacked Area (`stacked_area`)

**Purpose:** Same as Stacked Line but with filled color bands between lines. Makes composition more visually clear.

**Column Mapping:** Same as Stacked Line.

**Variant Settings:**
- **Area Opacity (0-1):** Default `0.3`. Increase to `0.5-0.7` for visible bands.
- **Gradient Fill:** Adds depth to each band.

**When to use over Stacked Line:** When the visual composition (how much space each category occupies) matters more than exact line positions.

---

### 5. Waterfall/Bridge (`waterfall`)

**Purpose:** Shows sequential positive/negative deltas. Green bars = increases, red bars = decreases. Dashed connector line traces running total.

**Column Mapping:**
| Field | Value | Notes |
|-------|-------|-------|
| X-axis | `source` | Category/step names |
| Y-axis | `yoy_change` | **Single** delta column (can be positive or negative) |
| Series | (empty) | Not used |

**Variant Settings:**
- **Positive Color:** Green bars (default `#91cc75`)
- **Negative Color:** Red bars (default `#ee6666`)
- **Total Bar Color:** Connector line color (default `#5470c6`)
- **Show Connector Lines:** Toggle dashed running-total line

**How it works internally:**
- Computes running total from deltas
- Creates 3 stacked bar series: invisible base + positive + negative
- Connector line traces cumulative total

**All-positive data works fine** — creates a composition waterfall showing how pieces build up to a total.

**Sample Custom SQL (YoY change by source):**
```sql
WITH sel AS (
    SELECT MAX(year)::int AS cur_year
    FROM mv_referral_velocity
    WHERE year::text IN %(year)s
)
SELECT r.source,
       SUM(CASE WHEN r.year = s.cur_year THEN r.total_admits ELSE 0 END) -
       SUM(CASE WHEN r.year = s.cur_year - 1 THEN r.total_admits ELSE 0 END) AS yoy_change
FROM mv_referral_velocity r
CROSS JOIN sel s
WHERE r.year IN (s.cur_year, s.cur_year - 1)
  AND r.hha_ccn IN %(hha_ccn)s
  [[AND r.ffs_ma IN %(ffs_ma)s]]
GROUP BY r.source
ORDER BY yoy_change DESC
```

**Common pitfall:** Y-column name must match the SQL alias exactly (e.g., `yoy_change` not `total_admits`).

---

### 6. Combo — Bar + Line (`combo`)

**Purpose:** Mixed bar and line from one query. Perfect for showing two metrics with different scales (e.g., volume as bars + rate as line).

**Column Mapping:**
| Field | Value | Notes |
|-------|-------|-------|
| X-axis | `source` | Category dimension |
| Y-axis | `total_admits, hosp_rate` | Multiple Y-columns |
| Series | (empty) | **Must be empty** — do NOT put a metric name here |

**Variant Settings:**
- **Bar Columns (comma-separated):** Column names to render as bars (e.g., `total_admits`). Everything else renders as lines.
- **Dual Y-Axis:** Enable when bar and line have very different scales. Left axis = bars, right axis = lines.

**Supports WAVG aggregation:** For rate metrics, use Weighted Average with a weight column:
- Y #1: `total_admits` → SUM (renders as bars)
- Y #2: `hospitalization_rate` → WAVG, weight = `total_admits` (renders as line)

**Sample Custom SQL:**
```sql
SELECT source,
       SUM(total_admits) AS total_admits,
       ROUND((SUM(hospitalization_rate * total_admits) / NULLIF(SUM(total_admits), 0))::numeric, 2) AS hosp_rate
FROM mv_referral_velocity
WHERE hha_ccn IN %(hha_ccn)s
  AND year::text IN %(year)s
  [[AND ffs_ma IN %(ffs_ma)s]]
GROUP BY source
ORDER BY total_admits DESC
```

---

### 7. Trend + Benchmark (`benchmark`)

**Purpose:** Actual trend line vs a reference/target. Reference can be a static number or a dynamic column from the query.

**Column Mapping:**
| Field | Value | Notes |
|-------|-------|-------|
| X-axis | `year` | Time dimension |
| Y-axis | `provider_rate, national_avg` | Actual + benchmark columns |
| Series | (empty) | Not used |

**Mode A — Static Benchmark:**
- **Benchmark Source:** `Static Value`
- **Benchmark Value:** e.g., `15` (fixed horizontal dashed line)
- **Benchmark Label:** e.g., `Target`

**Mode B — Column Benchmark (recommended):**
- **Benchmark Source:** `Column from Query`
- **Benchmark Column Name:** e.g., `national_avg` (rendered as dashed line)
- **Benchmark Label:** e.g., `National Avg`

**Sample Custom SQL (Provider vs National Average):**
```sql
SELECT year,
       ROUND((SUM(hospitalization_rate * total_admits) / NULLIF(SUM(total_admits), 0))::numeric, 2) AS provider_rate,
       (SELECT ROUND((SUM(r2.hospitalization_rate * r2.total_admits) / NULLIF(SUM(r2.total_admits), 0))::numeric, 2)
        FROM mv_referral_velocity r2
        WHERE r2.year = mv_referral_velocity.year
          [[AND r2.ffs_ma IN %(ffs_ma)s]]) AS national_avg
FROM mv_referral_velocity
WHERE hha_ccn IN %(hha_ccn)s
  AND year::text IN %(year)s
  [[AND ffs_ma IN %(ffs_ma)s]]
GROUP BY year
ORDER BY year
```

---

## Flag System

```
chart_flags.py
├── LINE_FLAGS (28+ flags)
│
├── Primary variant selector
│   └── line_style (select: basic/area/stacked_line/stacked_area/waterfall/combo/benchmark)
│
├── Universal line appearance (show_when: basic/area/stacked_line/stacked_area/benchmark)
│   ├── smooth (boolean, default: False — spline interpolation)
│   ├── show_points (boolean, default: True — circle markers)
│   ├── point_size (number, default: 4, show_when: show_points)
│   ├── line_width (number, default: 2)
│   └── step_type (select: none/start/middle/end)
│
├── Area-specific (show_when: area/stacked_area)
│   ├── area_opacity (number, default: 0.3)
│   └── area_gradient (boolean, default: False)
│
├── Waterfall-specific (show_when: waterfall)
│   ├── wf_positive_color (text, default: #91cc75)
│   ├── wf_negative_color (text, default: #ee6666)
│   ├── wf_total_color (text, default: #5470c6)
│   └── wf_show_connectors (boolean, default: True)
│
├── Combo-specific (show_when: combo)
│   ├── combo_bar_columns (text — comma-separated column names)
│   └── combo_secondary_axis (boolean, default: False — dual Y-axis)
│
├── Benchmark-specific (show_when: benchmark)
│   ├── benchmark_mode (select: static/column)
│   ├── benchmark_value (number, show_when: static)
│   ├── benchmark_label (text, default: 'Target')
│   └── benchmark_column (text, show_when: column)
│
└── Common controls
    ├── show_labels, label_position, number_format
    ├── show_axis_labels, legend_position
    ├── target_line, target_label (reference line for basic/area/stacked)
    └── sort, limit
```

### Data Flow

```
Admin selects line_style in LineStylePicker (Step 1 sub-panel)
  → stored in state.visualFlags.line_style
  → saved to widget.visual_config JSON field
  → _build_echart_option() reads vc.get('line_style', 'basic')
  → Dispatches to _apply_line_variant_flags() → variant-specific builder
  → ECharts option dict returned
  → JSON sent to React → EChartWidget.jsx renders
```

### Two Parallel Code Paths (MUST STAY IN SYNC)

1. **Portal rendering:** `posterra_portal/models/dashboard_widget.py` → `_apply_line_variant_flags()`
   - Called by `_build_echart_option()` when `ct == 'line'`
   - Helper methods: `_build_waterfall_series()`, `_build_combo_series()`, `_build_benchmark_series()`

2. **Builder preview:** `dashboard_builder/services/preview_formatter.py` → `_apply_line_variant_flags()`
   - Called by `_build_echart_preview()` when `chart_type == 'line'`
   - Same helper functions mirrored

Both must produce IDENTICAL ECharts options for the same inputs.

---

## Key Files

| File | Purpose |
|------|---------|
| `dashboard_builder/services/chart_flags.py` | LINE_FLAGS definition (28+ flags) |
| `posterra_portal/models/dashboard_widget.py` | `_apply_line_variant_flags()` — portal rendering |
| `dashboard_builder/services/preview_formatter.py` | `_apply_line_variant_flags()` — builder preview |
| `dashboard_builder/static/src/designer/src/components/builder/LineStylePicker.jsx` | Variant selector sub-panel with 7 SVG icons + config sections |
| `dashboard_builder/static/src/designer/src/components/builder/ChartTypePicker.jsx` | Renders LineStylePicker when chartType='line' |
| `dashboard_builder/static/src/designer/src/components/builder/CustomSqlEditor.jsx` | SQL help text for line variants |
| `dashboard_builder/static/src/designer/src/components/builder/ColumnMapper.jsx` | AGG_FUNCS includes WAVG with weight column dropdown |
| `dashboard_builder/services/query_builder.py` | WAVG → `SUM(col*weight)/NULLIF(SUM(weight),0)` expression |

---

## Choosing the Right Variant

| Goal | Best Variant | X-axis | Y-axis | Series |
|------|-------------|--------|--------|--------|
| Compare metrics over time | **Basic Line** | year | metric1, metric2 (SUM) | (empty) |
| Show volume trend | **Area** | year | total_admits (SUM) | (empty) |
| Composition by category over time | **Stacked Area** | year | total_admits (SUM) | ffs_ma or source |
| Cumulative trends | **Stacked Line** | year | total_admits (SUM) | ffs_ma or source |
| Year-over-year change breakdown | **Waterfall** | source | yoy_change | (empty) |
| Volume + rate on same chart | **Combo** | source | total_admits (SUM), hosp_rate (WAVG) | (empty) |
| Actual vs target/benchmark | **Benchmark** | year | provider_rate, national_avg | (empty) |

### When to Use Series Column vs Multiple Y-Columns

| Data Format | Example | Series Column | Y-Columns |
|-------------|---------|---------------|-----------|
| **Wide** (each metric is a column) | `year, admits, episodes` | (empty) | `admits, episodes` |
| **Long** (metric name in a column) | `year, ffs_ma, total_admits` | `ffs_ma` | `total_admits` |

---

## Weighted Average (WAVG) Aggregation

Available in the Visual Builder for any chart type. Computes `SUM(value × weight) / SUM(weight)` instead of simple `AVG`.

**When to use:** Rate/ratio metrics where rows have different volumes (e.g., hospitalization_rate weighted by total_admits).

**Visual Builder setup:**
1. Select Y-column → choose WAVG radio button
2. Weight column dropdown appears → select the weight column
3. QueryBuilder generates: `ROUND((SUM(col * weight) / NULLIF(SUM(weight), 0))::numeric, 4)`

---

## How to Add a New Line Variant

1. **chart_flags.py:** Add value to `line_style` options + any variant-specific flags
2. **preview_formatter.py:** Add handler in `_apply_line_variant_flags()` or new `_build_*_series()` function
3. **dashboard_widget.py:** Mirror the same logic (MUST match)
4. **LineStylePicker.jsx:** Add entry to `LINE_STYLES` array + SVG icon component + ICON_MAP entry + settings panel
5. **CustomSqlEditor.jsx:** Add SQL help entry if SQL shape differs

---

## Common Pitfalls

- **Duplicate year in SQL:** Don't put the same column as both X-axis AND Series — creates one line per unique value instead of one line per Y-column
- **Stacking rates:** Never use Stacked Line/Area with non-additive metrics (rates, percentages). Stacking 15% + 20% = 35% is meaningless
- **Y-column name mismatch:** SQL alias must exactly match the Y-column name in column mapping (e.g., `yoy_change` not `total_admits`)
- **Empty series for combo/waterfall:** Series column must be empty for combo and waterfall — they use multiple Y-columns, not series breaks
- **WAVG without weight:** Selecting WAVG aggregation without choosing a weight column causes save to fail. Always select a weight column from the dropdown
- **Type mismatch in CTE:** When using `year::text IN %(year)s` in a CTE, cast MAX result back to `::int` for arithmetic (`cur_year - 1`)

---

## Backward Compatibility

When `visual_config` is empty (widgets created before line variants):
- `line_style` defaults to `'basic'` → standard straight lines
- `show_points=True`, `line_width=2` → circle markers with 2px lines
- No area fill, no stacking, no waterfall
- **Output is identical to the old basic line chart behavior**
