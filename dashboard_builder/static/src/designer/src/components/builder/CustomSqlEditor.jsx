import React, { useState, useMemo, useCallback, useEffect } from 'react'
import { designerFetch } from '../../api/client'
import { previewUrl, pageFiltersUrl } from '../../api/endpoints'

const SQL_COLUMN_HELP = {
  bar:           { cols: 'category, value1 [, value2, ...]', example: 'SELECT state, SUM(admits) AS admits FROM mv_hha GROUP BY state' },
  line:          { cols: 'x_value, y_value1 [, y_value2, ...]', example: 'SELECT year, total_visits, total_admits FROM mv_summary ORDER BY year' },
  pie:           { cols: 'label, value', example: 'SELECT payer_type, COUNT(*) AS count FROM mv_claims GROUP BY payer_type' },
  donut:         { cols: 'label, value', example: 'SELECT status, SUM(episodes) AS episodes FROM mv_discharge GROUP BY status' },
  donut_nested:  { cols: 'parent, child, value', example: 'SELECT payer, sub_type, SUM(episodes) FROM mv_claims GROUP BY 1, 2' },
  donut_multi_ring: { cols: 'ring_group, label, value', example: 'SELECT year, source_type, COUNT(*) FROM mv_admissions GROUP BY 1, 2' },
  gauge:         { cols: 'value', example: 'SELECT AVG(star_rating) AS rating FROM mv_quality' },
  radar:         { cols: 'indicator, score1 [, score2, ...]', example: 'SELECT metric_name, your_score, benchmark FROM mv_compare' },
  scatter:       { cols: 'x_value, y_value', example: 'SELECT latitude, longitude FROM mv_locations' },
  heatmap:       { cols: 'x_category, y_category, intensity', example: 'SELECT day_of_week, hour, visit_count FROM mv_traffic GROUP BY 1, 2' },
  kpi:           { cols: 'value [, prior_value]', example: 'SELECT SUM(revenue) AS revenue FROM mv_financial' },
  status_kpi:    { cols: 'value, status_text', example: 'SELECT total_patients, trend_label FROM mv_kpi' },
  table:         { cols: 'col1, col2, col3, ...', example: 'SELECT patient_id, name, status, score FROM mv_patients' },
}

function getSqlHelpKey(chartType, donutStyle) {
  if (chartType === 'donut' && donutStyle === 'nested') return 'donut_nested'
  if (chartType === 'donut' && donutStyle === 'multi_ring') return 'donut_multi_ring'
  return chartType
}

/**
 * Step 2 (Custom SQL mode): Write raw SQL with test query.
 *
 * Auto-detects %(param_name)s placeholders from the SQL and shows input
 * fields for each so admins can enter test values before running preview.
 *
 * When appContext has a page selected, shows the page's actual filter
 * param_names as insert pills (instead of hardcoded COMMON_PARAMS).
 *
 * Props:
 *   sql, xColumn, yColumns, seriesColumn, testResult, testParams, onUpdate, apiBase
 *   appContext  — { app, page, tab } | null — from AppContextBar
 *   chartType  — string — current chart type for SQL column help
 *   donutStyle — string — optional donut variant (standard, nested, multi_ring)
 */
export default function CustomSqlEditor({
  sql, xColumn, yColumns, seriesColumn, testResult,
  testParams = {}, onUpdate, apiBase, appContext = null,
  chartType, donutStyle,
}) {
  const [testing, setTesting] = useState(false)
  const [pageParams, setPageParams] = useState([])

  // Load page filter param names when page context changes
  useEffect(() => {
    if (!appContext?.page?.id) {
      setPageParams([])
      return
    }
    designerFetch(pageFiltersUrl(apiBase, appContext.page.id))
      .then(filters => {
        setPageParams(
          filters
            .filter(f => f.param_name)
            .map(f => ({ param: f.param_name, label: f.label || f.param_name }))
        )
      })
      .catch(() => setPageParams([]))
  }, [apiBase, appContext?.page?.id])

  const setTestParam = useCallback((key, value) => {
    onUpdate({ testParams: { ...testParams, [key]: value } })
  }, [testParams, onUpdate])

  // Insert pills: page filter params when context is set, otherwise auto-detected from SQL
  const insertPills = useMemo(() => {
    if (pageParams.length > 0) return pageParams
    // Fallback: auto-detect unique params from SQL
    if (!sql) return []
    const matches = [...sql.matchAll(/%\((\w+)\)s/g)]
    return [...new Set(matches.map(m => m[1]))].map(p => ({ param: p, label: p }))
  }, [pageParams, sql])

  // Auto-extract %(param_name)s placeholders from SQL (deduplicated, in order)
  const detectedParams = useMemo(() => {
    if (!sql) return []
    const matches = [...sql.matchAll(/%\((\w+)\)s/g)]
    return [...new Set(matches.map(m => m[1]))]
  }, [sql])

  const runTest = async () => {
    setTesting(true)
    try {
      const params = {}
      for (const p of detectedParams) {
        params[p] = testParams[p] || ''
      }
      const result = await designerFetch(previewUrl(apiBase), {
        method: 'POST',
        body: JSON.stringify({ mode: 'custom_sql', sql, params }),
      })
      onUpdate({ testResult: { columns: result.columns, rows: result.rows, error: null } })
    } catch (err) {
      onUpdate({ testResult: { columns: [], rows: [], error: err.message } })
    } finally {
      setTesting(false)
    }
  }

  const insertParam = (param) => {
    onUpdate({ sql: (sql || '') + `%(${param})s` })
  }

  return (
    <div>
      <h3 className="wb-step-title">Custom SQL Query</h3>

      {/* SQL column help */}
      {chartType && SQL_COLUMN_HELP[getSqlHelpKey(chartType, donutStyle)] && (
        <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 6, padding: '8px 12px', marginBottom: 10, fontSize: 13 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            Expected columns for {chartType}{donutStyle && donutStyle !== 'standard' ? ` (${donutStyle})` : ''}:
          </div>
          <code style={{ background: '#e0f2fe', padding: '2px 6px', borderRadius: 3 }}>
            {SQL_COLUMN_HELP[getSqlHelpKey(chartType, donutStyle)].cols}
          </code>
          <div style={{ color: '#6b7280', marginTop: 4, fontSize: 12 }}>
            Example: <code>{SQL_COLUMN_HELP[getSqlHelpKey(chartType, donutStyle)].example}</code>
          </div>
        </div>
      )}

      {/* SQL textarea */}
      <div className="wb-field-group">
        <label className="wb-label">SQL Query</label>
        <textarea
          className="wb-textarea wb-sql-editor"
          rows={8}
          value={sql || ''}
          onChange={e => onUpdate({ sql: e.target.value })}
          placeholder="SELECT hha_state, SUM(total_admits) AS admits&#10;FROM mv_hha_kpi_summary&#10;WHERE hha_state = %(hha_state)s&#10;GROUP BY hha_state&#10;ORDER BY admits DESC LIMIT 10"
        />
      </div>

      {/* Available params — quick-insert pills (dynamic from page context or SQL) */}
      <div className="wb-field-group">
        <label className="wb-label">
          Insert Filter Param
          {pageParams.length > 0 && (
            <span className="wb-hint-inline"> (from {appContext.page.name} filters)</span>
          )}
        </label>
        <div className="wb-param-pills">
          {insertPills.map(p => (
            <button
              key={p.param}
              type="button"
              className="wb-pill"
              onClick={() => insertParam(p.param)}
              title={`Insert %(${p.param})s`}
            >
              %({p.param})s
            </button>
          ))}
          {insertPills.length === 0 && (
            <span className="wb-hint">
              {appContext?.page
                ? 'No filters found for this page.'
                : 'Select a page in the Context bar to see available params, or type SQL with %(param)s placeholders.'}
            </span>
          )}
        </div>
      </div>

      {/* Test param values — auto-detected from SQL */}
      {detectedParams.length > 0 && (
        <div className="wb-field-group">
          <label className="wb-label">Test Values for Preview</label>
          <div className="wb-test-params">
            {detectedParams.map(p => (
              <div key={p} className="wb-test-param-row">
                <label className="wb-label-sm wb-test-param-label">
                  %({p})s
                </label>
                <input
                  type="text"
                  className="wb-input wb-test-param-input"
                  value={testParams[p] || ''}
                  onChange={e => setTestParam(p, e.target.value)}
                  placeholder={`e.g. test value for ${p}`}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Test button */}
      <div className="wb-field-group">
        <button
          type="button"
          className="wb-btn wb-btn--primary"
          onClick={runTest}
          disabled={testing || !sql?.trim()}
        >
          {testing ? (
            <><i className="fa fa-spinner fa-spin" /> Testing...</>
          ) : (
            <><i className="fa fa-play" /> Test Query</>
          )}
        </button>
        {testResult && !testResult.error && (
          <span className="wb-test-result wb-test-result--ok">
            <i className="fa fa-check" /> {testResult.rows.length} rows, {testResult.columns.length} columns
          </span>
        )}
        {testResult?.error && (
          <span className="wb-test-result wb-test-result--err">
            <i className="fa fa-exclamation-triangle" /> {testResult.error}
          </span>
        )}
      </div>

      {/* Column mapping */}
      <div className="wb-field-group">
        <label className="wb-label">Column Mapping</label>
        <div className="wb-inline-fields">
          <div>
            <label className="wb-label-sm">X-axis column</label>
            <input
              type="text"
              className="wb-input"
              value={xColumn || ''}
              onChange={e => onUpdate({ xColumn: e.target.value })}
              placeholder="e.g. state"
            />
          </div>
          <div>
            <label className="wb-label-sm">Y-axis columns</label>
            <input
              type="text"
              className="wb-input"
              value={yColumns || ''}
              onChange={e => onUpdate({ yColumns: e.target.value })}
              placeholder="e.g. admits, episodes"
            />
          </div>
          <div>
            <label className="wb-label-sm">Series column (optional)</label>
            <input
              type="text"
              className="wb-input"
              value={seriesColumn || ''}
              onChange={e => onUpdate({ seriesColumn: e.target.value })}
              placeholder="e.g. ffs_ma"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
