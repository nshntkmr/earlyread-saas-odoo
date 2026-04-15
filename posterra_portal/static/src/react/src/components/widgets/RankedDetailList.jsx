import React, { useState, useCallback, useRef, useEffect } from 'react'
import * as echarts from 'echarts'
import { useFilters } from '../../state/FilterContext'
import { apiFetch } from '../../api/client'
import { widgetDetailUrl } from '../../api/endpoints'
import { CELL_RENDERERS } from '@posterra/grid-utils'

/**
 * RankedDetailList
 *
 * A ranked list widget where each row can expand inline to show
 * detail charts (ECharts) and a nested sub-list. Configurable via
 * admin: master SQL + column config, detail SQL + chart/sublist config.
 *
 * Props:
 *   data    — { rowData, columnDefs, key_column, has_detail,
 *              detail_chart_config, detail_sublist_config, row_count }
 *   height  — optional max height (enables scrolling)
 *   name    — widget title
 *   widgetId — widget ID (for detail API calls)
 */

// ── Tiny EChart instance (embedded in detail panel) ────────────────────
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

// ── Cell value renderer (reuses @posterra/grid-utils renderers) ────────
function CellValue({ colDef, row }) {
  const field = colDef.field
  const value = row[field]
  const rendererName = colDef.cellRenderer
  const rendererParams = colDef.cellRendererParams || {}

  if (rendererName && CELL_RENDERERS[rendererName]) {
    const Renderer = CELL_RENDERERS[rendererName]
    // Build a params object matching AG Grid's ICellRendererParams shape
    const params = { value, data: row, colDef, ...rendererParams }
    return <Renderer params={params} />
  }

  // Plain text fallback
  if (value === null || value === undefined || value === '') return null
  return <span>{String(value)}</span>
}

// ── Sparkline (inline SVG, standalone for master rows) ─────────────────
function InlineSparkline({ data, color }) {
  if (!data) return null
  let points = data
  if (typeof data === 'string') {
    try { points = JSON.parse(data) } catch { points = data.split(',').map(Number) }
  }
  if (!Array.isArray(points) || points.length < 2) return null

  const nums = points.map(Number).filter(n => !isNaN(n))
  if (nums.length < 2) return null

  const w = 60, h = 20, pad = 2
  const min = Math.min(...nums), max = Math.max(...nums)
  const range = max - min || 1
  const coords = nums.map((v, i) => {
    const x = pad + (i / (nums.length - 1)) * (w - 2 * pad)
    const y = h - pad - ((v - min) / range) * (h - 2 * pad)
    return `${x},${y}`
  }).join(' ')

  const trend = nums[nums.length - 1] >= nums[0]
  const strokeColor = color || (trend ? '#10b981' : '#ef4444')

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: 'block' }}>
      <polyline points={coords} fill="none" stroke={strokeColor} strokeWidth="1.5" />
    </svg>
  )
}

// ── Master row ─────────────────────────────────────────────────────────
function RankedRow({ row, columnDefs, keyColumn, hasDetail, isExpanded, onToggle, onNavigate }) {
  const keyValue = row[keyColumn] || ''

  return (
    <div className={`pv-ranked-row${isExpanded ? ' pv-ranked-row--expanded' : ''}`}>
      {/* Rank */}
      <div className="pv-ranked-row-rank">
        {row._rank <= 3
          ? ['', '\u{1F947}', '\u{1F948}', '\u{1F949}'][row._rank]
          : row._rank}
      </div>

      {/* Configured columns */}
      <div className="pv-ranked-row-body">
        {columnDefs.map((col, i) => (
          <div key={col.field || i} className="pv-ranked-row-cell" style={col.width ? { width: col.width, flexShrink: 0 } : { flex: i === 0 ? 1 : undefined }}>
            <CellValue colDef={col} row={row} />
          </div>
        ))}
      </div>

      {/* Action buttons */}
      <div className="pv-ranked-row-actions">
        {onNavigate && (
          <button className="pv-ranked-action-btn" title="View details" onClick={() => onNavigate(keyValue, row)}>
            <i className="fa fa-arrow-right" />
          </button>
        )}
        {hasDetail && (
          <button className="pv-ranked-action-btn" title={isExpanded ? 'Collapse' : 'Expand'} onClick={() => onToggle(keyValue)}>
            <i className={`fa fa-chevron-${isExpanded ? 'up' : 'down'}`} />
          </button>
        )}
      </div>
    </div>
  )
}

// ── Detail panel (charts + sub-list) ───────────────────────────────────
function DetailPanel({ detailData, sublistColumnDefs }) {
  if (!detailData || detailData === 'loading') {
    return (
      <div className="pv-ranked-detail pv-ranked-detail--loading">
        <span className="spinner-border spinner-border-sm me-2" />
        Loading details...
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

  const { charts = [], sublist = {} } = detailData

  return (
    <div className="pv-ranked-detail">
      {/* Charts (side by side) */}
      {charts.length > 0 && (
        <div className="pv-ranked-detail-charts" style={{ gridTemplateColumns: `repeat(${charts.length}, 1fr)` }}>
          {charts.map((c, i) => (
            <div key={i} className="pv-ranked-detail-chart-card">
              <MiniChart option={c.echart_option} height={180} />
            </div>
          ))}
        </div>
      )}

      {/* Nested sub-list */}
      {sublist.rowData && sublist.rowData.length > 0 && (
        <div className="pv-ranked-detail-sublist">
          {sublist.title && (
            <div className="pv-ranked-detail-sublist-title">{sublist.title}</div>
          )}
          {sublist.rowData.map((sr, i) => (
            <div key={i} className="pv-ranked-subrow">
              <div className="pv-ranked-subrow-rank">{i + 1}</div>
              <div className="pv-ranked-subrow-body">
                {(sublist.columnDefs || []).map((col, j) => (
                  <div key={col.field || j} className="pv-ranked-subrow-cell" style={col.width ? { width: col.width, flexShrink: 0 } : { flex: j === 0 ? 1 : undefined }}>
                    <CellValue colDef={col} row={sr} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────
export default function RankedDetailList({ data, height, name, widgetId }) {
  const { filterValues, accessToken, refreshToken, apiBase } = useFilters()
  const [expandedRows, setExpandedRows] = useState({}) // { keyValue: detailData | 'loading' }

  const {
    rowData = [],
    columnDefs = [],
    key_column: keyColumn = '',
    has_detail: hasDetail = false,
    detail_sublist_config: sublistConfig = {},
  } = data || {}

  const toggleRow = useCallback(async (keyValue) => {
    // If already expanded, collapse
    if (expandedRows[keyValue] && expandedRows[keyValue] !== 'loading') {
      setExpandedRows(prev => {
        const next = { ...prev }
        delete next[keyValue]
        return next
      })
      return
    }

    // Mark as loading
    setExpandedRows(prev => ({ ...prev, [keyValue]: 'loading' }))

    try {
      const wid = widgetId || data?.id
      if (!wid) return
      const url = widgetDetailUrl(apiBase, wid, keyValue, filterValues)
      const result = await apiFetch(url, accessToken, {}, refreshToken)
      setExpandedRows(prev => ({ ...prev, [keyValue]: result }))
    } catch (err) {
      setExpandedRows(prev => ({ ...prev, [keyValue]: { error: err.message || 'Failed to load' } }))
    }
  }, [expandedRows, widgetId, data?.id, apiBase, filterValues, accessToken, refreshToken])

  // Navigate arrow handler (go_to_page pattern)
  const handleNavigate = useCallback((keyValue, row) => {
    // Use first columnDef's click action config if available
    const firstCol = columnDefs.find(c => c.clickAction && c.clickAction !== 'none')
    if (firstCol) {
      const pageKey = firstCol.actionPageKey || ''
      const tabKey = firstCol.actionTabKey || ''
      const paramName = firstCol.actionPassValueAs || firstCol.actionFilterParam || keyColumn
      if (pageKey) {
        const url = new URL(window.location)
        const pathParts = url.pathname.split('/')
        // Replace last path segment with target page key
        pathParts[pathParts.length - 1] = pageKey
        url.pathname = pathParts.join('/')
        if (paramName && keyValue) url.searchParams.set(paramName, keyValue)
        if (tabKey) url.searchParams.set('tab', tabKey)
        window.location.href = url.toString()
        return
      }
    }
    // Fallback: no navigation configured
  }, [columnDefs, keyColumn])

  if (!rowData.length) {
    return (
      <div className="pv-ranked-list pv-ranked-list--empty">
        <p className="text-muted text-center py-4">No data available</p>
      </div>
    )
  }

  return (
    <div className="pv-ranked-list" style={height ? { maxHeight: height, overflowY: 'auto' } : undefined}>
      {rowData.map((row) => {
        const kv = row[keyColumn] || row._rank
        return (
          <React.Fragment key={kv}>
            <RankedRow
              row={row}
              columnDefs={columnDefs}
              keyColumn={keyColumn}
              hasDetail={hasDetail}
              isExpanded={!!expandedRows[kv]}
              onToggle={toggleRow}
              onNavigate={columnDefs.some(c => c.clickAction && c.clickAction !== 'none') ? handleNavigate : null}
            />
            {expandedRows[kv] && (
              <DetailPanel
                detailData={expandedRows[kv]}
                sublistColumnDefs={sublistConfig.columns || []}
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}
