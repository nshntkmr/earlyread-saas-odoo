// MetricListConfigurator — the complete structured editor for
// metric_list_config (canonical v1): column mapping (incl. per-row format +
// scale + direction columns), per-metric direction settings, scoped status
// rules with explicit inclusivity, the guarded band generator, legend mode.

import React, { useState } from 'react'
import {
  normalizeMetricList, DIRECTIONS, LEGEND_MODES, METRIC_FORMAT_TYPES,
} from '@posterra/grid-utils'
import IconKeyPicker from './IconKeyPicker'

const MAP_ROLES = [
  ['key_column', 'Metric key'],
  ['label_column', 'Label *'],
  ['value_column', 'Value *'],
  ['status_column', 'Status text'],
  ['detail_column', 'Detail'],
  ['icon_column', 'Icon key'],
  ['scale_min_column', 'Scale min'],
  ['scale_max_column', 'Scale max'],
  ['format_type_column', 'Format type'],
  ['decimals_column', 'Decimals'],
  ['display_multiplier_column', 'Multiplier'],
  ['prefix_column', 'Prefix'],
  ['suffix_column', 'Suffix'],
  ['direction_column', 'Direction'],
]

function Sel({ value, options, onChange, style }) {
  return (
    <select className="form-select form-select-sm" style={style}
      value={value} onChange={e => onChange(e.target.value)}>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

function Txt({ value, onChange, placeholder, style, mono }) {
  return (
    <input className="form-control form-control-sm"
      style={{ ...(mono ? { fontFamily: 'monospace' } : {}), ...style }}
      value={value ?? ''} placeholder={placeholder}
      onChange={e => onChange(e.target.value)} />
  )
}

function Num({ value, onChange, min, max, step, style, placeholder }) {
  return (
    <input type="number" className="form-control form-control-sm" style={style}
      value={value ?? ''} min={min} max={max} step={step || 'any'} placeholder={placeholder}
      onChange={e => onChange(e.target.value === '' ? null : Number(e.target.value))} />
  )
}

// ── Band generator (guarded) ────────────────────────────────────────────────
// Writes EXPLICIT half-open status_rules; runtime never reinterprets.
function generateBands({ direction, goodCutoff, badCutoff, appliesTo }) {
  const errs = []
  const fin = (v) => typeof v === 'number' && Number.isFinite(v)
  if (!fin(goodCutoff) || !fin(badCutoff)) errs.push('Both cutoffs must be finite numbers.')
  else if (goodCutoff === badCutoff) errs.push('Cutoffs cannot be equal.')
  else if (direction === 'lower_is_better' && !(goodCutoff < badCutoff)) {
    errs.push('lower_is_better requires good_cutoff < bad_cutoff.')
  } else if (direction === 'higher_is_better' && !(badCutoff < goodCutoff)) {
    errs.push('higher_is_better requires bad_cutoff < good_cutoff.')
  }
  if (errs.length) return { errs, rules: [] }
  const scope = appliesTo ? [appliesTo] : []
  const sfx = appliesTo ? `_${appliesTo}` : ''
  const mk = (key, label, color, background, range) => ({
    key: key + sfx, applies_to: scope, match_values: [], label,
    color, background, range, show_in_legend: true,
  })
  const G = ['Low', '#16a34a', '#dcfce7']
  const A = ['Moderate', '#d97706', '#fef3c7']
  const R = ['Elevated', '#dc2626', '#fee2e2']
  const rules = direction === 'lower_is_better' ? [
    mk('green', ...G, { min: null, min_inclusive: true, max: goodCutoff, max_inclusive: false }),
    mk('amber', ...A, { min: goodCutoff, min_inclusive: true, max: badCutoff, max_inclusive: false }),
    mk('red', ...R, { min: badCutoff, min_inclusive: true, max: null, max_inclusive: false }),
  ] : [
    mk('red', ...R, { min: null, min_inclusive: true, max: badCutoff, max_inclusive: false }),
    mk('amber', ...A, { min: badCutoff, min_inclusive: true, max: goodCutoff, max_inclusive: false }),
    mk('green', ...G, { min: goodCutoff, min_inclusive: true, max: null, max_inclusive: false }),
  ]
  return { errs: [], rules }
}

function BandGenerator({ cfg, onAppend }) {
  const [direction, setDirection] = useState('lower_is_better')
  const [good, setGood] = useState(null)
  const [bad, setBad] = useState(null)
  const [scope, setScope] = useState('')
  const [errs, setErrs] = useState([])

  const globalScale = cfg.scale
  const perRow = !!(cfg.mapping.scale_min_column && cfg.mapping.scale_max_column)
  const outOfScale = !perRow && good !== null && bad !== null
    && ([good, bad].some(v => v < globalScale.min || v > globalScale.max))

  return (
    <div className="border rounded p-2 mb-2 bg-light">
      <div className="small fw-bold mb-2">
        Generate bands from cutoffs (writes explicit rules below — raw-value units)
      </div>
      <div className="d-flex flex-wrap gap-2 align-items-end">
        <div>
          <label className="form-label small mb-1">Direction</label>
          <Sel value={direction} options={['lower_is_better', 'higher_is_better']}
            onChange={setDirection} style={{ width: 160 }} />
        </div>
        <div>
          <label className="form-label small mb-1">Good cutoff</label>
          <Num value={good} onChange={setGood} style={{ width: 100 }} />
        </div>
        <div>
          <label className="form-label small mb-1">Bad cutoff</label>
          <Num value={bad} onChange={setBad} style={{ width: 100 }} />
        </div>
        <div>
          <label className="form-label small mb-1">Scope to metric key (blank = global)</label>
          <Txt mono value={scope} onChange={setScope} placeholder="high_cost" style={{ width: 150 }} />
        </div>
        <button type="button" className="btn btn-sm btn-outline-primary"
          onClick={() => {
            const { errs: e, rules } = generateBands({
              direction, goodCutoff: good, badCutoff: bad, appliesTo: scope.trim(),
            })
            setErrs(e)
            if (!e.length) onAppend(rules)
          }}>
          Generate
        </button>
      </div>
      {errs.map((e, i) => <div key={i} className="text-danger small mt-1">{e}</div>)}
      {outOfScale && (
        <div className="text-warning small mt-1">
          Cutoff outside the global scale {globalScale.min}–{globalScale.max}.
          Allowed — verify units. (With per-row scale columns this warning never blocks.)
        </div>
      )}
    </div>
  )
}

export default function MetricListConfigurator({ config, onChange, apiBase }) {
  const cfg = normalizeMetricList(config || {})
  const set = (patch) => onChange({ ...(config || {}), version: 1, ...patch })
  const setNested = (key, patch) => set({ [key]: { ...cfg[key], ...patch } })

  const setRule = (idx, patch) =>
    set({ status_rules: cfg.status_rules.map((r, i) => (i === idx ? { ...r, ...patch } : r)) })
  const setRange = (idx, patch) => {
    const r = cfg.status_rules[idx]
    const base = r.range || { min: null, min_inclusive: true, max: null, max_inclusive: false }
    setRule(idx, { range: { ...base, ...patch } })
  }
  const removeRule = (idx) => set({ status_rules: cfg.status_rules.filter((_, i) => i !== idx) })
  const addRule = () => set({
    status_rules: [...cfg.status_rules, {
      key: `rule_${cfg.status_rules.length + 1}`, applies_to: [], match_values: [],
      label: '', color: '#16a34a', background: '#dcfce7',
      range: { min: null, min_inclusive: true, max: null, max_inclusive: false },
      show_in_legend: true,
    }],
  })

  const setSetting = (idx, patch) =>
    set({ metric_settings: cfg.metric_settings.map((s, i) => (i === idx ? { ...s, ...patch } : s)) })

  const scopedOrSettings = cfg.metric_settings.length > 0
    || cfg.status_rules.some(r => (r.applies_to || []).length > 0)

  return (
    <div className="wb-mlc">
      {/* ── Mapping ── */}
      <div className="small fw-bold mb-2">Column mapping (SQL aliases; Label + Value required)</div>
      <div className="d-flex flex-wrap gap-2 mb-2">
        {MAP_ROLES.map(([role, label]) => (
          <div key={role}>
            <label className="form-label small mb-1">{label}</label>
            <Txt mono value={cfg.mapping[role]} style={{ width: 130 }}
              onChange={v => setNested('mapping', { [role]: v })} />
          </div>
        ))}
      </div>
      {scopedOrSettings && !cfg.mapping.key_column && (
        <div className="text-danger small mb-2">
          Metric key column is required when rules are scoped or per-metric directions exist.
        </div>
      )}
      {cfg.mapping.icon_column && (
        <div className="d-flex flex-wrap gap-3 align-items-end mb-2">
          <div>
            <label className="form-label small mb-1">Allowed icon keys * (CSV — export bundles exactly these)</label>
            <Txt mono value={(cfg.icon.allowed_keys || []).join(',')} placeholder="warning,check-circle"
              onChange={v => setNested('icon', { allowed_keys: v.split(',').map(s => s.trim()).filter(Boolean) })} />
          </div>
          <div>
            <label className="form-label small mb-1">Fallback icon</label>
            <IconKeyPicker apiBase={apiBase} value={cfg.icon.fallback_key}
              onChange={v => setNested('icon', { fallback_key: v })} />
          </div>
        </div>
      )}

      {/* ── Scale / format / progress / misc ── */}
      <div className="d-flex flex-wrap gap-3 align-items-end mb-3">
        <div>
          <label className="form-label small mb-1">Scale min</label>
          <Num value={cfg.scale.min} style={{ width: 90 }}
            onChange={v => setNested('scale', { min: v ?? 0 })} />
        </div>
        <div>
          <label className="form-label small mb-1">Scale max</label>
          <Num value={cfg.scale.max} style={{ width: 90 }}
            onChange={v => setNested('scale', { max: v ?? 1 })} />
        </div>
        <div className="form-check mt-3">
          <input className="form-check-input" type="checkbox" checked={cfg.scale.clamp} id="mlc-clamp"
            onChange={e => setNested('scale', { clamp: e.target.checked })} />
          <label className="form-check-label small" htmlFor="mlc-clamp">
            Clamp out-of-range (off → no bar + out_of_range flag)
          </label>
        </div>
        <div>
          <label className="form-label small mb-1">Value format</label>
          <Sel value={cfg.value_format.type} options={METRIC_FORMAT_TYPES}
            onChange={v => setNested('value_format', { type: v })} style={{ width: 110 }} />
        </div>
        <div>
          <label className="form-label small mb-1">Decimals</label>
          <Num value={cfg.value_format.decimals} min={0} max={6} style={{ width: 70 }}
            onChange={v => setNested('value_format', { decimals: v ?? 0 })} />
        </div>
        <div>
          <label className="form-label small mb-1">× Multiplier</label>
          <Num value={cfg.value_format.display_multiplier} style={{ width: 90 }}
            onChange={v => setNested('value_format', { display_multiplier: v ?? 1 })} />
        </div>
        <div>
          <label className="form-label small mb-1">Detail label</label>
          <Txt value={cfg.detail_label} placeholder="Drivers" style={{ width: 120 }}
            onChange={v => set({ detail_label: v })} />
        </div>
        <div>
          <label className="form-label small mb-1">Max items</label>
          <Num value={cfg.max_items} min={1} max={100} style={{ width: 80 }}
            onChange={v => set({ max_items: v ?? 20 })} />
        </div>
        <div>
          <label className="form-label small mb-1">Bar height</label>
          <Num value={cfg.progress.height} min={2} max={32} style={{ width: 70 }}
            onChange={v => setNested('progress', { height: v ?? 10 })} />
        </div>
        <div className="form-check mt-3">
          <input className="form-check-input" type="checkbox" checked={cfg.progress.show} id="mlc-bar"
            onChange={e => setNested('progress', { show: e.target.checked })} />
          <label className="form-check-label small" htmlFor="mlc-bar">Show bars</label>
        </div>
        <div>
          <label className="form-label small mb-1">Legend</label>
          <Sel value={cfg.legend.mode} options={LEGEND_MODES}
            onChange={v => setNested('legend', { mode: v })} style={{ width: 120 }} />
        </div>
        <div>
          <label className="form-label small mb-1">Default direction</label>
          <Sel value={cfg.default_direction} options={DIRECTIONS}
            onChange={v => set({ default_direction: v })} style={{ width: 150 }} />
        </div>
      </div>

      {/* ── Per-metric direction settings ── */}
      <details className="mb-3" open={cfg.metric_settings.length > 0}>
        <summary className="small fw-bold">Per-metric directions ({cfg.metric_settings.length})</summary>
        <div className="mt-2 d-flex flex-column gap-1">
          {cfg.metric_settings.map((s, i) => (
            <div key={i} className="d-flex gap-2 align-items-center">
              <Txt mono value={s.metric_key} placeholder="metric_key" style={{ width: 180 }}
                onChange={v => setSetting(i, { metric_key: v })} />
              <Sel value={s.direction} options={DIRECTIONS} style={{ width: 160 }}
                onChange={v => setSetting(i, { direction: v })} />
              <button type="button" className="btn btn-sm btn-outline-danger"
                onClick={() => set({ metric_settings: cfg.metric_settings.filter((_, j) => j !== i) })}>
                <i className="fa fa-trash" />
              </button>
            </div>
          ))}
          <button type="button" className="btn btn-sm btn-outline-secondary align-self-start"
            onClick={() => set({ metric_settings: [...cfg.metric_settings, { metric_key: '', direction: 'lower_is_better' }] })}>
            <i className="fa fa-plus me-1" />Add metric direction
          </button>
          <div className="form-text">
            Priority: this setting → SQL direction column → widget default. Explicit
            ranges below are never reversed by direction.
          </div>
        </div>
      </details>

      {/* ── Status rules ── */}
      <div className="d-flex align-items-center justify-content-between mb-2">
        <span className="small fw-bold">
          Status rules ({cfg.status_rules.length}) — unmatched values render neutral
        </span>
        <button type="button" className="btn btn-sm btn-primary" onClick={addRule}>
          <i className="fa fa-plus me-1" />Add rule
        </button>
      </div>
      <BandGenerator cfg={cfg} onAppend={(rules) => set({ status_rules: [...cfg.status_rules, ...rules] })} />
      <div className="d-flex flex-column gap-2">
        {cfg.status_rules.map((r, i) => (
          <div key={i} className="border rounded p-2">
            <div className="d-flex flex-wrap gap-2 align-items-end">
              <div>
                <label className="form-label small mb-1">Key</label>
                <Txt mono value={r.key} style={{ width: 130 }} onChange={v => setRule(i, { key: v })} />
              </div>
              <div>
                <label className="form-label small mb-1">Label</label>
                <Txt value={r.label} style={{ width: 110 }} onChange={v => setRule(i, { label: v })} />
              </div>
              <div>
                <label className="form-label small mb-1">Applies to (CSV metric keys; blank = global)</label>
                <Txt mono value={(r.applies_to || []).join(',')} placeholder="sepsis,high_cost"
                  onChange={v => setRule(i, { applies_to: v.split(',').map(s => s.trim()).filter(Boolean) })} />
              </div>
              <div>
                <label className="form-label small mb-1">Match values (CSV, case-insensitive)</label>
                <Txt mono value={(r.match_values || []).join(',')} placeholder="low,low risk"
                  onChange={v => setRule(i, { match_values: v.split(',').map(s => s.trim()).filter(Boolean) })} />
              </div>
              <div>
                <label className="form-label small mb-1">Color</label>
                <input type="color" value={r.color} onChange={e => setRule(i, { color: e.target.value })} />
              </div>
              <div>
                <label className="form-label small mb-1">Bg</label>
                <input type="color" value={r.background} onChange={e => setRule(i, { background: e.target.value })} />
              </div>
              <div className="form-check mt-3">
                <input className="form-check-input" type="checkbox" checked={r.show_in_legend} id={`mlc-leg-${i}`}
                  onChange={e => setRule(i, { show_in_legend: e.target.checked })} />
                <label className="form-check-label small" htmlFor={`mlc-leg-${i}`}>Legend</label>
              </div>
              <button type="button" className="btn btn-sm btn-outline-danger ms-auto" onClick={() => removeRule(i)}>
                <i className="fa fa-trash" />
              </button>
            </div>
            <div className="d-flex flex-wrap gap-2 align-items-end mt-2">
              <div className="form-check">
                <input className="form-check-input" type="checkbox" checked={r.range !== null} id={`mlc-rng-${i}`}
                  onChange={e => setRule(i, {
                    range: e.target.checked
                      ? { min: null, min_inclusive: true, max: null, max_inclusive: false }
                      : null,
                  })} />
                <label className="form-check-label small" htmlFor={`mlc-rng-${i}`}>
                  Numeric range (off = status-text-only rule)
                </label>
              </div>
              {r.range !== null && (
                <>
                  <div>
                    <label className="form-label small mb-1">Min (blank = −∞)</label>
                    <Num value={r.range.min} style={{ width: 100 }} onChange={v => setRange(i, { min: v })} />
                  </div>
                  <div className="form-check mt-3">
                    <input className="form-check-input" type="checkbox" checked={r.range.min_inclusive} id={`mlc-mi-${i}`}
                      onChange={e => setRange(i, { min_inclusive: e.target.checked })} />
                    <label className="form-check-label small" htmlFor={`mlc-mi-${i}`}>min inclusive</label>
                  </div>
                  <div>
                    <label className="form-label small mb-1">Max (blank = +∞)</label>
                    <Num value={r.range.max} style={{ width: 100 }} onChange={v => setRange(i, { max: v })} />
                  </div>
                  <div className="form-check mt-3">
                    <input className="form-check-input" type="checkbox" checked={r.range.max_inclusive} id={`mlc-ma-${i}`}
                      onChange={e => setRange(i, { max_inclusive: e.target.checked })} />
                    <label className="form-check-label small" htmlFor={`mlc-ma-${i}`}>max inclusive</label>
                  </div>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
