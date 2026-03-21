import React, { useState, useMemo, useCallback } from 'react'
import { designerFetch } from '../../api/client'
import { previewUrl } from '../../api/endpoints'

/**
 * Step 2 (Custom SQL mode): Write raw SQL with test query.
 *
 * Auto-detects %(param_name)s placeholders from the SQL and shows input
 * fields for each so admins can enter test values before running preview.
 *
 * Props:
 *   sql              — current SQL text
 *   xColumn          — X-axis column name
 *   yColumns         — comma-separated Y column names
 *   seriesColumn     — optional series column
 *   testResult       — {columns, rows, error} or null
 *   onUpdate         — ({sql, xColumn, yColumns, seriesColumn, testResult}) => void
 *   apiBase          — string
 */
export default function CustomSqlEditor({
  sql, xColumn, yColumns, seriesColumn, testResult,
  testParams = {}, onUpdate, apiBase,
}) {
  const [testing, setTesting] = useState(false)

  // Propagate test param changes to parent state (so LivePreview can use them)
  const setTestParam = useCallback((key, value) => {
    onUpdate({ testParams: { ...testParams, [key]: value } })
  }, [testParams, onUpdate])

  // Common params for quick-insert pills
  const COMMON_PARAMS = [
    'hha_state', 'hha_county', 'hha_city', 'hha_id',
    'hha_ccn', 'hha_name', 'year', 'ffs_ma',
  ]

  // Auto-extract %(param_name)s placeholders from SQL (deduplicated, in order)
  const detectedParams = useMemo(() => {
    if (!sql) return []
    const matches = [...sql.matchAll(/%\((\w+)\)s/g)]
    return [...new Set(matches.map(m => m[1]))]
  }, [sql])

  const runTest = async () => {
    setTesting(true)
    try {
      // Build params dict from test inputs for all detected placeholders
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

      {/* Available params — quick-insert pills */}
      <div className="wb-field-group">
        <label className="wb-label">Insert Filter Param</label>
        <div className="wb-param-pills">
          {COMMON_PARAMS.map(p => (
            <button
              key={p}
              type="button"
              className="wb-pill"
              onClick={() => insertParam(p)}
              title={`Insert %(${p})s`}
            >
              %({p})s
            </button>
          ))}
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
