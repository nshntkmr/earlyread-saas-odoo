import React, { useState, useEffect } from 'react'
import { apiFetch } from '../../api/client'
import { drillUrl } from '../../api/builder_endpoints'

/**
 * DrillDownModal
 *
 * Shown when a user clicks a chart element with click_action = 'show_details'.
 * Calls GET /api/v1/builder/widget/<id>/drill?click_column=...&click_value=...
 * and displays a sortable data table in a modal overlay.
 *
 * Props:
 *   widgetId       — number
 *   clickColumn    — string (the column axis the user clicked)
 *   clickValue     — string (the value the user clicked)
 *   filterParams   — object (current page filter params to pass through)
 *   onClose        — () => void
 *   apiBase        — string
 *   accessToken    — string
 */
export default function DrillDownModal({
  widgetId, clickColumn, clickValue, filterParams,
  onClose, apiBase, accessToken, refreshToken,
}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sortCol, setSortCol] = useState(null)
  const [sortAsc, setSortAsc] = useState(true)

  useEffect(() => {
    if (!widgetId || !clickColumn) return

    const params = new URLSearchParams({
      click_column: clickColumn,
      click_value: clickValue || '',
      ...(filterParams || {}),
    })

    const url = `${drillUrl(apiBase, widgetId)}?${params}`
    setLoading(true)
    setError(null)

    apiFetch(url, accessToken, {}, refreshToken)
      .then(result => setData(result))
      .catch(err => setError(err.message || 'Failed to load details'))
      .finally(() => setLoading(false))
  }, [widgetId, clickColumn, clickValue, filterParams, apiBase, accessToken, refreshToken])

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortAsc(!sortAsc)
    } else {
      setSortCol(col)
      setSortAsc(true)
    }
  }

  const sortedRows = React.useMemo(() => {
    if (!data?.rows || !sortCol) return data?.rows || []
    return [...data.rows].sort((a, b) => {
      const va = a[sortCol], vb = b[sortCol]
      if (va == null && vb == null) return 0
      if (va == null) return sortAsc ? -1 : 1
      if (vb == null) return sortAsc ? 1 : -1
      if (typeof va === 'number' && typeof vb === 'number') {
        return sortAsc ? va - vb : vb - va
      }
      return sortAsc
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va))
    })
  }, [data, sortCol, sortAsc])

  return (
    <div className="wb-modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="wb-modal wb-modal--wide">
        {/* Header */}
        <div className="wb-modal-header">
          <h3 className="wb-modal-title">
            Detail: {clickColumn} = {clickValue || '(empty)'}
          </h3>
          <button type="button" className="wb-btn-close" onClick={onClose}>
            <i className="fa fa-times" />
          </button>
        </div>

        {/* Body */}
        <div className="wb-modal-body">
          {loading && (
            <div className="wb-drill-loading">
              <span className="spinner-border spinner-border-sm me-2" />
              Loading details…
            </div>
          )}

          {error && (
            <div className="wb-preview-error">
              <i className="fa fa-exclamation-triangle me-1" />
              {error}
            </div>
          )}

          {!loading && !error && data && (
            <>
              {data.row_count != null && (
                <div className="text-muted small mb-2">
                  Showing {(data.rows || []).length} of {data.row_count} rows
                </div>
              )}
              <div className="table-responsive">
                <table className="table table-sm table-hover wb-drill-table">
                  <thead>
                    <tr>
                      {(data.columns || []).map(col => (
                        <th
                          key={col}
                          className="wb-drill-th"
                          onClick={() => handleSort(col)}
                          style={{ cursor: 'pointer' }}
                        >
                          {col}
                          {sortCol === col && (
                            <i className={`fa fa-sort-${sortAsc ? 'asc' : 'desc'} ms-1`} />
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sortedRows.map((row, ri) => (
                      <tr key={ri}>
                        {(data.columns || []).map(col => (
                          <td key={col}>{row[col] ?? ''}</td>
                        ))}
                      </tr>
                    ))}
                    {sortedRows.length === 0 && (
                      <tr>
                        <td colSpan={(data.columns || []).length} className="text-center text-muted">
                          No rows returned.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="wb-modal-footer">
          <button type="button" className="wb-btn wb-btn--outline" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
