import React, { useState, useCallback, useEffect } from 'react'
import {
  Table, TableHead, TableHeaderCell, TableBody, TableRow, TableCell,
  Badge, ProgressBar, Card, Metric, Text, Title, Subtitle,
  BarChart, LineChart, AreaChart, SparkAreaChart, SparkLineChart,
  Flex, Grid, Col,
} from '@tremor/react'
import { useFilters } from '../../state/FilterContext'
import { apiFetch } from '../../api/client'
import { widgetDetailUrl } from '../../api/endpoints'

/**
 * RankedDetailList (v3 — Tremor)
 *
 * A ranked list widget rendered with Tremor components. Each row can expand
 * inline to show detail tiles (bar/line/KPI via Tremor charts) and a nested
 * sub-list (also Tremor Table).
 *
 * Supports v2 config (master_config + detail_config from Dashboard Builder)
 * and v1 legacy (columnDefs arrays).
 *
 * Props:
 *   data      — { rowData, key_column, has_detail, master_config, detail_config, columnDefs }
 *   height    — optional max height (enables scrolling)
 *   name      — widget title
 *   widgetId  — widget ID (for detail API calls)
 *   scopeOptionId — optional Mode B scope option id
 */

// ── Sparkline helper (parses JSON array or CSV) ──────────────────────
function parseSparkData(raw) {
  if (!raw) return null
  let arr = raw
  if (typeof raw === 'string') {
    try { arr = JSON.parse(raw) } catch { arr = raw.split(',').map(Number) }
  }
  if (!Array.isArray(arr) || arr.length < 2) return null
  return arr.map((v, i) => ({ i: String(i), v: Number(v) || 0 }))
}

// ── Master-JSON parser (used by master_json tile mode) ───────────────
// Parses a master row's column value into a shape descriptor that
// MasterJsonTile uses to decide how to render. Returns null when the
// value is empty / unparseable.
//   kind = 'array-of-objects' | 'array-of-scalars' | 'object' | 'scalar'
function parseMasterJson(raw) {
  if (raw == null || raw === '') return null

  let value = raw
  if (typeof raw === 'string') {
    try {
      value = JSON.parse(raw)
    } catch {
      // Fallback: comma-separated numbers (e.g. "10,12,15")
      const parts = raw.split(',').map(s => Number(s.trim()))
      if (parts.length >= 2 && parts.every(n => !isNaN(n))) {
        return { kind: 'array-of-scalars', data: parts }
      }
      // Otherwise treat as plain string scalar
      return { kind: 'scalar', data: raw }
    }
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return null
    if (value.every(v => v && typeof v === 'object' && !Array.isArray(v))) {
      return { kind: 'array-of-objects', data: value }
    }
    return { kind: 'array-of-scalars', data: value }
  }

  if (typeof value === 'object' && value !== null) {
    return { kind: 'object', data: value }
  }

  return { kind: 'scalar', data: value }
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

// ── Badge color map for Tremor ───────────────────────────────────────
function badgeColor(hexOrName) {
  if (!hexOrName) return 'gray'
  const map = {
    '#10b981': 'emerald', '#059669': 'emerald', '#22c55e': 'green',
    '#3b82f6': 'blue', '#6366f1': 'indigo', '#8b5cf6': 'violet',
    '#f59e0b': 'amber', '#f97316': 'orange', '#ef4444': 'red',
    '#ec4899': 'pink', '#14b8a6': 'teal', '#0d9488': 'teal',
  }
  return map[hexOrName?.toLowerCase()] || 'gray'
}

// ── Shared Tremor chart renderer ─────────────────────────────────────
// Extracted helper used by both TileChart (server-built echart_option
// path) and MasterJsonTile (client-built path from master row JSON).
// tt = lowercase chart kind ('bar', 'line', 'line_area', etc.)
function renderTremorChart({ tt, title, chartData, categories, colors }) {
  if (tt.includes('area') || tt === 'line_area' || tt === 'line_stacked_area') {
    return (
      <Card className="p-4">
        <Title className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          {title || ''}
        </Title>
        <AreaChart
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
  if (tt.includes('line')) {
    return (
      <Card className="p-4">
        <Title className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          {title || ''}
        </Title>
        <LineChart
          data={chartData}
          index="x"
          categories={categories}
          colors={colors}
          showLegend={false}
          showAnimation={true}
          valueFormatter={(v) => v.toLocaleString()}
          className="h-44"
        />
      </Card>
    )
  }
  // Default: bar
  return (
    <Card className="p-4">
      <Title className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        {title || ''}
      </Title>
      <BarChart
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

// ── Tile chart types → Tremor component ──────────────────────────────
// Routes between three rendering paths:
//   1. master_json mode → MasterJsonTile (reads from master row's column)
//   2. KPI tile (server-built kpi_data) → inline render
//   3. Chart tile (server-built echart_option) → renderTremorChart
function TileChart({ tile, masterRow }) {
  if (!tile) return null

  // master_json mode — render from master row's JSON column (no SQL ran)
  if (tile.type === 'master_json') {
    return <MasterJsonTile tile={tile} masterRow={masterRow} />
  }

  const tt = (tile.tile_type || tile.type || 'bar').toLowerCase()

  // KPI tiles (from server-built kpi_data)
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

  // Chart tiles — extract data from echart_option
  const opt = tile.echart_option
  if (!opt) return <Card className="p-4"><Text className="text-gray-400">No data</Text></Card>

  const xData = opt.xAxis?.data || []
  const series = opt.series || []
  if (!xData.length || !series.length) {
    return <Card className="p-4"><Text className="text-gray-400">No data</Text></Card>
  }

  // Build Tremor-compatible data array
  const chartData = xData.map((x, i) => {
    const point = { x: String(x) }
    series.forEach(s => {
      const key = s.name || tile.title || 'value'
      point[key] = s.data?.[i] ?? 0
    })
    return point
  })
  const categories = series.map(s => s.name || tile.title || 'value')
  const colors = series.map(s => {
    const c = s.itemStyle?.color || s.lineStyle?.color || '#0d9488'
    return badgeColor(c) || 'teal'
  })

  return renderTremorChart({ tt, title: tile.title, chartData, categories, colors })
}

// ── Master-JSON tile (no per-tile SQL — reads from master row) ───────
// Renders a tile whose data comes from a column in the master row.
// Server has already passed through the spec; we resolve the value
// here, parse it, and render via the shared chart helper.
function MasterJsonTile({ tile, masterRow }) {
  const raw = masterRow?.[tile.master_json_column]
  const shape = parseMasterJson(raw)

  if (!shape) {
    return <Card className="p-4"><Text className="text-gray-400">No data</Text></Card>
  }

  const tt = (tile.tile_type || 'bar').toLowerCase()

  // KPI mode — single value (scalar column OR object key)
  if (tt.startsWith('kpi')) {
    let value = null
    if (shape.kind === 'scalar') {
      value = shape.data
    } else if (shape.kind === 'object' && tile.json_y_key) {
      value = shape.data[tile.json_y_key]
    }
    if (value == null || value === '') {
      return <Card className="p-4"><Text className="text-gray-400">No data</Text></Card>
    }
    return (
      <Card className="p-4">
        <Text>{tile.title || ''}</Text>
        <Metric className="mt-1">{fmt(value, tile.value_format)}</Metric>
      </Card>
    )
  }

  // Chart mode — needs an array of points
  let chartData = []
  if (shape.kind === 'array-of-objects') {
    if (!tile.json_x_key || !tile.json_y_key) {
      return (
        <Card className="p-4">
          <Text className="text-gray-400">Pick X and Y keys</Text>
        </Card>
      )
    }
    chartData = shape.data.map(o => ({
      x: String(o[tile.json_x_key] ?? ''),
      value: Number(o[tile.json_y_key]) || 0,
    }))
  } else if (shape.kind === 'array-of-scalars') {
    chartData = shape.data.map((v, i) => ({
      x: String(i),
      value: Number(v) || 0,
    }))
  } else {
    return (
      <Card className="p-4">
        <Text className="text-gray-400">Expected array data for chart</Text>
      </Card>
    )
  }

  if (!chartData.length) {
    return <Card className="p-4"><Text className="text-gray-400">No data</Text></Card>
  }

  const categories = ['value']
  const colors = [badgeColor(tile.color) || 'teal']

  return renderTremorChart({ tt, title: tile.title, chartData, categories, colors })
}

// ── Detail panel (tiles + sub-list) ──────────────────────────────────
// masterRow: the full row data from the master query for the expanded
// row. Threaded through to TileChart so master_json tiles can read
// their JSON column without an extra fetch.
function DetailPanel({ detailData, sublistLayout, youConfig, masterRow }) {
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
  const showBar = youConfig?.showProgressBar !== false

  return (
    <div className="bg-gray-50 border-b border-gray-200 px-6 py-4">
      {/* Tiles */}
      {tiles.length > 0 && (
        <Grid numItems={Math.min(tiles.length, 3)} className="gap-4 mb-4">
          {tiles.map((t, i) => (
            <Col key={i}>
              <TileChart tile={t} masterRow={masterRow} />
            </Col>
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

                return (
                  <TableRow key={i} className={isYou ? 'bg-emerald-50' : ''}>
                    {/* Rank */}
                    <TableCell className="w-10 text-center text-gray-400 font-medium">
                      {i + 1}
                    </TableCell>

                    {/* Name + subtitle + progress bar */}
                    <TableCell>
                      <Flex justifyContent="start" alignItems="center" className="gap-2">
                        <Text className="font-semibold text-gray-900">
                          {nameCol ? sr[nameCol] : ''}
                        </Text>
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

                    {/* Sparkline */}
                    {sparkCol && (
                      <TableCell className="w-20">
                        {(() => {
                          const d = parseSparkData(sr[sparkCol])
                          if (!d) return null
                          const trend = d[d.length - 1].v >= d[0].v
                          return (
                            <SparkAreaChart
                              data={d}
                              index="i"
                              categories={['v']}
                              colors={[trend ? 'emerald' : 'red']}
                              className="h-6 w-16"
                            />
                          )
                        })()}
                      </TableCell>
                    )}

                    {/* Metric + secondary */}
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

// ── Main component ───────────────────────────────────────────────────
export default function RankedDetailList({ data, height, name, widgetId, scopeOptionId }) {
  const { filterValues, accessToken, refreshToken, apiBase } = useFilters()
  const [expandedRows, setExpandedRows] = useState({})

  useEffect(() => { setExpandedRows({}) }, [scopeOptionId])

  const {
    rowData = [],
    key_column: keyColumn = '',
    has_detail: hasDetail = false,
    master_config: mc = {},
    detail_config: dc = {},
  } = data || {}

  const rankCfg = mc.rank || {}
  const badgeCfg = mc.badge || {}
  const subtitleCfg = mc.subtitle || {}
  const sparklineCfg = mc.sparkline || {}
  const primaryCfg = mc.primaryMetric || {}
  const secondaryCfg = mc.secondaryMetric || {}
  const navCfg = mc.navigationArrow || {}
  const expandCfg = mc.expandChevron || {}
  const nameCol = mc.name?.column

  const toggleRow = useCallback(async (kv) => {
    if (expandedRows[kv] && expandedRows[kv] !== 'loading') {
      setExpandedRows(prev => { const n = { ...prev }; delete n[kv]; return n })
      return
    }
    setExpandedRows(prev => ({ ...prev, [kv]: 'loading' }))
    try {
      const wid = widgetId || data?.id
      if (!wid) return
      const params = { ...filterValues }
      if (scopeOptionId) params._scope_option_id = scopeOptionId
      const url = widgetDetailUrl(apiBase, wid, kv, params)
      const result = await apiFetch(url, accessToken, {}, refreshToken)
      setExpandedRows(prev => ({ ...prev, [kv]: result }))
    } catch (err) {
      setExpandedRows(prev => ({ ...prev, [kv]: { error: err.message || 'Failed' } }))
    }
  }, [expandedRows, widgetId, data?.id, apiBase, filterValues, accessToken, refreshToken, scopeOptionId])

  const handleNavigate = useCallback((kv) => {
    const url = new URL(window.location)
    if (keyColumn && kv) url.searchParams.set(keyColumn, kv)
    window.location.href = url.toString()
  }, [keyColumn])

  if (!rowData.length) {
    return <Card className="p-8 text-center"><Text className="text-gray-400">No data available</Text></Card>
  }

  const sublistLayout = dc?.sublist?.layout || null
  const youConfig = dc?.sublist?.you || null

  return (
    <div style={height ? { maxHeight: height, overflowY: 'auto' } : undefined}>
      <Table>
        <TableBody>
          {rowData.map(row => {
            const kv = row[keyColumn] || row._rank
            const isExpanded = !!expandedRows[kv]

            return (
              <React.Fragment key={kv}>
                <TableRow
                  className={`cursor-default transition-colors ${isExpanded ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50'}`}
                >
                  {/* Rank */}
                  {rankCfg.enabled !== false && (
                    <TableCell className="w-10 text-center font-medium text-gray-400">
                      {rankCfg.style === 'medal' && row._rank <= 3
                        ? ['\u{1F947}', '\u{1F948}', '\u{1F949}'][row._rank - 1]
                        : row._rank}
                    </TableCell>
                  )}

                  {/* Name + badge + subtitle */}
                  <TableCell>
                    <Flex justifyContent="start" alignItems="center" className="gap-2">
                      <Text className="font-semibold text-gray-900">
                        {nameCol ? row[nameCol] : ''}
                      </Text>
                      {badgeCfg.enabled && (() => {
                        const t = badgeCfg.source === 'static'
                          ? badgeCfg.text
                          : (badgeCfg.column ? row[badgeCfg.column] : '')
                        return t ? <Badge color={badgeColor(badgeCfg.color)} size="xs">{t}</Badge> : null
                      })()}
                    </Flex>
                    {subtitleCfg.enabled && subtitleCfg.column && row[subtitleCfg.column] && (
                      <Text className="text-xs text-gray-400 mt-0.5">{row[subtitleCfg.column]}</Text>
                    )}
                  </TableCell>

                  {/* Sparkline */}
                  {sparklineCfg.enabled && sparklineCfg.column && (
                    <TableCell className="w-20">
                      {(() => {
                        const d = parseSparkData(row[sparklineCfg.column])
                        if (!d) return null
                        const trend = d[d.length - 1].v >= d[0].v
                        return (
                          <SparkAreaChart
                            data={d}
                            index="i"
                            categories={['v']}
                            colors={[trend ? 'emerald' : 'red']}
                            className="h-6 w-16"
                          />
                        )
                      })()}
                    </TableCell>
                  )}

                  {/* Primary metric + secondary */}
                  <TableCell className="text-right w-28">
                    <Text className="font-bold text-lg text-gray-900">
                      {fmt(row[primaryCfg.column], primaryCfg)}
                    </Text>
                    {secondaryCfg.enabled && secondaryCfg.column && (
                      <Text className="text-xs text-gray-400">
                        {fmt(row[secondaryCfg.column], secondaryCfg)}
                      </Text>
                    )}
                  </TableCell>

                  {/* Actions */}
                  <TableCell className="w-20 text-right">
                    <Flex justifyContent="end" className="gap-1">
                      {navCfg.enabled && (
                        <button
                          className="p-1.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition"
                          title="View details"
                          onClick={() => handleNavigate(kv)}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                          </svg>
                        </button>
                      )}
                      {hasDetail && expandCfg.enabled !== false && (
                        <button
                          className="p-1.5 rounded text-gray-400 hover:text-blue-600 hover:bg-blue-50 transition"
                          title={isExpanded ? 'Collapse' : 'Expand'}
                          onClick={() => toggleRow(kv)}
                        >
                          <svg
                            className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                            fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                          </svg>
                        </button>
                      )}
                    </Flex>
                  </TableCell>
                </TableRow>

                {/* Expanded detail panel */}
                {isExpanded && (
                  <TableRow>
                    <TableCell colSpan={99} className="p-0">
                      <DetailPanel
                        detailData={expandedRows[kv]}
                        sublistLayout={sublistLayout}
                        youConfig={youConfig}
                        masterRow={row}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
