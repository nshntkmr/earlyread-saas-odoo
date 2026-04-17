import React from 'react'
import { TANSTACK_RENDERERS, TANSTACK_FORMATTERS } from './tanstackAdapters'

/**
 * resolveTanStackColumns
 *
 * Converts admin-configured columnDefs (AG Grid shape) into TanStack Table
 * column definition objects. This is the TanStack equivalent of
 * resolveColumnDefs.jsx (which does the same for AG Grid).
 *
 * The admin JSON shape is UNCHANGED — same as what TableConfigurator produces.
 * This function maps AG Grid keys → TanStack keys internally.
 *
 * @param {Array} adminColumnDefs — from widget.table_column_config (JSON parsed)
 * @param {Object} masterConfig — optional ranked_detail_list master_config
 * @returns {Array} — TanStack column definitions
 */
export function resolveTanStackColumns(adminColumnDefs, masterConfig) {
  if (!adminColumnDefs || !adminColumnDefs.length) return []

  return adminColumnDefs
    .filter(col => !col.hide)
    .map(col => {
      const tanCol = {
        // Identity
        accessorKey: col.field || col.accessorKey || col.column || '',
        header: col.headerName || col.header || col.field || '',
        id: col.field || col.accessorKey || col.column || undefined,

        // Sizing
        size: col.width || undefined,
        minSize: col.minWidth || 60,
        maxSize: col.maxWidth || undefined,

        // Sorting
        enableSorting: col.sortable !== false,

        // Filtering
        enableColumnFilter: !!col.filter,

        // Meta (carries AG Grid-specific config for adapters)
        meta: {
          rendererParams: col.cellRendererParams || {},
          clickAction: col.clickAction || 'none',
          actionPageKey: col.actionPageKey || '',
          actionTabKey: col.actionTabKey || '',
          actionFilterParam: col.actionFilterParam || '',
          actionUrlTemplate: col.actionUrlTemplate || '',
          pinned: col.pinned || null,
          cellStyle: col.cellStyle || null,
          cellClassRules: col.cellClassRules || null,
          type: col.type || null,
          tooltipField: col.tooltipField || null,
          align: col.cellStyle?.textAlign || (col.type === 'numericColumn' ? 'right' : 'left'),
        },
      }

      // Cell renderer (priority: cellRenderer > valueFormatter > plain text)
      if (col.cellRenderer && TANSTACK_RENDERERS[col.cellRenderer]) {
        tanCol.cell = TANSTACK_RENDERERS[col.cellRenderer]
      } else if (col.valueFormatter && TANSTACK_FORMATTERS[col.valueFormatter]) {
        tanCol.cell = TANSTACK_FORMATTERS[col.valueFormatter]
      }
      // else: TanStack default (renders getValue() as text)

      // Pre-sort
      if (col.sort) {
        tanCol.sortDescFirst = col.sort === 'desc'
      }

      return tanCol
    })
}

/**
 * Build a rank column definition (prepended when master_config.rank.enabled).
 *
 * @param {Object} rankConfig — { enabled, style: 'medal'|'number' }
 * @returns {Object|null} — TanStack column def, or null if disabled
 */
export function buildRankColumn(rankConfig) {
  if (!rankConfig || rankConfig.enabled === false) return null

  const style = rankConfig.style || 'number'
  const medals = ['\u{1F947}', '\u{1F948}', '\u{1F949}']

  return {
    id: '_rank',
    accessorKey: '_rank',
    header: '#',
    size: 50,
    enableSorting: false,
    enableColumnFilter: false,
    cell: (info) => {
      const rank = info.getValue()
      if (style === 'medal' && rank <= 3) {
        return <span title={`${rank}${rank === 1 ? 'st' : rank === 2 ? 'nd' : 'rd'}`}>{medals[rank - 1]}</span>
      }
      return <span className="text-gray-400 font-medium">{rank}</span>
    },
  }
}

/**
 * Build an expand chevron column (appended when has_detail is true).
 *
 * @param {Object} expandConfig — { enabled }
 * @returns {Object|null} — TanStack column def, or null if disabled
 */
export function buildExpandColumn(expandConfig) {
  if (!expandConfig || expandConfig.enabled === false) return null

  return {
    id: '_expand',
    header: '',
    size: 40,
    enableSorting: false,
    enableColumnFilter: false,
    cell: ({ row }) => {
      if (!row.getCanExpand()) return null
      return (
        <button
          className="p-1.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition"
          onClick={row.getToggleExpandedHandler()}
          title={row.getIsExpanded() ? 'Collapse' : 'Expand'}
        >
          <svg
            className={`w-4 h-4 transition-transform ${row.getIsExpanded() ? 'rotate-180' : ''}`}
            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
          </svg>
        </button>
      )
    },
  }
}

/**
 * Build a navigate arrow column (appended when navigationArrow.enabled).
 *
 * @param {Object} navConfig — { enabled }
 * @param {Function} onNavigate — (rowOriginal) => void
 * @returns {Object|null}
 */
export function buildNavigateColumn(navConfig, onNavigate) {
  if (!navConfig || !navConfig.enabled || !onNavigate) return null

  return {
    id: '_navigate',
    header: '',
    size: 40,
    enableSorting: false,
    enableColumnFilter: false,
    cell: ({ row }) => (
      <button
        className="p-1.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition"
        onClick={() => onNavigate(row.original)}
        title="View details"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
        </svg>
      </button>
    ),
  }
}
