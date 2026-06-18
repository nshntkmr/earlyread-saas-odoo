import React from 'react'
import CategoryIcon from './CategoryIcons'
import KPIStrip from './KPIStrip'
import { resolveLabelPlacement } from './kpiLabelPosition'

/**
 * KPICard — chart_type: "kpi"
 *
 * Displays a large primary metric with a label and optional secondary line.
 * Supports compact mode (renders as KPIStrip) and category icons.
 *
 * Expected data shape:
 * {
 *   formatted_value: "1,234",
 *   label:           "Total Active Patients",
 *   secondary:       "as of Jan 2025",     // optional
 *   icon_name:       "users",              // optional
 *   display_mode:    "standard",           // "standard" | "compact"
 * }
 */
export default function KPICard({ data = {}, name }) {
  const { formatted_value, label, secondary, icon_name, display_mode,
          kpi_layout, label_font_weight, value_font_weight, label_color, value_color, text_align,
          icon_color, icon_bg } = data

  if (display_mode === 'compact') {
    return <KPIStrip data={data} name={name} />
  }

  const iconPosition = data.icon_position || 'title'
  const showIcon = icon_name && icon_name !== 'none' && iconPosition === 'body'
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

  // Label placement (opt-in). KPICard's current default differs by layout:
  // vertical renders the label BELOW the value, inline renders it ABOVE (in the
  // header row). Both preserved when kpi_label_position is unset/'default'.
  const showLabel = data.kpi_label_position !== 'hidden'
  const isLabelBadge = data.card_label_style === 'badge'
  const labelBadgeStyle = isLabelBadge ? {
    ...(data.card_label_badge_bg && { background: data.card_label_badge_bg }),
    ...(data.card_label_badge_text && { color: data.card_label_badge_text }),
  } : undefined
  const labelEl = (label && showLabel)
    ? <div className={`pv-widget-kpi-label${isLabelBadge ? ' pv-widget-kpi-label--badge' : ''}`}
           style={{ ...labelStyle, ...labelBadgeStyle }}>{label}</div>
    : null

  if (kpi_layout === 'inline') {
    const { above: labelAbove, below: labelBelow } = resolveLabelPlacement(data.kpi_label_position, true)
    return (
      <div className="pv-widget-kpi pv-kpi-strip--header-inline" style={alignStyle}>
        {(showIcon || labelAbove) && (
          <div className="pv-kpi-header-row" style={alignStyle && { justifyContent: text_align }}>
            {showIcon && (
              <div className="pv-category-icon" style={iconStyle}>
                <CategoryIcon name={icon_name} />
              </div>
            )}
            {labelAbove && labelEl}
          </div>
        )}
        <div className="pv-widget-kpi-value" style={{ ...valueStyle, ...alignStyle }}>{formatted_value ?? '—'}</div>
        {labelBelow && labelEl}
        {secondary && <div className="pv-widget-kpi-secondary" style={alignStyle}>{secondary}</div>}
      </div>
    )
  }

  const { above: labelAbove, below: labelBelow } = resolveLabelPlacement(data.kpi_label_position, false)
  return (
    <div className="pv-widget-kpi" style={alignStyle}>
      {showIcon && (
        <div className="pv-category-icon">
          <CategoryIcon name={icon_name} />
        </div>
      )}
      {labelAbove && labelEl}
      <div className="pv-widget-kpi-value" style={{ ...valueStyle, ...alignStyle }}>{formatted_value ?? '—'}</div>
      {labelBelow && labelEl}
      {secondary && <div className="pv-widget-kpi-secondary" style={alignStyle}>{secondary}</div>}
    </div>
  )
}
