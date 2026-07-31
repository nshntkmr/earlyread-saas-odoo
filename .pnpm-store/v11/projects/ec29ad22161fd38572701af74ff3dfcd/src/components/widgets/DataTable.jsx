import React, { useMemo, useCallback, useEffect, useRef, useState } from 'react'
import { ModuleRegistry, AllCommunityModule, themeQuartz } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import DetailDrawer from './DetailDrawer'
// Import CELL_RENDERERS explicitly to prevent Rollup tree-shaking.
// resolveColumnDefs uses dynamic property access (CELL_RENDERERS[key])
// which Rollup may not trace as "used" during static analysis.
import { CUSTOM_COLUMN_TYPES, CELL_RENDERERS, resolveColumnDefs } from '@posterra/grid-utils'
// Force side-effect: ensure all renderers are retained in the bundle
void CELL_RENDERERS

// Register all AG Grid Community modules (required for v35+)
ModuleRegistry.registerModules([AllCommunityModule])

// ── AG Grid Table (new mode) ────────────────────────────────────────────────
function AGGridTable({ data, onCellClick, searchText, fillHeight = false, widgetId, fetchDrawerDetail, registerGridApi }) {
  const { columnDefs, rowData = [], row_count, visual_config: vc = {}, detail_drawer: drawer } = data
  const gridRef = useRef(null)

  // Expose the grid api upward (WidgetGrid download export reads the
  // filtered/sorted row set through it). Ref-latched so the inline closure
  // WidgetGrid passes each render never re-triggers effects; deregister on
  // unmount so a stale api is never used after tab switches.
  const registerRef = useRef(registerGridApi)
  registerRef.current = registerGridApi
  useEffect(() => () => registerRef.current?.(null), [])

  // Detail Drawer state — owned by DataTable (it has event.data locally; the
  // WidgetGrid onCellClick bridge drops the row). null = closed.
  const [drawerRow, setDrawerRow] = useState(null)
  const canDrawer = !!(drawer && drawer.enabled && widgetId != null && fetchDrawerDetail)
  const openDrawer = useCallback((row) => { if (canDrawer) setDrawerRow(row || {}) }, [canDrawer])
  const closeDrawer = useCallback(() => setDrawerRow(null), [])

  // Table display mode from admin config (visual_config).
  // fillHeight (widget has an exact Height) overrides autoHeight so the grid fills
  // the fixed card body and scrolls internally instead of expanding the card.
  const displayMode = vc.tableDisplayMode || 'autoHeight'
  const pageSize = vc.paginationPageSize || 50
  const tableHeight = vc.tableHeight || 400

  const resolvedColDefs = useMemo(
    () => resolveColumnDefs(columnDefs),
    [columnDefs]
  )

  const defaultColDef = useMemo(() => ({
    resizable: true,
    sortable: true,
    suppressMovable: true,
  }), [])

  const handleCellClicked = useCallback((event) => {
    const colDef = event.colDef
    const action = colDef.clickAction || 'none'

    // Backward compat: legacy cellRendererParams.pageKey → go_to_page
    if (action === 'none' && colDef.cellRendererParams?.pageKey && onCellClick) {
      const params = colDef.cellRendererParams
      onCellClick({
        column: colDef.field,
        value: event.value,
        row: event.data,
        linkConfig: {
          action: 'go_to_page',
          page_key: params.pageKey,
          tab_key: params.tabKey || '',
          filter_param: params.filterParam || colDef.field,
        },
      })
      return
    }

    // Detail Drawer (cell trigger): a column explicitly set to open_detail_drawer
    // opens the drawer — this is that column's action and always wins for it.
    if (action === 'open_detail_drawer') {
      openDrawer(event.data)
      return
    }

    // Detail Drawer (row trigger): clicking a column with NO action opens the
    // drawer. Columns WITH their own action fall through to the switch below and
    // never open the drawer (existing click actions always win).
    if (action === 'none') {
      if (canDrawer && drawer.trigger === 'row') openDrawer(event.data)
      return
    }

    // Resolve value: actionValueField reads from a different column in row data
    // e.g. display = "147000 - VNA HEALTH CARE" but actionValueField = "hha_ccn" → passes "147000"
    const valueField = colDef.actionValueField
    const rawValue = valueField ? event.data?.[valueField] : event.value
    const value = rawValue != null ? String(rawValue) : ''

    switch (action) {
      case 'filter_page': {
        const param = colDef.actionFilterParam || colDef.field
        const url = new URL(window.location)
        url.searchParams.set(param, value)
        window.location.href = url.toString()
        break
      }
      case 'go_to_page': {
        const pageKey = colDef.actionPageKey || colDef.cellRendererParams?.pageKey || ''
        const tabKey = colDef.actionTabKey || colDef.cellRendererParams?.tabKey || ''
        const param = colDef.actionFilterParam || colDef.cellRendererParams?.filterParam || colDef.field
        if (!pageKey) return
        // App is implicit in the host (e.g. posterra.example.com), so
        // links are same-host relative paths — no /my/<app_key>/ prefix.
        let targetUrl = `/${pageKey}`
        if (tabKey) targetUrl += `?tab=${tabKey}`
        if (param && value) {
          targetUrl += (targetUrl.includes('?') ? '&' : '?') + `${param}=${encodeURIComponent(value)}`
        }
        window.location.href = targetUrl
        break
      }
      case 'show_details': {
        if (onCellClick) {
          onCellClick({
            column: colDef.field,
            value: value,
            row: event.data,
            linkConfig: { action: 'show_details' },
          })
        }
        break
      }
      case 'open_url': {
        const tpl = colDef.actionUrlTemplate || ''
        let finalUrl = tpl.replace(/\{value\}/g, encodeURIComponent(value))
        // {filters} expands to the current page's URL-synced filter params so
        // navigation carries context (Month, Market, ...). Params written
        // explicitly in the template win over carried ones; `tab` is never
        // carried (the template targets its own tab or none).
        if (finalUrl.includes('{filters}')) {
          const carried = new URLSearchParams(window.location.search)
          carried.delete('tab')
          const explicit = new URLSearchParams(
            (finalUrl.replace(/\{filters\}/g, '').split('?')[1] || '')
          )
          for (const k of explicit.keys()) carried.delete(k)
          finalUrl = finalUrl.replace(/\{filters\}/g, carried.toString())
          // Tidy artifacts when nothing is carried ("...&" / "...?")
          finalUrl = finalUrl.replace(/[?&]+$/, '')
        }
        if (finalUrl) window.open(finalUrl, '_blank', 'noopener')
        break
      }
    }
  }, [onCellClick, canDrawer, drawer, openDrawer])

  // Container style: fillHeight (exact widget height) → no inline height; the
  // .pv-widget-table-wrap--fill CSS (flex:1; min-height:0) gives the grid a
  // flex-computed height so AG Grid scrolls inside the fixed card. Else fixed height
  // for pagination/scroll, auto for autoHeight.
  const containerStyle = fillHeight
    ? undefined
    : (displayMode !== 'autoHeight' ? { height: tableHeight, width: '100%' } : undefined)

  return (
    <div className={`pv-widget-table-wrap${fillHeight ? ' pv-widget-table-wrap--fill' : ''}`}>
      <div className="pv-ag-grid-container" style={containerStyle}>
        <AgGridReact
          ref={gridRef}
          theme={themeQuartz}
          columnDefs={resolvedColDefs}
          rowData={rowData}
          defaultColDef={defaultColDef}
          columnTypes={CUSTOM_COLUMN_TYPES}
          domLayout={(fillHeight || displayMode !== 'autoHeight') ? 'normal' : 'autoHeight'}
          pagination={displayMode === 'pagination'}
          paginationPageSize={pageSize}
          paginationPageSizeSelector={[20, 50, 100, 200]}
          suppressCellFocus={true}
          enableCellTextSelection={true}
          onCellClicked={handleCellClicked}
          onGridReady={(params) => registerRef.current?.(params.api)}
          animateRows={false}
          quickFilterText={searchText || ''}
        />
      </div>
      {displayMode !== 'pagination' && row_count != null && (
        <div className="pv-table-meta text-muted small mt-1">
          Showing {rowData.length} of {row_count} rows
        </div>
      )}
      {canDrawer && drawerRow && (
        <DetailDrawer
          schema={drawer}
          row={drawerRow}
          fetchDetail={(rowKey) => fetchDrawerDetail(rowKey)}
          onClose={closeDrawer}
        />
      )}
    </div>
  )
}

// ── Legacy Bootstrap Table (backward compat) ────────────────────────────────
function LegacyTable({ data, columnLinkConfig, onCellClick }) {
  const { cols = [], rows = [], row_count, label_font_weight, label_color } = data
  const headerStyle = (label_font_weight || label_color)
    ? { ...(label_font_weight && { fontWeight: label_font_weight }), ...(label_color && { color: label_color }) }
    : undefined
  const linkMap = columnLinkConfig || {}

  if (!cols.length) {
    return <div className="pv-widget-empty p-3 text-muted">No data available.</div>
  }

  const handleCellClick = (col, value, row) => {
    const cfg = linkMap[col.key]
    if (!cfg || !onCellClick) return
    onCellClick({ column: col.key, value, row, linkConfig: cfg })
  }

  return (
    <div className="pv-widget-table-wrap">
      {row_count != null && (
        <div className="pv-table-meta text-muted small mb-1">
          Showing {rows.length} of {row_count} rows
        </div>
      )}
      <div className="table-responsive">
        <table className="table table-sm table-hover pv-widget-table">
          <thead>
            <tr>
              {cols.map(col => (
                <th
                  key={col.key}
                  className={`text-${col.align || 'start'}`}
                  scope="col"
                  style={headerStyle}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri}>
                {cols.map(col => {
                  const cellVal = row[col.key] ?? ''
                  const isLinked = !!linkMap[col.key]
                  return (
                    <td
                      key={col.key}
                      className={`text-${col.align || 'start'} ${isLinked ? 'pv-cell-link' : ''}`}
                    >
                      {isLinked ? (
                        <button
                          type="button"
                          className="pv-cell-link-btn"
                          onClick={() => handleCellClick(col, cellVal, row)}
                        >
                          {cellVal}
                        </button>
                      ) : (
                        cellVal
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Main DataTable — auto-detects AG Grid vs legacy mode ────────────────────

/**
 * DataTable — chart_type: "table"
 *
 * Dual-mode rendering:
 * - AG Grid mode: when data.columnDefs is present (from table_column_config)
 * - Legacy mode: when data.cols/rows is present (backward compat)
 *
 * Props:
 *   data            — { columnDefs, rowData, row_count } (AG Grid)
 *                      OR { cols, rows, row_count } (legacy)
 *   columnLinkConfig — legacy column link map (only used in legacy mode)
 *   onCellClick     — ({ column, value, row, linkConfig }) => void
 */
export default function DataTable({ data = {}, columnLinkConfig, onCellClick, searchText, fillHeight, widgetId, fetchDrawerDetail, registerGridApi }) {
  // AG Grid mode: has columnDefs from table_column_config
  if (data.columnDefs) {
    return <AGGridTable data={data} onCellClick={onCellClick} searchText={searchText} fillHeight={fillHeight}
      widgetId={widgetId} fetchDrawerDetail={fetchDrawerDetail} registerGridApi={registerGridApi} />
  }

  // Legacy mode: plain cols/rows (backward compat for existing widgets)
  return <LegacyTable data={data} columnLinkConfig={columnLinkConfig} onCellClick={onCellClick} />
}
