import React from 'react'

// Color palettes — keep aligned with backend healthcare default and ECharts.
const PALETTES = {
  healthcare: ['#10b981', '#3b82f6', '#a855f7', '#ef4444', '#f59e0b',
               '#06b6d4', '#ec4899', '#84cc16'],
  default:    ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
               '#3ba272', '#fc8452', '#9a60b4'],
}

/**
 * LegendList — rows of {dot, label, value, pct}.
 *
 * Data shape (from dashboard.widget._build_legend_list_data):
 *   {
 *     type: 'legend_list',
 *     palette: 'healthcare',
 *     rows: [{ label, value, pct }, ...]
 *   }
 */
export default function LegendList({ data }) {
  const rows = data?.rows || []
  const palette = PALETTES[data?.palette] || PALETTES.healthcare
  if (!rows.length) {
    return <div className="pv-legend-empty">No data</div>
  }
  return (
    <ul className="pv-legend-list">
      {rows.map((r, i) => (
        <li key={i} className="pv-legend-list-row">
          <span
            className="pv-legend-dot"
            style={{ background: palette[i % palette.length] }}
          />
          <span className="pv-legend-label">{r.label}</span>
          <span className="pv-legend-value">
            {typeof r.value === 'number' ? r.value.toLocaleString() : r.value}
          </span>
          <span className="pv-legend-pct">({r.pct}%)</span>
        </li>
      ))}
    </ul>
  )
}
