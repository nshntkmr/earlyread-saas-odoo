import React, { useState, useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { designerFetch } from '../../api/client'
import { previewUrl } from '../../api/endpoints'

/**
 * Step 6: Live Preview + Save.
 *
 * Designer version — no pages endpoint (placement is done via AppPagePicker after save).
 *
 * Props:
 *   builderState   — full useReducer state (chartType, dataMode, sources, columns, etc.)
 *   generatedSql   — SQL string from preview API (set after first preview)
 *   onSqlGenerated — (sql) => void — propagate generated SQL back up
 *   onSave         — () => void — trigger save
 *   saving         — boolean
 *   apiBase        — string
 */
export default function LivePreview({
  builderState, generatedSql, onSqlGenerated,
  onSave, saving, apiBase,
}) {
  const [previewData, setPreviewData] = useState(null)
  const [previewError, setPreviewError] = useState(null)
  const [loading, setLoading] = useState(false)
  const chartRef = useRef(null)
  const containerRef = useRef(null)

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

  // Update chart when preview data arrives
  useEffect(() => {
    if (!chartRef.current || !previewData?.echart_option) return
    chartRef.current.setOption(previewData.echart_option, { notMerge: true })
  }, [previewData])

  const isChart = ['bar', 'line', 'pie', 'donut', 'radar', 'scatter', 'heatmap', 'gauge'].includes(
    builderState.chartType
  )
  const isTable = builderState.chartType === 'table'

  const runPreview = async () => {
    setLoading(true)
    setPreviewError(null)
    try {
      const body = buildPreviewPayload(builderState)
      const result = await designerFetch(previewUrl(apiBase), {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setPreviewData(result)
      if (result.sql) onSqlGenerated(result.sql)
    } catch (err) {
      setPreviewError(err.message || 'Preview failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h3 className="wb-step-title">Preview & Save</h3>

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

      {/* Chart preview */}
      {isChart && (
        <div className="wb-preview-chart">
          <div
            ref={containerRef}
            style={{ height: `${builderState.appearance?.chartHeight || 350}px`, width: '100%' }}
          />
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

      {/* Note: In designer, placement is done via AppPagePicker after saving */}
      <div className="wb-section">
        <p className="wb-hint">
          <i className="fa fa-info-circle me-1" />
          After saving, you can place this widget on any app's dashboard.
        </p>
      </div>

      {/* Save button */}
      <div className="wb-save-row">
        <button
          type="button"
          className="wb-btn wb-btn--success wb-btn--lg"
          onClick={onSave}
          disabled={saving}
        >
          {saving ? (
            <><span className="spinner-border spinner-border-sm me-1" /> Saving…</>
          ) : (
            <><i className="fa fa-check me-1" /> Save to Library</>
          )}
        </button>
      </div>
    </div>
  )
}

/**
 * Build the preview payload from builder state.
 *
 * Backend expects:
 *   mode='custom_sql' → { sql: '...' }
 *   mode='visual'     → { config: { source_ids, columns, filters, ... } }
 */
function buildPreviewPayload(state) {
  // Common widget config for the preview formatter
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
  }

  if (isCustomSql) {
    // Include test param values so the preview can execute parameterised SQL
    const sql = state.customSql?.sql || ''
    const testParams = state.customSql?.testParams || {}
    const params = {}
    for (const m of sql.matchAll(/%\((\w+)\)s/g)) {
      params[m[1]] = testParams[m[1]] || ''
    }
    return {
      mode: 'custom_sql',
      sql,
      params,
      chart_type: state.chartType,
      widget_config: widgetConfig,
    }
  }

  // Visual mode — build config dict matching QueryBuilder.build_select_query()
  const columns = (state.columns || []).map(c => ({
    source_id: c.source_id,
    column: c.column,
    agg: c.agg || null,
    alias: c.alias || null,
  }))

  const sourceIds = (state.sources || []).map(s => s.id)

  // Build group_by from x_column if present
  const groupBy = []
  if (state.xColumn) {
    const src = state.sources?.[0]
    if (src) groupBy.push({ source_id: src.id, column: state.xColumn })
  }

  // Build order_by
  const orderBy = []
  if (state.orderBy) {
    orderBy.push({ alias: state.orderBy, dir: 'ASC' })
  }

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
  }
}
