import React, { useState, useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import { designerFetch } from '../../api/client'
import { previewUrl, libraryPlaceUrl } from '../../api/endpoints'
import PageFilterPanel from './PageFilterPanel'

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
}) {
  const [previewData, setPreviewData] = useState(null)
  const [previewError, setPreviewError] = useState(null)
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
      const body = buildPreviewPayload(builderState, hasPageContext ? filterValues : null)
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

  const handleSaveAndPlace = async () => {
    if (!appContext?.page) return
    setPlacing(true)
    try {
      // First save (onSave returns the created definition)
      const result = await onSave()
      if (!result?.id) {
        setPlacing(false)
        return
      }
      // Then place on the selected page/tab
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
function buildPreviewPayload(state, pageFilterValues) {
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

  // Visual mode
  const columns = (state.columns || []).map(c => ({
    source_id: c.source_id,
    column: c.column,
    agg: c.agg || null,
    alias: c.alias || null,
  }))

  const sourceIds = (state.sources || []).map(s => s.id)

  const groupBy = []
  if (state.xColumn) {
    const src = state.sources?.[0]
    if (src) groupBy.push({ source_id: src.id, column: state.xColumn })
  }

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
    params: pageFilterValues || {},
  }
}
