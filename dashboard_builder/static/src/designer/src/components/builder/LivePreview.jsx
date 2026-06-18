import React, { useState, useEffect, useRef } from 'react'
import * as echarts from 'echarts'
// Same SmartTable the portal renders — composite smart_table children preview
// through the identical component (no preview-only fork).
import { SmartTable } from '@posterra/grid-utils'
import { designerFetch } from '../../api/client'
import { previewUrl, libraryPlaceUrl } from '../../api/endpoints'
import PageFilterPanel from './PageFilterPanel'
import { serializeCompositeChildren } from './compositeUtils'

/* ── Lightweight gauge preview renderers (inline, no external deps) ─── */

const RAG_COLORS = {
  red: '#ef4444', amber: '#f59e0b', green: '#10b981',
}
const RAG_BG = {
  red: '#fef2f2', amber: '#fffbeb', green: '#f0fdf4',
}

function GaugePreviewInline({ data, height }) {
  if (!data) return null
  const v = data.gauge_variant
  if (v === 'bullet') return <BulletPreview data={data} height={height} />
  if (v === 'traffic_light_rag') return <RagPreview data={data} height={height} />
  if (v === 'percentile_rank') return <PercentilePreview data={data} height={height} />
  return null
}

function BulletRowPrev({ label, formatted_value, value, target, target_label, min, max, ranges }) {
  const rng = max - min || 1
  const pct = Math.max(0, Math.min(100, ((value - min) / rng) * 100))
  const tPct = target != null ? Math.max(0, Math.min(100, ((target - min) / rng) * 100)) : null
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span>
        <span style={{ fontWeight: 700, fontSize: 15, color: '#0d9488' }}>{formatted_value}</span>
      </div>
      <div style={{ position: 'relative', height: 16, borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
        {ranges.map((r, i) => {
          const prevTo = i > 0 ? ranges[i-1].to : min
          return <div key={i} style={{ width: `${((r.to - prevTo) / rng) * 100}%`, backgroundColor: r.color, opacity: 0.25 }} />
        })}
        <div style={{ position: 'absolute', top: 3, left: 0, height: 10, width: `${pct}%`, borderRadius: 2, backgroundColor: '#0d9488' }} />
        {tPct != null && <div style={{ position: 'absolute', left: `${tPct}%`, top: 0, width: 2, height: 16, backgroundColor: '#374151' }} />}
      </div>
      {target_label && <div style={{ fontSize: 10, color: '#6b7280', textAlign: 'right', marginTop: 1 }}>{target_label}</div>}
    </div>
  )
}

function BulletPreview({ data, height }) {
  if (data.multi && data.items) {
    const { items, min = 0, max = 100, ranges = [], threshold_text = '' } = data
    return (
      <div style={{ padding: '12px 20px', height }}>
        {items.map((item, i) => (
          <BulletRowPrev key={i} {...item} min={min} max={max} ranges={ranges} />
        ))}
        {threshold_text && <div style={{ fontSize: 11, color: '#9ca3af', borderTop: '1px solid #f3f4f6', paddingTop: 4 }}>{threshold_text}</div>}
      </div>
    )
  }
  const { value = 0, formatted_value = '', target, min = 0, max = 100, ranges = [],
          label = '', threshold_text = '', target_label = '' } = data
  return (
    <div style={{ padding: '16px 20px', height }}>
      <BulletRowPrev label={label} formatted_value={formatted_value} value={value}
        target={target} target_label={target_label} min={min} max={max} ranges={ranges} />
      {threshold_text && <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 6 }}>{threshold_text}</div>}
    </div>
  )
}

function RagRowPrev({ label, formatted_value, rag_status, status_text }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '5px 0' }}>
      <div style={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: RAG_COLORS[rag_status] || RAG_COLORS.green, flexShrink: 0 }} />
      <span style={{ fontWeight: 600, fontSize: 13, minWidth: 100 }}>{label}</span>
      <span style={{ fontWeight: 600, fontSize: 13, color: '#374151', minWidth: 45 }}>{formatted_value}</span>
      {status_text && <span style={{ fontSize: 12, color: '#6b7280', marginLeft: 'auto' }}>{status_text}</span>}
    </div>
  )
}

function RagPreview({ data, height }) {
  // Multi-row
  if (data.multi && data.items) {
    return (
      <div style={{ padding: '8px 20px', height }}>
        {data.items.map((item, i) => (
          <RagRowPrev key={i} {...item} />
        ))}
      </div>
    )
  }
  // Single-row
  const { formatted_value = '', rag_status = 'green', badge_text = '', threshold_text = '', label = '' } = data
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 16, height }}>
      {label && <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>{label}</div>}
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        {['red', 'amber', 'green'].map(s => (
          <div key={s} style={{
            width: s === rag_status ? 30 : 22, height: s === rag_status ? 30 : 22,
            borderRadius: '50%', backgroundColor: s === rag_status ? RAG_COLORS[s] : RAG_BG[s],
            opacity: s === rag_status ? 1 : 0.5, transition: 'all .3s',
          }} />
        ))}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: RAG_COLORS[rag_status] }}>{formatted_value}</div>
      {badge_text && <div style={{ padding: '2px 8px', borderRadius: 12, fontSize: 11, fontWeight: 600,
        backgroundColor: RAG_BG[rag_status], color: RAG_COLORS[rag_status], marginTop: 4 }}>{badge_text}</div>}
      {threshold_text && <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 6 }}>{threshold_text}</div>}
    </div>
  )
}

function PercentilePreview({ data, height }) {
  const { percentile = 0, ordinal_text = '', subtitle = '', quartile_label = '', quartile_color = '#16a34a',
          actual_label = '', actual_value = '', show_quartile_markers = true } = data
  const pct = Math.max(0, Math.min(100, percentile))
  return (
    <div style={{ padding: '14px 20px', height }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{data.label || ''}</span>
        {quartile_label && <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 600, color: quartile_color, backgroundColor: '#f3f4f6' }}>{quartile_label}</span>}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: quartile_color, marginBottom: 2 }}>{ordinal_text}</div>
      {subtitle && <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 8 }}>{subtitle}</div>}
      <div style={{ position: 'relative', height: 8, borderRadius: 4, backgroundColor: '#e5e7eb', marginBottom: show_quartile_markers ? 20 : 8 }}>
        <div style={{ position: 'absolute', top: 0, left: 0, height: '100%', width: `${pct}%`, borderRadius: 4, backgroundColor: quartile_color }} />
        <div style={{ position: 'absolute', left: `${pct}%`, top: -3, width: 4, height: 14, borderRadius: 2, backgroundColor: '#1f2937', transform: 'translateX(-2px)' }} />
        {show_quartile_markers && [25, 50, 75].map(q => (
          <React.Fragment key={q}>
            <div style={{ position: 'absolute', left: `${q}%`, top: 10, width: 1, height: 6, backgroundColor: '#9ca3af' }} />
            <span style={{ position: 'absolute', left: `${q}%`, top: 18, fontSize: 9, color: '#9ca3af', transform: 'translateX(-50%)' }}>{q}th</span>
          </React.Fragment>
        ))}
      </div>
      {(actual_label || actual_value) && <div style={{ fontSize: 11, color: '#6b7280' }}>{actual_label}{actual_label && actual_value ? ' — ' : ''}{actual_value && <strong>actual: {actual_value}</strong>}</div>}
    </div>
  )
}

function MemberFlowPreviewInline({ data, height }) {
  const months = Array.isArray(data?.months) ? data.months : []
  const labels = data?.labels || {}
  const fmt = (v) => {
    const n = Number(v || 0)
    return Number.isFinite(n) ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(n) : '0'
  }
  if (!months.length) {
    return <div style={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>No member flow data.</div>
  }
  const lanes = [
    ['new_alignments', labels.new_alignments || 'New Alignments', '#14b8a6', 64],
    ['still_active', labels.still_active || 'Still Active', '#60a5fa', 138],
    ['recaptured', labels.recaptured || 'Re-captured', '#8b5cf6', 218],
    ['disaligned', labels.disaligned || 'Disaligned', '#ef4444', 264],
  ]
  const width = 920
  const step = months.length > 1 ? 560 / (months.length - 1) : 0
  const xs = months.map((_, i) => 240 + i * step)
  const start = data?.start || {}
  return (
    <div style={{ height, overflowX: 'auto', background: '#fff' }}>
      <svg viewBox={`0 0 ${width} 330`} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" style={{ minWidth: 780 }}>
        <rect x="22" y="128" width="136" height="76" rx="6" fill="#9ee6d6" />
        <text x="90" y="152" textAnchor="middle" fontSize="12" fontWeight="700" fill="#0f172a">Starting</text>
        <text x="90" y="170" textAnchor="middle" fontSize="12" fontWeight="700" fill="#0f172a">Aligned Members</text>
        <text x="90" y="188" textAnchor="middle" fontSize="12" fill="#0f172a">{start.period || months[0].label}</text>
        <text x="90" y="202" textAnchor="middle" fontSize="12" fontWeight="700" fill="#0f172a">{fmt(start.value)}</text>
        {months.map((m, i) => (
          <g key={m.key || i}>
            <text x={xs[i]} y="38" textAnchor="middle" fontSize="12" fontWeight="700" fill="#334155">{m.label}</text>
            {i < months.length - 1 && <text x={xs[i] + step / 2} y="38" textAnchor="middle" fontSize="14" fill="#94a3b8">-&gt;</text>}
          </g>
        ))}
        {lanes.map(([key, label, color, y]) => (
          <g key={key}>
            <path d={`M 158 166 C 210 166, 202 ${y}, 230 ${y}`} stroke={color} strokeWidth={key === 'still_active' ? 48 : 18} opacity="0.18" fill="none" strokeLinecap="round" />
            {months.slice(0, -1).map((m, i) => (
              <path key={`${key}-${i}`} d={`M ${xs[i] + 36} ${y} C ${xs[i] + step / 2} ${y}, ${xs[i] + step / 2} ${y}, ${xs[i + 1] - 36} ${y}`} stroke={color} strokeWidth={key === 'still_active' ? 48 : 18} opacity="0.18" fill="none" strokeLinecap="round" />
            ))}
            <text x="820" y={y + 4} fontSize="12" fontWeight="700" fill={color}>{label}</text>
            {months.map((m, i) => (
              <g key={`${key}-${i}-v`}>
                <rect x={xs[i] - 34} y={y - (key === 'still_active' ? 38 : 13)} width="68" height={key === 'still_active' ? 76 : 26} rx="5" fill={color} opacity={key === 'still_active' ? '0.72' : '0.86'} />
                <text x={xs[i]} y={y + 4} textAnchor="middle" fontSize="12" fontWeight="700" fill={key === 'still_active' ? '#0f172a' : '#fff'}>{fmt(m[key])}</text>
              </g>
            ))}
          </g>
        ))}
        <text x="460" y="315" textAnchor="middle" fontSize="12" fill="#64748b">{data.footer || ''}</text>
      </svg>
    </div>
  )
}

/* ── Composite preview (12-col grid mirroring portal CompositeWidget) ── */

const LEGEND_PALETTES = {
  healthcare: ['#0d9488', '#14b8a6', '#2dd4bf', '#6ee7b7', '#34d399', '#059669'],
  ocean:      ['#1d4ed8', '#3b82f6', '#60a5fa', '#93c5fd', '#0ea5e9', '#38bdf8'],
  warm:       ['#ea580c', '#f97316', '#fb923c', '#fbbf24', '#f59e0b', '#d97706'],
  mono:       ['#374151', '#6b7280', '#9ca3af', '#d1d5db', '#e5e7eb', '#f3f4f6'],
  default:    ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#fc8452'],
}

function ChildEChart({ option, height }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!ref.current || !option) return undefined
    const chart = echarts.init(ref.current)
    chart.setOption(option, { notMerge: true })
    const onResize = () => chart.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chart.dispose()
    }
  }, [option])
  return <div ref={ref} style={{ width: '100%', height }} />
}

function CompositeChildPreview({ child }) {
  const d = child.data || {}
  const h = Math.max(80, child.min_height_px || 240)

  if (d.echart_option) {
    return <ChildEChart option={d.echart_option} height={h} />
  }
  if (d.type === 'legend_list') {
    const colors = Array.isArray(d.colors) && d.colors.length
      ? d.colors
      : (LEGEND_PALETTES[d.palette] || LEGEND_PALETTES.healthcare)
    const fmt = v => new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Number(v || 0))
    return (
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', height: '100%', gap: 6, padding: '4px 2px' }}>
        {(d.rows || []).map((r, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
            <span style={{ width: 9, height: 9, borderRadius: '50%', backgroundColor: colors[i % colors.length], flexShrink: 0 }} />
            <span style={{ flex: 1, color: '#334155', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.label}</span>
            <strong style={{ color: '#0f172a' }}>{fmt(r.value)}</strong>
            <span style={{ color: '#64748b', minWidth: 42, textAlign: 'right' }}>{Number(r.pct).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    )
  }
  if (d.type === 'text_note') {
    return (
      <div style={{ fontSize: 12, color: '#64748b', background: '#f8fafc', borderRadius: 6, padding: '8px 10px', whiteSpace: 'pre-wrap' }}>
        {d.body || ''}
      </div>
    )
  }
  if (d.type === 'smart_table') {
    // Portal-shape payload → identical component the dashboard uses
    return (
      <div style={{ overflow: 'auto', maxHeight: h }}>
        <SmartTable data={d} height={h} />
      </div>
    )
  }
  if (Array.isArray(d.columns) && Array.isArray(d.rows)) {
    return (
      <div style={{ overflow: 'auto', maxHeight: h }}>
        <table className="wb-preview-table" style={{ width: '100%', fontSize: 12 }}>
          <thead>
            <tr>{d.columns.map(col => <th key={col} style={{ textAlign: 'left', padding: '4px 6px', borderBottom: '1px solid #e5e7eb', color: '#475569' }}>{col}</th>)}</tr>
          </thead>
          <tbody>
            {d.rows.slice(0, 15).map((row, ri) => (
              <tr key={ri}>{row.map((cell, ci) => <td key={ci} style={{ padding: '3px 6px', borderBottom: '1px solid #f1f5f9' }}>{cell == null ? '' : String(cell)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  if (d.formatted_value !== undefined) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        {d.icon_class && <i className={`fa ${d.icon_class} wb-kpi-icon ${d.status_css || ''}`} />}
        <span style={{ fontSize: 26, fontWeight: 700, color: '#0f172a' }}>{d.formatted_value || '—'}</span>
        {d.label && <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '.04em' }}>{d.label}</span>}
        {d.secondary && <span className={`wb-kpi-secondary ${d.status_css || ''}`} style={{ fontSize: 12 }}>{d.secondary}</span>}
      </div>
    )
  }
  return <div style={{ color: '#94a3b8', fontSize: 12, textAlign: 'center' }}>No preview for this block.</div>
}

function CompositePreviewInline({ data }) {
  const children = Array.isArray(data?.children) ? data.children : []
  if (!children.length) {
    return <div style={{ padding: 24, textAlign: 'center', color: '#64748b' }}>No child blocks to preview.</div>
  }
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(12, 1fr)',
      gap: 12,
      padding: 12,
      background: '#fff',
      border: '1px solid #e5e7eb',
      borderRadius: 8,
    }}>
      {children.map(child => {
        // Content alignment — mirrors CompositeWidget.jsx exactly. Missing or
        // unrecognized values normalize to 'stretch' (today's behavior: no
        // styles emitted, no extra DOM node).
        const vAlign = ['top', 'center', 'bottom'].includes(child.content_vertical_align)
          ? child.content_vertical_align : 'stretch'
        const hAlign = ['left', 'center', 'right'].includes(child.content_horizontal_align)
          ? child.content_horizontal_align : 'stretch'
        const hasAlignment = vAlign !== 'stretch' || hAlign !== 'stretch'
        const bodyStyle = { flex: 1, minHeight: 0 }
        if (hasAlignment) {
          // column-direction flex → vertical = main axis (justifyContent),
          // horizontal = cross axis (alignItems)
          bodyStyle.display = 'flex'
          bodyStyle.flexDirection = 'column'
          if (vAlign !== 'stretch') bodyStyle.justifyContent =
            { top: 'flex-start', center: 'center', bottom: 'flex-end' }[vAlign]
          if (hAlign !== 'stretch') bodyStyle.alignItems =
            { left: 'flex-start', center: 'center', right: 'flex-end' }[hAlign]
        }
        return (
          <div
            key={child.id}
            style={{
              gridColumn: `${child.col_start} / span ${child.col_span}`,
              ...(Number(child.row_start) > 0
                ? { gridRow: `${child.row_start} / span ${child.row_span}` }
                : { gridRow: `span ${child.row_span}` }),
              minHeight: child.min_height_px || 240,
              minWidth: 0,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {child.title && (
              <div style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 4 }}>{child.title}</div>
            )}
            <div style={bodyStyle}>
              {hasAlignment ? (
                // Auto-sized wrapper lets content shrink to natural size so the
                // alignment is visible (a child's height:100% resolves to auto
                // against this auto-height parent).
                <div style={{ flex: '0 0 auto', maxWidth: '100%' }}>
                  <CompositeChildPreview child={child} />
                </div>
              ) : (
                <CompositeChildPreview child={child} />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/**
 * Step 5: Live Preview + Save.
 *
 * When appContext has a page selected, shows real filter dropdowns
 * from the page's filter definitions. Otherwise falls back to manual test params.
 *
 * Props:
 *   builderState   — full useReducer state
 *   generatedSql   — SQL string from preview API
 *   onSqlGenerated — (sql) => void
 *   onSave         — () => Promise — trigger save, returns { id } on success
 *   saving         — boolean
 *   apiBase        — string
 *   appContext     — { app, page, tab } | null
 */
export default function LivePreview({
  builderState, generatedSql, onSqlGenerated,
  onSave, saving, apiBase, appContext = null,
  onAppearanceChange = null, editId = null,
}) {
  const [previewData, setPreviewData] = useState(null)
  const [previewError, setPreviewError] = useState(null)
  const [previewCounter, setPreviewCounter] = useState(0)
  const [loading, setLoading] = useState(false)
  const [filterValues, setFilterValues] = useState({})
  const [placing, setPlacing] = useState(false)
  const [placeSuccess, setPlaceSuccess] = useState(false)
  const chartRef = useRef(null)
  const containerRef = useRef(null)

  const hasPageContext = !!appContext?.page?.id

  // Init ECharts
  useEffect(() => {
    if (!containerRef.current) return
    chartRef.current = echarts.init(containerRef.current, null, { renderer: 'canvas' })
    const onResize = () => chartRef.current?.resize()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  // Update chart when preview data arrives — counter ensures re-render
  useEffect(() => {
    if (!chartRef.current || !previewData?.echart_option) return
    chartRef.current.clear()
    chartRef.current.setOption(previewData.echart_option, { notMerge: true })
  }, [previewData, previewCounter])

  const isChart = ['bar', 'line', 'pie', 'donut', 'radar', 'scatter', 'heatmap', 'sankey'].includes(
    builderState.chartType
  )
  // Gauge is a chart only when using ECharts variants (not bullet/RAG/percentile)
  const gaugeStyle = builderState.visualFlags?.gauge_style || 'standard'
  const isEChartsGauge = builderState.chartType === 'gauge' &&
    !['bullet', 'traffic_light_rag', 'percentile_rank'].includes(gaugeStyle)
  const isNonEChartsGauge = builderState.chartType === 'gauge' &&
    ['bullet', 'traffic_light_rag', 'percentile_rank'].includes(gaugeStyle)
  const isTable = builderState.chartType === 'table'
  const isMemberFlow = builderState.chartType === 'sankey_member_flow'
  const isComposite = builderState.chartType === 'composite'
  // KPI label placement (opt-in) — read from live config so the preview reflects
  // above/below/hidden without a backend round-trip. Default keeps current order.
  const kpiLabelPos = builderState.visualFlags?.kpi_label_position || 'default'
  const kpiShowLabel = kpiLabelPos !== 'hidden'
  const kpiLabelAbove = kpiLabelPos === 'above_value'

  const runPreview = async () => {
    setLoading(true)
    setPreviewError(null)
    try {
      const body = buildPreviewPayload(builderState, hasPageContext ? filterValues : null)
      // Pass page_id so preview endpoint can load filter metadata
      // (multiselect awareness, _year_single/_year_prior helpers)
      if (hasPageContext && appContext?.page?.id) {
        body.page_id = appContext.page.id
      }
      const result = await designerFetch(previewUrl(apiBase), {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setPreviewData(result)
      setPreviewCounter(c => c + 1)
      if (result.sql) onSqlGenerated(result.sql)
    } catch (err) {
      setPreviewError(err.message || 'Preview failed')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveAndPlace = async () => {
    if (!appContext?.page) return
    setPlacing(true)
    try {
      // Build the PLACE body BEFORE saving, because handleSave() resets state
      const placeBody = {
        page_id: appContext.page.id,
        tab_id: appContext.tab?.id || null,
      }
      // Capture scope options NOW (before RESET wipes state)
      if (builderState.scopeMode !== 'none' && builderState.optionConfigs?.length) {
        placeBody.scope_options = (builderState.scopeOptions || []).map((opt, idx) => {
          const cfg = (builderState.optionConfigs || [])[idx] || {}
          const cs = cfg.customSql || {}
          const ai = cfg.aiState || {}
          const optSql = cfg.dataMode === 'ai' ? (ai.generatedSql || '') : (cs.sql || '')
          const optPayload = {
            label: opt.label || '', value: opt.value || '', icon: opt.icon || '',
            sequence: (idx + 1) * 10, query_sql: optSql,
            table_column_config: cfg.tableColumnConfig?.length ? JSON.stringify(cfg.tableColumnConfig) : '',
            x_column: cs.xColumn || '', y_columns: cs.yColumns || '', series_column: cs.seriesColumn || '',
            click_action: cfg.clickAction || 'none', action_page_key: cfg.actionPageKey || '',
            action_tab_key: cfg.actionTabKey || '', action_pass_value_as: cfg.actionPassValueAs || '',
            drill_detail_columns: cfg.drillDetailColumns || '', action_url_template: cfg.actionUrlTemplate || '',
          }
          // Mode B: per-option ranked configs
          if (
            builderState.chartType === 'ranked_detail_list'
            && builderState.scopeQueryMode === 'query'
          ) {
            if (cfg.masterRowConfig) {
              optPayload.ranked_master_config = JSON.stringify(cfg.masterRowConfig)
            }
            if (cfg.detailConfig) {
              // Strip internal test-only fields
              const cleaned = { ...cfg.detailConfig }
              delete cleaned._testResult
              delete cleaned._testParams
              if (Array.isArray(cleaned.tiles)) {
                cleaned.tiles = cleaned.tiles.map(t => {
                  const ct = { ...t }
                  delete ct._testResult
                  delete ct._testParams
                  return ct
                })
              }
              if (cleaned.sublist) {
                const cs2 = { ...cleaned.sublist }
                delete cs2._testResult
                delete cs2._testParams
                cleaned.sublist = cs2
              }
              optPayload.ranked_detail_config = JSON.stringify(cleaned)
            }
          }
          return optPayload
        })
      }

      // NOW save (this triggers RESET which wipes state)
      const result = await onSave()
      if (!result?.id) {
        setPlacing(false)
        return
      }
      // When editing, library_update already synced all instances —
      // don't call place_on_page or it creates a duplicate instance.
      if (editId) {
        setPlaceSuccess(true)
        return
      }
      // New widget: place instance with pre-captured scope_options
      await designerFetch(libraryPlaceUrl(apiBase, result.id), {
        method: 'POST',
        body: JSON.stringify(placeBody),
      })
      setPlaceSuccess(true)
    } catch (err) {
      setPreviewError(err.message || 'Save & Place failed')
    } finally {
      setPlacing(false)
    }
  }

  return (
    <div>
      <h3 className="wb-step-title">Preview & Save</h3>

      {/* Widget name */}
      <div className="wb-field-group" style={{ marginBottom: 16 }}>
        <label className="wb-field-label">Widget Name <span style={{ color: '#ef4444' }}>*</span></label>
        <input
          type="text"
          className="wb-input"
          value={builderState.appearance?.title || ''}
          placeholder="e.g. Total Admits by Year, Revenue/Visit Trend"
          onChange={e => {
            if (onAppearanceChange) {
              onAppearanceChange({ ...builderState.appearance, title: e.target.value })
            }
          }}
        />
      </div>

      {/* Page filter dropdowns (when app context has a page) */}
      {hasPageContext && (
        <div className="wb-field-group">
          <PageFilterPanel
            pageId={appContext.page.id}
            apiBase={apiBase}
            values={filterValues}
            onChange={setFilterValues}
          />
        </div>
      )}

      {/* Preview button */}
      <div className="wb-field-group">
        <button
          type="button"
          className="wb-btn wb-btn--primary"
          onClick={runPreview}
          disabled={loading}
        >
          {loading ? (
            <><span className="spinner-border spinner-border-sm me-1" /> Generating…</>
          ) : (
            <><i className="fa fa-play me-1" /> Run Preview</>
          )}
        </button>
      </div>

      {/* Error */}
      {previewError && (
        <div className="wb-preview-error">
          <i className="fa fa-exclamation-triangle me-1" />
          {previewError}
        </div>
      )}

      {/* Chart preview (ECharts) */}
      {(isChart || isEChartsGauge) && (
        <div className="wb-preview-chart">
          <div
            ref={containerRef}
            style={{ height: `${builderState.appearance?.chartHeight || 350}px`, width: '100%' }}
          />
        </div>
      )}

      {/* Non-ECharts gauge preview (bullet, RAG, percentile) */}
      {isNonEChartsGauge && previewData?.gauge_variant && (
        <div className="wb-preview-chart" style={{ border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff' }}>
          <GaugePreviewInline data={previewData} height={builderState.appearance?.chartHeight || 200} />
        </div>
      )}

      {/* Table preview */}
      {isTable && previewData?.rows && (
        <div className="wb-preview-table">
          <div className="table-responsive">
            <table className="table table-sm table-hover">
              <thead>
                <tr>
                  {(previewData.columns || []).map(col => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewData.rows.slice(0, 20).map((row, ri) => (
                  <tr key={ri}>
                    {(previewData.columns || []).map(col => (
                      <td key={col}>{row[col] ?? ''}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {previewData.rows.length > 20 && (
            <p className="wb-hint">Showing first 20 of {previewData.rows.length} rows</p>
          )}
        </div>
      )}

      {/* Member Flow preview */}
      {isMemberFlow && previewData && (
        <div className="wb-preview-chart" style={{ border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff' }}>
          <MemberFlowPreviewInline data={previewData} height={builderState.appearance?.chartHeight || 420} />
        </div>
      )}

      {/* Composite preview — exact 12-col card layout */}
      {isComposite && previewData && (
        <CompositePreviewInline data={previewData} />
      )}

      {/* KPI / Gauge preview */}
      {!isChart && !isTable && !isMemberFlow && !isComposite && previewData && (
        <div className="wb-preview-kpi">
          <div className="wb-kpi-preview-card">
            {previewData.icon_class && (
              <i className={`fa ${previewData.icon_class} wb-kpi-icon ${previewData.status_css || ''}`} />
            )}
            {kpiShowLabel && kpiLabelAbove && (
              <span className="wb-kpi-label">
                {previewData.label || builderState.appearance?.title || 'KPI'}
              </span>
            )}
            <span className="wb-kpi-value">
              {previewData.formatted_value || '—'}
            </span>
            {kpiShowLabel && !kpiLabelAbove && (
              <span className="wb-kpi-label">
                {previewData.label || builderState.appearance?.title || 'KPI'}
              </span>
            )}
            {previewData.secondary && (
              <span className="wb-kpi-secondary">{previewData.secondary}</span>
            )}
          </div>
        </div>
      )}

      {/* Generated SQL */}
      {generatedSql && (
        <div className="wb-field-group">
          <label className="wb-label">Generated SQL</label>
          <pre className="wb-sql-display">{generatedSql}</pre>
        </div>
      )}

      {/* Placement hint */}
      <div className="wb-section">
        <p className="wb-hint">
          <i className="fa fa-info-circle me-1" />
          {hasPageContext
            ? `You can save & place directly on ${appContext.page.name}${appContext.tab ? ` → ${appContext.tab.name}` : ''}.`
            : 'After saving, you can place this widget on any app\'s dashboard.'}
        </p>
      </div>

      {/* Place success message */}
      {placeSuccess && (
        <div className="wb-place-success">
          <i className="fa fa-check-circle me-1" />
          Widget saved and placed on <strong>{appContext?.page?.name}</strong>
          {appContext?.tab && <> → <strong>{appContext.tab.name}</strong></>}!
        </div>
      )}

      {/* Save buttons */}
      <div className="wb-save-row">
        <button
          type="button"
          className="wb-btn wb-btn--success wb-btn--lg"
          onClick={onSave}
          disabled={saving || placing}
        >
          {saving ? (
            <><span className="spinner-border spinner-border-sm me-1" /> Saving…</>
          ) : (
            <><i className="fa fa-check me-1" /> Save to Library</>
          )}
        </button>

        {/* Save & Place shortcut */}
        {hasPageContext && !placeSuccess && (
          <button
            type="button"
            className="wb-btn wb-btn--primary wb-btn--lg"
            onClick={handleSaveAndPlace}
            disabled={saving || placing}
            style={{ marginLeft: '12px' }}
          >
            {placing ? (
              <><span className="spinner-border spinner-border-sm me-1" /> Placing…</>
            ) : (
              <>
                <i className="fa fa-external-link me-1" />
                Save & Place on {appContext.page.name}
                {appContext.tab && ` → ${appContext.tab.name}`}
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

/**
 * Build the preview payload from builder state.
 * When pageFilterValues is provided, uses those as params instead of manual testParams.
 */
export function buildPreviewPayload(state, pageFilterValues) {
  const isCustomSql = state.dataMode === 'custom_sql'
  const isAi = state.dataMode === 'ai'
  const widgetConfig = {
    x_column: isCustomSql ? (state.customSql?.xColumn || '') : isAi ? (state.aiState?.xColumn || '') : (state.xColumn || ''),
    y_columns: isCustomSql ? (state.customSql?.yColumns || '') : isAi ? (state.aiState?.yColumns || '') : '',
    series_column: isCustomSql ? (state.customSql?.seriesColumn || '') : (state.seriesColumn || ''),
    kpi_format: state.appearance?.kpiFormat || 'number',
    kpi_prefix: state.appearance?.kpiPrefix || '',
    kpi_suffix: state.appearance?.kpiSuffix || '',
    color_palette: state.appearance?.colorPalette || 'default',
    title: state.appearance?.title || '',
    visual_config: state.visualFlags || {},
  }

  // AI mode: use AI-generated SQL with same preview path as custom SQL
  if (isAi && state.aiState?.generatedSql) {
    const sql = state.aiState.generatedSql
    const params = {}
    for (const m of sql.matchAll(/%\((\w+)\)s/g)) {
      const paramName = m[1]
      if (pageFilterValues && paramName in pageFilterValues) {
        params[paramName] = pageFilterValues[paramName]
      } else {
        params[paramName] = ''
      }
    }
    // AI's source picker (TableJoinBuilder) puts the source on state.sources[0].
    // Pass it through so the preview executor dispatches to the right backend.
    const aiSourceId = (state.sources || [])[0]?.id || null
    return {
      mode: 'custom_sql',
      sql,
      params,
      chart_type: state.chartType,
      widget_config: widgetConfig,
      schema_source_id: aiSourceId,
    }
  }

  if (isCustomSql) {
    const sql = state.customSql?.sql || ''
    const testParams = state.customSql?.testParams || {}

    // Use page filter values if available, otherwise fall back to manual test params
    const params = {}
    const collectParams = (sqlText) => {
      for (const m of (sqlText || '').matchAll(/%\((\w+)\)s/g)) {
        const paramName = m[1]
        if (paramName in params) continue
        if (pageFilterValues && paramName in pageFilterValues) {
          params[paramName] = pageFilterValues[paramName]
        } else {
          params[paramName] = testParams[paramName] || ''
        }
      }
    }
    collectParams(sql)
    // Composite: own-SQL children carry their own %(param)s placeholders —
    // the preview executes them with the same param dict as the parent.
    if (state.chartType === 'composite') {
      for (const ch of (state.compositeChildren || [])) {
        if (ch.data_mode === 'own_sql') collectParams(ch.query_sql)
      }
    }
    return {
      mode: 'custom_sql',
      sql,
      params,
      chart_type: state.chartType,
      widget_config: widgetConfig,
      // ONE serialization — same shape as the save payload
      ...(state.chartType === 'composite' ? {
        composite_children: serializeCompositeChildren(state.compositeChildren),
      } : {}),
      // Phase 3 Path B fix-up: the wizard's final preview path goes
      // through here (separate from CustomSqlEditor's inline Test Query).
      // Without this, CH-backed Custom SQL widgets fail final preview
      // with "relation X does not exist" because the dispatch falls
      // back to local PG.
      schema_source_id: state.customSql?.schemaSourceId || null,
    }
  }

  const sourceIds = (state.sources || []).map(s => s.id)

  // ── Table type: build columns from tableColumnConfig ──────────────────────
  if (state.chartType === 'table' && state.tableColumnConfig?.length) {
    const tcc = state.tableColumnConfig
    const primarySourceId = sourceIds[0] ?? null
    const columns = tcc.map(c => ({
      source_id: c.source_id || primarySourceId,
      column: c.column || c.field,
      agg: null,
      alias: c.alias || c.column || c.field,
    }))
    widgetConfig.x_column = columns[0]?.alias || ''
    widgetConfig.y_columns = columns.map(c => c.alias).join(',')
    widgetConfig.series_column = ''

    return {
      mode: 'visual',
      chart_type: 'table',
      widget_config: widgetConfig,
      config: {
        source_ids: sourceIds,
        columns,
        filters: state.filters || [],
        group_by: [],
        order_by: [],
        limit: 50,
      },
      params: pageFilterValues || {},
    }
  }

  // ── Chart types: build columns from ColumnMapper's {x, y, series} ─────────
  const colState = state.columns || {}
  const columns = []

  // X dimension column (no aggregation)
  if (colState.x && colState.x.column) {
    columns.push({
      source_id: colState.x.source_id,
      column: colState.x.column,
      agg: null,
      alias: colState.x.alias || colState.x.column,
    })
  }

  // Y measure columns (with aggregation)
  for (const yc of (colState.y || [])) {
    if (yc.column) {
      const colEntry = {
        source_id: yc.source_id,
        column: yc.column,
        agg: yc.agg || 'sum',
        alias: yc.alias || yc.column,
      }
      if (yc.weightColumn) colEntry.weight_column = yc.weightColumn
      columns.push(colEntry)
    }
  }

  const groupBy = []
  // Group by X column
  if (colState.x && colState.x.column) {
    groupBy.push({ source_id: colState.x.source_id, column: colState.x.column })
  }

  // Series break column as GROUP BY + added to SELECT
  const seriesCol = colState.series
  if (seriesCol && seriesCol.column) {
    columns.push({
      source_id: seriesCol.source_id,
      column: seriesCol.column,
      agg: null,
      alias: seriesCol.alias || seriesCol.column,
    })
    groupBy.push({ source_id: seriesCol.source_id, column: seriesCol.column })
  }

  // Build order by — state.orderBy can be a string (legacy) or array (from ColumnMapper)
  const orderBy = []
  if (Array.isArray(state.orderBy)) {
    for (const ob of state.orderBy) {
      if (ob.alias) orderBy.push({ alias: ob.alias, dir: ob.dir || 'ASC' })
    }
  } else if (state.orderBy) {
    const dir = state.orderByDir || 'ASC'
    orderBy.push({ alias: state.orderBy, dir })
  }

  // Build y_columns for widget_config (needed by preview_formatter)
  const yColNames = (colState.y || []).map(c => c.alias || c.column).filter(Boolean).join(',')
  widgetConfig.y_columns = yColNames
  widgetConfig.x_column = colState.x?.alias || colState.x?.column || ''
  widgetConfig.series_column = seriesCol?.alias || seriesCol?.column || ''

  return {
    mode: 'visual',
    chart_type: state.chartType,
    widget_config: widgetConfig,
    config: {
      source_ids: sourceIds,
      columns,
      filters: state.filters || [],
      group_by: groupBy,
      order_by: orderBy,
      limit: state.limit ? parseInt(state.limit, 10) : null,
    },
    params: pageFilterValues || {},
  }
}
