import React from 'react'

/**
 * BattleCard — chart_type: "battle_card"
 *
 * Side-by-side comparison: "You" (current HHA) vs "Competitor" (national/peer).
 *
 * Expected data shape:
 * {
 *   you_label:        "Elara Caring",
 *   competitor_label: "National Avg",
 *   rows: [
 *     {
 *       metric:           "Timely Initiation of Care",
 *       your_value:       "94.2%",
 *       competitor_value: "88.7%",
 *       your_bar_pct:     94.2,
 *       competitor_bar_pct: 88.7,
 *       result:           "WIN"   // "WIN" | "TIE" | "LOSE"
 *     },
 *     ...
 *   ],
 *   summary: "You outperform on 4 of 6 metrics."  // optional
 * }
 */
export default function BattleCard({ data = {} }) {
  const { you_label = 'You', competitor_label = 'Competitor', rows = [], summary,
          label_font_weight, value_font_weight, label_color, value_color } = data
  const valueStyle = (value_font_weight || value_color)
    ? { ...(value_font_weight && { fontWeight: value_font_weight }), ...(value_color && { color: value_color }) }
    : undefined
  const labelStyle = (label_font_weight || label_color)
    ? { ...(label_font_weight && { fontWeight: label_font_weight }), ...(label_color && { color: label_color }) }
    : undefined

  const resultBadge = (result) => {
    const cls = { WIN: 'success', TIE: 'secondary', LOSE: 'danger' }[result] || 'secondary'
    return <span className={`badge bg-${cls} pv-battle-badge`}>{result}</span>
  }

  return (
    <div className="pv-widget-battle">
      {/* Header row */}
      <div className="pv-battle-header">
        <div className="pv-battle-metric-col" />
        <div className="pv-battle-you-col" style={labelStyle}>{you_label}</div>
        <div className="pv-battle-comp-col" style={labelStyle}>{competitor_label}</div>
        <div className="pv-battle-result-col" style={labelStyle}>Result</div>
      </div>

      {/* Metric rows */}
      {rows.map((row, i) => (
        <div key={i} className="pv-battle-row">
          <div className="pv-battle-metric-col">{row.metric}</div>

          {/* Your value + bar */}
          <div className="pv-battle-you-col">
            <span className="pv-battle-val" style={valueStyle}>{row.your_value}</span>
            <div className="pv-battle-bar-wrap">
              <div
                className="pv-battle-bar pv-battle-bar-you"
                style={{ width: `${Math.min(row.your_bar_pct || 0, 100)}%` }}
              />
            </div>
          </div>

          {/* Competitor value + bar */}
          <div className="pv-battle-comp-col">
            <span className="pv-battle-val" style={valueStyle}>{row.competitor_value}</span>
            <div className="pv-battle-bar-wrap">
              <div
                className="pv-battle-bar pv-battle-bar-comp"
                style={{ width: `${Math.min(row.competitor_bar_pct || 0, 100)}%` }}
              />
            </div>
          </div>

          {/* WIN / TIE / LOSE */}
          <div className="pv-battle-result-col">
            {resultBadge(row.result)}
          </div>
        </div>
      ))}

      {/* Summary line */}
      {summary && (
        <div className="pv-battle-summary text-muted small mt-2">{summary}</div>
      )}
    </div>
  )
}
