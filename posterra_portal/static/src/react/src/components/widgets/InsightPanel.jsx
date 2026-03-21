import React from 'react'

/**
 * InsightPanel — chart_type: "insight_panel"
 *
 * Displays a classification badge, 1–3 key metrics, and a narrative text block.
 *
 * Expected data shape:
 * {
 *   classification:  "Good Standing",
 *   icon_class:      "bi bi-check-circle-fill",
 *   status_css:      "pv-status-good",   // CSS class for colour theming
 *   metric1_label:   "Star Rating",
 *   metric1_value:   "4.5",
 *   metric2_label:   "HHCAHPS Score",    // optional
 *   metric2_value:   "87.2",
 *   metric3_label:   "Deficiencies",     // optional
 *   metric3_value:   "0",
 *   narrative:       "This agency demonstrates strong performance across ..."
 * }
 */
export default function InsightPanel({ data = {} }) {
  const {
    classification, icon_class, status_css,
    metric1_label, metric1_value,
    metric2_label, metric2_value,
    metric3_label, metric3_value,
    narrative,
    label_font_weight, value_font_weight, label_color, value_color,
  } = data

  const metrics = [
    metric1_label && { label: metric1_label, value: metric1_value },
    metric2_label && { label: metric2_label, value: metric2_value },
    metric3_label && { label: metric3_label, value: metric3_value },
  ].filter(Boolean)

  const valueStyle = (value_font_weight || value_color)
    ? { ...(value_font_weight && { fontWeight: value_font_weight }), ...(value_color && { color: value_color }) }
    : undefined
  const labelStyle = (label_font_weight || label_color)
    ? { ...(label_font_weight && { fontWeight: label_font_weight }), ...(label_color && { color: label_color }) }
    : undefined

  return (
    <div className={`pv-widget-insight ${status_css || ''}`}>
      {/* Classification header */}
      <div className="pv-insight-header">
        {icon_class && <i className={`${icon_class} pv-insight-icon`} aria-hidden="true" />}
        <span className="pv-insight-classification">{classification || 'N/A'}</span>
      </div>

      {/* Metrics row */}
      {metrics.length > 0 && (
        <div className="pv-insight-metrics">
          {metrics.map((m, i) => (
            <div key={i} className="pv-insight-metric-tile">
              <div className="pv-insight-metric-value" style={valueStyle}>{m.value}</div>
              <div className="pv-insight-metric-label" style={labelStyle}>{m.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Narrative */}
      {narrative && (
        <div className="pv-insight-narrative">{narrative}</div>
      )}
    </div>
  )
}
