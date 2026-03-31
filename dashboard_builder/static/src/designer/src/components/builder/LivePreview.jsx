import React, { useState, useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { designerFetch } from '../../api/client'
import { previewUrl, libraryPlaceUrl } from '../../api/endpoints'
import PageFilterPanel from './PageFilterPanel'

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

function BulletPreview({ data, height }) {
  const { value = 0, formatted_value = '', target, min = 0, max = 100, ranges = [],
          label = '', threshold_text = '' } = data
  const range = max - min || 1
  const pct = Math.max(0, Math.min(100, ((value - min) / range) * 100))
  const tPct = target != null ? Math.max(0, Math.min(100, ((target - min) / range) * 100)) : null
  return (
    <div style={{ padding: '16px 20px', height }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>{label}</span>
        <span style={{ fontWeight: 700, fontSize: 18, color: '#0d9488' }}>{formatted_value}</span>
      </div>
      <div style={{ position: 'relative', height: 20, borderRadius: 4, overflow: 'hidden', display: 'flex' }}>
        {ranges.map((r, i) => {
          const prevTo = i > 0 ? ranges[i-1].to : min
          return <div key={i} style={{ width: `${((r.to - prevTo) / range) * 100}%`, backgroundColor: r.color, opacity: 0.25 }} />
        })}
        <div style={{ position: 'absolute', top: 4, left: 0, height: 12, width: `${pct}%`, borderRadius: 3, backgroundColor: '#0d9488' }} />
        {tPct != null && <div style={{ position: 'absolute', left: `${tPct}%`, top: 0, width: 2, height: 20, backgroundColor: '#374151' }} />}
      </div>
      {threshold_text && <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 6 }}>{threshold_text}</div>}
    </div>
  )
}

function RagPreview({ data, height }) {
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

  const isChart = ['bar', 'line', 'pie', 'donut', 'radar', 'scatter', 'heatmap'].includes(
    builderState.chartType
  )
  // Gauge is a chart only when using ECharts variants (not bullet/RAG/percentile)
  const gaugeStyle = builderState.visualFlags?.gauge_style || 'standard'
  const isEChartsGauge = builderState.chartType === 'gauge' &&
    !['bullet', 'traffic_light_rag', 'percentile_rank'].includes(gaugeStyle)
  const isNonEChartsGauge = builderState.chartType === 'gauge' &&
    ['bullet', 'traffic_light_rag', 'percentile_rank'].includes(gaugeStyle)
  const isTable = builderState.chartType === 'table'

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
      // First save (onSave returns the created/updated definition)
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
      // New widget: create instance on the selected page/tab
      await designerFetch(libraryPlaceUrl(apiBase, result.id), {
        method: 'POST',
        body: JSON.stringify({
          page_id: appContext.page.id,
          tab_id: appContext.tab?.id || null,
        }),
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

      {/* KPI / Gauge preview */}
      {!isChart && !isTable && previewData && (
        <div className="wb-preview-kpi">
          <div className="wb-kpi-preview-card">
            {previewData.icon_class && (
              <i className={`fa ${previewData.icon_class} wb-kpi-icon ${previewData.status_css || ''}`} />
            )}
            <span className="wb-kpi-value">
              {previewData.formatted_value || '—'}
            </span>
            <span className="wb-kpi-label">
              {previewData.label || builderState.appearance?.title || 'KPI'}
            </span>
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
  const widgetConfig = {
    x_column: isCustomSql ? (state.customSql?.xColumn || '') : (state.xColumn || ''),
    y_columns: isCustomSql ? (state.customSql?.yColumns || '') : '',
    series_column: isCustomSql ? (state.customSql?.seriesColumn || '') : (state.seriesColumn || ''),
    kpi_format: state.appearance?.kpiFormat || 'number',
    kpi_prefix: state.appearance?.kpiPrefix || '',
    kpi_suffix: state.appearance?.kpiSuffix || '',
    color_palette: state.appearance?.colorPalette || 'default',
    title: state.appearance?.title || '',
    visual_config: state.visualFlags || {},
  }

  if (isCustomSql) {
    const sql = state.customSql?.sql || ''
    const testParams = state.customSql?.testParams || {}

    // Use page filter values if available, otherwise fall back to manual test params
    const params = {}
    for (const m of sql.matchAll(/%\((\w+)\)s/g)) {
      const paramName = m[1]
      if (pageFilterValues && paramName in pageFilterValues) {
        params[paramName] = pageFilterValues[paramName]
      } else {
        params[paramName] = testParams[paramName] || ''
      }
    }
    return {
      mode: 'custom_sql',
      sql,
      params,
      chart_type: state.chartType,
      widget_config: widgetConfig,
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
