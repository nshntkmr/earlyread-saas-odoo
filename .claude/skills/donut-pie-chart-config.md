# Donut & Pie Chart Configuration — Dashboard Builder Skill

## When This Applies

Use this skill when working on:
- Donut or pie chart variants in the Dashboard Builder
- `_build_echart_option()` pie/donut section in `dashboard_widget.py`
- `_build_echart_preview()` pie/donut section in `preview_formatter.py`
- `DonutStylePicker.jsx` component (variant selection sub-panel with SVG icons)
- Chart flags for pie/donut in `chart_flags.py`
- `visual_config` JSON for donut/pie widgets
- Custom SQL help text per chart type in `CustomSqlEditor.jsx`
- Any new donut/pie variant or flag additions

---

## Architecture Overview

### The 7 Variants

All variants use ECharts `type: 'pie'`. The `chart_type` field stays `'donut'` or `'pie'` — variants are selected via `donut_style` flag in `visual_config` JSON.

| # | Key | Name | ECharts Config | SQL Shape |
|---|-----|------|----------------|-----------|
| 1 | `standard` | Standard Donut | `radius:['40%','70%']` | X=label, Y=value |
| 2 | `nested` | Nested (2 rings) | Two pie series, inner `['0%','30%']` outer `['40%','65%']` | X=parent, Series=child, Y=value |
| 3 | `semi` | Half Donut (180°) | `startAngle:180, endAngle:360` + transparent filler | X=label, Y=value |
| 4 | `rose` | Nightingale Rose | `roseType:'area'` | X=label, Y=value |
| 5 | `label_center` | Center Label | `label.show:false, emphasis.label:{show:true, position:'center'}` | X=label, Y=value |
| 6 | `multi_ring` | Multi-Ring Comparison | Multiple pie series with different `center` positions | X=label, Series=ring_group, Y=value |
| 7 | `pie` | Standard Pie (no hole) | `radius:'70%'` (single value) | X=label, Y=value |

### Flag System

```
chart_flags.py
├── _PIE_DONUT_COMMON (6 flags shared by all variants)
│   ├── show_labels (boolean, default: True)
│   ├── label_position (select: outside/inside, show_when: show_labels)
│   ├── show_percent (boolean, default: False)
│   ├── legend_position (select: left/right/top/bottom/none)
│   ├── sort (select: none/value_desc/value_asc)
│   └── limit (number, default: 0, groups excess as "Other")
│
├── DONUT_FLAGS (5 donut-specific + 6 common = 11 total)
│   ├── donut_style (select: standard/label_center/rounded/semi/rose/nested/multi_ring)
│   ├── rose_type (select: area/radius, show_when: donut_style=rose)
│   ├── inner_radius (text, default: '40%')
│   ├── outer_radius (text, default: '70%')
│   └── center_text (text, for static center hole text)
│
└── PIE_FLAGS (6 common flags only)
```

### Data Flow

```
Admin selects donut_style in DonutStylePicker (Step 1 sub-panel)
  → stored in state.visualFlags.donut_style
  → saved to widget.visual_config JSON field
  → _build_echart_option() reads vc.get('donut_style', 'standard')
  → Builds ECharts option dict based on style
  → echart_override deep-merged on top (escape hatch)
  → JSON sent to React → EChartWidget.jsx renders
```

### Two Parallel Code Paths (MUST STAY IN SYNC)

1. **Portal rendering:** `posterra_portal/models/dashboard_widget.py` → `_build_echart_option()`
   - Reads `self.visual_config`, `self.series_column`
   - Called by `get_portal_data()` for live portal pages

2. **Builder preview:** `dashboard_builder/services/preview_formatter.py` → `_build_echart_preview()`
   - Reads `vc` param (dict), `series_col` from config
   - Called by `/dashboard/designer/api/preview` endpoint

Both must produce IDENTICAL ECharts options for the same inputs.

---

## Key Files

| File | Purpose |
|------|---------|
| `dashboard_builder/services/chart_flags.py` | DONUT_FLAGS, PIE_FLAGS, _PIE_DONUT_COMMON definitions |
| `posterra_portal/models/dashboard_widget.py` | `_build_echart_option()` — portal rendering (lines ~996-1285) |
| `dashboard_builder/services/preview_formatter.py` | `_build_echart_preview()` — builder preview (mirrored logic) |
| `dashboard_builder/static/src/designer/src/components/builder/DonutStylePicker.jsx` | Variant selector sub-panel with SVG icons + config sections |
| `dashboard_builder/static/src/designer/src/components/builder/ChartTypePicker.jsx` | Renders DonutStylePicker when chartType='donut' |
| `dashboard_builder/static/src/designer/src/components/builder/CustomSqlEditor.jsx` | SQL help text per chart type (SQL_COLUMN_HELP constant) |
| `posterra_portal/views/widget_views.xml` | Odoo admin form — series_column visible for donut |

---

## How to Add a New Donut Variant

1. **chart_flags.py:** Add the new value to `donut_style` options list
2. **dashboard_widget.py:** Add `elif donut_style == 'new_variant':` in the switch block
3. **preview_formatter.py:** Mirror the same logic (MUST match)
4. **DonutStylePicker.jsx:** Add entry to `DONUT_STYLES` array with SVG icon + description
5. **CustomSqlEditor.jsx:** Add help entry if SQL shape differs from standard

### How to Add a New Common Flag

1. **chart_flags.py:** Add to `_PIE_DONUT_COMMON` list
2. **dashboard_widget.py:** Read the flag value with `vc.get('flag_name', default)`, apply in option building
3. **preview_formatter.py:** Mirror the same logic
4. No React changes needed — the builder dynamically renders controls from the flag schema

---

## Backward Compatibility

When `visual_config` is empty (all existing widgets created before this feature):
- `donut_style` defaults to `'standard'` → radius `['40%','70%']`
- `show_labels=True`, `label_position='outside'` → labels shown outside
- `legend_position='left'` → `{orient:'vertical', left:'left'}`
- No sort, no limit → SQL order, all slices shown
- **Output is byte-for-byte identical to the old hardcoded code**

---

## Color System

Colors are injected into `option['color']` BEFORE the pie/donut block runs (line ~784). ECharts auto-assigns colors from this array to slices in order.

6 palettes: `healthcare` (teal, default), `ocean` (blue), `warm` (orange), `mono` (grey), `default` (ECharts), `custom` (admin JSON).

For nested donut: inner ring gets first N colors, outer ring continues from there. For multi-ring: all rings share the same palette.

---

## Interactive Behavior

All variants get dim-on-hover by default via `emphasis: {focus: 'self', blurScope: 'series'}`. This is always-on — admin can override via `echart_override` if needed.

Click actions (filter_page, go_to_page, show_details, open_url) work on all variants — handled by `EChartWidget.jsx` generically.

---

## Template for Future Chart Family Skills

This donut/pie implementation establishes the pattern for gauge, heatmap, scatter, radar variants:

1. Define `*_FLAGS` in `chart_flags.py` with common + family-specific flags
2. Add variant builder in `_build_echart_option()` reading `visual_config`
3. Mirror in `preview_formatter.py`
4. Create `*StylePicker.jsx` sub-panel with SVG icons
5. Add SQL help text for the chart type in `CustomSqlEditor.jsx`
6. Create skill file documenting the work
