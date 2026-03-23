import React, { useState, useMemo, useCallback, useEffect } from 'react'
import { designerFetch } from '../../api/client'
import { previewUrl, pageFiltersUrl } from '../../api/endpoints'

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
 */
export default function CustomSqlEditor({
  sql, xColumn, yColumns, seriesColumn, testResult,
  testParams = {}, onUpdate, apiBase, appContext = null,
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
