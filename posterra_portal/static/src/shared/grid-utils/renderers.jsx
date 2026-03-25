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
  return (
    <span style={{ color: '#f59e0b', whiteSpace: 'nowrap' }}>
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
// Params: colorMap { "MA": "#3b82f6" }, defaultColor
function BadgeRenderer(params) {
  const val = params.value
  if (val == null || val === '') return null
  const p = params.colDef?.cellRendererParams || {}
  const colorMap = p.colorMap || {}
  const bg = colorMap[String(val)] || p.defaultColor || '#6b7280'
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
// Tiny SVG line chart. Input: JSON array or comma-separated string.
// Params: color (default teal)
function SparklineRenderer(params) {
  let values = params.value
  if (!values) return null
  if (typeof values === 'string') {
    try { values = JSON.parse(values) }
    catch { values = values.split(',').map(Number) }
  }
  if (!Array.isArray(values) || values.length < 2) return <span>{String(params.value)}</span>

  const p = params.colDef?.cellRendererParams || {}
  const color = p.color || '#0d9488'
  const w = 60, h = 20
  const nums = values.map(Number).filter(n => !isNaN(n))
  if (nums.length < 2) return <span>{String(params.value)}</span>

  const min = Math.min(...nums), max = Math.max(...nums)
  const range = max - min || 1
  const points = nums.map((v, i) =>
    `${(i / (nums.length - 1)) * w},${h - ((v - min) / range) * h}`
  ).join(' ')

  return (
    <svg width={w} height={h} style={{ verticalAlign: 'middle' }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  )
}

// ── 5. Inline Bar ───────────────────────────────────────────────────────────
// Horizontal bar proportional to value, with value label.
// Params: max (100), color, multiply (false)
function BarInlineRenderer(params) {
  const v = Number(params.value)
  if (isNaN(v)) return <span>{params.value}</span>
  const p = params.colDef?.cellRendererParams || {}
  const max = p.max || 100
  const multiply = p.multiply === true
  const val = multiply ? v * 100 : v
  const pct = Math.min(Math.max((val / max) * 100, 0), 100)
  const color = p.color || '#3b82f6'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
      <div style={{
        flex: 1, height: 8, backgroundColor: '#e5e7eb',
        borderRadius: 4, overflow: 'hidden',
      }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          backgroundColor: color, borderRadius: 4,
        }} />
      </div>
      <span style={{ fontSize: '0.8em', minWidth: 30, textAlign: 'right' }}>
        {val % 1 === 0 ? val : val.toFixed(1)}
      </span>
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

  return (
    <span style={{ whiteSpace: 'nowrap' }}>
      <strong>{primary}</strong>
      {secondary != null && (
        <span style={{ color: '#6b7280', marginLeft: 6, fontSize: '0.9em' }}>{secondary}</span>
      )}
    </span>
  )
}

// ── Registry ────────────────────────────────────────────────────────────────
export const CELL_RENDERERS = {
  starRating:  StarRatingRenderer,
  pctColored:  PctColoredRenderer,
  badge:       BadgeRenderer,
  sparkline:   SparklineRenderer,
  barInline:   BarInlineRenderer,
  composite:   CompositeRenderer,
  dualValue:   DualValueRenderer,
}
