import React from 'react'

// ── Cell renderer registry ──────────────────────────────────────────────────
// Keys match the Renderer dropdown in TableColumnSettings.jsx.
// Each is a React component receiving AG Grid's standard params object.
// Params come from colDef.cellRendererParams (admin-configured in builder).

// ── 1. Star Rating ──────────────────────────────────────────────────────────
// Displays a gold star icon + numeric value (e.g., ★ 4.5)
function StarRatingRenderer(params) {
  const v = Number(params.value)
  if (isNaN(v) || params.value == null || params.value === '') return null
  // Use 'inherit' so conditional formatting classes (cell-good, cell-bad, cell-warn)
  // on the parent AG Grid cell control the color. The default star color (#f59e0b)
  // is applied via CSS class .pv-star-rating when no conditional class overrides it.
  return (
    <span className="pv-star-rating" style={{ whiteSpace: 'nowrap' }}>
      ★ {v % 1 === 0 ? v : v.toFixed(1)}
    </span>
  )
}

// ── 2. Colored Percentage ───────────────────────────────────────────────────
// Shows percentage value with color based on thresholds.
// Params: goodAbove (70), badBelow (50), multiply (true), goodColor, badColor
function PctColoredRenderer(params) {
  const v = Number(params.value)
  if (isNaN(v)) return <span>{params.value}</span>
  const p = params.colDef?.cellRendererParams || {}
  const multiply = p.multiply !== false
  const pct = multiply ? v * 100 : v
  const goodAbove = p.goodAbove ?? 70
  const badBelow = p.badBelow ?? 50
  const color = pct >= goodAbove ? (p.goodColor || '#10b981')
              : pct < badBelow  ? (p.badColor || '#ef4444')
              : '#f59e0b'
  return <span style={{ color, fontWeight: 600 }}>{pct.toFixed(1)}%</span>
}

// ── 3. Badge ────────────────────────────────────────────────────────────────
// Pill badge with background color. Good for categorical data (MA/FFS, Active/Inactive).
//
// Color resolution priority:
//   1. cellRendererParams.colorMap[value]   ← explicit JSON config
//   2. wizard's cellClassRules (Conditional Formatting)
//   3. cellRendererParams.defaultColor
//   4. neutral gray
//
// The cellClassRules fallback lets admins use the Designer's
// Conditional Formatting UI to color badges without touching JSON —
// the same way other renderers respect those rules. Each known CSS
// class maps to a brand color via BADGE_CLASS_COLORS below.
const BADGE_CLASS_COLORS = {
  'cell-good':  '#059669',  // emerald — Good
  'cell-warn':  '#d97706',  // amber   — Warning
  'cell-bad':   '#dc2626',  // red     — Critical
  'cell-info':  '#3b82f6',  // blue    — Info
  'cell-muted': '#6b7280',  // gray    — Muted
}

function BadgeRenderer(params) {
  const val = params.value
  if (val == null || val === '') return null
  const p = params.colDef?.cellRendererParams || {}
  let bg = (p.colorMap || {})[String(val)]

  // Fallback: derive from wizard's Conditional Formatting rules
  // (cellClassRules). Conditions are admin-saved JS expressions
  // like 'x === "Tier 1"'; we evaluate with x = cell value and
  // pick the first matching rule's color. Malformed rules are
  // silently skipped — they fall through to defaultColor.
  if (!bg) {
    const rules = params.colDef?.cellClassRules
    if (rules && typeof rules === 'object') {
      for (const cls of Object.keys(rules)) {
        const color = BADGE_CLASS_COLORS[cls]
        if (!color) continue
        const condition = rules[cls]
        try {
          // eslint-disable-next-line no-new-func
          const fn = new Function('x', `return (${condition})`)
          if (fn(val)) {
            bg = color
            break
          }
        } catch (_) { /* skip bad expression */ }
      }
    }
  }

  bg = bg || p.defaultColor || '#6b7280'
  return (
    <span style={{
      backgroundColor: bg,
      color: '#fff',
      padding: '2px 8px',
      borderRadius: 12,
      fontSize: '0.8em',
      fontWeight: 500,
      display: 'inline-block',
      lineHeight: 1.4,
    }}>
      {val}
    </span>
  )
}

// ── 4. Sparkline ────────────────────────────────────────────────────────────
// Tiny SVG sparkline. Supports 5 variants via `variant` param.
// Input: JSON array, comma-separated numbers, or (bullet) an object.
// Params:
//   variant:   'line' | 'bar' | 'area' | 'winloss' | 'bullet'  (default 'line')
//   color:     fixed hex, or 'auto' (line/area/bar: green up / red down;
//              bullet: green if value >= target, else amber)
//   width, height: SVG size (default 60x20)
//   targetColor: (bullet only) target line color   (default '#0f172a')
//   trackColor:  (bullet only) background track color (default '#e2e8f0')
function SparklineRenderer(params) {
  const p = params.colDef?.cellRendererParams || {}
  const variant = p.variant || 'line'
  const w = p.width || 60
  const h = p.height || 20
  const raw = params.value
  if (raw === null || raw === undefined || raw === '') return null

  // ── Bullet variant: input is {value, target, max} object or JSON ─────
  if (variant === 'bullet') {
    let bulletData = raw
    if (typeof bulletData === 'string') {
      try { bulletData = JSON.parse(bulletData) } catch { return <span>{String(raw)}</span> }
    }
    const { value = 0, target = 0, max = 100 } = bulletData || {}
    const valueNum = Number(value)
    const targetNum = Number(target)
    const maxNum = Number(max)
    // Guard against non-numeric / zero-max input (valid JSON, bad values) that would
    // otherwise yield NaN/Infinity SVG dimensions. Numeric strings stay supported.
    if (!Number.isFinite(valueNum) || !Number.isFinite(targetNum) ||
        !Number.isFinite(maxNum) || maxNum <= 0) {
      return null
    }
    // color 'auto' (or empty) → automatic green/amber; otherwise literal SVG color.
    const barColor = (p.color && p.color !== 'auto')
      ? p.color
      : (valueNum >= targetNum ? '#10b981' : '#f59e0b')
    const targetColor = p.targetColor || '#0f172a'
    const trackColor = p.trackColor || '#e2e8f0'
    const valW = Math.max(0, Math.min(1, valueNum / maxNum)) * w
    const tgtX = Math.max(0, Math.min(1, targetNum / maxNum)) * w
    return (
      <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
        <rect x={0} y={h / 2 - 3} width={w} height={6} fill={trackColor} />
        <rect x={0} y={h / 2 - 3} width={valW} height={6} fill={barColor} />
        <line x1={tgtX} y1={1} x2={tgtX} y2={h - 1} stroke={targetColor} strokeWidth={1.5} />
      </svg>
    )
  }

  // Other variants: input is an array of numbers
  let values = raw
  if (typeof values === 'string') {
    try { values = JSON.parse(values) }
    catch { values = values.split(',').map(Number) }
  }
  if (!Array.isArray(values) || values.length < 2) return <span>{String(raw)}</span>
  const nums = values.map(Number).filter(n => !isNaN(n))
  if (nums.length < 2) return <span>{String(raw)}</span>

  // Color: auto (trend-based) or fixed hex
  const trendUp = nums[nums.length - 1] >= nums[0]
  const color = (p.color && p.color !== 'auto')
    ? p.color
    : (trendUp ? '#10b981' : '#ef4444')

  // ── Win/Loss variant ────────────────────────────────────────────────
  if (variant === 'winloss') {
    const ticks = nums.map((v, i) => {
      const x = (i / (nums.length - 1)) * w
      const color = v > 0 ? '#10b981' : (v < 0 ? '#ef4444' : '#94a3b8')
      const top = v > 0 ? 2 : (v < 0 ? h / 2 : h / 2 - 1)
      const tickH = v !== 0 ? (h / 2 - 2) : 2
      return <rect key={i} x={x - 2} y={top} width={3} height={tickH} fill={color} />
    })
    return (
      <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
        <line x1={0} y1={h / 2} x2={w} y2={h / 2} stroke="#cbd5e1" strokeWidth="0.5" />
        {ticks}
      </svg>
    )
  }

  const min = Math.min(...nums), max = Math.max(...nums)
  const range = max - min || 1

  // ── Bar variant ─────────────────────────────────────────────────────
  if (variant === 'bar') {
    const barW = Math.max(1, (w / nums.length) - 1)
    return (
      <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
        {nums.map((v, i) => {
          const barH = ((v - min) / range) * (h - 2)
          const x = (i / nums.length) * w
          const y = h - barH - 1
          return <rect key={i} x={x} y={y} width={barW} height={barH} fill={color} />
        })}
      </svg>
    )
  }

  // ── Line / Area variants ────────────────────────────────────────────
  const points = nums.map((v, i) =>
    `${(i / (nums.length - 1)) * w},${h - ((v - min) / range) * (h - 2) - 1}`
  ).join(' ')

  if (variant === 'area') {
    const polyPts = `0,${h} ${points} ${w},${h}`
    return (
      <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
        <polygon points={polyPts} fill={color} opacity={0.2} />
        <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
      </svg>
    )
  }

  // Default: line variant
  return (
    <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}

// ── 5. Inline Bar ───────────────────────────────────────────────────────────
// Horizontal bar proportional to value, with value label.
// Params: max (100), color, multiply (false), format, scale, decimals,
// prefix, suffix, valuePosition ('right'|'left'|'hidden')
const BAR_INLINE_SCALES = {
  none: ['', 1],
  thousands: ['K', 1e3],
  millions: ['M', 1e6],
  billions: ['B', 1e9],
}

function formatBarInlineValue(value, params) {
  const p = params || {}
  const format = p.format || 'number'
  if (format === 'raw') return String(value)

  const [scaleSuffix, divisor] = BAR_INLINE_SCALES[p.scale || 'none'] || BAR_INLINE_SCALES.none
  const scaled = value / divisor
  const explicitDecimals = p.decimals !== null && p.decimals !== undefined && p.decimals !== ''
  const decimals = explicitDecimals
    ? Math.max(0, Math.min(6, Number(p.decimals) || 0))
    : (
        format === 'percent' || format === 'pp' ? 1
        : format === 'currency' && scaleSuffix ? 1
        : Number.isInteger(scaled) ? 0 : 1
      )
  const sign = (p.showSign === true || format === 'pp') && scaled > 0 ? '+' : ''
  const prefix = p.prefix !== null && p.prefix !== undefined
    ? p.prefix
    : (format === 'currency' ? '$' : '')
  const suffix = p.suffix !== null && p.suffix !== undefined
    ? p.suffix
    : (format === 'percent' ? '%' : (format === 'pp' ? ' pp' : ''))
  const body = Number(scaled).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
  return `${sign}${prefix}${body}${scaleSuffix}${suffix}`
}

function BarInlineRenderer(params) {
  const v = Number(params.value)
  if (isNaN(v)) return <span>{params.value}</span>
  const p = params.colDef?.cellRendererParams || {}
  const max = p.max || 100
  const multiply = p.multiply === true
  const val = multiply ? v * 100 : v
  const pct = Math.min(Math.max((val / max) * 100, 0), 100)
  const color = p.color || '#3b82f6'
  const valuePosition = p.valuePosition || 'right'
  const label = valuePosition === 'hidden' ? null : formatBarInlineValue(val, p)
  const labelEl = label !== null && (
    <span style={{ fontSize: '0.8em', minWidth: p.labelMinWidth || 30, textAlign: 'right' }}>
      {label}
    </span>
  )
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
      {valuePosition === 'left' && labelEl}
      <div style={{
        flex: 1, height: 8, backgroundColor: '#e5e7eb',
        borderRadius: 4, overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          backgroundColor: color, borderRadius: 4,
        }} />
      </div>
      {valuePosition !== 'left' && labelEl}
    </div>
  )
}

// ── 6. Composite ────────────────────────────────────────────────────────────
// Multi-line cell showing multiple fields from the same row. Admin configures
// lines via cellRendererParams.lines — each line specifies fields, separator,
// styling (bold, muted, small), and optional prefix/suffix.
//
// Example config:
//   cellRendererParams: {
//     lines: [
//       { fields: ["hospital_name"], bold: true },
//       { fields: ["ccn", "city", "state"], separator: " · ", muted: true, prefix: "CCN " }
//     ]
//   }
// Renders as:
//   NORTHWESTERN MEMORIAL HOSPITAL
//   CCN 140281 · CHICAGO, IL
function CompositeRenderer(params) {
  const p = params.colDef?.cellRendererParams || {}
  const lines = p.lines || []
  const row = params.data || {}

  if (!lines.length) {
    // Fallback: just show the primary field value
    return <span>{params.value}</span>
  }

  return (
    <div style={{ lineHeight: 1.3, padding: '2px 0' }}>
      {/* Primary field value — always shown as bold title line */}
      {params.value != null && params.value !== '' && (
        <div style={{ fontWeight: 600 }}>{params.value}</div>
      )}
      {/* Configured sub-lines (secondary fields) */}
      {lines.map((line, li) => {
        const fields = line.fields || []
        const sep = line.separator || ' '
        const parts = fields
          .map(f => row[f] != null && row[f] !== '' ? String(row[f]) : null)
          .filter(Boolean)

        if (!parts.length) return null

        let text = parts.join(sep)
        if (line.prefix) text = line.prefix + text
        if (line.suffix) text = text + line.suffix

        const style = {}
        if (line.bold) style.fontWeight = 600
        if (line.muted) { style.color = '#6b7280'; style.fontSize = '0.85em' }
        if (line.small) style.fontSize = '0.8em'
        if (line.color) style.color = line.color

        return (
          <div key={li} style={style}>
            {text}
            {line.linkField && row[line.linkField] && (
              <span style={{ marginLeft: 4, fontSize: '0.85em', opacity: 0.6 }}>↗</span>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── 7. Dual Value ───────────────────────────────────────────────────────────
// Shows primary value + secondary value side by side.
// Primary: the column's own field value. Secondary: another field from the row.
//
// Example config:
//   field: "total_admits",
//   cellRenderer: "dualValue",
//   cellRendererParams: { secondaryField: "admit_pct", secondaryFormat: "pct" }
//
// Renders as: 231  4%
function DualValueRenderer(params) {
  const v = params.value
  if (v == null || v === '') return null
  const p = params.colDef?.cellRendererParams || {}
  const row = params.data || {}
  const secondaryField = p.secondaryField
  const secondaryRaw = secondaryField ? row[secondaryField] : null
  const secondaryFormat = p.secondaryFormat || 'pct' // pct | number | raw

  // Format primary
  const primary = typeof v === 'number' ? v.toLocaleString('en-US') : String(v)

  // Format secondary
  let secondary = null
  if (secondaryRaw != null && secondaryRaw !== '') {
    const sv = Number(secondaryRaw)
    if (!isNaN(sv)) {
      if (secondaryFormat === 'pct') {
        const multiply = p.secondaryMultiply !== false
        secondary = (multiply ? sv * 100 : sv).toFixed(p.secondaryDecimals ?? 0) + '%'
      } else if (secondaryFormat === 'number') {
        secondary = sv.toLocaleString('en-US')
      } else {
        secondary = String(secondaryRaw)
      }
    } else {
      secondary = String(secondaryRaw)
    }
  }

  // ── Sign-based coloring + arrow on secondary (opt-in via coloredDelta) ──
  // Default behaviour (gray, no arrow) is preserved when coloredDelta is
  // absent or false — every widget currently using dualValue renders
  // exactly as before. Only widgets that explicitly pass coloredDelta: true
  // in their cellRendererParams get the green/red ▲/▼ treatment.
  const coloredDelta = p.coloredDelta === true
  let secondaryColor = '#6b7280'
  let arrow = ''
  if (coloredDelta && secondaryRaw != null && secondaryRaw !== '') {
    const n = Number(secondaryRaw)
    if (!isNaN(n)) {
      if (n > 0) { secondaryColor = '#059669'; arrow = '▲ ' }
      else if (n < 0) { secondaryColor = '#dc2626'; arrow = '▼ ' }
    }
  }

  return (
    <span style={{ whiteSpace: 'nowrap' }}>
      <strong>{primary}</strong>
      {secondary != null && (
        <span style={{ color: secondaryColor, marginLeft: 6, fontSize: '0.9em' }}>
          {arrow}{secondary}
        </span>
      )}
    </span>
  )
}

// ── 8. Inline Mini-Chart ────────────────────────────────────────────────────
// Small inline bar/line/KPI rendered via lightweight SVG.
// Params:
//   type:   'bar' | 'line' | 'kpi'  (default 'bar')
//   size:   'small' (80x32) | 'medium' (150x40)  (default 'small')
//   color:  fixed hex (default teal)
//
// Input formats:
//   bar / line: JSON array of numbers (or comma-separated)
//   kpi:        JSON object {value, label, color} or just a number
//
// Note: implemented as SVG (not ECharts) for zero bundle cost. For heavier
// charts inside rows, consider a future lazy-loaded ECharts variant.
function InlineChartRenderer(params) {
  const p = params.colDef?.cellRendererParams || {}
  const type = p.type || 'bar'
  const size = p.size === 'medium' ? { w: 150, h: 40 } : { w: 80, h: 32 }
  const color = p.color || '#0d9488'
  const raw = params.value
  if (raw === null || raw === undefined || raw === '') return null

  if (type === 'kpi') {
    let kpi = raw
    if (typeof kpi === 'string') {
      try { kpi = JSON.parse(kpi) } catch { kpi = { value: raw } }
    }
    const value = (typeof kpi === 'object' && kpi !== null) ? kpi.value : kpi
    const label = (typeof kpi === 'object' && kpi !== null) ? kpi.label : null
    const kpiColor = (typeof kpi === 'object' && kpi !== null && kpi.color)
      ? kpi.color
      : color
    return (
      <div style={{
        width: size.w, height: size.h,
        display: 'flex', flexDirection: 'column', alignItems: 'flex-start',
        justifyContent: 'center', lineHeight: 1.1,
      }}>
        <div style={{ color: kpiColor, fontWeight: 600, fontSize: 14 }}>
          {value != null ? String(value) : ''}
        </div>
        {label && (
          <div style={{ color: '#6b7280', fontSize: 10 }}>{label}</div>
        )}
      </div>
    )
  }

  // bar or line: array input
  let values = raw
  if (typeof values === 'string') {
    try { values = JSON.parse(values) }
    catch { values = values.split(',').map(Number) }
  }
  if (!Array.isArray(values) || values.length < 2) {
    return <span>{String(raw)}</span>
  }
  const nums = values.map(Number).filter(n => !isNaN(n))
  if (nums.length < 2) return <span>{String(raw)}</span>

  const min = Math.min(...nums)
  const max = Math.max(...nums)
  const range = max - min || 1
  const { w, h } = size

  if (type === 'bar') {
    const barW = Math.max(1, (w / nums.length) - 1)
    return (
      <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
        {nums.map((v, i) => {
          const barH = ((v - min) / range) * (h - 4)
          const x = (i / nums.length) * w
          const y = h - barH - 2
          return <rect key={i} x={x} y={y} width={barW} height={barH} fill={color} />
        })}
      </svg>
    )
  }

  // line
  const points = nums.map((v, i) =>
    `${(i / (nums.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`
  ).join(' ')
  return (
    <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}

// ── 9. Compliance dot-strip ───────────────────────────────────────────────────
// PURE, AG-Grid-independent component: a horizontal row of small status cells
// (e.g. Jan..Dec, each compliant / nonCompliant / na). Reused by the AG-Grid
// renderer below AND directly by the Detail Drawer's measure cards — so drawer
// code never depends on AG-Grid renderer params. Config-driven: months/colours
// come from data + params, nothing hardcoded.
//
// `items`: array of { label, status }, status ∈ {compliant, nonCompliant, na}.
const STRIP_DEFAULT_COLORS = { compliant: '#16a34a', nonCompliant: '#dc2626', na: '#e5e7eb' }
const STRIP_SIZES = { sm: 12, md: 16, lg: 20 }

// Accepts native array, stringified JSON, null/empty, or malformed — never throws.
function normalizeStripItems(items) {
  let arr = items
  if (typeof arr === 'string') {
    const s = arr.trim()
    if (!s) return []
    try { arr = JSON.parse(s) } catch { console.warn('[ComplianceStrip] malformed JSON value'); return [] }
  }
  if (!Array.isArray(arr)) {
    if (arr != null) console.warn('[ComplianceStrip] unexpected value shape:', typeof arr)
    return []
  }
  return arr.map(it => (it && typeof it === 'object')
    ? { label: it.label ?? '', status: it.status ?? 'na' }
    : { label: '', status: 'na' })
}

// `size` accepts a keyword (sm/md/lg) OR a number (custom px). For pills
// (showLabels), `fontSize`/`padding` give full control. All three default so
// keyword sizes render byte-identical to before (sm → 11px font / 3px 7px pad).
export function ComplianceStrip({ items, colors, size = 'sm', showLabels = false, fontSize, padding }) {
  const list = normalizeStripItems(items)
  if (!list.length) return <span style={{ color: '#9ca3af', fontSize: '0.8em' }}>—</span>
  const c = { ...STRIP_DEFAULT_COLORS, ...(colors || {}) }
  const px = typeof size === 'number' ? size : (STRIP_SIZES[size] || STRIP_SIZES.sm)
  const pillFont = fontSize != null ? fontSize : (typeof size === 'number' ? size : 11)
  const pillPad = padding != null ? padding : `${Math.round(pillFont * 0.3)}px ${Math.round(pillFont * 0.65)}px`
  return (
    <div style={{ display: 'inline-flex', gap: 2, alignItems: 'center' }}>
      {list.map((it, i) => {
        const status = c[it.status] ? it.status : 'na'
        return (
          <span
            key={i}
            title={it.label ? `${it.label}: ${it.status}` : it.status}
            style={showLabels
              ? { fontSize: pillFont, fontWeight: 700, borderRadius: 4, padding: pillPad, color: '#fff', backgroundColor: c[status] }
              : { width: px, height: px, borderRadius: 3, backgroundColor: c[status], display: 'inline-block' }}
          >
            {showLabels ? it.label : ''}
          </span>
        )
      })}
    </div>
  )
}

// Thin AG-Grid wrapper: maps cellRendererParams → the pure component.
function ComplianceStripRenderer(params) {
  const p = params.colDef?.cellRendererParams || {}
  const raw = p.itemsField ? params.data?.[p.itemsField] : params.value
  return <ComplianceStrip items={raw} colors={p.colors} size={p.size || 'sm'} showLabels={p.showLabels} fontSize={p.fontSize} padding={p.padding} />
}

// ── Registry ────────────────────────────────────────────────────────────────
export const CELL_RENDERERS = {
  starRating:      StarRatingRenderer,
  pctColored:      PctColoredRenderer,
  badge:           BadgeRenderer,
  sparkline:       SparklineRenderer,
  barInline:       BarInlineRenderer,
  composite:       CompositeRenderer,
  dualValue:       DualValueRenderer,
  inlineChart:     InlineChartRenderer,
  complianceStrip: ComplianceStripRenderer,
}
