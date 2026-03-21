import React from 'react'

const CHART_TYPES = [
  { key: 'bar',           label: 'Bar',           icon: 'fa-bar-chart',       desc: 'Compare values across categories' },
  { key: 'line',          label: 'Line',          icon: 'fa-line-chart',      desc: 'Show trends over time' },
  { key: 'pie',           label: 'Pie',           icon: 'fa-pie-chart',       desc: 'Show proportions of a whole' },
  { key: 'donut',         label: 'Donut',         icon: 'fa-circle-o-notch',  desc: 'Proportions with center stat' },
  { key: 'gauge',         label: 'Gauge',         icon: 'fa-tachometer',      desc: 'Show a single value vs target' },
  { key: 'radar',         label: 'Radar',         icon: 'fa-bullseye',        desc: 'Multi-axis profile comparison' },
  { key: 'kpi',           label: 'KPI Card',      icon: 'fa-hashtag',         desc: 'Single metric with formatting' },
  { key: 'status_kpi',    label: 'Status KPI',    icon: 'fa-arrow-up',        desc: 'KPI with up/down status icon' },
  { key: 'table',         label: 'Data Table',    icon: 'fa-table',           desc: 'Tabular data with sortable cols' },
  { key: 'scatter',       label: 'Scatter',       icon: 'fa-braille',         desc: 'X-Y correlation plot' },
  { key: 'heatmap',       label: 'Heatmap',       icon: 'fa-th',              desc: 'Color-coded matrix grid' },
  { key: 'battle_card',   label: 'Battle Card',   icon: 'fa-columns',         desc: 'You vs competitor side-by-side' },
  { key: 'insight_panel', label: 'Insight Panel',  icon: 'fa-lightbulb-o',     desc: 'Narrative text with metrics' },
  { key: 'gauge_kpi',     label: 'Gauge + KPI',   icon: 'fa-dashboard',       desc: 'Gauge with sub-KPI breakdown' },
]

/**
 * Step 1: Pick a chart type.
 *
 * Props:
 *   selected    — current chart type key
 *   onSelect    — (chartType: string) => void
 *   barStack    — boolean
 *   onBarStack  — (checked: boolean) => void
 */
export default function ChartTypePicker({ selected, onSelect, barStack, onBarStack }) {
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

      {/* Bar-specific options */}
      {selected === 'bar' && (
        <div className="wb-field-group" style={{ marginTop: 16 }}>
          <label className="wb-label">Bar Options</label>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={barStack === true}
                onChange={e => onBarStack?.(e.target.checked)}
              />
              Stack bars (series on top of each other)
            </label>
          </div>
        </div>
      )}
    </div>
  )
}
