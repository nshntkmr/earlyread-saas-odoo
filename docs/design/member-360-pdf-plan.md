# Member 360 — PDF export plan (v1, 2026-10-16)

**Status:** accepted 2026-10-16 with D1–D3 as recommended (always print notes, embed icons, print
row span) and BUILT on branch `claude/member-360-pdf-generation-ef85a9` (not committed yet).
60/60 `posterra_pdf_export` tests + both Node parity scripts pass on the scratch DB
`pdf_export_test`; widgets without the new settings render the same body markup as before
(whitespace-normalised comparison against the old template). Fictional-data samples:
`member-360-pdf-samples/`. Not yet verified on dev.

**Goal:** "Export PDF" on the Member 360 page (`ulh_member_360`, ulh-humana app, dev) prints the
selected member the way the screen and the prototype show it, for the tab that is open
(Patient Details or Recent Encounters).

**Sources used:** the "PIQ dashboard page design for Humana" session (prototype V19, the widget
configs given there, the dev build state on 2026-10-16) and the PDF export code on `main`
(`posterra_portal/services/pdf_export/`, `views/pdf_export_templates.xml`).

No code is changed until you accept this plan. Values in the examples below are illustrative,
not read from dev.

---

## 1. What the PDF prints today (config only, no code)

The renderer is already on in dev (`pdf.enabled: true`). An admin can switch the feature on for
this page now:

| Where | Setting | Value for Member 360 |
|---|---|---|
| Page form → PDF Export | Export PDF | On |
| | Tabs | Patient Details, Recent Encounters (the 8 placeholder tabs are inactive anyway) |
| | Title template | `Member 360 — {tab_name}` (`{SRC_MBR_ID}` would print the finder label `EID/ID/MBI/Name`) |
| | Show filters / logo | On |
| Each widget → PDF Export tab | PDF Width | The PDF ignores the custom 58 % / 42 % widths and uses the preset (25/33/50/67/100 %). Set Member Profile and Risk & Acuity to 50 % each, or 67 % / 33 %. |

What comes out of that today, widget by widget:

| Widget | Type | Printed today? |
|---|---|---|
| Member header (page summary) | Record Header, scorecard | **Partly.** Name, the 4 value tiles and the "Eligible 2026" month chips print. The status chip ("Currently eligible · 6 of 8 months"), the Gender / Age line, the 4 ID badges (Member ID, MBI, UMID, EID), the tile captions ("Aug 2026") and the MLR status pill do not. |
| Page badge "Risk scores through Aug 2026" | Page badge | Yes, under the title |
| Member filter | Remote search | Yes, in the filters line, with its label |
| Member Profile | Attribute Grid | **No** — listed as "not included" |
| Risk & Acuity | Metric List | **No** |
| Primary Care Provider | Attribute Grid | **No** |
| Top 5 Providers by Diagnosis | Bar chart | Yes (same chart as the screen); its subtitle (PCP note) is not printed |
| Care Concentration | Metric List | **No** |
| Year / Month (Recent Encounters) | Tab filters | Yes, in the filters line |
| Provider Engagement History | Attribute Grid | **No** |
| Clinical Overview | Heatmap | Yes; subtitle ("N encounters · claim type by month") and footnote ("Claims incurred through …") are not printed |
| All Encounters | Table | Yes, with the Badge and Composite cells; subtitle not printed |

So the Patient Details PDF today is a header, one chart and a list of five "not included"
widgets. Recent Encounters is closer: two of three widgets print.

---

## 2. Proposed changes (code)

Every change is generic (any app, any page), driven by the widget's existing config, and
listed with what could break.

### B1. Print Attribute Grids (Member Profile, Primary Care Provider, Provider Engagement History)

**What it does:** the PDF draws the card the screen draws: label in small grey capitals, value
under it (bold when Emphasis = strong, grey when NULL), the secondary line under the value,
divider lines, the leading initials circle, and the field icons (see B5). Links print as plain
text, so a phone number is still readable.

**How the layout stays identical:** the screen decides where each field goes with the shared
`placement.js` (row order, column start, span, holes filled from the top, fewer columns on a
narrow card: ≥ 900 px keeps the configured count, ≥ 560 px max 4, ≥ 360 px max 2). The PDF gets
a line-for-line Python copy of that function, run against the card's printed width (already
computed for charts). A shared fixture is checked by a Python test and by a Node test that runs
the real `placement.js`, the same way the table cell formats are kept in sync today.

**Example, Member Profile (2 columns), as printed:**

| | |
|---|---|
| DATE OF BIRTH 01/24/1948 | PLAN Humana Gold Plus |
| ATTRIBUTED CLINIC … | MARKET … |
| HOME ADDRESS … | MSO PROVIDER GROUP … |
| PRIMARY CARE PROVIDER (full row, divider above) | |
| SPECIALTY (full row) | |
| NPI … | TELEPHONE … |

**Example, Provider Engagement History (attribute rows):** five lines, e.g.
"LAST VISIT  Jun 12, 2026 / Office visit · Smith, John MD", "LAST ANNUAL WELLNESS VISIT  Not
completed / No annual wellness visit recorded for this member · due now" with the warning icon.

**Risk:** a new block type only; nothing existing changes shape. One visible effect on any
other PDF-enabled page that has an Attribute Grid: that card now prints instead of being named
in the "not included" notice. Per-widget "Include in PDF" turns it off.

### B2. Print Metric Lists (Risk & Acuity, Care Concentration)

**What it does:** per row: label (with icon), status pill, value coloured by the status, the
progress bar (plain CSS, no script), the detail line, per-metric thresholds when configured,
and the legend at the bottom (numeric or semantic, as on screen). Rows hidden by `max_items`
stay hidden.

**Example, Risk & Acuity:** "Unplanned admits  [High Risk]  92nd" with a red bar at 92 %, then
Sepsis, High cost, End of life, then the legend "Low < 0.65 · Medium 0.65–0.90 · High ≥ 0.90".
The "Overall: Low Risk" badge comes from B4.

**Risk:** same as B1.

### B3. Record Header extras in the PDF

**What it does:** prints the keys the header already sends to the screen:

| On screen | In the PDF |
|---|---|
| Status chip beside the name | Same pill, tone colours (green "Currently eligible · 6 of 8 months") |
| Subtitle items (Gender, Age) | "Male · 80 yrs" under the name, replacing the plain subtitle when present (screen rule) |
| ID badges (Member ID, MBI, UMID, EID) | One row of pills "MEMBER ID 019622015", no copy button |
| Tile caption ("Aug 2026") | Small text after the value |
| Tile status pill (MLR "Below 85 %") | Same pill, value coloured by status when the tile asks for it |
| `stats_style = panel` | One grey panel with hairline dividers, 4 across (2 × 2 on a portrait page) |
| `empty_text` ("Find a member to begin") | That text instead of "No record for the selected filters." |

**Rule (your comment, 2026-10-16):** each item prints only when it is configured on the header;
anything not configured is left out, exactly as on screen. The print layout follows
`RecordHeader.jsx`: identity on the left (avatar, name + status chip, subtitle items, ID
badges), the values on the right (panel or tiles), the chip row along the bottom.

**Member 360 header, setting by setting (from your Configure Header screen):**

| Configured | PDF today | After B3 |
|---|---|---|
| Layout Scorecard, avatar Initials `#1d5fbf` circle | printed | unchanged |
| Empty State Text "Find a member to begin" | "No record for the selected filters." | "Find a member to begin" |
| Title Status Chip `ELIG_STATUS` / `ELIG_TONE` | missing | green pill beside the name |
| Subtitle Items `GENDER` (fa-user), `AGE_TEXT` (fa-calendar) | missing | "Male · 80 yrs" with the two icons (B5) |
| Identifier Badges Member ID, MBI, UMID, EID | missing | one row of label/value pills; the copy button is screen-only |
| Stats Style Panel | four separate grey boxes | one grey panel with dividers |
| Tile icons (fa-line-chart, fa-credit-card, fa-usd, fa-percent) + icon colours | missing | printed in their colours (B5) |
| Tile label / value colours (`#4a5568`, `#172033`, per-tile overrides) | printed | unchanged |
| Risk score caption `RISK_MONTH` | missing | "1.370 Aug 2026" style, small text after the value |
| MLR status `MLR_STATUS` / `MLR_TONE` | missing | tone pill after the value ("Colour value by status" is off, so the value keeps its colour) |
| Chips `ELIG_CHIPS` "Eligible 2026" `#dcfce7` / `#166534` | printed | unchanged |

**Risk:** a header that does not set these keys gets exactly today's PDF output (the payload
simply has no such keys). A test renders a classic and a plain scorecard header before and
after the change and compares the HTML.

### B4. Widget subtitle, footnote and header badge

**What it does:** prints the card's subtitle under its title, its footnote at the bottom, and
its header badge (annotation type "badge") beside the title, with the same text the screen
shows: the SQL-resolved text when there is one, else the static text. Colours come from the
already validated `subtitle_color`, `footnote_color` and the SQL-driven badge colour. A text
that still contains a raw `%(…)s` template (annotation query failed) is left out rather than
printed. The ⓘ info tooltip stays screen-only.

**Examples:** Top 5 Providers → its PCP note; Risk & Acuity → "Overall: Low Risk" in green;
Clinical Overview → "214 encounters · claim type by month" + "Claims incurred through Sep 2026";
All Encounters → "48 encounters · Jan–Sep 2026 · newest first".

**Risk — needs your decision (D1):** this one changes PDFs that already exist. Any PDF-enabled
page whose widgets have a subtitle or footnote
gains those lines on its next export (the Humana Provider Scorecard, if its widgets carry
subtitles; I could not check the dev DB from here). Options: (a) always print them, like the screen
(recommended); (b) a page setting "Print widget notes", off by default, so existing PDFs stay
exactly as they are.

### B5. Icons in the PDF (decision D2)

The Attribute Grid fields, Metric List rows and the header's Gender / Age line use Font Awesome
icons. The render service has no network access, so today it has no icon font. Proposal: embed
Odoo's own Font Awesome 4.7 font (already in the image, `web/static/src/libs/fontawesome`) as a
`data:` URI, only in PDFs that use an icon. Nothing is fetched; the renderer's deny-list is
unchanged. Cost: about 100 KB more HTML per such PDF.
Alternative: print without icons (labels carry the meaning). Recommended: embed.

### B6. Row span (decision D3)

On screen Risk & Acuity spans two rows, so Member Profile and Primary Care Provider stack on
the left beside it. The print grid ignores row span today, so Risk & Acuity would sit beside
Member Profile only, with empty space under the shorter card. Proposal: print the configured
row span (`grid-row: span N`).
**Risk:** any other PDF-enabled page with a row span > 1 re-flows to match its screen.
Recommended: yes.

### B7. Bookkeeping

- Designer: add `attribute_grid` and `metric_list` to `PRINTED_TYPES` in
  `PdfExportOptions.jsx` (so the Builder stops saying "not printed"); rebuild the Designer
  bundle and commit `dist`.
- The intro notice in the PDF ("This PDF includes record headers, KPI cards, tables and
  charts") lists the two new types.
- CLAUDE.md "Part G" bullet updated; tests below.

---

## 3. Known limits (not in this plan)

- **One tab per PDF**, as today. Patient Details and Recent Encounters are two exports. A
  "whole member" PDF with both tabs is a larger change (the original PDF plan deferred
  all-tabs) and can follow later.
- **Clinical Overview prints the window the screen shows.** With one year selected every month
  fits; with Year = All the invisible drag zoom shows the latest 14 months, and earlier months
  are not printed. Printing the full range is possible later as an option.
- **Screen-only things stay out:** info tooltips, click-to-copy, links and drill actions.
- **The Year = "All" bug** you set aside is untouched.
- **The Eligibility card from prototype V19** is not built on dev; the header's month chips are
  what prints.
- No member selected → the PDF prints the header's empty text and empty cards. (We could hide
  the button until a member is chosen; not proposed now.)

---

## 4. Testing

1. New tests under `--test-tags posterra_pdf_export`: Attribute Grid and Metric List block
   building, header extras, notes (incl. the raw-template guard), classic-header and existing
   block HTML unchanged, placement parity (Python fixture + `node --test` against
   `placement.js`).
2. Run on the scratch DB `pdf_export_test`, never the live DB.
3. Render a sample PDF through a local Gotenberg on port 3100 (JavaScript on, like dev) from a
   PostgreSQL fixture page that mirrors Member 360 with fictional members; you get both tab PDFs
   to look at before anything is merged.
4. After the dev image bump: you export a real member on both tabs.

## 5. Files

| File | Change |
|---|---|
| `posterra_portal/services/pdf_export/collector.py` | `attribute_grid`, `metric_list` kinds; notes from `_resolved_*`; row span |
| `posterra_portal/services/pdf_export/document.py` | view builders for the two kinds, header extras, notes, icon flag |
| `posterra_portal/services/pdf_export/placement.py` (new) | Python copy of `placement.js` |
| `posterra_portal/services/pdf_export/icons.py` (new) | Font Awesome `data:` URI + class map, only when used |
| `posterra_portal/views/pdf_export_templates.xml` | blocks + CSS (mirrors `widgetCards.css`, `RecordHeader` scorecard) |
| `posterra_portal/tests/…`, `tests/fixtures/pdf_placement.json`, `static/src/react/scripts/test_pdf_placement_parity.mjs` | tests |
| `dashboard_builder/static/src/designer/src/components/builder/PdfExportOptions.jsx` + `dist` | printed types |
| `CLAUDE.md` | Part G bullet |

## 6. Decisions for you

| # | Question | Recommendation |
|---|---|---|
| D1 | Widget subtitles / footnotes / header badges: always, or behind a page setting (off by default)? | Always |
| D2 | Icons in the PDF via the embedded Font Awesome font? | Yes |
| D3 | Print row span? | Yes |
