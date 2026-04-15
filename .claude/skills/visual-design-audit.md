# Visual Design Audit: Ariv Health vs Posterra Portal

## Purpose
This skill documents every visual design difference between the competitor (Ariv Health) and our system (Posterra Portal). Use this as a reference when making CSS/styling improvements.

**Competitor URL:** https://hha.ariv.health/overview
**Our URL:** http://localhost:8069/my/inhome/inhome_comparison

## Ariv's Design System

**Tech Stack:** ShadCN/Radix UI + Tailwind CSS + Inter font
**Philosophy:** Everything on a strict scale, no arbitrary values

---

## 1. FONT FAMILY

| | Ariv | Posterra | Fix |
|--|------|----------|-----|
| Font | Inter, "Inter Fallback" | System default (Odoo's) | Add Inter via Google Fonts or local |

**Impact:** Inter is a modern, clean sans-serif designed for UI. It has wider letter-spacing and cleaner at small sizes than system fonts.

## 2. PAGE BACKGROUND

| | Ariv | Posterra | Status |
|--|------|----------|--------|
| Body bg | `rgb(255,255,255)` (pure white) | `#f8fafc` (slight gray) | ✅ Already close after last fix |
| Sidebar bg | White + 0.8px right border | Dark navy `#1a1f2e` | Different design choice — not a bug |

## 3. SIDEBAR

| | Ariv | Posterra |
|--|------|----------|
| Background | White | Dark navy (#1a1f2e) |
| Text | Dark gray | Light gray on dark |
| Active item | Teal text + teal left border | Blue background |
| Section headers | 11px, uppercase, gray-400 | Similar |
| Border | 0.8px solid gray-200 right | No border (dark bg) |

**Note:** Ariv uses a light sidebar, Posterra uses dark. This is a design identity choice, not a deficiency.

## 4. TOP BAR

| | Ariv | Posterra |
|--|------|----------|
| Height | 64px | 52px |
| Border bottom | 0.8px solid gray-200 | 1px solid #e2e8f0 |
| Provider selector | Rounded chip with chevron | Similar |

## 5. FILTER BAR

| Element | Ariv | Posterra | Fix Needed |
|---------|------|----------|------------|
| Filter label | 11px, weight 600, uppercase, gray-400, letter-spacing 0.55px | Hidden or different | Add filter labels above dropdowns |
| Filter dropdown | 14px, weight 500, 0.8px border, border-radius **9999px** (pill), padding 6px 12px, height ~34px | Standard select, rectangle | Make dropdowns pill-shaped |
| Filter icon | Small icon left of label (fa-map-marker, fa-calendar) | No icons | Add icons to filter labels |
| Apply button | Not visible (auto-apply?) | Blue "Apply" button | Different UX pattern |

## 6. PAGE TITLE

| | Ariv | Posterra | Status |
|--|------|----------|--------|
| Size | 24px | 24px | ✅ Fixed |
| Weight | 700 | 700 | ✅ Fixed |
| Color | `#111827` (gray-900) | `#111827` | ✅ Fixed |
| Subtitle | 14px, gray-400, weight 400 | smaller, text-muted | Increase subtitle size |

## 7. TABS (Page-Level)

| | Ariv | Posterra |
|--|------|----------|
| Font size | 14px | 14px |
| Font weight | 500 | 500 |
| Active color | Teal `rgb(15,118,110)` | Blue (primary color) |
| Active indicator | 2px bottom border (teal) | 2px bottom border (blue) |
| Inactive color | gray-500 | gray-500 |
| Icon | Small icon before tab text | No icons on tabs |
| Padding | 8px 12px | 10px 16px |

**Gap:** Ariv has icons on tabs (📊 Overview, ⭐ Quality, etc.). Posterra doesn't.

## 8. KPI CARDS

| Element | Ariv | Posterra | Fix Needed |
|---------|------|----------|------------|
| Card border-radius | 14px | 12px | Bump to 14px |
| Card border | 0.8px solid gray-200 | 0.8px solid #e2e8f0 | ✅ Close |
| Card shadow | `shadow-sm` (0 1px 3px...) | Dual shadow | ✅ Close |
| Card padding | 10px 14px | 12px 16px | Slightly tighter in Ariv |
| **Icon** | 16px colored icon (teal/blue/orange) in the card, left of label | Either no icon or larger icon | Ariv uses small inline icons |
| **Label** (e.g., "Total Admits") | 12px, weight 500, gray-500, **normal case** | 12px, weight 500, gray-500, normal case | ✅ Fixed |
| **Value** (e.g., "47,303") | 24-30px, weight 700, gray-900 | Similar | ✅ Close |
| **Trend badge** | Small pill with ↗+5.7% (green) or ↘-1.4% (red), 11px | Similar with pv-trend-badge | Check sizing |
| **Layout** | Icon + Label + Trend in one row, Value below | Icon + Label + Trend above, Value below | Match row layout |

## 9. TOGGLE BUTTONS (Widget-Scoped Controls)

This is the biggest visual gap. Ariv's toggle buttons look polished; ours look basic.

| Element | Ariv | Posterra |
|---------|------|----------|
| **Container** | No visible border on group — individual buttons have subtle bg | 1px solid border on group, overflow hidden |
| **Active button** | White bg (`rgb(255,255,255)`) with subtle shadow, dark text | Primary blue bg, white text |
| **Inactive button** | Transparent bg, gray-500 text | Transparent bg, gray text |
| **Border-radius** | 8px per button (not a pill group) | 6px group with square internal edges |
| **Font size** | 12px | 11px |
| **Font weight** | 500 | 500 |
| **Padding** | 6px 12px | 3px 10px |
| **Height** | ~28px | ~22px |
| **Gap** | 6px between buttons | 0 (joined) |
| **Icon** | Small icon before text, 6px gap | Icon before text, 4px gap |
| **Active indicator** | Subtle shadow (`shadow-sm`) on active button | Filled bg color change |
| **Position** | Right-aligned in card header | Right-aligned (same) |

**Key difference:** Ariv uses **separate rounded buttons with shadow on active** (like ShadCN Tabs). Posterra uses **joined segmented control with fill color on active**. Ariv's approach feels more modern.

### CSS Fix for Toggle Buttons:
```css
/* Change from joined group to separate buttons */
.pv-widget-toggle-group {
    display: inline-flex;
    gap: 4px;                    /* was: 0, joined */
    border: none;                /* was: 1px solid border */
    border-radius: 0;            /* was: 6px group radius */
    overflow: visible;           /* was: hidden */
    background: #f1f5f9;         /* subtle gray background behind all buttons */
    padding: 3px;
    border-radius: 10px;
}
.pv-widget-toggle-btn {
    padding: 5px 12px;           /* was: 3px 10px */
    font-size: 12px;             /* was: 11px */
    border: none;                /* was: border-right between buttons */
    border-radius: 8px;          /* was: 0 (except first/last) */
    background: transparent;
    color: #64748b;
    transition: all 0.15s;
}
.pv-widget-toggle-btn:last-child {
    border-right: none;          /* remove old rule */
}
.pv-widget-toggle-btn.active {
    background: #ffffff;          /* was: primary blue */
    color: #0f172a;               /* was: white */
    box-shadow: 0 1px 3px rgba(0,0,0,.1), 0 1px 2px rgba(0,0,0,.06);
}
.pv-widget-toggle-btn i {
    font-size: 11px;              /* was: 10px */
}
```

## 10. SECTION HEADERS (Inside Cards)

| Element | Ariv | Posterra |
|---------|------|----------|
| Title font size | 16px | 15px (var(--w-font-md)) |
| Title weight | 600 | 600 |
| Title color | gray-800 | gray-700 |
| Subtitle | 12px, gray-400, below title | Similar |
| **Context badge** (e.g., "OK · 181 HHAs") | 12px, gray-400, right-aligned | action_label badge |
| Header padding | 24px (p-6) | 12px 16px |
| Header display | flex, justify-between, items-start | flex (but less spacious) |

## 11. WIDGET CARD HEADER

| Element | Ariv | Posterra |
|---------|------|----------|
| Padding | 20px 24px (p-5 or p-6) | 12px 16px |
| Title size | 14-16px | 15px (clamp) |
| Title weight | 600 | 600 |
| Border bottom | 1px solid gray-100 | 1px solid var(--w-border-light) |
| **Header display** | flex, justify-between | flex (inline) |

**Gap:** Ariv's card headers have more padding (20px vs 12px). This gives more breathing room.

## 12. SPACING & LAYOUT

| Element | Ariv | Posterra | Fix |
|---------|------|----------|-----|
| Widget grid gap | 24px | 20px | Bump to 24px |
| Content area padding | 24px | 24px | ✅ Same |
| Section vertical spacing | 24px (space-y-6) | 16px | Increase |
| Card internal padding | 20px | 16px | Increase |

## 13. BORDERS

| Element | Ariv | Posterra | Status |
|---------|------|----------|--------|
| All borders | 0.8px solid gray-200 | 0.8px solid #e2e8f0 | ✅ Fixed |
| Card border | Same | Same | ✅ |
| Header borders | Same | Same | ✅ |

## 14. COLORS

| Token | Ariv | Posterra |
|-------|------|----------|
| Primary | Teal `#0d9488` | Blue `#0066cc` |
| Active tab | Teal | Blue |
| Active toggle | White + shadow | Blue fill |
| KPI value | gray-900 `#111827` | `#1e40af` (blue-800) |
| Label | gray-500 `#6b7280` | `#6b7280` ✅ |
| Muted text | gray-400 `#9ca3af` | `#9ca3af` ✅ |
| Status green | `#16a34a` | `#16a34a` ✅ |
| Status red | `#e11d48` | `#e11d48` ✅ |

**KPI value color gap:** Ariv uses near-black (`#111827`), Posterra uses blue (`#1e40af`). Black is more readable and neutral.

## 15. ICONS

| Element | Ariv | Posterra |
|---------|------|----------|
| Library | Lucide icons (thin, modern) | Font Awesome (heavier) |
| KPI icons | 14-16px, colored (teal/blue), inline with label | Larger, in circle badges |
| Tab icons | Small icon before tab text | No icons on tabs |
| Toggle icons | Small, same size as text | Small, slightly smaller |

**Gap:** Ariv uses Lucide (thin line icons). Posterra uses Font Awesome (heavier stroke). Lucide looks more modern in dashboard context.

---

## PRIORITY FIXES (Impact vs Effort)

### Quick Wins (CSS only, < 30 min each):

1. **Toggle button style** — Change from joined/fill to separate/shadow (see CSS above)
2. **Widget grid gap** — 20px → 24px
3. **Card header padding** — 12px 16px → 16px 20px
4. **KPI value color** — `#1e40af` → `#111827` (near-black)
5. **Card border-radius** — 12px → 14px
6. **Filter dropdown border-radius** — rectangle → pill (9999px)

### Medium Effort (React + CSS, 1-2 hours each):

7. **Filter label icons** — Add FA icon before each filter label
8. **Tab icons** — Add icon support to tab rendering
9. **KPI card icon** — Small inline icon in the label row

### Larger Effort (New component/feature):

10. **Font family** — Switch to Inter (Google Fonts import)
11. **Sidebar redesign** — Light sidebar option
12. **Toggle button position** — Right side of card header (layout change)
