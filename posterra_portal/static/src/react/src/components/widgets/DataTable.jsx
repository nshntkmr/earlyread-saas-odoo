import React, { useMemo, useCallback, useRef } from 'react'
import { ModuleRegistry, AllCommunityModule, themeQuartz } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
// Import CELL_RENDERERS explicitly to prevent Rollup tree-shaking.
// resolveColumnDefs uses dynamic property access (CELL_RENDERERS[key])
// which Rollup may not trace as "used" during static analysis.
import { CUSTOM_COLUMN_TYPES, CELL_RENDERERS, resolveColumnDefs } from '@posterra/grid-utils'
// Force side-effect: ensure all renderers are retained in the bundle
void CELL_RENDERERS

// Register all AG Grid Community modules (required for v35+)
ModuleRegistry.registerModules([AllCommunityModule])

// ── AG Grid Table (new mode) ────────────────────────────────────────────────
function AGGridTable({ data, onCellClick }) {
  const { columnDefs, rowData = [], row_count, visual_config: vc = {} } = data
  const gridRef = useRef(null)

  // Table display mode from admin config (visual_config)
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

    if (action === 'none') return

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
        let targetUrl = window.location.pathname.replace(/\/[^/]+$/, `/${pageKey}`)
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
        const finalUrl = tpl.replace(/\{value\}/g, encodeURIComponent(value))
        if (finalUrl) window.open(finalUrl, '_blank', 'noopener')
        break
      }
    }
  }, [onCellClick])

  // Container style: fixed height for pagination/scroll, auto for autoHeight
  const containerStyle = displayMode !== 'autoHeight'
    ? { height: tableHeight, width: '100%' }
    : undefined

  return (
    <div className="pv-widget-table-wrap">
      <div className="pv-ag-grid-container" style={containerStyle}>
        <AgGridReact
          ref={gridRef}
          theme={themeQuartz}
          columnDefs={resolvedColDefs}
          rowData={rowData}
          defaultColDef={defaultColDef}
          columnTypes={CUSTOM_COLUMN_TYPES}
          domLayout={displayMode === 'autoHeight' ? 'autoHeight' : 'normal'}
          pagination={displayMode === 'pagination'}
          paginationPageSize={pageSize}
          paginationPageSizeSelector={[20, 50, 100, 200]}
          suppressCellFocus={true}
          enableCellTextSelection={true}
          onCellClicked={handleCellClicked}
          animateRows={false}
        />
      </div>
      {displayMode !== 'pagination' && row_count != null && (
        <div className="pv-table-meta text-muted small mt-1">
          Showing {rowData.length} of {row_count} rows
        </div>
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
export default function DataTable({ data = {}, columnLinkConfig, onCellClick }) {
  // AG Grid mode: has columnDefs from table_column_config
  if (data.columnDefs) {
    return <AGGridTable data={data} onCellClick={onCellClick} />
  }

  // Legacy mode: plain cols/rows (backward compat for existing widgets)
  return <LegacyTable data={data} columnLinkConfig={columnLinkConfig} onCellClick={onCellClick} />
}
