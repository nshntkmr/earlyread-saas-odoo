// @posterra/grid-utils — cell recipes for chart_type='smart_table'
//
// Five composable recipes that cover ~95% of analytical-table cell types.
// Designed for SmartTable.jsx (NOT AG Grid). Each recipe is a plain React
// component receiving (value, row, cell) — no params object indirection.
//
// Recipe registry:
//   text                — plain string, optional truncate / link / style
//   metric              — number/currency/percent + optional rules-based color
//   metric_with_delta   — main value + colored sub-delta (YoY, benchmark Δ)
//   badge               — status pill with rule-mapped variant color
//   composite           — multi-item cell (text + sub-text, text + badge)
//
// Variants enum (color tokens):
//   success | warning | danger | neutral | muted
//
// All Tailwind classes referenced here are listed in tremorSafelist.js so
// the JIT keeps them in main.css.

import React from 'react'

// ── Variant style tokens ─────────────────────────────────────────────
// Single source of truth — both pill and text usage. Component picks the
// right slice via applyVariant() below.
export const VARIANT_STYLES = {
  success:  { text: 'text-emerald-700', pill: 'bg-emerald-50 text-emerald-700' },
  warning:  { text: 'text-amber-700',   pill: 'bg-amber-50 text-amber-700' },
  danger:   { text: 'text-red-700',     pill: 'bg-red-50 text-red-700' },
  neutral:  { text: 'text-gray-700',    pill: 'bg-gray-100 text-gray-700' },
  muted:    { text: 'text-gray-300',    pill: 'bg-transparent text-gray-300' },
}

// Style-token variants for the "style" prop on text and composite items.
const TEXT_STYLE_CLASSES = {
  default: 'text-gray-900',
  primary: 'font-semibold text-gray-900',
  muted:   'text-xs text-gray-500',
  bold:    'font-bold text-gray-900',
}

// ── Helpers ──────────────────────────────────────────────────────────

// Format a value per the recipe's `format` field.
//   number    → "1,234"
//   decimal   → "1,234.5"
//   currency  → "$1,234"
//   percent   → "12.3%"
//   pp        → "+1.7pp"  (percentage points; respects showSign)
//   text      → string passthrough
function formatValue(value, format, opts = {}) {
  if (value === null || value === undefined || value === '') return ''
  const decimals = opts.decimals ?? (format === 'decimal' ? 1 : 0)
  const prefix = opts.prefix || ''
  const suffix = opts.suffix || ''
  const showSign = !!opts.showSign

  if (format === 'text' || format === undefined || format === null) {
    return String(value)
  }

  const n = Number(value)
  if (!isFinite(n)) return String(value)

  let body
  switch (format) {
    case 'currency': {
      const cur = opts.currency || 'USD'
      try {
        body = new Intl.NumberFormat('en-US', {
          style: 'currency', currency: cur,
          minimumFractionDigits: decimals, maximumFractionDigits: decimals,
        }).format(n)
      } catch {
        body = '$' + n.toLocaleString('en-US', {
          minimumFractionDigits: decimals, maximumFractionDigits: decimals,
        })
      }
      break
    }
    case 'percent':
      body = n.toFixed(decimals) + '%'
      break
    case 'pp':
      body = (showSign && n > 0 ? '+' : '') + n.toFixed(decimals) + 'pp'
      break
    case 'decimal':
      body = n.toLocaleString('en-US', {
        minimumFractionDigits: decimals, maximumFractionDigits: decimals,
      })
      break
    case 'number':
    default:
      body = n.toLocaleString('en-US', {
        minimumFractionDigits: decimals, maximumFractionDigits: decimals,
      })
  }

  // Sign prefix for non-pp formats when showSign is on
  if (showSign && format !== 'pp' && n > 0 && !body.startsWith('+')) {
    body = '+' + body
  }
  return prefix + body + suffix
}

// Evaluate a single rule against a numeric value.
//   {op: 'gte', value: 10}                  → value >= 10
//   {op: 'between', value: [5, 10]}         → 5 <= value <= 10
//   {op: 'is_null'}                         → value is null/empty
function evaluateRule(value, rule) {
  if (!rule || !rule.op) return false
  if (rule.op === 'is_null') return (value === null || value === undefined || value === '')
  if (value === null || value === undefined || value === '') return false
  const n = Number(value)
  if (!isFinite(n) && rule.op !== 'eq' && rule.op !== 'ne') return false
  switch (rule.op) {
    case 'gte': return n >= Number(rule.value)
    case 'gt':  return n >  Number(rule.value)
    case 'lte': return n <= Number(rule.value)
    case 'lt':  return n <  Number(rule.value)
    case 'eq':  return String(value) === String(rule.value)
    case 'ne':  return String(value) !== String(rule.value)
    case 'between': {
      if (!Array.isArray(rule.value) || rule.value.length !== 2) return false
      return n >= Number(rule.value[0]) && n <= Number(rule.value[1])
    }
    default: return false
  }
}

// First-match wins; returns variant string or default.
function pickVariant(value, rules, defaultVariant = null) {
  if (!Array.isArray(rules) || rules.length === 0) return defaultVariant
  for (const r of rules) {
    if (evaluateRule(value, r)) return r.variant || defaultVariant
  }
  return defaultVariant
}

// Resolve variant → Tailwind classes. kind = 'text' | 'pill'.
function applyVariant(variant, kind = 'text') {
  if (!variant || !VARIANT_STYLES[variant]) return ''
  return VARIANT_STYLES[variant][kind] || ''
}

// ── Recipe 1: text ──────────────────────────────────────────────────
function TextRecipe({ value, row, cell }) {
  const opts = cell || {}
  const styleClass = TEXT_STYLE_CLASSES[opts.style] || TEXT_STYLE_CLASSES.default
  const truncateClass = opts.truncate ? 'truncate' : ''
  const text = value === null || value === undefined ? '' : String(value)

  if (opts.link) {
    const url = new URL(window.location.href)
    if (opts.linkParam && row) {
      url.searchParams.set(opts.linkParam, row[opts.linkParam] ?? value)
    }
    // Page key navigation — caller can override pathname elsewhere
    return (
      <a href={url.toString()}
         className={`${styleClass} ${truncateClass} text-blue-600 hover:underline`}
         style={opts.maxWidth ? { maxWidth: opts.maxWidth, display: 'inline-block' } : undefined}>
        {text}
      </a>
    )
  }

  return (
    <span
      className={`${styleClass} ${truncateClass}`}
      style={opts.maxWidth ? { maxWidth: opts.maxWidth, display: 'inline-block' } : undefined}
      title={opts.truncate ? text : undefined}>
      {text}
    </span>
  )
}

// ── Recipe 2: metric ────────────────────────────────────────────────
function MetricRecipe({ value, row, cell }) {
  const opts = cell || {}
  const n = Number(value)
  const isZero = isFinite(n) && n === 0
  const isEmpty = value === null || value === undefined || value === ''

  // Pick variant: muted-zero takes priority when enabled
  let variant = null
  if (opts.muteZero && isZero) {
    variant = 'muted'
  } else if (opts.rules) {
    variant = pickVariant(value, opts.rules)
  }
  const colorClass = applyVariant(variant, 'text')

  const formatted = formatValue(value, opts.format || 'number', opts)
  if (isEmpty && !opts.showEmpty) {
    return <span className="text-gray-300">—</span>
  }

  return <span className={`whitespace-nowrap ${colorClass}`}>{formatted}</span>
}

// ── Recipe 3: metric_with_delta ─────────────────────────────────────
function MetricWithDeltaRecipe({ value, row, cell }) {
  const opts = cell || {}
  const main = opts.main || {}
  const delta = opts.delta || {}
  const color = opts.color || {}

  // Resolve main + delta values from row by field name
  const mainField = main.field || cell.field
  const mainValue = mainField ? (row?.[mainField]) : value
  const deltaValue = delta.field ? (row?.[delta.field]) : null

  const mainN = Number(mainValue)
  const isMainZero = isFinite(mainN) && mainN === 0
  const muteMain = opts.muteZero && isMainZero

  // Color basis
  const lowerIsBetter = !!color.lowerIsBetter
  const positiveVariant = color.positive || 'success'
  const negativeVariant = color.negative || 'danger'

  let deltaColor = ''
  if (deltaValue !== null && deltaValue !== '' && deltaValue !== undefined) {
    const d = Number(deltaValue)
    if (isFinite(d) && d !== 0) {
      const isPositive = d > 0
      // "good direction" = positive when higher-is-better, negative when lower-is-better
      const isGood = (isPositive && !lowerIsBetter) || (!isPositive && lowerIsBetter)
      deltaColor = applyVariant(isGood ? positiveVariant : negativeVariant, 'text')
    }
  }

  let mainColor = ''
  if (color.basis === 'main' && !muteMain) {
    if (isFinite(mainN) && mainN !== 0) {
      const isPositive = mainN > 0
      const isGood = (isPositive && !lowerIsBetter) || (!isPositive && lowerIsBetter)
      mainColor = applyVariant(isGood ? positiveVariant : negativeVariant, 'text')
    }
  }

  if (muteMain) mainColor = applyVariant('muted', 'text')

  const mainText = formatValue(mainValue, main.format || 'number', main)
  const deltaText = delta.field
    ? formatValue(deltaValue, delta.format || 'pp', delta)
    : null

  return (
    <span className="whitespace-nowrap">
      <span className={mainColor}>{mainText}</span>
      {deltaText && (
        <sub className={`ml-1 text-[0.75em] ${deltaColor}`}>{deltaText}</sub>
      )}
    </span>
  )
}

// ── Recipe 4: badge ─────────────────────────────────────────────────
function BadgeRecipe({ value, row, cell }) {
  const opts = cell || {}
  const field = opts.field
  const v = field ? row?.[field] : value
  if (v === null || v === undefined || v === '') {
    return <span className="text-gray-300">—</span>
  }

  // Find matching rule: exact-match on `match`
  let label = String(v)
  let variant = opts.defaultVariant || 'neutral'
  if (Array.isArray(opts.rules)) {
    for (const r of opts.rules) {
      if (String(r.match) === String(v)) {
        label = r.label || label
        variant = r.variant || variant
        break
      }
    }
  }

  const pillClass = applyVariant(variant, 'pill')
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${pillClass}`}>
      {label}
    </span>
  )
}

// ── Recipe 5: composite ─────────────────────────────────────────────
// Renders multiple items in one cell, vertically or horizontally.
// Each item is a flat {field, format, style, variant} — NO nesting.
function CompositeRecipe({ value, row, cell }) {
  const opts = cell || {}
  const layout = opts.layout || 'vertical'
  const items = Array.isArray(opts.items) ? opts.items : []

  if (items.length === 0) {
    return <span>{value === null || value === undefined ? '' : String(value)}</span>
  }

  const wrapperClass = layout === 'horizontal'
    ? 'flex items-center gap-2'
    : 'flex flex-col leading-tight'

  return (
    <div className={wrapperClass}>
      {items.map((item, i) => {
        const v = item.field ? row?.[item.field] : value
        const fmt = item.format || 'text'

        if (fmt === 'badge') {
          if (v === null || v === undefined || v === '') return null
          const variant = item.variant || 'neutral'
          const pillClass = applyVariant(variant, 'pill')
          return (
            <span key={i}
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${pillClass}`}>
              {String(v)}
            </span>
          )
        }

        if (fmt === 'icon') {
          // Reserved for future use; for now render as muted text
          return <span key={i} className="text-gray-400 text-xs">{String(v ?? '')}</span>
        }

        const styleClass = TEXT_STYLE_CLASSES[item.style] || TEXT_STYLE_CLASSES.default
        const text = formatValue(v, fmt, item)
        return <span key={i} className={styleClass}>{text}</span>
      })}
    </div>
  )
}

// ── Registry ────────────────────────────────────────────────────────
export const CELL_RECIPES = {
  text:               TextRecipe,
  metric:             MetricRecipe,
  metric_with_delta:  MetricWithDeltaRecipe,
  badge:              BadgeRecipe,
  composite:          CompositeRecipe,
}

// Default render fallback for unknown recipe types
export function CellHost({ col, row }) {
  const cell = col?.cell || {}
  const Recipe = CELL_RECIPES[cell.type] || TextRecipe
  // Resolve the primary value: cell.field overrides col.field for recipes
  // that pull from a different column than they're displayed in.
  const valueField = cell.field || col.field
  const value = row?.[valueField]
  return <Recipe value={value} row={row} cell={cell} />
}
