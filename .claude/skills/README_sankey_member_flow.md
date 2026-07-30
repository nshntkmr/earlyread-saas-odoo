# Sankey Member Flow Widget

This note documents the custom `sankey_member_flow` chart type added for the UL Humana MA Alignment Engine.

## Purpose

`sankey_member_flow` renders a monthly member-flow timeline similar to the Humana reference image:

- Green lane: New Alignments
- Blue lane: Still Active
- Purple lane: Re-captured
- Red lane: Disaligned
- Starting block: Starting aligned members / 12M active context

This is separate from the existing generic `sankey` chart. Existing Sankey, KPI, table, and ECharts widgets should keep their previous behavior.

## Admin Chart Type

In the Dashboard Builder, select:

```text
Sankey Member Flow
```

Technical chart type key:

```text
sankey_member_flow
```

Use Custom SQL mode.

## Expected SQL Columns

The widget expects one row per month and reads these column names directly:

```text
YEAR_MONTH
Date
NEW_ALIGNEMENT
STILL_ACTIVE
RECAPTURED
DISALIGNED
12_month_active
```

Column names are tolerant for common aliases, but the above names are preferred because they match the ClickHouse tables.

## Recommended ClickHouse SQL

```sql
SELECT
    YEAR_MONTH,
    Date,
    sum(NEW_ALIGNEMENT) AS NEW_ALIGNEMENT,
    sum(STILL_ACTIVE) AS STILL_ACTIVE,
    sum(RECAPTURED) AS RECAPTURED,
    sum(DISALIGNED) AS DISALIGNED,
    sum(`12_month_active`) AS `12_month_active`
FROM shared.UL_HUMANA_KPI_Member_FLOW
WHERE (has(%(Month)s, '__all__') OR toString(YEAR_MONTH) IN %(Month)s)
  AND (has(%(PROVIDER_NAME)s, '__all__') OR PROVIDER_NAME IN %(PROVIDER_NAME)s)
  AND (has(%(MARKET)s, '__all__') OR MARKET IN %(MARKET)s)
GROUP BY YEAR_MONTH, Date
ORDER BY YEAR_MONTH
```

## Builder Column Mapping

The renderer uses the returned SQL columns directly, but the builder still asks for mappings.

Use:

```text
X-axis column: Date
Y-axis columns: NEW_ALIGNEMENT,STILL_ACTIVE,RECAPTURED,DISALIGNED,12_month_active
Series column: leave blank
```

## Filters

The SQL above assumes these page filter params:

```text
%(Month)s
%(PROVIDER_NAME)s
%(MARKET)s
```

All three filters can be multi-select and can include the `__all__` sentinel.

## Build Steps

After code changes, build both frontend bundles:

```powershell
cd C:\Users\nisha\Odoo_Dev\posterra_portal\static\src\react
npm run build

cd C:\Users\nisha\Odoo_Dev\dashboard_builder\static\src\designer
npm run build
```

Then restart Odoo so Python chart type metadata reloads.

## Files Changed

Main portal/runtime files:

```text
posterra_portal/models/dashboard_widget.py
posterra_portal/static/src/react/src/components/WidgetGrid.jsx
posterra_portal/static/src/react/src/components/widgets/MemberFlowTimeline.jsx
```

Dashboard builder/admin files:

```text
dashboard_builder/models/dashboard_widget_definition.py
dashboard_builder/models/dashboard_widget_template.py
dashboard_builder/controllers/designer_api.py
dashboard_builder/services/chart_flags.py
dashboard_builder/services/preview_formatter.py
dashboard_builder/static/src/designer/src/components/builder/ChartTypePicker.jsx
dashboard_builder/static/src/designer/src/components/builder/CustomSqlEditor.jsx
dashboard_builder/static/src/designer/src/components/builder/LivePreview.jsx
dashboard_builder/static/src/designer/src/components/WidgetLibrary.jsx
dashboard_builder/static/src/designer/src/components/TemplateGallery.jsx
```

## Regression Notes

- Existing `sankey` remains the generic ECharts Sankey chart.
- `sankey_member_flow` is opt-in and only runs when the admin selects that chart type.
- The chart requires Custom SQL because it needs multiple monthly KPI measure columns.
- The backend sorts by `YEAR_MONTH` if returned, so month order is protected even if the SQL result is accidentally unordered.
