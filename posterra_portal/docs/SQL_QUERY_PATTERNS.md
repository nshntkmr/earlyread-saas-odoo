# SQL Query Patterns for Dashboard Widgets

## Overview

Every dashboard widget falls into one of three categories based on SQL complexity.
The filter builder handles Categories A and B. Category C is fully manual.

**Rules that apply to ALL categories:**
- Multi-select filters use `IN %(param)s` with Python tuples — never `ANY()`
- Single-select filters use `= %(param)s` with a scalar string
- If a filter value is None or empty, the clause is skipped entirely
- Never write `IN NULL` or `IN ()` — the builder/controller prevents this
- Always use `%(param)s` named parameters — never string interpolation

---

## Category A: Simple Aggregation (~60% of widgets)

**Use when:** No year comparison, no cross-HHA logic, just filter and aggregate.

**Widget config:**
- Schema Source: select the MV (e.g. `Total admits`)
- Exclude from {where_clause}: *(leave empty)*

**The builder auto-generates all WHERE clauses from the page's Context Filters.**
Only columns that exist in the selected Schema Source get a clause.

---

### Bar Chart

```sql
SELECT hha_state, SUM(total_admits) AS total_admits
FROM mv_hha_kpi_summary
WHERE {where_clause}
GROUP BY hha_state
ORDER BY total_admits DESC
```

- X Column: `hha_state`
- Y Column(s): `total_admits`

---

### Line Chart

```sql
SELECT year, SUM(total_episodes) AS total_episodes
FROM mv_hha_kpi_summary
WHERE {where_clause}
GROUP BY year
ORDER BY year
```

- X Column: `year`
- Y Column(s): `total_episodes`

---

### Pie / Donut Chart

```sql
SELECT ffs_ma AS payer_type, SUM(total_admits) AS total_admits
FROM mv_hha_kpi_summary
WHERE {where_clause}
GROUP BY ffs_ma
```

- X Column: `payer_type`
- Y Column(s): `total_admits`

---

### Radar / Spider Chart

```sql
SELECT
  SUM(total_admits) AS admits,
  SUM(total_episodes) AS episodes,
  AVG(star_rating) AS star_rating
FROM mv_hha_kpi_summary
WHERE {where_clause}
```

- X Column: metric names (derived from column aliases)
- Y Column(s): `admits,episodes,star_rating`

---

### KPI Card (simple — no comparison)

```sql
SELECT SUM(total_admits) AS value
FROM mv_hha_kpi_summary
WHERE {where_clause}
```

- X Column: `value`
- Y Column(s): *(empty)*

---

### KPI Card -- Dynamic Icon (simple — no comparison)

```sql
SELECT SUM(total_admits) AS value
FROM mv_hha_kpi_summary
WHERE {where_clause}
```

- X Column: `value`
- Y Column(s): *(empty)*

---

### Data Table

```sql
SELECT hha_ccn, hha_name, hha_city, hha_state,
       SUM(total_admits) AS total_admits,
       SUM(total_episodes) AS total_episodes
FROM mv_hha_kpi_summary
WHERE {where_clause}
GROUP BY hha_ccn, hha_name, hha_city, hha_state
ORDER BY total_admits DESC
```

- X Column: `hha_ccn`
- Y Column(s): `hha_name,hha_city,hha_state,total_admits,total_episodes`

---

### Scatter Chart

```sql
SELECT hha_ccn,
       SUM(total_admits) AS admits,
       AVG(star_rating) AS rating
FROM mv_hha_kpi_summary
WHERE {where_clause}
GROUP BY hha_ccn
```

- X Column: `admits`
- Y Column(s): `rating`

---

### Gauge / Meter

```sql
SELECT AVG(star_rating) AS value
FROM mv_hha_kpi_summary
WHERE {where_clause}
```

- X Column: `value`
- Y Column(s): *(empty)*

---

### Heatmap

```sql
SELECT hha_state, ffs_ma, SUM(total_admits) AS value
FROM mv_hha_kpi_summary
WHERE {where_clause}
GROUP BY hha_state, ffs_ma
ORDER BY hha_state, ffs_ma
```

- X Column: `ffs_ma`
- Y Column(s): `value`
- Series Column: `hha_state`

---

## Category B: Year-over-Year Comparison (~25% of widgets)

**Use when:** Widget compares current year vs prior year (YoY KPIs, trend arrows).

**Widget config:**
- Schema Source: select the MV (e.g. `Total admits`)
- Exclude from {where_clause}: `year`

**The builder handles all non-year filters. Year logic is hand-written because
it must include the prior year row that the user did NOT select.**

**Auto-derived parameters (available in any widget SQL):**
- `%(_year_single)s` — the selected year as integer (e.g. `2024`), or `NULL` if "All" or multiple years
- `%(_year_prior)s` — selected year minus 1 (e.g. `2023`), or `NULL` if "All" or multiple years

**Three runtime cases:**
1. Single year selected (e.g. 2024): `_year_single=2024`, `_year_prior=2023`
2. All years selected: both `NULL` — sum everything, no comparison arrow
3. Oldest year selected (e.g. 2020 with no 2019 data): prior_year returns 0, frontend shows N/A

---

### Standard Year Block (copy this into every YoY widget)

```sql
-- Paste this WHERE block after {where_clause} for any YoY widget:
  AND (
    '__all__' IN %(year)s
    OR year::text IN %(year)s
    OR (%(_year_prior)s IS NOT NULL AND year = %(_year_prior)s)
  )
```

This block:
- When "All" is selected: `'__all__' IN %(year)s` is true, all years pass
- When specific year(s) selected: `year::text IN %(year)s` matches them
- Always includes the prior year row for comparison: `year = %(_year_prior)s`

---

### KPI Card -- Dynamic Icon (YoY comparison)

```sql
SELECT
  SUM(CASE
    WHEN %(_year_single)s IS NOT NULL AND year = %(_year_single)s THEN total_admits
    WHEN %(_year_single)s IS NULL THEN total_admits
    ELSE 0
  END) AS current_year,
  SUM(CASE
    WHEN %(_year_single)s IS NOT NULL AND year = %(_year_prior)s THEN total_admits
    ELSE 0
  END) AS prior_year
FROM mv_hha_kpi_summary
WHERE {where_clause}
  AND (
    '__all__' IN %(year)s
    OR year::text IN %(year)s
    OR (%(_year_prior)s IS NOT NULL AND year = %(_year_prior)s)
  )
```

- X Column: `current_year`
- Y Column(s): `prior_year`
- Exclude from {where_clause}: `year`

---

### KPI Card (YoY comparison)

```sql
SELECT
  SUM(CASE
    WHEN %(_year_single)s IS NOT NULL AND year = %(_year_single)s THEN total_episodes
    WHEN %(_year_single)s IS NULL THEN total_episodes
    ELSE 0
  END) AS current_year,
  SUM(CASE
    WHEN %(_year_single)s IS NOT NULL AND year = %(_year_prior)s THEN total_episodes
    ELSE 0
  END) AS prior_year
FROM mv_hha_kpi_summary
WHERE {where_clause}
  AND (
    '__all__' IN %(year)s
    OR year::text IN %(year)s
    OR (%(_year_prior)s IS NOT NULL AND year = %(_year_prior)s)
  )
```

- X Column: `current_year`
- Y Column(s): `prior_year`
- Exclude from {where_clause}: `year`

---

### Bar Chart (YoY side-by-side)

```sql
SELECT
  hha_state,
  SUM(CASE WHEN year = %(_year_single)s THEN total_admits ELSE 0 END) AS current_year,
  SUM(CASE WHEN year = %(_year_prior)s THEN total_admits ELSE 0 END) AS prior_year
FROM mv_hha_kpi_summary
WHERE {where_clause}
  AND (
    '__all__' IN %(year)s
    OR year::text IN %(year)s
    OR (%(_year_prior)s IS NOT NULL AND year = %(_year_prior)s)
  )
GROUP BY hha_state
ORDER BY current_year DESC
```

- X Column: `hha_state`
- Y Column(s): `current_year,prior_year`
- Exclude from {where_clause}: `year`

---

### Line Chart (YoY trend)

```sql
SELECT
  year,
  SUM(total_admits) AS total_admits
FROM mv_hha_kpi_summary
WHERE {where_clause}
  AND (
    '__all__' IN %(year)s
    OR year::text IN %(year)s
    OR (%(_year_prior)s IS NOT NULL AND year = %(_year_prior)s)
  )
GROUP BY year
ORDER BY year
```

- X Column: `year`
- Y Column(s): `total_admits`
- Exclude from {where_clause}: `year`

---

### Gauge / Meter (YoY)

```sql
SELECT
  AVG(CASE
    WHEN %(_year_single)s IS NOT NULL AND year = %(_year_single)s THEN star_rating
    WHEN %(_year_single)s IS NULL THEN star_rating
    ELSE NULL
  END) AS current_value,
  AVG(CASE
    WHEN %(_year_single)s IS NOT NULL AND year = %(_year_prior)s THEN star_rating
    ELSE NULL
  END) AS prior_value
FROM mv_hha_kpi_summary
WHERE {where_clause}
  AND (
    '__all__' IN %(year)s
    OR year::text IN %(year)s
    OR (%(_year_prior)s IS NOT NULL AND year = %(_year_prior)s)
  )
```

- Exclude from {where_clause}: `year`

---

## Category C: Complex / Manual SQL (~15% of widgets)

**Use when:** Cross-HHA ranking, leakage matrix, JOINs across MVs,
or any SQL that doesn't map cleanly to a single MV with standard filters.

**Widget config:**
- Schema Source: *(leave empty — no builder)*
- Exclude from {where_clause}: *(not applicable)*
- Do NOT use `{where_clause}` in the SQL

**Write all WHERE clauses manually using `IN %(param)s` for multi-select
and `= %(param)s` for single-select.**

---

### Cross-HHA Ranking (Data Table)

```sql
SELECT
  r.hha_ccn,
  r.hha_name,
  r.total_admits,
  r.rank
FROM (
  SELECT
    hha_ccn,
    hha_name,
    SUM(total_admits) AS total_admits,
    RANK() OVER (ORDER BY SUM(total_admits) DESC) AS rank
  FROM mv_hha_kpi_summary
  WHERE hha_state IN %(hha_state)s
    AND year::text IN %(year)s
    AND (%(ffs_ma)s = '' OR LOWER(%(ffs_ma)s) = 'all' OR ffs_ma = %(ffs_ma)s)
  GROUP BY hha_ccn, hha_name
) r
WHERE r.hha_ccn IN %(hha_ccn)s
   OR r.rank <= 10
ORDER BY r.rank
```

---

### Scatter (Cross-HHA comparison)

```sql
SELECT
  a.hha_ccn,
  a.hha_name,
  a.total_admits,
  b.star_rating
FROM (
  SELECT hha_ccn, hha_name, SUM(total_admits) AS total_admits
  FROM mv_hha_kpi_summary
  WHERE hha_state IN %(hha_state)s
    AND year::text IN %(year)s
  GROUP BY hha_ccn, hha_name
) a
JOIN (
  SELECT hha_ccn, AVG(star_rating) AS star_rating
  FROM mv_hha_quality_summary
  WHERE year::text IN %(year)s
  GROUP BY hha_ccn
) b ON a.hha_ccn = b.hha_ccn
```

---

### Heatmap (state x payer)

```sql
SELECT
  hha_state,
  ffs_ma,
  SUM(total_admits) AS value
FROM mv_hha_kpi_summary
WHERE hha_ccn IN %(hha_ccn)s
  AND year::text IN %(year)s
  AND (%(ffs_ma)s = '' OR LOWER(%(ffs_ma)s) = 'all' OR ffs_ma = %(ffs_ma)s)
GROUP BY hha_state, ffs_ma
ORDER BY hha_state, ffs_ma
```

---

## Common Bugs and How to Avoid Them

### Bug 1: `ANY()` with tuples
**Wrong:** `hha_ccn = ANY(%(hha_ccn)s)`
**Right:** `hha_ccn IN %(hha_ccn)s`

psycopg2 renders Python tuples as `('a', 'b')` which works with `IN` but fails
with `ANY()` (needs PostgreSQL array `{'a','b'}`).

### Bug 2: Comparing tuple to string
**Wrong:** `%(hha_ccn)s = '' OR hha_ccn IN %(hha_ccn)s`
**Right:** `'__all__' IN %(hha_ccn)s OR hha_ccn IN %(hha_ccn)s`

When multi-select is "All", the controller sends `('__all__',)` not `''`.
Comparing a tuple to `''` causes PostgreSQL error.

### Bug 3: Casting year for IN
**Wrong:** `year IN %(year)s` (when year is integer column, values are strings)
**Right:** `year::text IN %(year)s`

Multi-select values are always strings from URL params. Cast the integer column
to text for comparison.

### Bug 4: NULL in CASE WHEN with integer cast
**Wrong:** `CASE WHEN %(year)s ~ '^\d+$' THEN %(year)s::int ELSE NULL END`
**Right:** Use `%(_year_single)s` and `%(_year_prior)s` (pre-computed by controller)

PostgreSQL evaluates both branches for type-checking. Use the pre-derived
`_year_single` / `_year_prior` parameters instead of inline casting.

### Bug 5: Missing Schema Source
**Error:** "A Schema Source is required when using {where_clause} in SQL."
**Fix:** Set the Schema Source field on the widget to the MV it queries.

### Bug 6: Single-select filter with IN
**Wrong:** `ffs_ma IN %(ffs_ma)s` (when ffs_ma is single-select, value is a scalar)
**Right:** `ffs_ma = %(ffs_ma)s` or use `{where_clause}` (builder detects single vs multi)

The builder auto-detects: multi-select filters get `IN`, single-select get `=`.
In Category C manual SQL, check the filter's Multi-select toggle.

### Bug 7: Empty result with "All" selected
**Wrong:** No sentinel check — WHERE clause filters everything out
**Right:** Always check for `'__all__'` sentinel:
```sql
('__all__' IN %(hha_ccn)s OR hha_ccn IN %(hha_ccn)s)
```

### Bug 8: Prior year not included in results
**Wrong:** Only filtering by selected year — prior year row excluded
**Right:** Always include prior year in WHERE:
```sql
AND (
  '__all__' IN %(year)s
  OR year::text IN %(year)s
  OR (%(_year_prior)s IS NOT NULL AND year = %(_year_prior)s)
)
```

### Bug 9: Double filtering with {where_clause}
**Wrong:** Using `{where_clause}` AND manually writing `hha_ccn IN %(hha_ccn)s`
**Right:** Let `{where_clause}` handle it, or use Exclude to skip specific params

If the builder generates a clause for `hha_ccn` and you also write one manually,
the data gets double-filtered. Use Exclude from {where_clause} for any param
you handle manually.

### Bug 10: Forgetting to exclude year in YoY widgets
**Wrong:** `{where_clause}` generates `year IN %(year)s` AND manual year block also filters
**Right:** Set Exclude from {where_clause}: `year`

The builder's year clause only includes selected years, not prior year.
YoY widgets must exclude year from the builder and handle it manually.

---

## Quick Reference: Widget Config Checklist

| Widget Type | Category | Schema Source | Exclude | Notes |
|-------------|----------|--------------|---------|-------|
| Bar (simple) | A | Set to MV | *(empty)* | |
| Bar (YoY) | B | Set to MV | `year` | Two Y columns: current_year, prior_year |
| Line (simple) | A | Set to MV | *(empty)* | |
| Line (YoY) | B | Set to MV | `year` | Include prior year in WHERE |
| Pie / Donut | A | Set to MV | *(empty)* | |
| Radar / Spider | A | Set to MV | *(empty)* | |
| KPI Card (simple) | A | Set to MV | *(empty)* | |
| KPI Card (YoY) | B | Set to MV | `year` | current_year + prior_year columns |
| KPI Dynamic Icon | B | Set to MV | `year` | Same as KPI Card YoY |
| Data Table | A | Set to MV | *(empty)* | |
| Scatter | A or C | Depends | Depends | C if cross-HHA JOINs needed |
| Gauge / Meter | A or B | Set to MV | `year` if YoY | |
| Heatmap | A or C | Depends | Depends | C if multi-MV |
| Ranking Table | C | *(empty)* | N/A | No {where_clause}, manual SQL |
| Leakage Matrix | C | *(empty)* | N/A | No {where_clause}, manual SQL |

---

## Filter Parameter Reference

| Filter | URL Param | Multi-select | Controller Value | SQL Usage |
|--------|-----------|-------------|-----------------|-----------|
| Provider | `hha_ccn` | Yes | Tuple: `('017014', '017020')` or `('__all__',)` | `IN %(hha_ccn)s` |
| State | `hha_state` | Yes | Tuple: `('AL', 'FL')` or `('__all__',)` | `IN %(hha_state)s` |
| County | `hha_county` | Yes | Tuple or `('__all__',)` | `IN %(hha_county)s` |
| City | `hha_city` | Yes | Tuple or `('__all__',)` | `IN %(hha_city)s` |
| Year | `year` | Yes | Tuple: `('2024',)` or `('__all__',)` | `year::text IN %(year)s` |
| Payer | `ffs_ma` | No | String: `'MA'`, `'FFS'`, or `'all'` | `= %(ffs_ma)s` |

**Auto-derived year parameters:**
| Param | Type | When single year | When "All" / multiple |
|-------|------|------------------|-----------------------|
| `%(_year_single)s` | int or NULL | `2024` | `NULL` |
| `%(_year_prior)s` | int or NULL | `2023` | `NULL` |
