import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useFilters } from '../state/FilterContext'
import { apiFetch } from '../api/client'
import { widgetDataUrl } from '../api/endpoints'

// ── Widget components ─────────────────────────────────────────────────────────
import KPICard      from './widgets/KPICard'
import BattleCard   from './widgets/BattleCard'
import InsightPanel from './widgets/InsightPanel'
import RankedDetailList from './widgets/RankedDetailList'
import MemberFlowTimeline from './widgets/MemberFlowTimeline'
// SmartTable lives in the shared @posterra/grid-utils package so the
// designer's preview pane and the portal both render via the same code.
import { SmartTable }  from '@posterra/grid-utils'
// Composite widget — renders 1..N children inside one card
import CompositeWidget from './widgets/CompositeWidget'
// Shared child registry — handles bar/line/pie/donut/kpi/table/gauge/etc.
import { resolveChildWidget } from './widgets/childRegistry'

// Lazy-load MapWidget to avoid 600KB+ MapLibre bundle on non-map pages
const MapWidget = React.lazy(() => import('./widgets/MapWidget'))

// ── Icons ──────────────────────────────────────────────────────────────────
import CategoryIcon from './widgets/CategoryIcons'

// ── Widget-scoped controls ──────────────────────────────────────────────────
import WidgetControls from './WidgetControls'

// ── Drill-down ──────────────────────────────────────────────────────────────
import DrillDownModal from './builder/DrillDownModal'

// Module-scope sets so they're constructed once, not per render.
// ECHART_TYPES — widgets whose payload is an ECharts option (rendered by EChartWidget).
// SCALABLE_TYPES — widgets that fill the card's vertical space; the rest render
// at natural height and top-align.
const ECHART_TYPES = new Set([
  'bar', 'line', 'pie', 'donut', 'radar', 'scatter', 'heatmap',
  'sankey',
])

const SCALABLE_TYPES = new Set([
  ...ECHART_TYPES,
  'table', 'gauge_kpi', 'map', 'ranked_detail_list', 'sankey_member_flow',
])

function resolveWidget(chartType) {
  // Top-level-only types (NOT in childRegistry — not safe as v1 composite children).
  switch (chartType) {
    case 'composite':          return CompositeWidget
    case 'map':                return MapWidget         // lazy — Suspense boundary preserved
    case 'ranked_detail_list': return RankedDetailList  // needs widgetId for /detail
    case 'smart_table':        return SmartTable        // also in childRegistry (composite-child-safe)
    case 'battle_card':        return BattleCard        // complex per-widget config
    case 'insight_panel':      return InsightPanel      // complex per-widget config
    case 'sankey_member_flow': return MemberFlowTimeline
  }
  // Everything else (bar/line/pie/donut/radar/scatter/heatmap/sankey/gauge/
  // gauge_kpi/kpi/status_kpi/kpi_strip/table/legend_list/text_note) resolves
  // via the child registry — same component is used in standalone + composite.
  const Resolved = resolveChildWidget(chartType)
  return Resolved || KPICard  // KPICard fallback preserves prior behavior for unknown types
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

  // Widget-scoped control state
  const [scopeValues, setScopeValues] = useState({})      // { widgetId: scopeValue }
  const [scopeOptionIds, setScopeOptionIds] = useState({}) // { widgetId: optionId } (query mode)
  const [searchTexts, setSearchTexts] = useState({})

  // Auto-select first scope option on mount for query-mode widgets
  // so the toggle button is active and filter-Apply includes _scope_option_id
  useEffect(() => {
    const initScope = {}, initOptIds = {}
    Object.values(widgetData).forEach(w => {
      if (w.scope?.mode !== 'none' && w.scope?.query_mode === 'query' && w.scope?.options?.length) {
        const defVal = w.scope.default_value || w.scope.options[0]?.value || ''
        const match = w.scope.options.find(o => (o.value ?? '') === defVal) || w.scope.options[0]
        initScope[w.id] = match.value ?? ''
        initOptIds[w.id] = match.id
      }
    })
    if (Object.keys(initScope).length) {
      setScopeValues(prev => ({ ...initScope, ...prev }))
      setScopeOptionIds(prev => ({ ...initOptIds, ...prev }))
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Drill-down modal
  const [drillState, setDrillState] = useState(null) // { widgetId, clickColumn, clickValue }

  // Track whether this is the initial mount (skip refetch on first render)
  const isFirst = useRef(true)

  // ── Widget-scoped control handler ─────────────────────────────────────────
  const handleScopeChange = useCallback(async (widgetId, newValue, optionId) => {
    setScopeValues(prev => ({ ...prev, [widgetId]: newValue }))
    if (optionId != null) setScopeOptionIds(prev => ({ ...prev, [widgetId]: optionId }))

    const w = widgetData[String(widgetId)]
    if (!w) return

    // Build params: page filters + scope param
    const params = { ...filterValues }
    if (w.scope?.query_mode === 'query' && optionId) {
      params._scope_option_id = optionId  // Query mode: send option ID
    } else if (w.scope?.param_name && newValue) {
      params[w.scope.param_name] = newValue  // Parameter mode: send param value
    }

    setLoading(prev => ({ ...prev, [widgetId]: true }))
    try {
      const url = widgetDataUrl(apiBase, widgetId, params)
      const result = await apiFetch(url, accessToken, {}, refreshToken)
      setWidgetData(prev => ({
        ...prev,
        [String(widgetId)]: { ...prev[String(widgetId)], data: result.data },
      }))
    } catch (err) {
      setErrors(prev => ({ ...prev, [widgetId]: err.message || 'Failed to load' }))
    } finally {
      setLoading(prev => ({ ...prev, [widgetId]: false }))
    }
  }, [widgetData, filterValues, apiBase, accessToken, refreshToken])

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
        // Include scope param if widget has active scope control
        const params = { ...filterValues }
        const sv = scopeValues[w.id]
        if (w.scope?.query_mode === 'query' && scopeOptionIds[w.id]) {
          params._scope_option_id = scopeOptionIds[w.id]
        } else if (w.scope?.param_name && sv) {
          params[w.scope.param_name] = sv
        }
        const url = widgetDataUrl(apiBase, w.id, params)
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
        // Include scope param if widget has active scope control
        const params = { ...filterValues }
        const sv = scopeValues[w.id]
        if (w.scope?.query_mode === 'query' && scopeOptionIds[w.id]) {
          params._scope_option_id = scopeOptionIds[w.id]
        } else if (w.scope?.param_name && sv) {
          params[w.scope.param_name] = sv
        }
        const url = widgetDataUrl(apiBase, w.id, params)
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
    // Resolution priority for the value to send:
    //   1. clickData.clickValue   ← server-attached clean drilldown key
    //                                (e.g. CCN from scatter's clickValue)
    //   2. clickData.value         ← raw cell/data value
    //   3. clickData.name          ← display text (last resort)
    const value =
      clickData.clickValue != null && clickData.clickValue !== ''
        ? String(clickData.clickValue)
        : (clickData.value != null
            ? String(clickData.value)
            : String(name))

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
        // App is implicit in the host (e.g. posterra.example.com), so
        // links are same-host relative paths — no /my/<app_key>/ prefix.
        const pageKey = widget.action_page_key || ''
        const tabKey = widget.action_tab_key || ''
        const param = widget.action_pass_value_as || ''
        let targetUrl = `/${pageKey}`
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

  // ── CSS Grid: convert percentage width to 24-column grid span ───
  // 24 columns gives finer control (supports 4%, 8%, 12%, 14% widths)
  const pctToGridCols = (pct) => {
    const p = pct || 50
    return Math.max(1, Math.round((p / 100) * 24))
  }

  // (ECHART_TYPES and SCALABLE_TYPES are declared at module scope above so
  // they're not reconstructed on every render. ECHART_TYPES had been
  // referenced here without being declared — fixed.)

  const renderWidget = (w) => {
    const WidgetComponent = resolveWidget(w.chart_type)
    const isLoading = !!loading[w.id]
    const error = errors[w.id]
    const isEChart = ECHART_TYPES.has(w.chart_type)
    const isTable = w.chart_type === 'table'

    // Compact mode: kpi_strip chart type or display_mode === 'compact'
    const isCompact = w.chart_type === 'kpi_strip' || w.display_mode === 'compact'

    // Scalable widgets (ECharts, tables) fill available height.
    // Non-scalable widgets (gauge variants, KPI, battle card) render at natural size
    // but still receive height prop so admin can constrain them for compact layouts.
    const isGaugeNonEchart = w.chart_type === 'gauge' && w.data?.gauge_variant
    const isScalable = SCALABLE_TYPES.has(w.chart_type) && !isGaugeNonEchart
    // KPI cards are non-scalable but should still honor an admin-set Height (px) so a rail
    // of KPIs can be equalized. Scoped to kpi/status_kpi only — other non-scalable types
    // (battle_card, insight_panel, text_note, gauge-non-echart) keep ignoring Height.
    const isKpiCard = w.chart_type === 'kpi' || w.chart_type === 'status_kpi'
    // Charts and the AG Grid table honor an admin Height as an EXACT card height (vs
    // minimum): the chart fills its body and the table scrolls internally, so the card
    // is truly that tall. (smart_table is excluded — it manages its own scroll height.)
    const isExactHeightType = isEChart || isTable
    const componentHeight = w.height || undefined

    // Extra props for interactive widgets
    const extraProps = {}
    if (isEChart) {
      extraProps.clickAction = w.click_action
      extraProps.onChartClick = (clickData) => handleWidgetClick(w, clickData)
      // Fill the card body (flex) instead of a fixed-px canvas → no white band.
      extraProps.fill = true
    }
    if (isTable) {
      // Pass search text for AG Grid quickFilterText
      if (w.search && searchTexts[w.id]) {
        extraProps.searchText = searchTexts[w.id]
      }
      if (w.column_link_config) {
        extraProps.columnLinkConfig = w.column_link_config
      }
      // Always pass onCellClick for AG Grid tables — column-level clickAction
      // handles its own dispatch in DataTable.jsx (filter_page, go_to_page, open_url).
      // show_details needs WidgetGrid's drillState, so it dispatches through onCellClick.
      extraProps.onCellClick = (clickData) => handleWidgetClick(w, {
        name: clickData.column,
        value: clickData.value,
      })
      // Exact height set → table fills the card and scrolls internally (overrides
      // the autoHeight default which would expand the card past the configured height).
      if (!isCompact && w.height) {
        extraProps.fillHeight = true
      }
    }
    if (w.chart_type === 'ranked_detail_list') {
      extraProps.widgetId = w.id
      // Pass the active scope option id (Mode B) so detail fetches include it
      if (w.scope?.query_mode === 'query' && scopeOptionIds[w.id]) {
        extraProps.scopeOptionId = scopeOptionIds[w.id]
      }
    }

    // CSS Grid placement: column span from width, row span for tall widgets
    const gridColSpan = pctToGridCols(w.col_span)
    const gridRowSpan = w.row_span || 1

    return (
      <div
        key={w.id}
        className="pv-widget-col"
        style={{
          gridColumn: `span ${gridColSpan}`,
          gridRow: `span ${gridRowSpan}`,
          ...(!isScalable && !isCompact ? { alignSelf: 'start' } : {}),
        }}
      >
        <div
          className={`pv-widget-card${
            w.display_density === 'compact' ? ' pv-widget-card--compact-density' :
            w.display_density === 'dense' ? ' pv-widget-card--dense' : ''
          }${
            w.card_padding && w.card_padding !== 'standard'
              ? ` pv-widget-card--pad-${w.card_padding}` : ''
          }`}
          style={{
            // Charts/tables with a Height set → EXACT height (content fills/scrolls inside).
            ...(!isCompact && w.height && isExactHeightType ? { height: w.height } : {}),
            // KPI cards + other scalable types → Height is a minimum (grow-only).
            ...(!isCompact && w.height && !isExactHeightType && (isScalable || isKpiCard) ? { minHeight: w.height } : {}),
            // Non-scalable widgets with no exact height → natural height.
            ...(!isScalable && !isCompact && !(w.height && isExactHeightType) ? { height: 'auto' } : {}),
          }}
        >
          {!isCompact && (
            <div className="pv-widget-card-header">
              {w.icon_name && w.icon_name !== 'none' && w.icon_position === 'title' && (() => {
                const titleStatusCss = w.title_icon_color_mode === 'status'
                  ? (w.data?.status_css || '')
                  : ''
                const titleStyle = w.title_icon_color && w.title_icon_color_mode !== 'status'
                  ? { color: w.title_icon_color }
                  : undefined
                return (
                  <span
                    className={`pv-widget-title-icon${titleStatusCss ? ` ${titleStatusCss}` : ''}`}
                    style={titleStyle}
                  >
                    <CategoryIcon name={w.icon_name} />
                  </span>
                )
              })()}
              <span
                className="pv-widget-title"
                style={w.title_text_color
                  ? { color: w.title_text_color }
                  : (w.label_font_weight || w.label_color)
                    ? { ...(w.label_font_weight && { fontWeight: w.label_font_weight }), ...(w.label_color && { color: w.label_color }) }
                    : undefined}
              >{w.name}</span>
              {/* Widget-scoped controls (toggle/dropdown/search) */}
              <WidgetControls
                scope={w.scope}
                search={w.search}
                scopeValue={scopeValues[w.id] ?? w.scope?.default_value ?? ''}
                onScopeChange={(val, optId) => handleScopeChange(w.id, val, optId)}
                searchText={searchTexts[w.id] || ''}
                onSearchChange={(val) => setSearchTexts(prev => ({ ...prev, [w.id]: val }))}
              />
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
      <React.Suspense fallback={null}>
      <div className="pv-widget-grid">
        {visibleWidgets.map(w => renderWidget(w))}
      </div>

      </React.Suspense>

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
