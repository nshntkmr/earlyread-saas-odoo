import React, { useState, useMemo, useCallback } from 'react'
// Import sibling from inside the package — both portal and designer
// consume this component via @posterra/grid-utils. We avoid importing
// from @tremor/react so the designer (which has no Tremor) can render
// previews without adding a new dependency.
import { CellHost } from './cellRecipes.jsx'

// Local Card replacement — same look as Tremor's <Card> but no dependency.
// In the portal, Tailwind utilities are loaded and the Card looks styled.
// In the designer (no Tailwind), the structure still renders correctly
// with browser defaults; styling fidelity is portal-only.
function Card({ className = '', children, style }) {
  return (
    <div
      className={`bg-white border border-gray-200 rounded-lg shadow-sm ${className}`}
      style={style}
    >
      {children}
    </div>
  )
}

/**
 * SmartTable
 *
 * Widget for chart_type='smart_table'. Independent of AG Grid: renders a
 * native HTML <table> wrapped in a Tremor <Card>, with per-cell rendering
 * dispatched through the cell-recipe registry (5 recipes: text, metric,
 * metric_with_delta, badge, composite).
 *
 * Schema is consumed from the server-side _build_smart_table_data():
 *   data = {
 *     type: 'smart_table',
 *     rowData: [{col_name: value}, ...],
 *     columns: [
 *       {field, label, width?, align?, sortable?, cell: {type, ...options}}
 *     ],
 *     table: {density?, height?, stickyHeader?, zebraRows?, sortable?},
 *     row_count: N
 *   }
 *
 * Props:
 *   data    — server response (above)
 *   height  — optional pixel max-height (table-level height takes priority)
 *   name    — widget title (rendered by parent WidgetGrid card frame)
 */
export default function SmartTable({ data, height }) {
  const {
    rowData = [],
    columns = [],
    table = {},
  } = data || {}

  // Sort state
  const [sort, setSort] = useState({ field: null, dir: 'asc' })

  const tableSortable = table.sortable !== false

  const sortedRows = useMemo(() => {
    if (!sort.field) return rowData
    const dir = sort.dir === 'asc' ? 1 : -1
    const out = [...rowData].sort((a, b) => {
      const va = a?.[sort.field]
      const vb = b?.[sort.field]
      // null/empty always sort to bottom regardless of direction
      if (va === null || va === undefined || va === '') return 1
      if (vb === null || vb === undefined || vb === '') return -1
      const na = Number(va)
      const nb = Number(vb)
      if (isFinite(na) && isFinite(nb)) return (na - nb) * dir
      return String(va).localeCompare(String(vb)) * dir
    })
    return out
  }, [rowData, sort])

  const handleSort = useCallback((field, columnSortable) => {
    if (!tableSortable || columnSortable === false) return
    setSort(s => {
      if (s.field !== field) return { field, dir: 'asc' }
      if (s.dir === 'asc') return { field, dir: 'desc' }
      return { field: null, dir: 'asc' }   // third click clears sort
    })
  }, [tableSortable])

  // Density → padding/font-size
  const densityClass = {
    compact:     'py-1 px-2 text-xs',
    comfortable: 'py-2 px-3 text-sm',
    spacious:    'py-3 px-4 text-sm',
  }[table.density || 'comfortable']

  const headerClass = {
    compact:     'py-1 px-2 text-xs',
    comfortable: 'py-2 px-3 text-xs',
    spacious:    'py-3 px-4 text-sm',
  }[table.density || 'comfortable']

  // Effective scroll height: table.height wins, then prop, then no max.
  const maxHeight = table.height || height || null

  // Server-reported config error (e.g. unparseable smart_table_config).
  // Surface it visibly so admin knows to re-open the builder.
  if (data?.error) {
    return (
      <Card className="p-6">
        <p className="text-red-700 text-sm font-medium mb-1">
          Smart Table configuration error
        </p>
        <p className="text-red-600 text-xs">{data.error}</p>
      </Card>
    )
  }

  // Empty state
  if (!columns.length) {
    return (
      <Card className="p-8 text-center">
        <p className="text-gray-400 text-sm">No columns configured.</p>
      </Card>
    )
  }
  if (!rowData.length) {
    return (
      <Card className="p-8 text-center">
        <p className="text-gray-400 text-sm">No data.</p>
      </Card>
    )
  }

  return (
    <Card className="p-0 overflow-hidden">
      <div
        style={maxHeight ? { maxHeight, overflowY: 'auto', overflowX: 'auto' } : undefined}>
        <table className="w-full border-collapse">
          <thead className={`bg-gray-50 border-b border-gray-200 ${table.stickyHeader !== false ? 'sticky top-0 z-10' : ''}`}>
            <tr>
              {columns.map((col) => {
                const align = col.align || 'left'
                const colSortable = tableSortable && col.sortable !== false
                const isSorted = sort.field === col.field
                return (
                  <th
                    key={col.field}
                    className={`${headerClass} font-medium text-gray-600 text-${align} ${colSortable ? 'cursor-pointer select-none hover:bg-gray-100' : ''}`}
                    style={col.width ? { width: col.width } : undefined}
                    onClick={() => handleSort(col.field, col.sortable)}>
                    {col.label || col.field}
                    {colSortable && (
                      <span className="ml-1 text-gray-400">
                        {isSorted ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}
                      </span>
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, i) => (
              <tr
                key={i}
                className={`border-b border-gray-100 last:border-b-0 ${table.zebraRows && i % 2 ? 'bg-gray-50/40' : ''} hover:bg-gray-50/60`}>
                {columns.map((col) => {
                  const align = col.align || 'left'
                  return (
                    <td
                      key={col.field}
                      className={`${densityClass} text-${align} align-middle`}>
                      <CellHost col={col} row={row} />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
