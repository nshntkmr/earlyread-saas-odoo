# AI SQL Assistant — Best Practices & Schema Design Guide

## What This Document Covers

1. How the AI SQL Assistant works (architecture)
2. How to use it effectively (prompting, modes, workflow)
3. Schema design for accurate AI responses (column intelligence)
4. Table/MV design patterns for healthcare analytics
5. Common pitfalls and how to avoid them

---

## 1. How the AI SQL Assistant Works

### Architecture

```
User types prompt in Dashboard Builder
    |
    v
AiSqlEditor.jsx (React) --POST--> /dashboard/designer/api/ai-generate
    |
    v
designer_api.py --> AiSqlGenerator (Python)
    |
    +--> assemble_context()
    |      - Primary table columns + metadata
    |      - Related tables + join paths
    |      - Page filters + helper params
    |      - Chart type column requirements
    |
    +--> Claude Sonnet 4.6 (Azure AI Foundry)
    |      - System prompt with 10 SQL rules
    |      - User message with schema context
    |      - Structured output tool (sql, x_column, y_columns, warnings)
    |
    v
Returns: SQL query + column mappings + explanation
```

### Five Layers of Context Sent to Claude

| Layer | What | Source | Example |
|-------|------|--------|---------|
| 1. System Prompt | SQL rules, rate computation patterns, param syntax | `ai_sql_generator.py` | "NEVER AVG pre-computed rates" |
| 2. Column Intelligence | Roles, pairs, descriptions, domain notes | `dashboard_schema.py` column metadata | `ip_timely_count` role=ratio_numerator, paired_with=ip_referral_count |
| 3. Table Relationships | JOINs between tables | Schema Source relations | `mv_hha_quality JOIN hha_provider ON hha_ccn` |
| 4. Page Filters | Available parameters + multiselect flags | `dashboard.page.filter` records | `year` (multi), `ffs_ma` (single), `hha_ccn` (multi) |
| 5. Chart Requirements | Expected output columns | `SQL_COLUMN_REQUIREMENTS` dict | KPI expects `value [, prior_value]` |

### Four Modes

| Mode | When Used | What Happens |
|------|-----------|-------------|
| `suggest` | Auto-fires when source + chart type selected | Claude generates 10 natural language suggestions based on schema |
| `generate` | User types a prompt or clicks a suggestion | Claude generates full SQL + column mappings |
| `fix` | SQL execution fails with PostgreSQL error | Claude receives the error + original SQL, returns corrected query |
| `refine` | User wants to modify existing SQL | Claude receives current SQL + refinement prompt, returns updated query |

---

## 2. How to Use It Effectively

### Step 1: Select the Right Data Source

Before typing a prompt, select a **Schema Source** (materialized view). This gives the AI:
- All available columns with types and business descriptions
- Column roles (what can be summed, what's a rate, what's a dimension)
- Paired columns for rate computations

**Without a schema source, the AI is flying blind.**

### Step 2: Write Good Prompts

**Bad prompts** (vague, no context):
```
Show me some data
Make a chart
Give me KPIs
```

**Good prompts** (specific, mentions metrics and dimensions):
```
Total episode count for the selected year vs. prior year, showing
year-over-year growth as a KPI with trend arrow

Timely access rate by state for the top 10 states, as a horizontal bar chart

Monthly admits trend over the last 3 years with a benchmark line at 500
```

**Great prompts** (mentions aggregation strategy, edge cases):
```
Hospitalization rate computed as SUM(hospitalization_count) /
NULLIF(SUM(episode_count), 0) * 100 for selected filters,
compared to the prior year value. Handle multi-year selection
by summing all selected years.

Payer mix donut showing FFS vs MA as percentage of total admits,
with the smaller segment having a minimum 5% visual slice
```

### Prompt Tips

| Tip | Why |
|-----|-----|
| Name the metric explicitly | "timely access rate" not "quality metric" |
| Specify aggregation | "SUM of total_admits" not "count of admits" |
| Mention comparison | "vs prior year" or "vs state benchmark" |
| State the chart type context | "as a KPI card" or "for a bullet gauge" |
| Mention edge cases | "handle multi-year", "handle All providers" |

### Step 3: Review Generated SQL

Always check:
1. **Column mappings** — X column (label/value) and Y columns (data series) are correct
2. **WHERE clause** — uses `{where_clause}` or `[[...]]` optional clauses
3. **Rate computations** — uses `SUM(num) / NULLIF(SUM(denom), 0)`, not `AVG(rate)`
4. **Year handling** — uses `%(_year_single)s` / `%(_year_prior)s` helpers for YoY
5. **Preview data** — click Preview to verify actual numbers

### Step 4: Use Fix & Refine

- **Fix**: If preview shows a PostgreSQL error, click Fix. The AI receives the exact error message and corrects it.
- **Refine**: If the query works but needs adjustment, type a refinement prompt like "add a benchmark column" or "filter to FFS only". The AI builds on the existing SQL.

### Workflow Summary

```
1. Select Schema Source (MV)
2. Select Chart Type
3. Review smart suggestions OR type your own prompt
4. Click Generate
5. Review SQL + column mappings
6. Click Preview to test
7. If error → Fix
8. If needs changes → Refine
9. Save widget
```

---

## 3. Schema Design for Accurate AI Responses

### Column Intelligence Fields

Every column in a Schema Source can have these metadata fields configured in
**Settings > Schema Sources > [Source] > Columns** tab:

| Field | What It Does | Impact on AI |
|-------|-------------|-------------|
| `column_role` | Semantic role | Determines how AI aggregates the column |
| `paired_column_id` | Links numerator to denominator | AI builds correct rate formulas |
| `never_avg` | Flag: never use AVG() | Prevents incorrect averaging of pre-computed rates |
| `description` | Business meaning | AI understands what the column represents |
| `domain_notes` | Special rules/caveats | AI adds correct filters or warnings |

### Column Roles (Critical)

| Role | Meaning | AI Behavior | Examples |
|------|---------|------------|---------|
| `additive_measure` | Safe to SUM directly | `SUM(col)` | `total_admits`, `episode_count`, `unique_patients` |
| `ratio_numerator` | Numerator of a rate | `SUM(col) / NULLIF(SUM(paired), 0)` | `ip_timely_count`, `hospitalization_count` |
| `ratio_denominator` | Denominator of a rate | Used in division, never standalone | `ip_referral_count`, `total_episodes` |
| `pre_computed_rate` | Already a rate/percentage | NEVER AVG, uses numerator pair | `timely_access_pct`, `rehospitalization_rate` |
| `weight` | For weighted averaging | Used as weight in weighted formulas | `case_mix_weight` |
| `dimension` | Grouping/filtering column | GROUP BY, X-axis | `year`, `hha_state`, `ffs_ma` |
| `identifier` | Entity key | WHERE clause only, never aggregated | `hha_ccn`, `hha_npi` |

### Auto-Detection Rules

Columns are auto-classified when first imported. You can override manually.

| Pattern | Auto-Detected Role |
|---------|-------------------|
| Ends with `_pct`, `_rate`, `_ratio` | `pre_computed_rate` + `never_avg=True` |
| Starts with `avg_` | `pre_computed_rate` + `never_avg=True` |
| Ends with `_count` | `ratio_numerator` |
| Exact match: `id`, `hha_ccn`, `hha_npi` | `identifier` |
| Starts with `total_` or `sum_` | `additive_measure` |
| Numeric (int/float) default | `additive_measure` |
| Text/date | `dimension` |

### Paired Columns (Critical for Rates)

When you have a pre-computed rate like `timely_access_pct`, you MUST configure:

```
timely_access_pct
  role: pre_computed_rate
  never_avg: True
  paired_column: ip_timely_count  <-- tells AI to use this numerator

ip_timely_count
  role: ratio_numerator
  paired_column: ip_referral_count  <-- tells AI to use this denominator

ip_referral_count
  role: ratio_denominator
```

**What the AI generates from this:**
```sql
-- CORRECT (from column intelligence):
SUM(ip_timely_count) / NULLIF(SUM(ip_referral_count), 0) AS timely_access

-- WRONG (without column intelligence):
AVG(timely_access_pct) AS timely_access  -- INCORRECT! AVG of rates is statistically wrong
```

### Business Descriptions

Add `description` to every column. The AI uses these to understand what metrics mean.

**Good descriptions:**
```
ip_timely_count: "Inpatient referrals served within 48 hours of admission"
total_admits: "Total home health admissions (unduplicated per episode)"
hha_alwd: "Total Medicare allowed amount in dollars"
```

**Bad descriptions (too vague):**
```
ip_timely_count: "count"
total_admits: "admits"
hha_alwd: "amount"
```

### Domain Notes

Add `domain_notes` for special rules the AI must follow:

```
hha_alwd:
  domain_notes: "Always $0 for MA records — filter to ffs_ma='FFS' when using this column"

star_rating:
  domain_notes: "Scale is 1-5, not percentage. Only available for years 2022+"

hha_ccn:
  domain_notes: "CCNs starting with '9' are test/demo data — exclude in production queries"
```

---

## 4. Table/MV Design Patterns for Healthcare Analytics

### Pattern 1: Pre-Aggregated Summary MV

Best for KPI cards, bar charts, line trends.

```sql
CREATE MATERIALIZED VIEW mv_hha_kpi_summary AS
SELECT
    hha_ccn,           -- identifier
    hha_state,         -- dimension
    hha_county,        -- dimension
    hha_city,          -- dimension
    year,              -- dimension
    ffs_ma,            -- dimension

    -- Additive measures (safe to SUM)
    total_admits,
    total_episodes,
    unique_patients,

    -- Ratio pairs (numerator + denominator)
    ip_timely_count,        -- ratio_numerator, paired with ip_referral_count
    ip_referral_count,      -- ratio_denominator

    hospitalization_count,  -- ratio_numerator, paired with episode_count
    episode_count,          -- ratio_denominator

    -- Pre-computed rates (NEVER AVG)
    timely_access_pct,      -- pre_computed_rate, paired with ip_timely_count
    rehospitalization_rate  -- pre_computed_rate, paired with hospitalization_count

FROM ...
```

**Key design rules:**
1. **Always include both numerator AND denominator** for every rate
2. **Include the pre-computed rate too** — useful for display but AI knows not to AVG it
3. **Include all dimension columns** that filters might use (state, county, city, year, payer)
4. **One row per granularity level** — typically per HHA + year + payer type
5. **No NULLs in dimension columns** — use empty string or 'Unknown' instead

### Pattern 2: Quality Metrics with Benchmarks

Best for gauge charts, RAG status, comparison cards.

```sql
CREATE MATERIALIZED VIEW mv_hha_quality AS
SELECT
    hha_ccn,
    year,

    -- Your metrics (ratio pairs)
    ip_timely_count,
    ip_referral_count,
    timely_access_pct,

    -- Benchmark columns (from peer/national data)
    state_avg_timely_access,    -- dimension or weight
    national_avg_timely_access, -- dimension or weight
    peer_group_rank,            -- additive_measure

    star_rating                 -- pre_computed_rate (scale 1-5, not %)

FROM ...
```

### Pattern 3: Financial/Claims MV

Best for revenue KPIs, cost analysis.

```sql
CREATE MATERIALIZED VIEW mv_hha_financial AS
SELECT
    hha_ccn,
    year,
    ffs_ma,

    -- Dollar amounts (additive)
    total_hha_alwd,          -- additive_measure
    total_hha_paid,          -- additive_measure
    total_supply_cost,       -- additive_measure

    -- Volume (additive)
    claim_count,             -- additive_measure
    visit_count,             -- additive_measure

    -- Per-unit (pre-computed, NEVER AVG)
    avg_cost_per_episode,    -- pre_computed_rate, paired with total_hha_alwd
    avg_visits_per_episode   -- pre_computed_rate, paired with visit_count

FROM ...
```

**Critical:** Add `domain_notes` on financial columns:
```
total_hha_alwd: "Always $0 for MA records — filter to ffs_ma='FFS'"
```

### Column Naming Conventions

| Convention | Role | Examples |
|-----------|------|---------|
| `total_*`, `sum_*` | additive_measure | `total_admits`, `sum_revenue` |
| `*_count` | ratio_numerator | `ip_timely_count`, `visit_count` |
| `*_pct`, `*_rate`, `*_ratio` | pre_computed_rate | `timely_access_pct`, `rehospitalization_rate` |
| `avg_*` | pre_computed_rate | `avg_cost_per_episode` |
| `hha_*` (text) | dimension/identifier | `hha_state`, `hha_ccn` |
| `*_id`, `*_ccn`, `*_npi` | identifier | `hha_id`, `source_npi` |

Following these conventions enables **auto-detection** — columns are automatically classified
when imported into a Schema Source, reducing manual configuration.

---

## 5. Common Pitfalls

### Pitfall 1: No Schema Source Selected

**Problem:** AI generates generic SQL with guessed column names.
**Fix:** Always select a Schema Source before generating SQL.

### Pitfall 2: Missing Column Pairs

**Problem:** AI uses `AVG(timely_access_pct)` instead of the correct weighted formula.
**Fix:** Configure `paired_column_id` on rate columns pointing to their numerator,
and on numerator columns pointing to their denominator.

### Pitfall 3: No Column Descriptions

**Problem:** AI doesn't know what `hha_alwd` means, generates wrong aggregation.
**Fix:** Add business descriptions to every column:
`"Total Medicare allowed amount in dollars (FFS claims only)"`

### Pitfall 4: Missing Domain Notes

**Problem:** AI doesn't know that financial columns are $0 for MA records.
**Fix:** Add domain_notes: `"Always $0 for MA records — filter to ffs_ma='FFS'"`

### Pitfall 5: Rate Columns Without never_avg Flag

**Problem:** AI computes `AVG(rate)` which is statistically incorrect for weighted rates.
**Fix:** Set `never_avg=True` on all pre-computed rate columns. Auto-detected for
columns ending in `_pct`, `_rate`, `_ratio` or starting with `avg_`.

### Pitfall 6: Vague Prompts

**Problem:** "Show me quality data" generates an overly broad query.
**Fix:** Be specific: "Timely access rate by state for FFS patients in 2024,
computed as SUM(ip_timely_count) / NULLIF(SUM(ip_referral_count), 0)"

### Pitfall 7: Not Using Fix Mode

**Problem:** User manually edits SQL to fix errors, losing AI context.
**Fix:** Click the Fix button. The AI receives the exact PostgreSQL error
and corrects the query while preserving the original intent.

### Pitfall 8: Year Handling in KPI Cards

**Problem:** `year = %(_year_prior)s` crashes when multiple years selected.
**Fix:** Always guard with `%(_year_single)s IS NOT NULL` or use `{where_clause}`
with the year excluded. See SQL_QUERY_PATTERNS.md Category B.

---

## 6. Schema Source Setup Checklist

When creating a new Schema Source (materialized view):

- [ ] All dimension columns have `role: dimension`
- [ ] All identifier columns have `role: identifier`
- [ ] All summable columns have `role: additive_measure`
- [ ] All rate columns have `role: pre_computed_rate` + `never_avg: True`
- [ ] All rate numerators have `role: ratio_numerator` + `paired_column: denominator`
- [ ] All rate denominators have `role: ratio_denominator`
- [ ] Every column has a business `description` (not just the column name)
- [ ] Financial columns have `domain_notes` about payer restrictions
- [ ] Scale-based columns (star ratings) have `domain_notes` about valid ranges
- [ ] Test data exclusion rules are in `domain_notes` (e.g., CCNs starting with '9')
- [ ] Related tables are linked with proper join columns

---

## 7. Quick Reference: Chart Type Column Requirements

| Chart Type | Expected SQL Output Columns |
|-----------|---------------------------|
| `bar` | `category, value1 [, value2, ...]` |
| `line` | `x_value, y_value1 [, y_value2, ...]` |
| `pie` / `donut` | `label, value` |
| `gauge` (arc variants) | `value` |
| `gauge` (bullet) | `metric_name, actual_value, benchmark_value [, benchmark_label]` |
| `gauge` (RAG) | `value [, red_threshold, green_threshold, badge_text]` |
| `gauge` (multi-ring) | `metric_name, metric_value [, metric_max]` |
| `kpi` (stat card) | `value [, prior_value]` |
| `kpi` (sparkline) | `value [, prior_value, sparkline_data]` |
| `kpi` (progress) | `value, target` |
| `kpi` (comparison) | `value, prior_value [, current_label, prior_label]` |
| `kpi` (RAG status) | `value` |
| `table` | `col1, col2, col3, ...` |
| `scatter` | `x_value, y_value` |
| `heatmap` | `x_category, y_category, intensity` |
| `radar` | `indicator, score1 [, score2, ...]` |
