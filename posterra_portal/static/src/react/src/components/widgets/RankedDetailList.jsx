import React, { useState, useCallback, useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { useFilters } from '../../state/FilterContext'
import { apiFetch } from '../../api/client'
import { widgetDetailUrl } from '../../api/endpoints'
import { CELL_RENDERERS } from '@posterra/grid-utils'

/**
 * RankedDetailList (v2)
 *
 * A ranked list widget where each row can expand inline to show detail
 * tiles (bar/line/KPI) and a nested sub-list.
 *
 * Supports two config formats:
 *   v2 (preferred): consolidated master_config + detail_config (built by
 *       the Dashboard Builder — all element toggles, column refs, tiles,
 *       sub-list layout, YOU indicator, inline charts)
 *   v1 (legacy): AG Grid columnDefs arrays + separate detail_chart_config
 *       + detail_sublist_config (kept for backward compat)
 *
 * Props:
 *   data     — { rowData, key_column, has_detail, master_config,
 *               detail_config, columnDefs, detail_chart_config,
 *               detail_sublist_config }
 *   height   — optional max height (enables scrolling)
 *   name     — widget title
 *   widgetId — widget ID (for detail API calls)
 */

// ── Embedded ECharts tile ─────────────────────────────────────────────
function MiniChart({ option, height = 200 }) {
  const ref = useRef(null)
  const chartRef = useRef(null)

  useEffect(() => {
    if (!ref.current) return
    chartRef.current = echarts.init(ref.current, null, { renderer: 'canvas' })
    chartRef.current.setOption(option, { notMerge: true })

    const onResize = () => chartRef.current?.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    if (chartRef.current && option) {
      chartRef.current.setOption(option, { notMerge: true })
    }
  }, [option])

  return <div ref={ref} style={{ width: '100%', height }} />
}

// ── KPI tile (simple card; reuses the visual style of KPICard) ───────
function KpiTile({ data }) {
  if (!data) return null
  const type = data.type || 'kpi'

  if (type === 'kpi_strip') {
    return (
      <div className="pv-ranked-kpi-strip">
        {(data.items || []).map((it, i) => (
          <div key={i} className="pv-ranked-kpi-strip-item">
            <div className="pv-ranked-kpi-strip-value">{it.value}</div>
            <div className="pv-ranked-kpi-strip-label">{it.label}</div>
          </div>
        ))}
      </div>
    )
  }

  // status_kpi (RAG) or basic kpi
  const statusClass = data.status_val
    ? `pv-ranked-kpi-tile--${data.status_val}`
    : ''
  return (
    <div className={`pv-ranked-kpi-tile ${statusClass}`}>
      <div className="pv-ranked-kpi-value">
        {data.kpi_prefix}{data.formatted_value}{data.kpi_suffix}
      </div>
      <div className="pv-ranked-kpi-label">{data.label}</div>
    </div>
  )
}

// ── Cell-renderer helper (invokes shared CELL_RENDERERS) ──────────────
function CellValue({ rendererName, row, field, rendererParams }) {
  const value = field ? row[field] : null
  if (rendererName && CELL_RENDERERS[rendererName]) {
    const Renderer = CELL_RENDERERS[rendererName]
    const params = {
      value, data: row,
      colDef: { field, cellRendererParams: rendererParams || {} },
    }
    return <Renderer params={params} />
  }
  if (value === null || value === undefined || value === '') return null
  return <span>{String(value)}</span>
}

// ── Number formatter (shared across master + sublist rows) ────────────
function formatNumber(val, fmt) {
  if (val === null || val === undefined || val === '') return ''
  const n = Number(val)
  if (isNaN(n)) return String(val)
  const decimals = fmt?.decimals ?? 0
  const prefix = fmt?.prefix ?? ''
  const suffix = fmt?.suffix ?? ''
  if (fmt?.format === 'percentage') {
    const mult = fmt.multiply === false ? 1 : 1 // admin SQL usually pre-computes
    return prefix + (n * mult).toFixed(decimals) + '%' + suffix
  }
  if (fmt?.format === 'currency') {
    return prefix + '$' + n.toLocaleString('en-US', {
      minimumFractionDigits: decimals, maximumFractionDigits: decimals,
    }) + suffix
  }
  return prefix + n.toLocaleString('en-US', {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }) + suffix
}

// ── Shared row renderer (used for master rows AND sublist rows) ───────
// Renders a single row based on the layout config (v2 master_config shape).
// `isYou` forces YOU styling regardless of layout.
function LayoutRow({ layout, row, rankNum, onNavigate, onExternalLink, onToggle,
                    isExpanded, isYou, youColor, peerColor, showProgressBar,
                    sharePctField }) {
  if (!layout) return null

  const rankCfg = layout.rank || {}
  const badgeCfg = layout.badge || {}
  const subtitleCfg = layout.subtitle || {}
  const sparklineCfg = layout.sparkline || {}
  const inlineCfg = layout.inlineChart || {}
  const primaryCfg = layout.primaryMetric || {}
  const secondaryCfg = layout.secondaryMetric || {}
  const navCfg = layout.navigationArrow || {}
  const linkCfg = layout.externalLink || {}
  const expandCfg = layout.expandChevron || {}
  const nameCol = layout.name?.column

  const rankDisplay = rankCfg.enabled !== false
    ? (rankCfg.style === 'medal' && rankNum <= 3
        ? ['\u{1F947}', '\u{1F948}', '\u{1F949}'][rankNum - 1]
        : rankNum)
    : null

  const primaryVal = formatNumber(row[primaryCfg.column], primaryCfg)
  const secondaryVal = secondaryCfg.enabled !== false && secondaryCfg.column
    ? formatNumber(row[secondaryCfg.column], secondaryCfg)
    : null

  const sharePct = showProgressBar && sharePctField
    ? Number(row[sharePctField]) || 0
    : null
  const barColor = isYou ? (youColor || '#10b981') : (peerColor || '#f59e0b')

  return (
    <div
      className={`pv-ranked-row${isExpanded ? ' pv-ranked-row--expanded' : ''}${isYou ? ' pv-ranked-row--you' : ''}`}
    >
      {rankDisplay !== null && (
        <div className="pv-ranked-row-rank">{rankDisplay}</div>
      )}

      <div className="pv-ranked-row-body">
        <div className="pv-ranked-row-primary">
          <span className="pv-ranked-row-name">
            {nameCol ? row[nameCol] : ''}
          </span>
          {isYou && (
            <span
              className="pv-ranked-you-badge"
              style={{ backgroundColor: youColor || '#10b981' }}
            >YOU</span>
          )}
          {badgeCfg.enabled && (() => {
            const badgeText = badgeCfg.source === 'static'
              ? badgeCfg.text
              : (badgeCfg.column ? row[badgeCfg.column] : '')
            if (!badgeText) return null
            return (
              <span
                className="pv-ranked-row-badge"
                style={badgeCfg.color ? { backgroundColor: badgeCfg.color } : undefined}
              >{badgeText}</span>
            )
          })()}
        </div>
        {subtitleCfg.enabled && subtitleCfg.column && row[subtitleCfg.column] && (
          <div className="pv-ranked-row-subtitle">{row[subtitleCfg.column]}</div>
        )}
        {showProgressBar && sharePct !== null && (
          <div className="pv-ranked-row-progress">
            <div
              className="pv-ranked-row-progress-bar"
              style={{ width: `${Math.min(100, Math.max(0, sharePct))}%`, backgroundColor: barColor }}
            />
          </div>
        )}
      </div>

      <div className="pv-ranked-row-meta">
        {sparklineCfg.enabled && sparklineCfg.column && (
          <CellValue
            rendererName="sparkline"
            row={row}
            field={sparklineCfg.column}
            rendererParams={{
              variant: sparklineCfg.variant || 'line',
              color: sparklineCfg.color || 'auto',
            }}
          />
        )}
        {inlineCfg.enabled && inlineCfg.column && (
          <CellValue
            rendererName="inlineChart"
            row={row}
            field={inlineCfg.column}
            rendererParams={{
              type: inlineCfg.type || 'bar',
              size: inlineCfg.size || 'small',
              color: inlineCfg.color,
            }}
          />
        )}
        {primaryCfg.column && (
          <span className="pv-ranked-row-metric">
            <strong>{primaryVal}</strong>
            {secondaryVal && (
              <span className="pv-ranked-row-secondary">{secondaryVal}</span>
            )}
          </span>
        )}
      </div>

      <div className="pv-ranked-row-actions">
        {navCfg.enabled && onNavigate && (
          <button
            className="pv-ranked-action-btn"
            title="View details"
            onClick={onNavigate}
          ><i className="fa fa-arrow-right" /></button>
        )}
        {linkCfg.enabled && onExternalLink && (
          <button
            className="pv-ranked-action-btn"
            title="External link"
            onClick={onExternalLink}
          ><i className="fa fa-external-link" /></button>
        )}
        {expandCfg.enabled && onToggle && (
          <button
            className="pv-ranked-action-btn"
            title={isExpanded ? 'Collapse' : 'Expand'}
            onClick={onToggle}
          ><i className={`fa fa-chevron-${isExpanded ? 'up' : 'down'}`} /></button>
        )}
      </div>
    </div>
  )
}

// ── Detail panel ───────────────────────────────────────────────────────
function DetailPanel({ detailData, sublistLayout, youConfig }) {
  if (!detailData || detailData === 'loading') {
    return (
      <div className="pv-ranked-detail pv-ranked-detail--loading">
        <span className="spinner-border spinner-border-sm me-2" />
        Loading details…
      </div>
    )
  }
  if (detailData.error) {
    return (
      <div className="pv-ranked-detail pv-ranked-detail--error">
        <small className="text-danger">{detailData.error}</small>
      </div>
    )
  }

  const tiles = detailData.tiles || detailData.charts || []
  const sublist = detailData.sublist || {}
  const rows = sublist.rowData || []

  // Prefer v2 sublist layout; fall back to legacy columnDefs.
  const effectiveLayout = sublistLayout
    || (sublist.layout && Object.keys(sublist.layout).length ? sublist.layout : null)

  const youEnabled = youConfig?.enabled && youConfig.column
  const youColumn = youConfig?.column
  const showProgressBar = youConfig?.showProgressBar !== false
  const sharePctField = effectiveLayout?.secondaryMetric?.column

  return (
    <div className="pv-ranked-detail">
      {tiles.length > 0 && (
        <div
          className="pv-ranked-detail-tiles"
          style={{ gridTemplateColumns: `repeat(${Math.min(tiles.length, 3)}, 1fr)` }}
        >
          {tiles.map((t, i) => (
            <div key={i} className="pv-ranked-detail-tile-card">
              {t.tile_type && t.tile_type.startsWith('kpi')
                ? <KpiTile data={t.kpi_data} />
                : <MiniChart option={t.echart_option} height={180} />
              }
            </div>
          ))}
        </div>
      )}

      {rows.length > 0 && (
        <div className="pv-ranked-detail-sublist">
          {sublist.title && (
            <div className="pv-ranked-detail-sublist-title">{sublist.title}</div>
          )}
          {effectiveLayout
            ? rows.map((sr, i) => {
                const isYou = youEnabled && Number(sr[youColumn]) === 1
                return (
                  <LayoutRow
                    key={i}
                    layout={effectiveLayout}
                    row={sr}
                    rankNum={i + 1}
                    isYou={isYou}
                    youColor={youConfig?.youColor}
                    peerColor={youConfig?.peerColor}
                    showProgressBar={youEnabled && showProgressBar}
                    sharePctField={sharePctField}
                  />
                )
              })
            : rows.map((sr, i) => (
                // v1 legacy fallback: render columnDefs-style rows as a simple
                // composite row with name + raw cells
                <div key={i} className="pv-ranked-subrow">
                  <div className="pv-ranked-row-rank">{i + 1}</div>
                  <div className="pv-ranked-row-body">
                    {(sublist.columnDefs || []).map((col, j) => (
                      <CellValue
                        key={col.field || j}
                        rendererName={col.cellRenderer}
                        row={sr}
                        field={col.field}
                        rendererParams={col.cellRendererParams}
                      />
                    ))}
                  </div>
                </div>
              ))
          }
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────
export default function RankedDetailList({ data, height, name, widgetId, scopeOptionId }) {
  const { filterValues, accessToken, refreshToken, apiBase } = useFilters()
  const [expandedRows, setExpandedRows] = useState({})

  // When scope option changes, clear expanded rows (layout may differ per option)
  useEffect(() => {
    setExpandedRows({})
  }, [scopeOptionId])

  const {
    rowData = [],
    key_column: keyColumn = '',
    has_detail: hasDetail = false,
    master_config: masterConfig = {},
    detail_config: detailConfig = {},
    columnDefs = [],
  } = data || {}

  const useV2Layout = masterConfig && Object.keys(masterConfig).length > 0

  const toggleRow = useCallback(async (keyValue) => {
    if (expandedRows[keyValue] && expandedRows[keyValue] !== 'loading') {
      setExpandedRows(prev => {
        const next = { ...prev }
        delete next[keyValue]
        return next
      })
      return
    }
    setExpandedRows(prev => ({ ...prev, [keyValue]: 'loading' }))
    try {
      const wid = widgetId || data?.id
      if (!wid) return
      // Include scope option id so Mode B uses the option's detail_config
      const params = { ...filterValues }
      if (scopeOptionId) params._scope_option_id = scopeOptionId
      const url = widgetDetailUrl(apiBase, wid, keyValue, params)
      const result = await apiFetch(url, accessToken, {}, refreshToken)
      setExpandedRows(prev => ({ ...prev, [keyValue]: result }))
    } catch (err) {
      setExpandedRows(prev => ({
        ...prev,
        [keyValue]: { error: err.message || 'Failed to load' }
      }))
    }
  }, [expandedRows, widgetId, data?.id, apiBase, filterValues, accessToken, refreshToken])

  const handleNavigate = useCallback((keyValue) => {
    // Prefer v2 master_config action config; fall back to first column's action
    // (legacy). v2 action details are stored alongside — but currently the
    // actual target-page/param live at the widget level (click_action on
    // the widget record). React receives them via the widget wrapper.
    // For now we simply update the URL query param with the key column.
    const url = new URL(window.location)
    if (keyColumn && keyValue) {
      url.searchParams.set(keyColumn, keyValue)
    }
    window.location.href = url.toString()
  }, [keyColumn])

  if (!rowData.length) {
    return (
      <div className="pv-ranked-list pv-ranked-list--empty">
        <p className="text-muted text-center py-4">No data available</p>
      </div>
    )
  }

  // Sub-list layout + YOU config (from detail_config)
  const sublistLayout = detailConfig?.sublist?.layout || null
  const youConfig = detailConfig?.sublist?.you || null

  return (
    <div
      className="pv-ranked-list"
      style={height ? { maxHeight: height, overflowY: 'auto' } : undefined}
    >
      {rowData.map((row) => {
        const kv = row[keyColumn] || row._rank
        const isExpanded = !!expandedRows[kv]
        return (
          <React.Fragment key={kv}>
            {useV2Layout ? (
              <LayoutRow
                layout={masterConfig}
                row={row}
                rankNum={row._rank}
                isExpanded={isExpanded}
                onNavigate={masterConfig.navigationArrow?.enabled ? () => handleNavigate(kv) : null}
                onExternalLink={masterConfig.externalLink?.enabled ? () => {
                  const tmpl = masterConfig.externalLink.urlTemplate
                  const col = masterConfig.externalLink.column
                  const url = col ? row[col] : (tmpl ? tmpl.replace('{value}', kv) : '')
                  if (url) window.open(url, '_blank', 'noopener,noreferrer')
                } : null}
                onToggle={(hasDetail && masterConfig.expandChevron?.enabled !== false) ? () => toggleRow(kv) : null}
              />
            ) : (
              // v1 fallback: legacy columnDefs rendering
              <div className={`pv-ranked-row${isExpanded ? ' pv-ranked-row--expanded' : ''}`}>
                <div className="pv-ranked-row-rank">{row._rank}</div>
                <div className="pv-ranked-row-body">
                  {columnDefs.map((col, i) => (
                    <CellValue
                      key={col.field || i}
                      rendererName={col.cellRenderer}
                      row={row}
                      field={col.field}
                      rendererParams={col.cellRendererParams}
                    />
                  ))}
                </div>
                <div className="pv-ranked-row-actions">
                  {hasDetail && (
                    <button
                      className="pv-ranked-action-btn"
                      onClick={() => toggleRow(kv)}
                      title={isExpanded ? 'Collapse' : 'Expand'}
                    ><i className={`fa fa-chevron-${isExpanded ? 'up' : 'down'}`} /></button>
                  )}
                </div>
              </div>
            )}
            {isExpanded && (
              <DetailPanel
                detailData={expandedRows[kv]}
                sublistLayout={sublistLayout}
                youConfig={youConfig}
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}
