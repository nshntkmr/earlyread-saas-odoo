import React, { useEffect, useState, useCallback } from 'react'
import DonutStylePicker from './DonutStylePicker'
import LineStylePicker from './LineStylePicker'
import GaugeStylePicker from './GaugeStylePicker'
import KpiStylePicker from './KpiStylePicker'

const CHART_TYPES = [
  { key: 'bar',           label: 'Bar',           icon: 'fa-bar-chart',       desc: 'Compare values across categories' },
  { key: 'line',          label: 'Line',          icon: 'fa-line-chart',      desc: 'Show trends over time' },
  { key: 'pie',           label: 'Pie',           icon: 'fa-pie-chart',       desc: 'Show proportions of a whole' },
  { key: 'donut',         label: 'Donut',         icon: 'fa-circle-o-notch',  desc: 'Proportions with center stat' },
  { key: 'gauge',         label: 'Gauge',         icon: 'fa-tachometer',      desc: 'Show a single value vs target' },
  { key: 'radar',         label: 'Radar',         icon: 'fa-bullseye',        desc: 'Multi-axis profile comparison' },
  { key: 'kpi',           label: 'KPI Card',      icon: 'fa-hashtag',         desc: 'Metric cards with 7 style variants' },
  { key: 'table',         label: 'Data Table',    icon: 'fa-table',           desc: 'Tabular data with sortable cols' },
  { key: 'scatter',       label: 'Scatter',       icon: 'fa-braille',         desc: 'X-Y correlation plot' },
  { key: 'heatmap',       label: 'Heatmap',       icon: 'fa-th',              desc: 'Color-coded matrix grid' },
  { key: 'battle_card',   label: 'Battle Card',   icon: 'fa-columns',         desc: 'You vs competitor side-by-side' },
  { key: 'insight_panel', label: 'Insight Panel',  icon: 'fa-lightbulb-o',     desc: 'Narrative text with metrics' },
  { key: 'gauge_kpi',     label: 'Gauge + KPI',   icon: 'fa-dashboard',       desc: 'Gauge with sub-KPI breakdown' },
]

/**
 * Evaluate show_when conditions against current flag values.
 * Returns true if the flag should be visible.
 */
function shouldShow(showWhen, flagValues) {
  if (!showWhen) return true
  return Object.entries(showWhen).every(([key, expected]) => {
    const actual = flagValues[key]
    if (expected === '__not_null__') return actual != null && actual !== '' && actual !== 0
    if (Array.isArray(expected)) return expected.includes(actual)
    return actual === expected
  })
}

/**
 * Step 1: Pick a chart type + configure visual flags.
 *
 * Visual flags are loaded dynamically from the server based on chart type.
 * The flag schema drives which controls appear — no hardcoded per-chart UI.
 *
 * Props:
 *   selected      — current chart type key
 *   onSelect      — (chartType: string) => void
 *   visualFlags   — {flag: value} object (current visual_config state)
 *   onFlagChange  — (flag: string, value: any) => void
 *   barStack      — boolean (legacy, kept for backward compat)
 *   onBarStack    — (checked: boolean) => void (legacy)
 */
export default function ChartTypePicker({
  selected, onSelect,
  visualFlags = {}, onFlagChange,
  barStack, onBarStack,
}) {
  const [flagSchema, setFlagSchema] = useState([])

  // Fetch flag schema when chart type changes
  useEffect(() => {
    if (!selected) {
      setFlagSchema([])
      return
    }
    fetch(`/dashboard/designer/api/chart-flags/${selected}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(r => r.json())
      .then(data => {
        setFlagSchema(Array.isArray(data) ? data : (data.result || []))
      })
      .catch(() => setFlagSchema([]))
  }, [selected])

  const handleFlag = useCallback((flag, value) => {
    // Notify parent
    if (onFlagChange) onFlagChange(flag, value)
    // Keep legacy bar_stack in sync
    if (flag === 'stack' && onBarStack) onBarStack(value)
  }, [onFlagChange, onBarStack])

  // Resolve flag value: visualFlags → fallback to schema default
  const getFlagValue = (flag) => {
    if (flag.flag in visualFlags) return visualFlags[flag.flag]
    // Legacy backward compat for stack
    if (flag.flag === 'stack' && selected === 'bar' && barStack !== undefined) return barStack
    return flag.default
  }

  return (
    <div>
      <h3 className="wb-step-title">Choose Widget Type</h3>
      <div className="wb-chart-grid">
        {CHART_TYPES.map(ct => (
          <button
            key={ct.key}
            type="button"
            className={`wb-chart-card ${selected === ct.key ? 'wb-chart-card--active' : ''}`}
            onClick={() => onSelect(ct.key)}
          >
            <i className={`fa ${ct.icon} wb-chart-icon`} />
            <span className="wb-chart-label">{ct.label}</span>
            <span className="wb-chart-desc">{ct.desc}</span>
          </button>
        ))}
      </div>

      {/* Donut style sub-picker */}
      {selected === 'donut' && (
        <div style={{ marginTop: 16 }}>
          <DonutStylePicker
            selectedStyle={visualFlags.donut_style || 'standard'}
            onStyleChange={style => onFlagChange && onFlagChange('donut_style', style)}
            visualConfig={visualFlags}
            onVisualConfigChange={(key, value) => onFlagChange && onFlagChange(key, value)}
          />
        </div>
      )}

      {/* Line style sub-picker */}
      {selected === 'line' && (
        <div style={{ marginTop: 16 }}>
          <LineStylePicker
            selectedStyle={visualFlags.line_style || 'basic'}
            onStyleChange={style => onFlagChange && onFlagChange('line_style', style)}
            visualConfig={visualFlags}
            onVisualConfigChange={(key, value) => onFlagChange && onFlagChange(key, value)}
          />
        </div>
      )}

      {/* Gauge style sub-picker */}
      {selected === 'gauge' && (
        <div style={{ marginTop: 16 }}>
          <GaugeStylePicker
            selectedStyle={visualFlags.gauge_style || 'standard'}
            onStyleChange={style => onFlagChange && onFlagChange('gauge_style', style)}
            visualConfig={visualFlags}
            onVisualConfigChange={(key, value) => onFlagChange && onFlagChange(key, value)}
          />
        </div>
      )}

      {/* KPI style sub-picker */}
      {selected === 'kpi' && (
        <div style={{ marginTop: 16 }}>
          <KpiStylePicker
            selectedStyle={visualFlags.kpi_style || 'stat_card'}
            onStyleChange={style => onFlagChange && onFlagChange('kpi_style', style)}
            visualConfig={visualFlags}
            onVisualConfigChange={(key, value) => onFlagChange && onFlagChange(key, value)}
          />
        </div>
      )}

      {/* Dynamic chart-specific options from flag schema */}
      {/* Skip when a custom StylePicker already handles all flags (line, donut, gauge, kpi) */}
      {flagSchema.length > 0 && selected !== 'line' && selected !== 'donut' && selected !== 'gauge' && selected !== 'kpi' && (
        <div className="wb-field-group" style={{ marginTop: 16 }}>
          <label className="wb-label">
            {CHART_TYPES.find(c => c.key === selected)?.label || 'Chart'} Options
          </label>
          <div className="wb-flag-list">
            {flagSchema.map(flag => {
              if (!shouldShow(flag.show_when, visualFlags)) return null
              const val = getFlagValue(flag)

              // Info icon helper — renders a small (i) tooltip when help text exists
              const infoIcon = flag.help
                ? <i className="fa fa-info-circle wb-flag-info" title={flag.help} />
                : null

              if (flag.type === 'boolean') {
                return (
                  <div key={flag.flag} className="wb-toggle-group">
                    <label className="wb-toggle-label">
                      <input
                        type="checkbox"
                        checked={val === true}
                        onChange={e => handleFlag(flag.flag, e.target.checked)}
                      />
                      {flag.label} {infoIcon}
                    </label>
                    {flag.help && <span className="wb-flag-help">{flag.help}</span>}
                  </div>
                )
              }

              if (flag.type === 'select') {
                return (
                  <div key={flag.flag} className="wb-field-row">
                    <label className="wb-field-label">{flag.label} {infoIcon}</label>
                    <select
                      className="wb-select"
                      value={val ?? flag.default ?? ''}
                      onChange={e => handleFlag(flag.flag, e.target.value)}
                    >
                      {(flag.options || []).map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  </div>
                )
              }

              if (flag.type === 'number') {
                return (
                  <div key={flag.flag} className="wb-field-row">
                    <label className="wb-field-label">{flag.label} {infoIcon}</label>
                    <input
                      type="number"
                      className="wb-input wb-input--sm"
                      value={val ?? ''}
                      placeholder={flag.help || ''}
                      onChange={e => {
                        const v = e.target.value
                        handleFlag(flag.flag, v === '' ? null : Number(v))
                      }}
                    />
                  </div>
                )
              }

              if (flag.type === 'text') {
                return (
                  <div key={flag.flag} className="wb-field-row">
                    <label className="wb-field-label">{flag.label} {infoIcon}</label>
                    <input
                      type="text"
                      className="wb-input wb-input--sm"
                      value={val ?? ''}
                      placeholder={flag.help || ''}
                      onChange={e => handleFlag(flag.flag, e.target.value)}
                    />
                  </div>
                )
              }

              return null
            })}
          </div>
        </div>
      )}
    </div>
  )
}
