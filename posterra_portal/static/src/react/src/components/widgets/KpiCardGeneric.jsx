import React from 'react'
import EChartWidget from './EChartWidget'
import { TrendIcon } from './TrendIcons'
import CategoryIcon from './CategoryIcons'

/**
 * KpiCardGeneric — One generic KPI card, 3 layouts, ECharts for data-viz.
 *
 * All text comes from the backend — zero computation in frontend.
 * ECharts handles all data-viz variety (sparkline, progress bar, gauge ring).
 *
 * Layouts:
 *   standard  — vertical stack (sparkline, progress, rag_status)
 *   split     — horizontal: chart left, text right (mini_gauge)
 *   dual      — two value columns side by side (comparison)
 */
export default function KpiCardGeneric({ data = {}, name }) {
  const {
    kpi_variant, formatted_value, label, secondary, status_css, icon_name,
    icon_position, label_font_weight, value_font_weight, label_color, value_color,
    text_align, icon_color, icon_bg,
  } = data

  const showIcon = icon_name && icon_name !== 'none' && icon_position !== 'title'
  const valueStyle = (value_font_weight || value_color)
    ? { ...(value_font_weight && { fontWeight: value_font_weight }), ...(value_color && { color: value_color }) }
    : undefined
  const labelStyle = (label_font_weight || label_color)
    ? { ...(label_font_weight && { fontWeight: label_font_weight }), ...(label_color && { color: label_color }) }
    : undefined
  const iconStyle = (icon_color || icon_bg)
    ? { ...(icon_color && { color: icon_color }), ...(icon_bg && { background: icon_bg }) }
    : undefined

  // ── Layout: Split (mini_gauge) ────────────────────────────────────────
  if (kpi_variant === 'mini_gauge') {
    const chartSize = data.mini_gauge_size || 64
    return (
      <div className="pv-kpi-card-split">
        {data.echart_option && (
          <div className="pv-kpi-mini-chart pv-kpi-mini-chart--left"
               style={{ width: chartSize, height: chartSize, flexShrink: 0 }}>
            <EChartWidget data={data} height={chartSize} />
          </div>
        )}
        <div className="pv-kpi-card-text">
          {label && <div className="pv-widget-kpi-label" style={labelStyle}>{label}</div>}
          {data.gauge_status_text && (
            <div className="pv-widget-kpi-secondary">{data.gauge_status_text}</div>
          )}
          {data.progress_annotation && (
            <div className={`pv-kpi-annotation ${
              data.progress_pct >= 100 ? 'status-up' : 'status-down'
            }`}>
              {data.progress_annotation}
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Layout: Dual-column (comparison) ──────────────────────────────────
  if (kpi_variant === 'comparison') {
    return (
      <div className="pv-kpi-card-dual">
        <div className="pv-kpi-card-dual-header">
          {label && <div className="pv-widget-kpi-label" style={labelStyle}>{label}</div>}
        </div>
        <div className="pv-kpi-card-dual-columns">
          <div className="pv-kpi-card-dual-col">
            {data.current_label && (
              <div className="pv-kpi-card-period-label">{data.current_label}</div>
            )}
            <div className="pv-widget-kpi-value" style={valueStyle}>
              {formatted_value ?? '—'}
            </div>
          </div>
          <div className="pv-kpi-card-dual-vs">VS</div>
          <div className="pv-kpi-card-dual-col">
            {data.prior_label && (
              <div className="pv-kpi-card-period-label">{data.prior_label}</div>
            )}
            <div className="pv-widget-kpi-value pv-kpi-card-prior-value">
              {data.prior_formatted ?? '—'}
            </div>
          </div>
        </div>
        {data.diff_annotation && (
          <div className={`pv-trend-badge ${data.diff_status || ''}`}>
            <TrendIcon statusCss={data.diff_status} />
            <span>{data.diff_annotation}</span>
          </div>
        )}
      </div>
    )
  }

  // ── Layout: Standard (sparkline, progress, rag_status) ────────────────
  const isRag = kpi_variant === 'rag_status'
  const ragClass = isRag && data.rag_color ? `pv-kpi-card--rag-${data.rag_color}` : ''
  const hasChart = !!data.echart_option
  const isSparkline = kpi_variant === 'sparkline'
  const isProgress = kpi_variant === 'progress'

  return (
    <div className={`pv-kpi-card-standard ${ragClass}`}>
      {isSparkline && hasChart && (
        <div className="pv-kpi-mini-chart pv-kpi-mini-chart--top-right">
          <EChartWidget data={data} height={40} />
        </div>
      )}

      <div className="pv-kpi-card-body" style={text_align ? { textAlign: text_align } : undefined}>
        {showIcon && (
          <div className={`pv-category-icon ${iconStyle ? '' : (status_css || '')}`} style={iconStyle}>
            <CategoryIcon name={icon_name} />
          </div>
        )}
        {label && <div className="pv-widget-kpi-label" style={labelStyle}>{label}</div>}

        {isProgress && data.target_formatted && (
          <div className="pv-kpi-target-label">TARGET: {data.target_formatted}</div>
        )}

        <div className="pv-widget-kpi-value" style={{
          ...valueStyle,
          ...(isRag && data.rag_color ? { color: RAG_COLORS[data.rag_color] } : {}),
        }}>
          {formatted_value ?? '—'}
        </div>

        {secondary && !isProgress && !isRag && (
          <div className={`pv-trend-badge ${status_css || ''}`}>
            <TrendIcon statusCss={status_css} />
            <span>{secondary}</span>
          </div>
        )}

        {isRag && data.rag_badge && (
          <div className={`pv-kpi-rag-badge pv-kpi-rag-badge--${data.rag_color || 'neutral'}`}>
            {data.rag_badge}
          </div>
        )}
      </div>

      {isProgress && hasChart && (
        <div className="pv-kpi-mini-chart pv-kpi-mini-chart--bottom">
          <EChartWidget data={data} height={20} />
          <div className="pv-kpi-progress-scale">
            <span>0%</span>
            {data.progress_annotation && (
              <span className={data.progress_pct >= 100 ? 'status-up' : 'status-down'}>
                {data.progress_annotation}
              </span>
            )}
            <span>100%</span>
          </div>
        </div>
      )}
    </div>
  )
}

const RAG_COLORS = {
  green: '#10b981',
  amber: '#d97706',
  red: '#e11d48',
  neutral: '#6b7280',
}
