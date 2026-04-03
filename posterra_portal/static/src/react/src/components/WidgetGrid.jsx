import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useFilters } from '../state/FilterContext'
import { apiFetch } from '../api/client'
import { widgetDataUrl } from '../api/endpoints'

// ── Widget components ─────────────────────────────────────────────────────────
import EChartWidget from './widgets/EChartWidget'
import GaugeKPI     from './widgets/GaugeKPI'
import KPICard      from './widgets/KPICard'
import StatusKPI    from './widgets/StatusKPI'
import DataTable    from './widgets/DataTable'
import BattleCard   from './widgets/BattleCard'
import InsightPanel from './widgets/InsightPanel'
import KPIStrip    from './widgets/KPIStrip'
import GaugeRouter from './widgets/GaugeRouter'
import KpiRouter   from './widgets/KpiRouter'

// ── Drill-down ──────────────────────────────────────────────────────────────
import DrillDownModal from './builder/DrillDownModal'

// Chart types handled by the generic EChartWidget
const ECHART_TYPES = new Set(['bar', 'line', 'pie', 'donut', 'radar', 'scatter', 'heatmap'])

function resolveWidget(chartType) {
  if (ECHART_TYPES.has(chartType)) return EChartWidget
  switch (chartType) {
    case 'gauge':        return GaugeRouter
    case 'gauge_kpi':    return GaugeKPI
    case 'kpi':          return KpiRouter
    case 'status_kpi':   return KpiRouter
    case 'table':        return DataTable
    case 'battle_card':  return BattleCard
    case 'insight_panel':return InsightPanel
    case 'kpi_strip':   return KpiRouter
    default:             return KPICard   // safe fallback
  }
}

/**
 * WidgetGrid
 *
 * Displays all widgets for the active tab.
 *
 * First render: uses initialWidgets (data embedded in QWeb HTML, zero API calls).
 * After filter Apply: fires parallel GET /api/v1/widget/<id>/data?... for every
 * visible widget and re-renders as responses arrive.
 *
 * Click actions: dispatches drill-down, page navigation, filter, or URL open.
 */
export default function WidgetGrid({ initialWidgets }) {
  const { config, filterValues, currentTabKey, accessToken, refreshToken, apiBase } = useFilters()

  // widgetData state: { "<widgetId>": { ...widgetMeta, data: {...} } }
  const [widgetData, setWidgetData] = useState(initialWidgets || {})
  // loading state per widget
  const [loading, setLoading] = useState({})
  // error state per widget
  const [errors, setErrors] = useState({})

  // Drill-down modal
  const [drillState, setDrillState] = useState(null) // { widgetId, clickColumn, clickValue }

  // Track whether this is the initial mount (skip refetch on first render)
  const isFirst = useRef(true)

  // ── Refetch when filterValues changes (after Apply) ───────────────────────
  useEffect(() => {
    if (isFirst.current) {
      isFirst.current = false
      return
    }
    const visibleWidgets = Object.values(widgetData).filter(w =>
      !currentTabKey || !w.tab_key || w.tab_key === currentTabKey
    )

    // Mark non-visible (other-tab) widgets as deferred so they re-fetch
    // with new filter values when the user switches to that tab
    setWidgetData(prev => {
      const updated = { ...prev }
      Object.values(updated).forEach(w => {
        if (w.tab_key && w.tab_key !== currentTabKey) {
          updated[String(w.id)] = { ...w, data: { _deferred: true } }
        }
      })
      return updated
    })

    if (!visibleWidgets.length) return

    // Mark all visible widgets as loading
    const loadingMap = {}
    visibleWidgets.forEach(w => { loadingMap[w.id] = true })
    setLoading(loadingMap)
    setErrors({})

    // Fire all fetches in parallel
    visibleWidgets.forEach(async (w) => {
      try {
        const url = widgetDataUrl(apiBase, w.id, filterValues)
        const result = await apiFetch(url, accessToken, {}, refreshToken)
        setWidgetData(prev => ({
          ...prev,
          [String(w.id)]: { ...prev[String(w.id)], data: result.data },
        }))
      } catch (err) {
        setErrors(prev => ({ ...prev, [w.id]: err.message || 'Failed to load' }))
      } finally {
        setLoading(prev => ({ ...prev, [w.id]: false }))
      }
    })
  }, [filterValues]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Lazy-load deferred widgets when switching tabs ────────────────────────
  // Server sends _deferred: true for non-current-tab widgets (no SQL executed).
  // When user clicks a new tab, fetch those widgets via per-widget API.
  // Once fetched, they stay cached — switching back is instant.
  useEffect(() => {
    if (!currentTabKey) return
    const deferredWidgets = Object.values(widgetData).filter(w =>
      w.tab_key === currentTabKey && w.data && w.data._deferred
    )
    if (!deferredWidgets.length) return

    // Mark deferred widgets as loading
    const loadingMap = {}
    deferredWidgets.forEach(w => { loadingMap[w.id] = true })
    setLoading(prev => ({ ...prev, ...loadingMap }))

    // Fetch each deferred widget in parallel
    deferredWidgets.forEach(async (w) => {
      try {
        const url = widgetDataUrl(apiBase, w.id, filterValues)
        const result = await apiFetch(url, accessToken, {}, refreshToken)
        setWidgetData(prev => ({
          ...prev,
          [String(w.id)]: { ...prev[String(w.id)], data: result.data },
        }))
      } catch (err) {
        setErrors(prev => ({ ...prev, [w.id]: err.message || 'Failed to load' }))
      } finally {
        setLoading(prev => ({ ...prev, [w.id]: false }))
      }
    })
  }, [currentTabKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Click action handler ──────────────────────────────────────────────────
  const handleWidgetClick = useCallback((widget, clickData) => {
    const action = widget.click_action || 'none'
    const name = clickData.name || clickData.column || ''
    const value = clickData.value != null ? String(clickData.value) : String(name)

    switch (action) {
      case 'filter_page': {
        // Apply the clicked value as a filter on the current page
        // This would dispatch a filter update — handled via URL params
        const param = widget.action_pass_value_as || 'hha_name'
        const url = new URL(window.location)
        url.searchParams.set(param, value)
        window.location.href = url.toString()
        break
      }
      case 'go_to_page': {
        const pageKey = widget.action_page_key || ''
        const tabKey = widget.action_tab_key || ''
        const param = widget.action_pass_value_as || ''
        let targetUrl = `/my/posterra/${pageKey}`
        if (tabKey) targetUrl += `?tab=${tabKey}`
        if (param && value) {
          targetUrl += (targetUrl.includes('?') ? '&' : '?') + `${param}=${encodeURIComponent(value)}`
        }
        window.location.href = targetUrl
        break
      }
      case 'show_details': {
        setDrillState({
          widgetId: widget.id,
          clickColumn: name,
          clickValue: value,
        })
        break
      }
      case 'open_url': {
        const tpl = widget.action_url_template || ''
        const finalUrl = tpl.replace(/\{value\}/g, encodeURIComponent(value))
        window.open(finalUrl, '_blank', 'noopener')
        break
      }
      default:
        break
    }
  }, [])

  // ── Visible widgets for the current tab ──────────────────────────────────
  const visibleWidgets = Object.values(widgetData)
    .filter(w => !currentTabKey || !w.tab_key || w.tab_key === currentTabKey)
    .sort((a, b) => (a.sequence || 0) - (b.sequence || 0))

  if (!visibleWidgets.length) {
    return (
      <div className="pv-content">
        <div className="pv-placeholder">
          <p>No widgets configured for this tab.</p>
        </div>
      </div>
    )
  }

  // ── Auto row-break: group widgets into rows based on cumulative width ───
  const rows = []
  let currentRow = [], usedWidth = 0
  for (const w of visibleWidgets) {
    const widthPct = w.col_span || 50
    if (currentRow.length > 0 && usedWidth + widthPct > 100) {
      rows.push(currentRow)
      currentRow = [w]
      usedWidth = widthPct
    } else {
      currentRow.push(w)
      usedWidth += widthPct
    }
  }
  if (currentRow.length) rows.push(currentRow)

  // Widget types that scale their content to fill available height (ECharts canvas,
  // tables with more rows, gauge_kpi composite). Non-scalable widgets (traffic light,
  // bullet, percentile, KPI, battle card, insight) render at their natural height
  // and top-align within the card — they don't benefit from extra vertical space.
  const SCALABLE_TYPES = new Set([...ECHART_TYPES, 'table', 'gauge_kpi'])

  const renderWidget = (w, rowTotalWidth) => {
    const WidgetComponent = resolveWidget(w.chart_type)
    const isLoading = !!loading[w.id]
    const error = errors[w.id]
    const isEChart = ECHART_TYPES.has(w.chart_type)
    const isTable = w.chart_type === 'table'

    // Compact mode: kpi_strip chart type or display_mode === 'compact'
    const isCompact = w.chart_type === 'kpi_strip' || w.display_mode === 'compact'

    // Scalable widgets (ECharts, tables) get the configured height passed through.
    // Non-scalable widgets (gauge variants, KPI, battle card) render at natural size.
    const isGaugeNonEchart = w.chart_type === 'gauge' && w.data?.gauge_variant
    const isScalable = SCALABLE_TYPES.has(w.chart_type) && !isGaugeNonEchart
    const componentHeight = isScalable ? w.height : undefined

    // Extra props for interactive widgets
    const extraProps = {}
    if (isEChart) {
      extraProps.clickAction = w.click_action
      extraProps.onChartClick = (clickData) => handleWidgetClick(w, clickData)
    }
    if (isTable && w.column_link_config) {
      extraProps.columnLinkConfig = w.column_link_config
      extraProps.onCellClick = (clickData) => handleWidgetClick(w, {
        name: clickData.column,
        value: clickData.value,
      })
    }

    // Scale widget width to fill underfilled rows, capped by max_col_span
    const rawWidth = w.col_span || 50
    let scaledWidth = rawWidth
    if (rowTotalWidth > 0 && rowTotalWidth < 100) {
      scaledWidth = (rawWidth / rowTotalWidth) * 100
    }
    if (w.max_col_span > 0 && scaledWidth > w.max_col_span) {
      scaledWidth = w.max_col_span
    }

    return (
      <div
        key={w.id}
        className="pv-widget-col"
        style={{
          width: `${scaledWidth}%`,
          ...(!isScalable && !isCompact ? { alignSelf: 'flex-start' } : {}),
        }}
      >
        <div
          className="pv-widget-card"
          style={{
            ...(!isCompact && w.height && isScalable ? { minHeight: w.height } : {}),
            ...(!isScalable && !isCompact ? { height: 'auto' } : {}),
          }}
        >
          {!isCompact && (
            <div className="pv-widget-card-header">
              <span
                className="pv-widget-title"
                style={(w.label_font_weight || w.label_color)
                  ? { ...(w.label_font_weight && { fontWeight: w.label_font_weight }), ...(w.label_color && { color: w.label_color }) }
                  : undefined}
              >{w.name}</span>
              {w.annotation_type === 'badge' && w.annotation_text && (
                <span className="pv-widget-badge badge bg-light text-dark ms-2">
                  {w.annotation_text}
                </span>
              )}
              {isLoading && (
                <span className="pv-widget-spinner spinner-border spinner-border-sm ms-2" role="status" aria-hidden="true" />
              )}
            </div>
          )}
          {!isCompact && w.subtitle && (
            <div className="pv-widget-subtitle text-muted px-3">
              {w.subtitle}
            </div>
          )}
          {error || w.data?.error ? (
            <div className="pv-widget-error text-danger p-3">
              <small>⚠ {error || w.data?.error}</small>
            </div>
          ) : isLoading ? (
            <div className="pv-widget-loading" style={{ height: isCompact ? 48 : (w.height || 120) }}>
              <div className="pv-widget-skeleton" />
            </div>
          ) : (
            <WidgetComponent data={w.data} height={componentHeight} name={w.name} {...extraProps} />
          )}
          {w.footnote && (
            <div className="pv-widget-footnote text-muted px-3 pb-2 mt-auto border-top pt-1">
              {w.footnote}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="pv-content">
      {rows.map((rowWidgets, rowIdx) => {
        const rowTotal = rowWidgets.reduce((sum, w) => sum + (w.col_span || 50), 0)
        return (
          <div className="row g-3" key={rowIdx}>
            {rowWidgets.map(w => renderWidget(w, rowTotal))}
          </div>
        )
      })}

      {/* Drill-Down Modal */}
      {drillState && (
        <DrillDownModal
          widgetId={drillState.widgetId}
          clickColumn={drillState.clickColumn}
          clickValue={drillState.clickValue}
          filterParams={filterValues}
          onClose={() => setDrillState(null)}
          apiBase={apiBase}
          accessToken={accessToken}
          refreshToken={refreshToken}
        />
      )}
    </div>
  )
}
