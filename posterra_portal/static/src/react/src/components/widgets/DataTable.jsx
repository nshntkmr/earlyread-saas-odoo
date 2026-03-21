import React from 'react'

/**
 * DataTable — chart_type: "table"
 *
 * Renders a sortable Bootstrap table from cols/rows arrays.
 * Supports column_link_config for making cell values clickable.
 *
 * Expected data shape:
 * {
 *   cols: [
 *     { key: "patient_name", label: "Patient Name", align: "left" },
 *     ...
 *   ],
 *   rows: [
 *     { patient_name: "John Doe", ... },
 *     ...
 *   ],
 *   row_count: 42   // optional — shown as "Showing N rows"
 * }
 *
 * Props:
 *   data            — { cols, rows, row_count }
 *   columnLinkConfig — { "col_key": { action, page_key, tab_key, filter_param, url_template } }
 *   onCellClick     — ({ column, value, row, linkConfig }) => void
 */
export default function DataTable({ data = {}, columnLinkConfig, onCellClick }) {
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
