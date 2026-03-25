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

// ── Registry ────────────────────────────────────────────────────────────────
export const CELL_RENDERERS = {
  starRating:  StarRatingRenderer,
  pctColored:  PctColoredRenderer,
  badge:       BadgeRenderer,
  sparkline:   SparklineRenderer,
  barInline:   BarInlineRenderer,
}
