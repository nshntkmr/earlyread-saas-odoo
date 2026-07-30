# Configuring a drill-capable choropleth map (state → county)

This is **admin configuration guidance**, not code — nothing here is hardcoded in
the platform. A single map scope option can render **state** rows by default and
**county** rows when the user drills into a state, all from one level-aware SQL.

## 1. Scope option geo metadata (Widget Controls → the option row, map widgets only)

| Field | Value for a drill-capable option |
|-------|----------------------------------|
| **Map level** (`default_geo_level`) | `State` — renders the national state view first |
| **Allow county** (`allowed_geo_levels`) | ✓ (stores `state,county`) |
| **Drill state → county** (`supports_drill`) | ✓ |

A **county-first** tab instead sets Map level = `County` (no drill needed — it opens
on national counties). The backend `_effective_map_level()` is the single source of
truth: a `_map_level=county` request is honored **only** when county is allowed and
drill is supported (or the default is already county); anything else falls back to
state and the drill scope params are dropped.

## 2. Visual config keys (Style step)

- `choropleth_renderer` = `svg_albers_usa` (drill is SVG-Albers only)
- `choropleth_join_column` = the SQL column holding the region key
- `choropleth_metric_column` = the SQL column holding the metric
- `choropleth_level` = `state` (base level for the non-scoped fallback)

The join key must match the committed geometry (see `GEO_README.md`):
**state → 2-letter `STUSPS` (e.g. `CA`); county → 5-digit `GEOID` (e.g. `06037`)**.

## 3. The level-aware SQL

Three params are injected by the platform (never type them into filters):

- `%(_map_level)s` — `'state'` or `'county'` (resolved & validated server-side)
- `%(_drill_state_code)s` — 2-letter code of the drilled state (county level only)
- `%(_drill_state_fips)s` — 2-digit FIPS of the drilled state (county level only)

Wrap the drill filter in `[[ ... ]]` so it is **dropped** automatically at state
level (when `_drill_state_code` is absent) — this is the same optional-clause
mechanism used elsewhere. The join column must emit `STUSPS` at state level and the
5-digit county FIPS at county level, under **one consistent alias**.

```sql
-- TEMPLATE — replace table/column names with your dataset's.
-- Emits STUSPS at state level, 5-digit county FIPS at county level.
SELECT
    CASE WHEN %(_map_level)s = 'county'
         THEN county_geoid                  -- already 5-digit, or lpad(fips,5,'0')
         ELSE state_cd                      -- 2-letter STUSPS
    END                              AS region_key,     -- = choropleth_join_column
    SUM(rx_count)                    AS metric          -- = choropleth_metric_column
FROM incyte_market_metrics
WHERE 1 = 1
  -- Your normal page filters go here as usual, e.g.:
  [[ AND drug_class = %(drug_class)s ]]
  -- Drill filter: applies ONLY at county level (dropped at state level):
  [[ AND state_cd = %(_drill_state_code)s ]]
GROUP BY
    CASE WHEN %(_map_level)s = 'county' THEN county_geoid ELSE state_cd END
ORDER BY region_key
```

### Incyte specifics

- **County colors by Rx volume** — Rx is complete at county grain. Benes/Claims are a
  "less count" lower bound at county, so avoid using them for the county fill.
- **Penetration is state-grain only** — a Penetration option should be `State` level
  with **drill OFF** (no meaningful county rollup). Use a separate Rx-volume option
  for the county/drill experience.
- Prevalence is a 2024 snapshot; filter to a single `DATA_SOURCE` grain to avoid the
  3× inflation (see the Incyte data notes).

## 4. How it flows at runtime

1. User clicks a state → `AlbersChoroplethMap` fires `onDrill({code, fips, name})`.
2. `WidgetGrid.handleMapDrill` refetches `/api/v1/widget/<id>/data` with
   `_map_level=county`, `_drill_state_code`, `_drill_state_fips`, and the active
   `_scope_option_id`.
3. The route validates the params (format-checked, map-only) and injects them into
   `portal_ctx['sql_params']`; `execute_option_sql` resolves the effective level and
   drops the drill scope if it's not actually county.
4. The option SQL returns that state's county rows; the payload's `geo_level` is
   overwritten to `county` / `GEOID`; the renderer loads county geometry, filters to
   the drilled state's counties (`STATEFP`), and refits. A breadcrumb offers "← USA".
