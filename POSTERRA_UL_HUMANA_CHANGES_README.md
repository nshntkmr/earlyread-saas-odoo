# UL Humana MA Changes README

This note summarizes the code changes made while configuring the `ulh-humana-ma`
Alignment Engine app.

## 1. Filter Option Sort Setting

### File Changed

`posterra_portal/models/dashboard_page_filter.py`

`posterra_portal/views/page_views.xml`

### What Changed

Added a new per-filter admin field:

```text
Option Sort
```

Available values:

```text
Label (A-Z)
Value / source order
```

### Why

The Month filter uses:

```text
Source Column: YEAR_MONTH
Display Template: {Date}
```

Example values:

```text
202510 -> Oct 2025
202511 -> Nov 2025
202512 -> Dec 2025
202601 -> Jan 2026
```

Before the change, schema-template filter options were always sorted by the
display label. That caused month labels to appear alphabetically:

```text
Apr 2026
Dec 2025
Feb 2026
Jan 2026
```

The new setting allows the Month filter to preserve the SQL/value order from
`YEAR_MONTH`, while existing filters keep their previous alphabetical behavior.

### Backward Compatibility

Default value:

```text
Label (A-Z)
```

This preserves existing behavior for previous apps and filters.

Only filters explicitly set to:

```text
Value / source order
```

will use the new behavior.

### UL Humana Month Filter Setting

For the Alignment Engine Month filter, use:

```text
Source Column: YEAR_MONTH
URL Param: Month
Display Template: {Date}
Template Source: Schema Source
Option Sort: Value / source order
Default Strategy: Latest/last option
Multi-select: On
Include All: On
Searchable: On
```

## 2. ClickHouse Concurrent Query Lock

### File Changed

`posterra_portal/utils/query_executors/clickhouse.py`

### What Changed

Added a per-connection query lock around the cached ClickHouse client.

### Why

When multiple ClickHouse-backed widgets loaded at the same time, ClickHouse
could return:

```text
Attempt to execute concurrent queries within the same session.
Please use a separate client instance per thread/process.
```

This happened because the executor cached one ClickHouse client per connection,
and multiple widgets could use that same client concurrently.

The fix keeps the existing cached-client behavior but serializes query execution
per ClickHouse connection.

### Impacted Consumers

This affects only ClickHouse-backed execution paths:

```text
ClickHouse-backed widgets
ClickHouse schema column discovery
```

PostgreSQL widgets and non-ClickHouse filters are not affected.

## 3. ClickHouse Provider Name Data Issue

The provider filter originally used `PROVIDER_NAME` as the multiselect value.
Provider names containing commas caused incorrect splitting because multiselect
values are stored as CSV strings.

Example problematic value:

```text
Anuradha Kollipara, MD PC
```

This was split into:

```text
Anuradha Kollipara
MD PC
```

Immediate data fix:

```text
Remove commas from provider names before upload.
```

Better long-term design:

```text
Use a provider key or ID as the filter value.
Use PROVIDER_NAME only as the display label.
```

## 4. KPI Query Guidance

Because the Month filter now uses `YEAR_MONTH` as its value, widget SQL should
filter by `YEAR_MONTH`, not by `Date`.

Use the filter param exactly as configured:

```text
%(Month)s
```

Example condition:

```sql
(has(%(Month)s, '__all__') OR toString(YEAR_MONTH) IN %(Month)s)
```

Provider and Market multiselect filters should include the same All support:

```sql
(has(%(PROVIDER_NAME)s, '__all__') OR PROVIDER_NAME IN %(PROVIDER_NAME)s)
(has(%(MARKET)s, '__all__') OR MARKET IN %(MARKET)s)
```

## 5. Verification Performed

Python syntax checks passed for:

```text
posterra_portal/models/dashboard_page_filter.py
posterra_portal/utils/query_executors/clickhouse.py
```

XML parse check passed for:

```text
posterra_portal/views/page_views.xml
```

## 6. Required Runtime Step

Restart or upgrade Odoo after these code changes so the new field is registered
and the updated view is loaded.

