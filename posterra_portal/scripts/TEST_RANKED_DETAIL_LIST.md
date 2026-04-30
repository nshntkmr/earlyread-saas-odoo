# Ranked Detail List — End-to-End Test Guide (v3: per-element SQL + Mode B)

## What changed since your "all 2024" bug

The old design forced ONE detail SQL to drive both the tile charts and the peer sub-list — impossible when tiles want time-series for the clicked row while the sub-list wants peers for the current year. Now each tile AND the sub-list can have its OWN optional SQL. Plus, Mode B (Different SQL Per Option) now gives each toggle button its own complete master layout + detail config.

Two new capabilities in Step 6 (Detail Config):
- **Per-tile "Own SQL" toggle** — each tile can fetch its own data
- **Per-sublist "Own SQL" toggle** — the sub-list can fetch its own data
- Shared SQL in Section B is still there — used as fallback when a tile/sublist has no own SQL

Plus Mode B support in steps 4–6: when Widget Controls uses "Different SQL Per Option", an OptionTabBar appears so admin can configure each toggle (FFS/MA/ALL) independently.

---

## Prerequisites

1. Restart Odoo: `python odoo-bin -c odoo.conf -u posterra_portal -u dashboard_builder`
2. Open Dashboard Builder → **+ Create Widget**

---

## Step 1 — Chart Type
Click **"Ranked List"**.

## Step 2 — Widget Controls

| Field | Value |
|-------|-------|
| Mode | Toggle / Dropdown |
| UI Style | Toggle Buttons |
| Toggle Query Mode | **Same SQL, Different Parameter** *(Mode A — simplest test first)* |
| Scope SQL Param | `ffs_ma` |

Options:
| Label | Value | Icon |
|-------|-------|------|
| FFS | `FFS` | `fa-users` |
| MA | `MA` | `fa-medkit` |
| ALL | *(empty)* | `fa-globe` |

> **Later:** you can flip this to "Different SQL Per Option" and configure each tab independently. We'll cover that at the end.

## Step 3 — Master Data Source (Custom SQL)

```sql
SELECT
    hha_ccn,
    hha_brand_name,
    hha_rating,
    COALESCE(bd_priority_tier_overall, 'Unrated') AS priority_tier,
    CONCAT('CCN ', hha_ccn, ' · ', hha_city, ', ', hha_state_cd) AS subtitle_line,
    JSON_BUILD_ARRAY(
        COALESCE(admits_2022, 0),
        COALESCE(admits_2023, 0),
        COALESCE(admits_2024, 0),
        COALESCE(admits_2025, 0)
    )::text AS admits_trend,
    JSON_BUILD_ARRAY(
        COALESCE(admits_2022, 0),
        COALESCE(admits_2023, 0),
        COALESCE(admits_2024, 0)
    )::text AS admits_inline_bars,
    hha_admits AS total_admits,
    CASE WHEN state_hha_admits > 0
         THEN ROUND(100.0 * hha_admits / state_hha_admits, 1)
         ELSE 0 END AS market_share_pct
FROM mv_hha_final_inhome
WHERE year = 2024
  [[ AND ffs_ma = %(ffs_ma)s ]]
  [[ AND hha_state_cd IN %(hha_state)s ]]
ORDER BY hha_admits DESC NULLS LAST
LIMIT 15
```

Test Query with `ffs_ma=FFS`. 15 rows × 9 columns.

## Step 4 — Master Row Layout

- Rank: ✓ Numbers
- Primary Name: `hha_brand_name`
- Badge: ✓ Column=`priority_tier`, Color `#10b981`
- Subtitle: ✓ Column=`subtitle_line`
- Sparkline: ✓ Column=`admits_trend`, Variant=Line, Color=Auto
- Inline mini-chart: ✓ Column=`admits_inline_bars`, Type=Bar, Size=Small
- Primary Metric: Column=`total_admits`, Number, 0 decimals
- Secondary: ✓ Column=`market_share_pct`, Percentage, 1 decimal, Suffix=`%`
- Row actions: ✓ Navigation arrow, ✓ Expand chevron (External link optional)

## Step 5 — Filters & Actions

- **Click Action** = `Go to another page`
  - Target Page Key: `agency_comparison`
  - Pass clicked value as: `hha_ccn`
- **External Link** (if enabled): URL template = `https://www.medicare.gov/care-compare/details/home-health/{value}`, Open in new tab

## Step 6 — Detail Config (NEW architecture — per-element SQL)

### A. Row Key
`hha_ccn`

### B. Shared Detail SQL (optional fallback)

You can leave this EMPTY if every tile and the sub-list will have its own SQL. Or set it as a fallback — any tile or sub-list without its own SQL will use this one.

For this test, paste the peers query here (so the sub-list uses it by default):

```sql
SELECT
    hha_ccn AS peer_ccn,
    hha_brand_name AS peer_name,
    CONCAT('CCN ', hha_ccn, ' · ', hha_city, ', ', hha_state_cd) AS peer_subtitle,
    JSON_BUILD_ARRAY(
        COALESCE(admits_2022, 0),
        COALESCE(admits_2023, 0),
        COALESCE(admits_2024, 0)
    )::text AS peer_trend,
    hha_admits AS peer_admits,
    CASE WHEN state_hha_admits > 0
         THEN ROUND(100.0 * hha_admits / state_hha_admits, 2)
         ELSE 0 END AS peer_share_pct,
    CASE WHEN hha_ccn = %(row_key)s THEN 1 ELSE 0 END AS is_you
FROM mv_hha_final_inhome
WHERE hha_county = (
    SELECT hha_county FROM mv_hha_final_inhome
    WHERE hha_ccn = %(row_key)s
      [[ AND ffs_ma = %(ffs_ma)s ]]
    ORDER BY year DESC LIMIT 1
  )
  AND year = 2024
  [[ AND ffs_ma = %(ffs_ma)s ]]
ORDER BY
    CASE WHEN hha_ccn = %(row_key)s THEN 0 ELSE 1 END,
    hha_admits DESC
LIMIT 10
```

Test Query with `row_key=017014` (or any CCN from step 3) and `ffs_ma=FFS`. You should get ~10 rows of peer agencies.

### C. Detail Tiles

**Tile 1: Admits by Year — uses its own SQL (time-series)**

1. Click **+ Add Tile**
2. Title: `Admits by Year`
3. Type: `Bar — Basic`
4. **Check the box: "✓ Use own SQL for this tile"**
5. Paste this time-series SQL:

```sql
SELECT
    year,
    hha_admits AS yearly_admits,
    hha_visits AS yearly_visits,
    CASE WHEN state_hha_admits > 0
         THEN ROUND(100.0 * hha_admits / state_hha_admits, 2)
         ELSE 0 END AS share_pct,
    COALESCE(therapy_share, 0) AS therapy_share_pct
FROM mv_hha_final_inhome
WHERE hha_ccn = %(row_key)s
  [[ AND ffs_ma = %(ffs_ma)s ]]
ORDER BY year
```

6. Test Query with `row_key=017014` and `ffs_ma=FFS`. You should get **4 rows** (one per year 2022–2025).
7. X: `year`, Y: `yearly_admits`, Color `#0d9488`
8. ✓ Show data labels, ☐ Show legend

**Tile 2: Market Share Trend — reuses Tile 1's time-series SQL**

Rather than writing the SQL again, Tile 2 can share Tile 1's data IF you paste the same SQL in Shared Detail SQL (Section B). But we chose to put the peers SQL in B. So Tile 2 needs its own SQL too.

Quickest path for testing:

1. + Add Tile
2. Title: `Market Share Trend`
3. Type: `Line — Area`
4. ✓ Use own SQL for this tile — paste the SAME time-series SQL as Tile 1
5. Test Query with same params
6. X: `year`, Y: `share_pct`, Color `#3b82f6`
7. ✓ Show data labels

> **Performance note:** The backend caches by SQL text, so identical SQLs in two tiles only execute ONE query. Copy-paste is fine.

**Tile 3: Therapy Share — KPI Stat Card**

1. + Add Tile
2. Title: `Therapy Share`
3. Type: `KPI — Stat Card`
4. ✓ Use own SQL for this tile — paste (picks latest year):

```sql
SELECT ROUND(COALESCE(therapy_share, 0) * 100, 1) AS therapy_share_pct
FROM mv_hha_final_inhome
WHERE hha_ccn = %(row_key)s
  [[ AND ffs_ma = %(ffs_ma)s ]]
ORDER BY year DESC
LIMIT 1
```

5. Value: `therapy_share_pct`

### D. Sub-List

**Title:** `Top Agencies in Same County`

**"Use own SQL for sub-list"** — leave UNCHECKED so the sub-list uses the Shared Detail SQL from Section B (which is the peers SQL).

**Sub-List Row Layout** (dropdowns populate from Section B's test result):
- Rank: ✓ Numbers
- Primary Name: `peer_name`
- Badge: ☐
- Subtitle: ✓ Column=`peer_subtitle`
- Sparkline: ✓ Column=`peer_trend`, Variant=Line, Color=Auto
- Primary Metric: `peer_admits`, Number, 0 decimals
- Secondary: ✓ `peer_share_pct`, Percentage, 2 decimals, Suffix=`%`

**YOU Indicator:**
- ✓ Enable YOU indicator
- YOU column: `is_you`
- YOU color: `#10b981`, Peer color: `#f59e0b`
- ✓ Show colored progress bar

### Step 7 — Preview & Save

Save & Place on a page.

---

## What you should see on the portal

1. Master list: 15 ranked HHAs with all elements
2. Click ∨ on any row:
   - **Tile 1: Admits by Year** — 4 bars labeled **2022, 2023, 2024, 2025** ✓ (actual years, not just "2024" repeated)
   - **Tile 2: Market Share Trend** — line/area chart across years
   - **Tile 3: Therapy Share** — KPI stat card
   - **Sub-list** — peer agencies; user's own HHA shows YOU badge + green progress bar

## URL for testing YOU indicator
```
http://localhost:8069/my/<app>/<page>?hha_ccn=017014&ffs_ma=FFS&year=2024
```

---

## Testing Mode B (Different SQL Per Option)

Go back and edit the widget. In Step 2, change **Toggle Query Mode** to `Different SQL Per Option`. Now Steps 3, 4, 5, 6 all show an OptionTabBar at top: [FFS] [MA] [ALL].

- Each tab is independent — configure FFS fully, then click MA tab and configure that tab completely from scratch (different SQL, different master layout, different detail config, different YOU setting).
- Use case: FFS tab shows Hospitals with CMS data columns; MA tab shows Medicare Advantage plans with plan enrollment columns — completely different data models, same widget.

For a quick Mode B test: switch to Mode B, click each tab, and simply re-run the same configuration on each tab. Verify the portal shows different data per toggle.

---

## Troubleshooting

**"Use own SQL" toggle checked but dropdowns empty** → Click **Test Query** inside that tile's own SQL editor first. Dropdowns populate from the test result.

**Tile shows peers data when you wanted time-series** → The tile doesn't have its own SQL. Check "✓ Use own SQL for this tile" and paste the time-series query.

**Sub-list shows yearly rows instead of peers** → Sub-list is using a time-series SQL (probably the Shared Detail SQL was the time-series one). Either:
- Set Shared SQL to the peers query (as in this guide), OR
- Check "Use own SQL for sub-list" and write a peers query

**YOU badge missing** → Need `?hha_ccn=<ccn>` in URL OR single-HHA user. Backend sets `selected_hha_ccn` from the selected provider; if no single provider, `is_you` returns 0 for all rows (correct fallback).
