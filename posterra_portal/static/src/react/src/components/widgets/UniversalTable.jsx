import React, { useState, useCallback, useMemo, useEffect } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getExpandedRowModel,
  flexRender,
} from '@tanstack/react-table'
import {
  Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell,
  Badge, ProgressBar, Card, Metric, Text, Title, Flex, Grid, Col,
  BarChart, LineChart, AreaChart, SparkAreaChart,
} from '@tremor/react'
import { useFilters } from '../../state/FilterContext'
import { apiFetch } from '../../api/client'
import { widgetDetailUrl } from '../../api/endpoints'
import {
  resolveTanStackColumns,
  buildRankColumn,
  buildExpandColumn,
  buildNavigateColumn,
} from '@posterra/grid-utils/resolveTanStackColumns'

/**
 * UniversalTable
 *
 * A single table component powered by TanStack Table (headless) + Tremor (rendering).
 * Scales from a simple sortable table to a full ranked detail list with expandable
 * rows, inline charts, nested sub-lists, and YOU indicators — all via admin config.
 *
 * Used for chart_type = 'ranked_detail_list'. AG Grid DataTable.jsx remains
 * untouched for chart_type = 'table'.
 */

// ── Sparkline data parser ────────────────────────────────────────────
function parseSparkData(raw) {
  if (!raw) return null
  let arr = raw
  if (typeof raw === 'string') {
    try { arr = JSON.parse(raw) } catch { arr = raw.split(',').map(Number) }
  }
  if (!Array.isArray(arr) || arr.length < 2) return null
  return arr.map((v, i) => ({ i: String(i), v: Number(v) || 0 }))
}

// ── Badge color helper ───────────────────────────────────────────────
function badgeColor(hex) {
  if (!hex) return 'gray'
  const map = {
    '#10b981': 'emerald', '#059669': 'emerald', '#22c55e': 'green',
    '#3b82f6': 'blue', '#6366f1': 'indigo', '#8b5cf6': 'violet',
    '#f59e0b': 'amber', '#f97316': 'orange', '#ef4444': 'red',
    '#14b8a6': 'teal', '#0d9488': 'teal',
  }
  return map[hex?.toLowerCase()] || 'gray'
}

// ── Number formatter ─────────────────────────────────────────────────
function fmt(val, cfg) {
  if (val === null || val === undefined || val === '') return ''
  const n = Number(val)
  if (isNaN(n)) return String(val)
  const d = cfg?.decimals ?? 0
  const p = cfg?.prefix ?? ''
  const s = cfg?.suffix ?? ''
  if (cfg?.format === 'percentage') return p + n.toFixed(d) + '%' + s
  if (cfg?.format === 'currency') {
    return p + '$' + n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) + s
  }
  return p + n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) + s
}

// ── Build TanStack columns from master_config layout toggles ────────
// The MasterRowLayoutStep in the builder produces config like:
//   { rank, name:{column}, badge:{enabled,source,column,text,color},
//     subtitle:{enabled,column}, sparkline:{enabled,column,variant,color},
//     primaryMetric:{column,format,decimals,prefix,suffix},
//     secondaryMetric:{enabled,column,format,decimals,suffix} }
// This converts those toggle-based slots into TanStack column definitions,
// using Tremor components for rendering.
function buildColumnsFromMasterConfig(mc) {
  if (!mc || Object.keys(mc).length === 0) return []
  const cols = []
  const nameCol = mc.name?.column
  const badgeCfg = mc.badge || {}
  const subtitleCfg = mc.subtitle || {}
  const sparklineCfg = mc.sparkline || {}
  const primaryCfg = mc.primaryMetric || {}
  const secondaryCfg = mc.secondaryMetric || {}

  // Identity column: name + optional badge + optional subtitle below
  if (nameCol) {
    cols.push({
      accessorKey: nameCol,
      header: 'Name',
      enableSorting: true,
      cell: ({ row }) => {
        const d = row.original
        const badgeText = badgeCfg.enabled
          ? (badgeCfg.source === 'static' ? badgeCfg.text : (badgeCfg.column ? d[badgeCfg.column] : ''))
          : null
        const subtitle = subtitleCfg.enabled && subtitleCfg.column ? d[subtitleCfg.column] : null
        return (
          <div>
            <Flex justifyContent="start" alignItems="center" className="gap-2">
              <Text className="font-semibold text-gray-900">{d[nameCol] || ''}</Text>
              {badgeText && <Badge color={badgeColor(badgeCfg.color)} size="xs">{badgeText}</Badge>}
            </Flex>
            {subtitle && <Text className="text-xs text-gray-400 mt-0.5">{subtitle}</Text>}
          </div>
        )
      },
    })
  }

  // Sparkline column
  if (sparklineCfg.enabled && sparklineCfg.column) {
    cols.push({
      accessorKey: sparklineCfg.column,
      header: 'Trend',
      size: 80,
      enableSorting: false,
      cell: ({ getValue }) => {
        const d = parseSparkData(getValue())
        if (!d) return null
        const trend = d[d.length - 1].v >= d[0].v
        const color = sparklineCfg.color && sparklineCfg.color !== 'auto'
          ? badgeColor(sparklineCfg.color)
          : (trend ? 'emerald' : 'red')
        return (
          <SparkAreaChart data={d} index="i" categories={['v']} colors={[color]} className="h-6 w-16" />
        )
      },
    })
  }

  // Primary metric (+ inline secondary)
  if (primaryCfg.column) {
    cols.push({
      accessorKey: primaryCfg.column,
      header: 'Metric',
      size: 120,
      enableSorting: true,
      meta: { align: 'right' },
      cell: ({ row }) => {
        const d = row.original
        const primary = fmt(d[primaryCfg.column], primaryCfg)
        const showSec = secondaryCfg.enabled && secondaryCfg.column
        const secondary = showSec ? fmt(d[secondaryCfg.column], secondaryCfg) : null
        return (
          <div className="text-right">
            <Text className="font-bold text-gray-900">{primary}</Text>
            {secondary && <Text className="text-xs text-gray-400">{secondary}</Text>}
          </div>
        )
      },
    })
  }

  return cols
}

// ── Tile chart (Tremor) ──────────────────────────────────────────────
function TileChart({ tile }) {
  if (!tile) return null
  const tt = (tile.tile_type || tile.type || 'bar').toLowerCase()

  // KPI tiles
  if (tt.startsWith('kpi')) {
    const kpi = tile.kpi_data || tile
    return (
      <Card className="p-4">
        <Text>{kpi.label || tile.title || ''}</Text>
        <Metric className="mt-1">
          {kpi.kpi_prefix || ''}{kpi.formatted_value || ''}{kpi.kpi_suffix || ''}
        </Metric>
      </Card>
    )
  }

  // ECharts option → Tremor data
  const opt = tile.echart_option
  if (!opt) return <Card className="p-4"><Text className="text-gray-400">No data</Text></Card>

  const xData = opt.xAxis?.data || []
  const series = opt.series || []
  if (!xData.length || !series.length) {
    return <Card className="p-4"><Text className="text-gray-400">No data</Text></Card>
  }

  const chartData = xData.map((x, i) => {
    const point = { x: String(x) }
    series.forEach(s => {
      point[s.name || tile.title || 'value'] = s.data?.[i] ?? 0
    })
    return point
  })
  const categories = series.map(s => s.name || tile.title || 'value')
  const colors = series.map(s => badgeColor(s.itemStyle?.color || s.lineStyle?.color || '#0d9488') || 'teal')

  const ChartComponent = tt.includes('area') ? AreaChart : tt.includes('line') ? LineChart : BarChart

  return (
    <Card className="p-4">
      <Title className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        {tile.title || ''}
      </Title>
      <ChartComponent
        data={chartData}
        index="x"
        categories={categories}
        colors={colors}
        showLegend={false}
        showAnimation={true}
        valueFormatter={(v) => v.toLocaleString()}
        className="h-44"
        stack={tt.includes('stacked')}
      />
    </Card>
  )
}

// ── Detail panel (lazy-loaded on expand) ─────────────────────────────
function DetailPanel({ detailData, sublistLayout, youConfig, detailConfig }) {
  if (!detailData || detailData === 'loading') {
    return (
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200 text-gray-500 text-sm">
        <span className="spinner-border spinner-border-sm me-2" />
        Loading details...
      </div>
    )
  }
  if (detailData.error) {
    return (
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <Text color="red">{detailData.error}</Text>
      </div>
    )
  }

  const tiles = detailData.tiles || detailData.charts || []
  const sublist = detailData.sublist || {}
  const rows = sublist.rowData || []
  const layout = sublistLayout || sublist.layout || null
  const youEnabled = youConfig?.enabled && youConfig.column
  const youColumn = youConfig?.column

  return (
    <div className="bg-gray-50 border-b border-gray-200 px-6 py-4">
      {/* Tiles */}
      {tiles.length > 0 && (
        <Grid numItems={Math.min(tiles.length, 3)} className="gap-4 mb-4">
          {tiles.map((t, i) => (
            <Col key={i}><TileChart tile={t} /></Col>
          ))}
        </Grid>
      )}

      {/* Sub-list */}
      {rows.length > 0 && (
        <div>
          {sublist.title && (
            <Title className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2 mt-2">
              {sublist.title}
            </Title>
          )}
          <Table className="mt-2">
            <TableBody>
              {rows.map((sr, i) => {
                const isYou = youEnabled && Number(sr[youColumn]) === 1
                const nameCol = layout?.name?.column
                const subtitleCol = layout?.subtitle?.enabled && layout.subtitle.column
                const sparkCol = layout?.sparkline?.enabled && layout.sparkline.column
                const metricCol = layout?.primaryMetric?.column
                const secCol = layout?.secondaryMetric?.enabled && layout.secondaryMetric.column
                const sharePct = secCol ? Number(sr[secCol]) || 0 : 0
                const showBar = youConfig?.showProgressBar !== false

                return (
                  <TableRow key={i} className={isYou ? 'bg-emerald-50' : ''}>
                    <TableCell className="w-10 text-center text-gray-400 font-medium">{i + 1}</TableCell>
                    <TableCell>
                      <Flex justifyContent="start" alignItems="center" className="gap-2">
                        <Text className="font-semibold text-gray-900">{nameCol ? sr[nameCol] : ''}</Text>
                        {isYou && <Badge color="emerald" size="xs">YOU</Badge>}
                      </Flex>
                      {subtitleCol && sr[subtitleCol] && (
                        <Text className="text-xs text-gray-400 mt-0.5">{sr[subtitleCol]}</Text>
                      )}
                      {youEnabled && showBar && (
                        <ProgressBar
                          value={Math.min(100, Math.max(0, sharePct))}
                          color={isYou ? 'emerald' : 'amber'}
                          className="mt-1.5"
                        />
                      )}
                    </TableCell>
                    {sparkCol && (
                      <TableCell className="w-20">
                        {(() => {
                          const d = parseSparkData(sr[sparkCol])
                          if (!d) return null
                          const trend = d[d.length - 1].v >= d[0].v
                          return (
                            <SparkAreaChart
                              data={d} index="i" categories={['v']}
                              colors={[trend ? 'emerald' : 'red']}
                              className="h-6 w-16"
                            />
                          )
                        })()}
                      </TableCell>
                    )}
                    <TableCell className="text-right w-24">
                      <Text className="font-bold text-gray-900">
                        {metricCol ? fmt(sr[metricCol], layout?.primaryMetric) : ''}
                      </Text>
                      {secCol && (
                        <Text className="text-xs text-gray-400">
                          {fmt(sr[secCol], layout?.secondaryMetric)}
                        </Text>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

// ── Pagination controls ──────────────────────────────────────────────
function PaginationControls({ table }) {
  return (
    <Flex justifyContent="between" alignItems="center" className="px-4 py-3 border-t border-gray-200">
      <Text className="text-sm text-gray-500">
        Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
        {' · '}{table.getFilteredRowModel().rows.length} rows
      </Text>
      <Flex className="gap-2">
        <button
          className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >Previous</button>
        <button
          className="px-3 py-1.5 text-sm rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >Next</button>
      </Flex>
    </Flex>
  )
}

// ── Main component ───────────────────────────────────────────────────
export default function UniversalTable({
  data,
  height,
  name,
  widgetId,
  scopeOptionId,
  searchText,
  onCellClick,
}) {
  const { filterValues, accessToken, refreshToken, apiBase } = useFilters()
  const [expandedRows, setExpandedRows] = useState({}) // { rowKey: detailData | 'loading' }
  const [sorting, setSorting] = useState([])
  const [expanded, setExpanded] = useState({})

  // Reset expand state on scope option change
  useEffect(() => {
    setExpanded({})
    setExpandedRows({})
  }, [scopeOptionId])

  const {
    rowData = [],
    columnDefs = [],
    key_column: keyColumn = '',
    has_detail: hasDetail = false,
    master_config: mc = {},
    detail_config: dc = {},
    visual_config: vc = {},
    row_count: rowCount = 0,
  } = data || {}

  // Display mode: autoHeight (default), pagination, or fixed scroll
  const displayMode = vc.tableDisplayMode || 'autoHeight'
  const pageSize = vc.paginationPageSize || 20

  // Build TanStack columns from admin config
  const columns = useMemo(() => {
    const cols = []

    // Rank column (prepend)
    const rankCol = buildRankColumn(mc.rank)
    if (rankCol) cols.push(rankCol)

    // Data columns: prefer master_config layout (built by MasterRowLayoutStep),
    // fall back to AG Grid-style columnDefs (table_column_config),
    // final fallback: auto-generate from rowData keys
    let dataCols = []
    if (mc && Object.keys(mc).length > 0 && mc.name?.column) {
      // v2: master_config layout toggles (name + badge + subtitle + sparkline + metric)
      dataCols = buildColumnsFromMasterConfig(mc)
    } else if (columnDefs && columnDefs.length) {
      // v1: AG Grid-style columnDefs from table_column_config
      dataCols = resolveTanStackColumns(columnDefs, mc)
    } else if (rowData.length > 0) {
      // Auto-generate from first row's keys (excluding internal _fields)
      dataCols = Object.keys(rowData[0])
        .filter(k => !k.startsWith('_'))
        .map(k => ({
          accessorKey: k,
          header: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
          enableSorting: true,
        }))
    }
    cols.push(...dataCols)

    // Navigate column (append)
    const navCol = buildNavigateColumn(mc.navigationArrow, (row) => {
      const kv = row[keyColumn] || ''
      const url = new URL(window.location)
      if (keyColumn && kv) url.searchParams.set(keyColumn, kv)
      window.location.href = url.toString()
    })
    if (navCol) cols.push(navCol)

    // Expand column (append)
    const expandCol = buildExpandColumn(
      hasDetail ? (mc.expandChevron || { enabled: true }) : null
    )
    if (expandCol) cols.push(expandCol)

    return cols
  }, [columnDefs, mc, hasDetail, keyColumn, rowData])

  // TanStack table instance
  const table = useReactTable({
    data: rowData,
    columns,
    state: {
      sorting,
      globalFilter: searchText || '',
      expanded,
      ...(displayMode === 'pagination' ? { pagination: { pageIndex: 0, pageSize } } : {}),
    },
    onSortingChange: setSorting,
    onExpandedChange: setExpanded,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    ...(displayMode === 'pagination' ? { getPaginationRowModel: getPaginationRowModel() } : {}),
    getExpandedRowModel: getExpandedRowModel(),
    getRowCanExpand: () => hasDetail,
    globalFilterFn: 'includesString',
  })

  // Lazy-fetch detail data on expand
  const handleExpand = useCallback(async (rowKey) => {
    if (expandedRows[rowKey] && expandedRows[rowKey] !== 'loading') return // already loaded
    setExpandedRows(prev => ({ ...prev, [rowKey]: 'loading' }))
    try {
      const wid = widgetId || data?.id
      if (!wid) return
      const params = { ...filterValues }
      if (scopeOptionId) params._scope_option_id = scopeOptionId
      const url = widgetDetailUrl(apiBase, wid, rowKey, params)
      const result = await apiFetch(url, accessToken, {}, refreshToken)
      setExpandedRows(prev => ({ ...prev, [rowKey]: result }))
    } catch (err) {
      setExpandedRows(prev => ({ ...prev, [rowKey]: { error: err.message || 'Failed' } }))
    }
  }, [expandedRows, widgetId, data?.id, apiBase, filterValues, accessToken, refreshToken, scopeOptionId])

  // Trigger detail fetch when a row expands
  useEffect(() => {
    Object.entries(expanded).forEach(([idx, isExpanded]) => {
      if (!isExpanded) return
      const row = table.getRowModel().rows[Number(idx)]
      if (!row) return
      const kv = row.original[keyColumn] || row.original._rank
      if (kv && !expandedRows[kv]) handleExpand(String(kv))
    })
  }, [expanded]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!rowData.length) {
    return <Card className="p-8 text-center"><Text className="text-gray-400">No data available</Text></Card>
  }

  const sublistLayout = dc?.sublist?.layout || null
  const youConfig = dc?.sublist?.you || null

  return (
    <div style={height && displayMode !== 'autoHeight' ? { maxHeight: height, overflowY: 'auto' } : undefined}>
      <Table>
        {/* Header */}
        <TableHead>
          {table.getHeaderGroups().map(hg => (
            <TableRow key={hg.id}>
              {hg.headers.map(header => {
                const canSort = header.column.getCanSort()
                const sorted = header.column.getIsSorted()
                const align = header.column.columnDef.meta?.align || 'left'
                return (
                  <TableHeaderCell
                    key={header.id}
                    className={`${canSort ? 'cursor-pointer select-none' : ''} text-${align}`}
                    style={header.column.columnDef.size ? { width: header.column.columnDef.size } : undefined}
                    onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                  >
                    <Flex justifyContent="start" className="gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {sorted === 'asc' && <span className="text-blue-500">↑</span>}
                      {sorted === 'desc' && <span className="text-blue-500">↓</span>}
                    </Flex>
                  </TableHeaderCell>
                )
              })}
            </TableRow>
          ))}
        </TableHead>

        {/* Body */}
        <TableBody>
          {table.getRowModel().rows.map(row => {
            const kv = row.original[keyColumn] || row.original._rank
            const isExpanded = row.getIsExpanded()

            return (
              <React.Fragment key={row.id}>
                <TableRow
                  className={`transition-colors ${isExpanded ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50'}`}
                >
                  {row.getVisibleCells().map(cell => {
                    const align = cell.column.columnDef.meta?.align || 'left'
                    const style = {
                      ...(cell.column.columnDef.size ? { width: cell.column.columnDef.size } : {}),
                      textAlign: align,
                    }
                    return (
                      <TableCell key={cell.id} style={style}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </TableCell>
                    )
                  })}
                </TableRow>

                {/* Expanded detail panel */}
                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={columns.length} className="p-0">
                      <DetailPanel
                        detailData={expandedRows[String(kv)]}
                        sublistLayout={sublistLayout}
                        youConfig={youConfig}
                        detailConfig={dc}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            )
          })}
        </TableBody>
      </Table>

      {/* Pagination (only in pagination mode) */}
      {displayMode === 'pagination' && <PaginationControls table={table} />}
    </div>
  )
}
