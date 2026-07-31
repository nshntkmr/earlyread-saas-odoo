# Incyte "Market Insights" Dashboard — Design Reference

> Working design doc for the Incyte Market Insights page on the Posterra config-driven
> platform (Odoo + React, ClickHouse-backed). Captures the data model, the number-inflation
> rules, sentinel handling, the filter design, filter dependencies, and the KPI grain
> decisions agreed in the design discussion.
>
> Last updated: 2026-06-30. App: `incyte` (group-access — no HHA scoping).
> Source CSVs profiled: `C:\Users\nisha\Downloads\Incyte Dashboard\sparx_main_table.csv`,
> `sparx_prevalence.csv`. All numbers below verified against that data.

---

## 1. Data sources (ClickHouse, database `shared`)

| Table | Grain / purpose | Notes |
|---|---|---|
| `sparx_incyte_drug_claims` | Medicaid pharmacy claims, **3 grains stacked** via `DATA_SOURCE` | 2022-H1 … 2024-H2. The main table. |
| `sparx_incyte_prevalence` | Beneficiary prevalence (market size), **3 grains by NULL pattern** | **2024 only**, no `DATA_SOURCE`, no `half_year`. |
| `sparx_incyte_penetration_state` | Pre-agg penetration by state | Built `WHERE STATE_CD!='NATIONAL'` → National-free. Powers State map + Whitespace scatter. |
| `sparx_incyte_penetration_county` | Pre-agg penetration by county | `county!=''`, has FIPS. Powers County map. |
| `sparx_incyte_national_plan_totals` | National totals per plan | Built `WHERE PLAN_NAME IS NOT NULL` → **~8% short of grand total** (fine for ranking, wrong for headline). Powers Top MCO Plans. |
| `sparx_incyte_kpi_summary` ⭐ | **NEW (2026-07-01)** Pre-agg KPI table w/ explicit suppression flags (`IS_BENES_SUPPRESSED`/`IS_CLAIMS_SUPPRESSED`), precomputed `TREATED_STATES`/`TREATED_COUNTIES` (national period constants), and a new `TOTAL_DAYS_SUPPLY` measure | Serves the KPI strip, **both** map levels (has STATE + FIPS_COUNTY), YoY trend, Top MCO Plans, Plan-mix. **Grain-pin TBD — see §9 check #1.** Supersedes `penetration_state/_county` + `national_plan_totals` for most widgets. |
| `sparx_incyte_prevalence_plan` ⭐ | **NEW (2026-07-01)** Prevalence at STATE×PLAN×year — market size (`TOTAL_BENE_PREVALENT`) + treated measures in one row | Serves Whitespace + State×Plan detail + penetration-by-plan **without a join**. **State-rollup rows TBD — see §9 check #3** (needed for de-duplicated state market size; do NOT `SUM` plan rows). No `half_year` → annual. |

### `sparx_incyte_drug_claims` — the 3 grains (same ~16.48M Rx, re-cut 3 ways)

| `DATA_SOURCE` | Rows | Dims populated | Σ TOTAL_QTY (all yrs) |
|---|---|---|---|
| `county_level` | 8,571 | STATE_CD, county, PLAN_NAME (PLAN_ID blank) | 16,479,112 |
| `mco_plan_id` | 2,631 | STATE_CD, PLAN_NAME, **PLAN_ID** (county blank) | 16,479,274 |
| `overall_national` | 1,413 | `STATE_CD='NATIONAL'`, PLAN_NAME (county + PLAN_ID blank) | 16,479,286 |

### `sparx_incyte_prevalence` — 3 grains by NULL pattern

| PLAN_NAME | county | Grain | Σ TOTAL_BENE_PREVALENT |
|---|---|---|---|
| set | set | state × county × plan | 3,272,505 |
| NULL | set | state × county (geo) | 518,435 |
| NULL | NULL | state (geo) | 66,738 |

### Measure × grain availability (CORRECTED 2026-06-30 — data-model update)

Claims & Beneficiaries are NOT at county; county carries only Rx (+ market size from prevalence). Penetration is therefore state-level only (no county benes for the numerator). Plan IDs are now fully mapped to each plan.

| Measure | County | State | State×Plan / Plan-ID | National |
|---|:--:|:--:|:--:|:--:|
| Rx Quantity (`TOTAL_QTY`) | ✓ full | ✓ | ✓ | ✓ |
| Claims (`TOTAL_CLAIMS`) | ≈ less count | ✓ | ✓ | ✓ |
| Beneficiaries (`TOTAL_BENES`) | ≈ less count | ✓ | ✓ | ✓ |
| Market size (prevalence) | ✓ | ✓ | — | ✓ |
| Penetration (treated÷prevalent) | lower-bound only | ✓ | — | ✓ |

**Refined 2026-06-30 (per data owner's availability matrix):** Claims & Beneficiaries DO exist at county but as a **"less count" lower bound** (heavy CMS cell suppression), not absent. Rx Quantity is full at every level. Plan IDs are now fully mapped to each plan.

**Consequences:** Penetration is presented at **state level** (county penetration would only be a lower bound; keep it simple). Map county fills = **Volume (Rx, full)** + Market size; county **tooltips show Benes/Claims as a "~ less count"** lower bound. Claims/Benes KPIs: when a County is selected, show a county-level **lower-bound** value badged "less count · county lower bound" (not the full state figure, not "N/A"). Treated Counties (count of Rx-bearing counties) valid. Whitespace stays state-level. `penetration_county` pre-agg can still be built but its treated numerator is a lower bound — label accordingly. **There is no MCO-vs-FFS / payer-class field in the data** — the "Payer-class mix" widget was removed and replaced with **"Plan mix over time"** (top plans' share of Rx by half-year, which the data supports).

---

## 2. Cardinal rule — never inflate

1. **`drug_claims` is ONE universe stored 3×.** Summing across `DATA_SOURCE` = exactly **3.0×** (49,437,672 vs 16.48M). **Every widget must pin exactly one `DATA_SOURCE`.** There is no FY/ALL rollup — the partitions are alternate full views, not additive parts.
2. **`prevalence` is a UNION of 3 grains** (no `DATA_SOURCE` column). Unpinned `SUM(TOTAL_BENE_PREVALENT)` ≈ **5.8×**. Pin one NULL-pattern per widget. **State geo ≠ Σ county geo** (independent populations — AK 32 vs 2,153; CA 12,641 vs 977). Never roll county up to state.
3. **`TOTAL_QTY` is grain-insensitive** (0.001% spread). **`TOTAL_CLAIMS` / `TOTAL_BENES` are NOT** — finer grain suppresses more (county −17.5% claims / −25.4% benes vs national).
4. **Join geography on `FIPS_COUNTY` (5-digit), never county name** — 201 county names recur across states.
5. **Treated Counties** = `COUNT(DISTINCT (STATE_CD, county))` (or FIPS pair). Bare `COUNT(DISTINCT county)` undercounts **−31.8%** (960 vs 1,408).

---

## 3. Sentinel & NULL handling

- **`Suppress` → NULL (done at data layer).** Data owner ran `UPDATE PLAN_NAME=NULL WHERE PLAN_NAME='Suppress'` and `PLAN_ID=NULL WHERE PLAN_ID=''` on both tables (columns made Nullable). Effect: `SELECT DISTINCT` drops NULL → **plan dropdowns are clean off `drug_claims`, no view needed** — but TOTAL_QTY/CLAIMS/BENES stay on the rows so **totals are intact**.
  - ⚠ **Do NOT add `PLAN_NAME IS NOT NULL` to KPI totals** — it drops the ~8% formerly-Suppress quantity. Use it only on plan-attributed breakdowns.
- **`NATIONAL` sentinel still present.** `overall_national` rows have `STATE_CD='NATIONAL'` and **`STATE_NAME='National'`** (never blank) → a `STATE_NAME` dropdown off `drug_claims` **leaks "National"**. Fix: source the State filter from `sparx_incyte_penetration_state` (National-free), or null `STATE_NAME` for National.
- **Grand-total KPIs must read from `drug_claims` (`overall_national`)**, NOT `national_plan_totals` (which is ~8% short by construction).

---

## 4. Filter design (main page)

Six filters, all single config-driven `dashboard.page.filter` records. None use HHA machinery
(`is_provider_selector` / `scope_to_user_hha` / `auto_fill_from_hha` all OFF).

| Filter | `param_name` | Recommended source · value col | Multi | Search | Default | Notes |
|---|---|---|---|---|---|---|
| Year | `year` | `drug_claims` · `year` | – | – | **Latest** | numeric sort; prevalence widgets are 2024-only |
| Half-year | `half_year` | `drug_claims` · `half_year` | ✓ | – | **Latest** | {H1, H2}; no rollup |
| State | `STATE_NAME` | **`penetration_state`** · `STATE_NAME` | ✓ | ✓ | All | excludes `National` sentinel |
| County | `county` | **`penetration_county`** · `FIPS_COUNTY` (label `county`) | ✓* | ✓ | All | value = FIPS avoids name collisions; cascade child of State |
| MCO Plan | `PLAN_NAME` | `drug_claims` · `PLAN_NAME` | ✓ | ✓ | All | `Suppress` is NULL → auto-clean |
| ~~Plan ID~~ | — | **DROPPED as a filter** | — | — | — | see note below — surfaced as a *widget*, not a filter |

\* County is currently single-select in the configured page; multi-select is optional.

**Plan ID — dropped as a filter (decided 2026-06-30).** PLAN_ID only exists in the `mco_plan_id` grain (NULL in `county_level`), so when County was selected the same-table sibling constraint dragged the Plan ID option query into `county_level` → all NULL → "No matches". On top of that: one PLAN_NAME maps to many PLAN_IDs, the IDs are opaque and Excel-corrupted (e.g. `3.61237E+11`), and there's no UI way to hide Plan ID when County is chosen. Picking a PLAN_NAME already sums all its IDs, and State + Plan Name pins a per-state instance — so the filter bought nothing. **Instead, the plan-ID breakdown is a WIDGET** (table/bar at `mco_plan_id` grain, driven by the Plan Name filter, NO county bind): `SELECT PLAN_NAME, PLAN_ID, STATE_NAME, SUM(TOTAL_QTY), SUM(TOTAL_CLAIMS), SUM(TOTAL_BENES) ... WHERE DATA_SOURCE='mco_plan_id' AND PLAN_ID IS NOT NULL [[year/half/state/plan binds]] GROUP BY PLAN_NAME, PLAN_ID, STATE_NAME ORDER BY total_qty DESC`. Pick a plan → see its IDs/states/volumes. **Upstream data fix needed:** PLAN_ID scientific-notation corruption.

**Open config fixes vs current state:**
- Set **Year** and **Half-year** `default_strategy = Latest` (currently `Static` with no default → loads empty).
- Repoint **State → `penetration_state`** and **County → `penetration_county`** (value `FIPS_COUNTY`). Plan Name / Year / Half-year stay on `drug_claims`.
- **Remove the Plan ID filter and the `Plan Name → Plan ID` dependency edge.**
- `Hide "All"` toggles are a **no-op** while `Include "All"` is OFF (harmless).
- Empty multiselect → widget SQL must use optional-bind `[[ ... ]]` (or `(%(p)s IS NULL OR col IN %(p)s)`), else `IN ()` errors.

**Mixing sources tradeoff:** State/County on the penetration tables + Plan/Year on `drug_claims` means the automatic same-source option-narrowing won't span them — but the explicit cascade edges still work cross-source (child table carries `STATE_CD`/`STATE_NAME`).

**Not buildable / not a filter:**
- **ZIP** — no ZIP/ZCTA column exists (FIPS only). Needs a crosswalk or drop from mockup.
- **Metric** — a display selector (which measure the map colors by), not a row filter.

---

## 5. Filter dependencies (acyclic — no cycles)

Rule: **only "downhill" edges (parent → child), never child → parent.** A tree can't contain a
cycle. The platform allows cycles (visited-set guard prevents infinite loops) but we avoid them.

| When this changes… | …refresh this | Propagation | Reset Value |
|---|---|---|---|
| State | County | Required | Yes |
| State | Plan Name *(optional)* | Optional | No |

(The `Plan Name → Plan ID` edge is removed — Plan ID is no longer a filter.)

Do **not** add `County → State`, `Plan ID → Plan Name`, or `Plan Name → State` — any upward edge creates a loop. Option *narrowing* already happens via the same-table sibling constraint; these edges add the interactive reset-on-change behaviour.

---

## 6. KPI cards — grain decision & SQL

> **⚠ Partially superseded 2026-07-01** — the KPI strip now reads `sparx_incyte_kpi_summary`
> (single pre-agg table w/ suppression flags), not `drug_claims`/`mco_plan_id`. Treated
> States/Counties use `MAX()` of precomputed national constants, **frozen to `year`+`half_year`**
> (they never bind geo/plan). See **§9**. The `mco_plan_id` reasoning below is kept for history
> and still applies to the Plan-ID breakdown widget.

**Decision:** pin the plan/geo KPI cards to a FIXED `DATA_SOURCE='mco_plan_id'` (not dynamic).
- `TOTAL_QTY` is identical across grains; `mco_plan_id` keeps State + Plan + Plan ID drilling and the number stays consistent (no grain-jump). Dynamic grain would need Incyte-specific dim→grain logic in the controller = hardcoding (rejected).
- **National plan performance = the same cards** with geo empty + a plan selected (sums the plan across its states). **No separate widget needed.**
- Cost: claims/benes run −2.8% / −6.3% below the `overall_national` row (up to **−21% benes** for plans spread across many states, e.g. ANTHEM across 23 states). Acceptable under the "approx, suppressed" labels.
- County selection does **not** move these 4 cards (county only in `county_level`) → annotate.

```sql
-- Cards 1–4: Total Rx Quantity / Total Claims / Total Beneficiaries / Treated States
SELECT
    SUM(TOTAL_QTY)            AS rx_qty,
    SUM(TOTAL_CLAIMS)         AS claims,          -- approx, suppressed
    SUM(TOTAL_BENES)          AS benes,           -- approx, suppressed
    COUNT(DISTINCT STATE_CD)  AS treated_states   -- mco_plan_id has no 'NATIONAL'
FROM shared.sparx_incyte_drug_claims
WHERE DATA_SOURCE = 'mco_plan_id'
  AND year IN %(year)s AND half_year IN %(half_year)s
  [[ AND STATE_NAME IN %(STATE_NAME)s ]]
  [[ AND PLAN_NAME  IN %(PLAN_NAME)s ]]
  [[ AND PLAN_ID    IN %(PLAN_ID)s ]]
-- no county bind: county doesn't exist in this grain
```

```sql
-- Cards 4 & 5: Treated States / Treated Counties
-- SUPERSEDED 2026-07-01: no longer a county_level drug_claims widget.
-- Read precomputed NATIONAL period constants from kpi_summary via MAX().
-- FROZEN to national: bind ONLY year + half_year, never geo/plan.
-- Robust to the kpi_summary grain question (same constant on every row incl any rollups).
SELECT MAX(TREATED_STATES) AS treated_states       -- Card 4
FROM shared.sparx_incyte_kpi_summary
WHERE year = %(year)s [[ AND half_year IN %(half_year)s ]];

SELECT MAX(TREATED_COUNTIES) AS treated_counties   -- Card 5
FROM shared.sparx_incyte_kpi_summary
WHERE year = %(year)s [[ AND half_year IN %(half_year)s ]];
-- Multi-period selection → MAX returns the peak period (accepted, not a union).
```

Future upgrade for exact national-plan benes → a dedicated "plan scorecard" widget reading `overall_national`.

---

## 7. Per-widget grain map + annotations

"Honest annotation" strategy is fine for grain/precision/snapshot caveats — but it **cannot**
fix (a) summing across `DATA_SOURCE`, or (b) a widget showing a different *scope* than the filter set.

| Widget | Grain / source | Annotation to write |
|---|---|---|
| Total Rx Quantity | `mco_plan_id` | — (exact) |
| Total Claims / Beneficiaries | `mco_plan_id` | "Approx — small counts suppressed; state/plan level, not affected by county selection." |
| Treated States | `mco_plan_id` | "Distinct states with reported volume." |
| Treated Counties | `county_level` | "Distinct counties with reported volume; suppressed excluded." |
| Map · Volume (State/County) | `penetration_*` or `drug_claims` per view | "Suppressed cells excluded." |
| Map · Market Size / Penetration | prevalence (2024) | "Market size = 2024 snapshot, not per-year. Penetration = treated ÷ 2024 market." |
| Year-over-year trend | `mco_plan_id`, ignores Year by design | "Shows all periods — not affected by the Year filter." |
| Top MCO plans | `national_plan_totals` | "Ranks named plans; suppressed-plan rows excluded." |
| Whitespace (prevalence vs treated) | mixed | "Prevalence is a 2024 snapshot; treated reflects filters." |
| Detail table (State × Plan) | `mco_plan_id` + prevalence | "Prevalent is a 2024 state-level figure shown per row — do not sum this column." |

---

## 8. Decisions log & open questions

**Decided:**
- Per-widget grain pinning; **no** page-level grain-selector ("Explore") page. (Heterogeneous widgets don't re-cut in unison; grain is implied by filters.)
- KPI strip on `mco_plan_id`; national plan performance via the existing cards.
- `Suppress` nulled at data layer; State sourced from `penetration_state` to drop `National`.

**Open:**
- ZIP filter — no backing column. Drop, crosswalk, or defer.
- Prevalence state-vs-county inconsistency — confirm with data owner which is authoritative for Penetration views (they won't reconcile to each other).
- Whether the detail-table `Prevalent` column should be visually de-emphasised (shown once per state) in addition to the "do not sum" note.
- County multi-select vs single-select.

---

## 9. Update 2026-07-01 — two new pre-aggregated tables

The data owner added two clean serving tables that collapse most of the old 5-table mess and
remove the worst inflation/suppression pain.

### 9.1 `sparx_incyte_kpi_summary`
Columns: `STATE_CD, STATE_NAME, FIPS_STATE, FIPS_COUNTY, county, PLAN_NAME(Null), year, half_year,
TOTAL_BENES(Null), IS_BENES_SUPPRESSED, TOTAL_CLAIMS(Null), IS_CLAIMS_SUPPRESSED, TOTAL_QTY,
TOTAL_DAYS_SUPPLY, TREATED_STATES, TREATED_COUNTIES`.

Wins: explicit **suppression flags** (the old "≈ less count / county lower bound" caveat is now a
readable flag), **precomputed Treated States/Counties**, a **new `TOTAL_DAYS_SUPPLY`** measure
(adherence/days-of-therapy KPIs possible), and STATE + FIPS_COUNTY in one table → **one source
drives both map levels + drill**.

### 9.2 `sparx_incyte_prevalence_plan`
Columns: `STATE_CD, STATE_NAME, PLAN_NAME(Null), year, TOTAL_BENES(Null), IS_BENES_SUPPRESSED,
TOTAL_CLAIMS(Null), IS_CLAIMS_SUPPRESSED, TOTAL_QTY, TOTAL_DAYS_SUPPLY, TOTAL_BENE_PREVALENT`.
Grain = state × plan × year (no `half_year` → annual). Market size + treated in one row →
Whitespace + State×Plan detail + penetration-by-plan **without a join**.

### 9.3 Widget coverage (with the new tables)
~11 of 12 widgets are served cleanly by the two new tables. Still needs the old `drug_claims`:
- **Plan-ID breakdown widget** — neither new table carries `PLAN_ID`; keep `drug_claims`/`mco_plan_id`.

### 9.4 DECIDED — Treated States / Treated Counties
`TREATED_STATES`/`TREATED_COUNTIES` are **national period constants** (how many states/counties
were active across the whole US in that half-year, repeated on every row). Both cards read
`MAX(...)` from `kpi_summary`, **bind only `year` + `half_year`, and intentionally ignore
State/County/Plan** (a frozen national context tile). SQL in §6. Label them as national
(e.g. "48 · states active nationally, H1 2024") so a filtered user doesn't misread the frozen
number. This **removes** the old separate `county_level` Treated-Counties widget. Robust to §9.5
check #1 (the constant is identical on every row, incl any rollup rows).

### 9.5 OPEN — two grain checks gate the SUM-based widgets
The `SUM`-based cards (Rx/Claims/Benes) and the maps aggregate, so they depend on grain.

**Check #1 — RESOLVED 2026-07-01: single-grain, SUM freely.** No rollup/subtotal rows — every SUM
widget aggregates with filter binds, no NULL-pattern pinning. Accepted consequence: Claims/Benes
aggregate up from the finest grain and **undercount (worst at county)** as suppressed cells drop —
annotate via `SUM(IS_BENES_SUPPRESSED)`. Guard: confirm no stray `STATE_CD='NATIONAL'`/all-plan
subtotal row (would re-inflate). *(Original query kept below for the record.)*
```sql
SELECT (PLAN_NAME IS NULL) AS plan_null, (county='') AS county_blank,
       (STATE_CD IN ('','NATIONAL')) AS state_rollup, count() rows, sum(TOTAL_QTY) qty
FROM shared.sparx_incyte_kpi_summary
WHERE year=2024 AND half_year='H1'
GROUP BY plan_null, county_blank, state_rollup ORDER BY qty DESC;
```
Read: several same-magnitude buckets → stacked (pin `(0,0,0)` detail for KPI, state-total bucket for
state map, county-total bucket for county map). Only `(0,0,0)` → single-grain. Secondary payoff:
if single (finest) grain, aggregated Claims/Benes undercount (suppression) → annotate via
`SUM(IS_BENES_SUPPRESSED)` "N cells suppressed".

**Check #3 — does `prevalence_plan` carry state-rollup (`PLAN_NAME IS NULL`) rows?** Needed for honest
state market size — you must NOT `SUM(TOTAL_BENE_PREVALENT)` across plans (a bene attributed to
multiple plans double-counts; e.g. CA true 10,000 but AETNA 6k + BCBS 5k + MEDICAID 4k = 15k).
```sql
SELECT (PLAN_NAME IS NULL) AS plan_null, count(),
       sum(TOTAL_BENE_PREVALENT) prev, sum(TOTAL_QTY) qty
FROM shared.sparx_incyte_prevalence_plan GROUP BY plan_null;
SELECT min(year), max(year), count(DISTINCT year) FROM shared.sparx_incyte_prevalence_plan;
```
Read: `plan_null=1` exists → use those rows for state market size. Only `plan_null=0` → keep old
`sparx_incyte_prevalence` state-geo rows. `max(year)>2024` → prevalence is now multi-year (upgrade
over the old 2024-only table).

Also verify: NATIONAL sentinel presence in `kpi_summary`
(`SELECT DISTINCT STATE_CD, STATE_NAME ... WHERE STATE_CD IN ('NATIONAL','') OR STATE_NAME='National'`)
→ if present, State dropdown + state map must exclude it. Do **not** `SUM` the `TREATED_*` columns
(they're constants — MAX only).
