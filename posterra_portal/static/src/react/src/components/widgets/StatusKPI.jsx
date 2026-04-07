import React from 'react'
import { TrendIcon } from './TrendIcons'
import CategoryIcon from './CategoryIcons'
import KPIStrip from './KPIStrip'

/**
 * StatusKPI — chart_type: "status_kpi"
 *
 * A KPI tile with a modern trend badge showing direction and percentage.
 * Supports compact mode (renders as KPIStrip).
 *
 * Expected data shape:
 * {
 *   formatted_value: "468",
 *   label:           "Admits",
 *   secondary:       "-26% vs Prior",
 *   icon_name:       "users",       // category icon name
 *   display_mode:    "standard",    // "standard" | "compact"
 *   status_css:      "status-down"  // drives icon + colour selection
 * }
 */
export default function StatusKPI({ data = {}, name }) {
  const { formatted_value, label, secondary, icon_name, icon_position, display_mode,
          status_css, kpi_layout, label_font_weight, value_font_weight, label_color,
          value_color, text_align, icon_color, icon_bg } = data

  if (display_mode === 'compact') {
    return <KPIStrip data={data} name={name} />
  }

  const showIcon = icon_name && icon_name !== 'none' && icon_position !== 'title'
  const iconStyle = (icon_color || icon_bg)
    ? { ...(icon_color && { color: icon_color }), ...(icon_bg && { background: icon_bg }) }
    : undefined
  const valueStyle = (value_font_weight || value_color)
    ? { ...(value_font_weight && { fontWeight: value_font_weight }), ...(value_color && { color: value_color }) }
    : undefined
  const labelStyle = (label_font_weight || label_color)
    ? { ...(label_font_weight && { fontWeight: label_font_weight }), ...(label_color && { color: label_color }) }
    : undefined
  const alignStyle = text_align ? { textAlign: text_align } : undefined

  if (kpi_layout === 'inline') {
    return (
      <div className="pv-widget-status-kpi pv-kpi-strip--header-inline" style={alignStyle}>
        <div className="pv-kpi-header-row" style={alignStyle && { justifyContent: text_align }}>
          {showIcon && (
            <div className={`pv-category-icon ${iconStyle ? '' : (status_css || '')}`} style={iconStyle}>
              <CategoryIcon name={icon_name} />
            </div>
          )}
          {label && <div className="pv-widget-kpi-label" style={labelStyle}>{label}</div>}
        </div>
        <div className="pv-widget-kpi-value" style={{ ...valueStyle, ...alignStyle }}>{formatted_value ?? '—'}</div>
        {secondary && (
          <div className={`pv-trend-badge ${status_css || ''}`} style={alignStyle && { justifyContent: text_align }}>
            <TrendIcon statusCss={status_css} />
            <span>{secondary}</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="pv-widget-status-kpi" style={alignStyle}>
      {showIcon && (
        <div className={`pv-category-icon ${status_css || ''}`}>
          <CategoryIcon name={icon_name} />
        </div>
      )}
      {label && <div className="pv-widget-kpi-label" style={labelStyle}>{label}</div>}
      <div className="pv-widget-kpi-value" style={{ ...valueStyle, ...alignStyle }}>{formatted_value ?? '—'}</div>
      {secondary && (
        <div className={`pv-trend-badge ${status_css || ''}`} style={alignStyle && { justifyContent: text_align }}>
          <TrendIcon statusCss={status_css} />
          <span>{secondary}</span>
        </div>
      )}
    </div>
  )
}
