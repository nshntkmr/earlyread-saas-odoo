import React from 'react'
import { TrendIcon } from './TrendIcons'
import CategoryIcon from './CategoryIcons'

/**
 * KPIStrip — compact horizontal KPI row.
 *
 * Used by chart_type "kpi_strip" or when display_mode === "compact" on kpi/status_kpi.
 *
 * Expected data shape:
 * {
 *   formatted_value: "1,561",
 *   label:           "Total Admits",
 *   secondary:       "-54% vs Prior",
 *   icon_name:       "users",        // optional category icon
 *   status_css:      "status-down",  // optional trend status
 * }
 */
export default function KPIStrip({ data = {}, name }) {
  const { formatted_value, label, secondary, icon_name, icon_position, status_css,
          kpi_layout, label_font_weight, value_font_weight, label_color, value_color,
          text_align, icon_color, icon_bg } = data
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
      <div className="pv-kpi-strip pv-kpi-strip--header-inline" style={alignStyle}>
        <div className="pv-kpi-header-row" style={alignStyle && { justifyContent: text_align }}>
          {showIcon && (
            <div className={`pv-kpi-strip-icon ${iconStyle ? '' : (status_css || '')}`} style={iconStyle}>
              <CategoryIcon name={icon_name} />
            </div>
          )}
          <div className="pv-kpi-strip-label" style={labelStyle}>{label || name}</div>
        </div>
        <div className="pv-kpi-strip-value" style={{ ...valueStyle, ...alignStyle }}>{formatted_value ?? '—'}</div>
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
    <div className="pv-kpi-strip" style={alignStyle}>
      {showIcon && (
        <div className={`pv-kpi-strip-icon ${status_css || ''}`}>
          <CategoryIcon name={icon_name} />
        </div>
      )}
      <div className="pv-kpi-strip-label" style={labelStyle}>{label || name}</div>
      <div className="pv-kpi-strip-value" style={{ ...valueStyle, ...alignStyle }}>{formatted_value ?? '—'}</div>
      {secondary && (
        <div className={`pv-trend-badge ${status_css || ''}`} style={alignStyle && { justifyContent: text_align }}>
          <TrendIcon statusCss={status_css} />
          <span>{secondary}</span>
        </div>
      )}
    </div>
  )
}
