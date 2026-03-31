import React from 'react'
import GaugeRouter from './GaugeRouter'

/**
 * GaugeKPI
 *
 * Composite widget: gauge (top) + row of sub-KPI tiles + optional alert text.
 * Uses GaugeRouter to support all gauge variants (ECharts and non-ECharts).
 *
 * Expected data shape (from gauge_kpi widget type):
 * {
 *   echart_option: {...},          // gauge chart config (ECharts variants)
 *   gauge_variant: '...',          // non-ECharts variant key (optional)
 *   sub_kpis: [                    // optional row of mini-KPIs below the gauge
 *     { label, value, sub_label },
 *     ...
 *   ],
 *   alert_text: "...",             // optional amber/red alert string
 *   alert_class: "warning|danger"  // optional CSS class modifier
 * }
 */
export default function GaugeKPI({ data = {}, height = 280 }) {
  const { sub_kpis = [], alert_text, alert_class,
          label_font_weight, value_font_weight, label_color, value_color } = data
  const valueStyle = (value_font_weight || value_color)
    ? { ...(value_font_weight && { fontWeight: value_font_weight }), ...(value_color && { color: value_color }) }
    : undefined
  const labelStyle = (label_font_weight || label_color)
    ? { ...(label_font_weight && { fontWeight: label_font_weight }), ...(label_color && { color: label_color }) }
    : undefined

  return (
    <div className="pv-gauge-kpi-wrap">
      {/* Gauge (supports all variants via GaugeRouter) */}
      <GaugeRouter data={data} height={height} />

      {/* Sub-KPI row */}
      {sub_kpis.length > 0 && (
        <div className="pv-gauge-kpi-sub-row">
          {sub_kpis.map((sk, i) => (
            <div key={i} className="pv-gauge-kpi-sub-tile">
              <div className="pv-gauge-kpi-sub-label" style={labelStyle}>{sk.label}</div>
              <div className="pv-gauge-kpi-sub-value" style={valueStyle}>{sk.value}</div>
              {sk.sub_label && (
                <div className="pv-gauge-kpi-sub-sublabel">{sk.sub_label}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Alert text */}
      {alert_text && (
        <div className={`pv-gauge-kpi-alert pv-alert-${alert_class || 'warning'}`}>
          {alert_text}
        </div>
      )}
    </div>
  )
}
