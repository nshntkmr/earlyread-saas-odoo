import React, { useState, useCallback, useEffect } from 'react'
import { designerFetch } from '../../api/client'
import TableJoinBuilder from './TableJoinBuilder'

/**
 * AI SQL Editor — Step 2 component when "AI Assistant" mode is selected.
 *
 * Shows: table selector + prompt textarea + generate button + SQL output.
 * Supports: generate, regenerate, refine, fix, and edit-as-custom-sql.
 *
 * Props:
 *   sources             — selected sources with columns (from TableJoinBuilder)
 *   aiState             — { prompt, generatedSql, xColumn, yColumns, explanation, warnings }
 *   chartType           — current chart type
 *   gaugeStyle          — gauge variant (optional)
 *   lineStyle           — line variant (optional)
 *   donutStyle          — donut variant (optional)
 *   ragLayout           — rag layout (optional)
 *   appContext          — { app, page, tab } for context
 *   apiBase             — API base URL
 *   onSourcesChange     — (sources) => void — update selected tables
 *   onUpdate            — (aiResult) => void — update AI state
 *   onPromptChange      — (prompt) => void
 *   onSwitchToCustomSql — (sql, xColumn, yColumns) => void
 */

const SUGGESTIONS = {
  'gauge:bullet': [
    'Compare quality metrics (timely access, rehospitalization, mortality) with state benchmarks',
    'Show 5 operational KPIs with peer comparisons stacked as rows',
  ],
  'gauge:traffic_light_rag': [
    'Traffic light status for key quality measures with peer benchmarks',
    'RAG scorecard for compliance metrics',
  ],
  'gauge:multi_ring': [
    'Composite quality score with 3-4 metrics as concentric rings',
  ],
  'gauge:half_arc': [
    'Timely access rate with target marker at 85%',
  ],
  'gauge:standard': [
    'Hospitalization rate on a 0-30 scale with traffic light zones',
  ],
  'bar': [
    'Admissions by year grouped by payer type (FFS vs MA)',
    'Top 10 HHAs by total admits',
  ],
  'line': [
    'Trend of timely access rate over years',
    'Monthly admits with benchmark reference line',
  ],
  'kpi': [
    'Total admits for the selected provider',
    'Year-over-year change in admissions',
  ],
  'donut': [
    'Payer mix breakdown (FFS vs MA)',
    'Referral source distribution',
  ],
  'table': [
    'List of HHAs with admits, timely access, and hospitalization rate',
  ],
}

function getSuggestions(chartType, gaugeStyle) {
  if (chartType === 'gauge' && gaugeStyle) {
    return SUGGESTIONS[`gauge:${gaugeStyle}`] || SUGGESTIONS['gauge:standard'] || []
  }
  return SUGGESTIONS[chartType] || []
}


export default function AiSqlEditor({
  sources, aiState = {}, chartType, gaugeStyle, lineStyle, donutStyle, ragLayout,
  appContext, apiBase,
  onSourcesChange, onUpdate, onPromptChange, onSwitchToCustomSql,
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [refinePrompt, setRefinePrompt] = useState('')
  const [dynamicSuggestions, setDynamicSuggestions] = useState([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [showAllSuggestions, setShowAllSuggestions] = useState(false)
  const [suggestionsCache, setSuggestionsCache] = useState({}) // {source_id:chart_type: suggestions}

  const { prompt = '', generatedSql = '', xColumn = '', yColumns = '',
          seriesColumn = '', explanation = '', warnings = [] } = aiState

  const hasSource = sources && sources.length > 0
  const sourceId = hasSource ? sources[0].id : null
  const pageId = appContext?.page?.id

  // Static fallback suggestions
  const staticSuggestions = getSuggestions(chartType, gaugeStyle)

  // Fetch dynamic suggestions when source + chart type changes
  useEffect(() => {
    if (!sourceId || !chartType) {
      setDynamicSuggestions([])
      return
    }
    const cacheKey = `${sourceId}:${chartType}:${gaugeStyle || ''}`
    if (suggestionsCache[cacheKey]) {
      setDynamicSuggestions(suggestionsCache[cacheKey])
      return
    }
    setSuggestionsLoading(true)
    designerFetch(`${apiBase}/ai-generate`, {
      method: 'POST',
      body: JSON.stringify({
        mode: 'suggest',
        source_id: sourceId,
        page_id: pageId,
        chart_type: chartType,
        gauge_style: gaugeStyle || undefined,
        line_style: lineStyle || undefined,
        donut_style: donutStyle || undefined,
        rag_layout: ragLayout || undefined,
      }),
    })
      .then(result => {
        const suggs = result.suggestions || []
        setDynamicSuggestions(suggs)
        setSuggestionsCache(prev => ({ ...prev, [cacheKey]: suggs }))
      })
      .catch(() => {
        // Fallback to static suggestions on error
        setDynamicSuggestions([])
      })
      .finally(() => setSuggestionsLoading(false))
  }, [sourceId, chartType, gaugeStyle]) // eslint-disable-line react-hooks/exhaustive-deps

  // Use dynamic suggestions if available, otherwise static
  const allSuggestions = dynamicSuggestions.length > 0 ? dynamicSuggestions : staticSuggestions
  const visibleSuggestions = showAllSuggestions ? allSuggestions : allSuggestions.slice(0, 5)

  // ── Call the backend AI endpoint ────────────────────────────────
  const callAi = useCallback(async (userPrompt, previousSql = null, errorMessage = null) => {
    if (!sourceId) {
      setError('Please select a data table first.')
      return
    }
    if (!userPrompt && !errorMessage) {
      setError('Please describe what you want to display.')
      return
    }

    setLoading(true)
    setError(null)
    try {
      const body = {
        source_id: sourceId,
        page_id: pageId,
        chart_type: chartType,
        gauge_style: gaugeStyle || undefined,
        line_style: lineStyle || undefined,
        donut_style: donutStyle || undefined,
        rag_layout: ragLayout || undefined,
        prompt: userPrompt,
      }
      if (previousSql) body.previous_sql = previousSql
      if (errorMessage) body.error_message = errorMessage

      const result = await designerFetch(`${apiBase}/ai-generate`, {
        method: 'POST',
        body: JSON.stringify(body),
      })

      if (result.error) {
        setError(result.error)
      } else {
        onUpdate({
          generatedSql: result.sql || '',
          xColumn: result.x_column || '',
          yColumns: result.y_columns || '',
          seriesColumn: result.series_column || '',
          explanation: result.explanation || '',
          warnings: result.warnings || [],
        })
        setError(null)
      }
    } catch (err) {
      setError(err.message || 'AI generation failed. Check your API configuration.')
    } finally {
      setLoading(false)
    }
  }, [sourceId, pageId, chartType, gaugeStyle, lineStyle, donutStyle, ragLayout, apiBase, onUpdate])

  const handleGenerate = () => callAi(prompt)
  const handleRegenerate = () => callAi(prompt)
  const handleRefine = () => {
    if (refinePrompt.trim()) {
      callAi(refinePrompt, generatedSql)
      setRefinePrompt('')
    }
  }
  const handleFix = (errMsg) => callAi(prompt, generatedSql, errMsg)

  const handleEditAsSql = () => {
    if (onSwitchToCustomSql) {
      onSwitchToCustomSql(generatedSql, xColumn, yColumns, seriesColumn)
    }
  }

  return (
    <div>
      {/* ── Table selector (reuse TableJoinBuilder) ──────────────── */}
      <TableJoinBuilder
        sources={sources}
        onUpdate={({ sources: newSources }) => {
          if (onSourcesChange) onSourcesChange(newSources)
        }}
        apiBase={apiBase}
      />

      {/* ── AI prompt section ────────────────────────────────────── */}
      <div style={{ marginTop: 20 }}>
        <h4 className="wb-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <i className="fa fa-magic" style={{ color: '#8b5cf6' }} />
          Describe what you want to display
        </h4>

        <textarea
          className="wb-input"
          rows={4}
          placeholder="Example: Show timely access rate, rehospitalization, and mortality for the selected HHA compared to state benchmarks. Stack them as rows for a bullet gauge."
          value={prompt}
          onChange={e => onPromptChange && onPromptChange(e.target.value)}
          style={{ resize: 'vertical', fontFamily: 'inherit' }}
        />

        {/* ── Suggestion pills ───────────────────────────────────── */}
        {!generatedSql && (
          <div style={{ marginTop: 8 }}>
            {suggestionsLoading ? (
              <div style={{ fontSize: 11, color: '#6b7280' }}>
                <span className="spinner-border spinner-border-sm me-2" style={{ width: 12, height: 12 }} />
                Loading smart suggestions...
              </div>
            ) : visibleSuggestions.length > 0 ? (
              <>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  <span style={{ fontSize: 11, color: '#6b7280', marginRight: 4, lineHeight: '24px' }}>
                    {dynamicSuggestions.length > 0 ? '✨ Smart suggestions:' : 'Suggestions:'}
                  </span>
                  {visibleSuggestions.map((s, i) => (
                    <button
                      key={i}
                      type="button"
                      className="wb-btn wb-btn--outline"
                      style={{ fontSize: 11, padding: '3px 8px', borderRadius: 12, textAlign: 'left' }}
                      onClick={() => onPromptChange && onPromptChange(s)}
                    >
                      {s}
                    </button>
                  ))}
                </div>
                {allSuggestions.length > 5 && !showAllSuggestions && (
                  <button
                    type="button"
                    className="wb-btn wb-btn--outline"
                    style={{ fontSize: 10, padding: '2px 8px', marginTop: 4 }}
                    onClick={() => setShowAllSuggestions(true)}
                  >
                    Show {allSuggestions.length - 5} more suggestions...
                  </button>
                )}
              </>
            ) : null}
          </div>
        )}

        {/* ── Generate button ────────────────────────────────────── */}
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button
            type="button"
            className="wb-btn wb-btn--primary"
            disabled={loading || !prompt.trim() || !hasSource}
            onClick={handleGenerate}
            style={{ minWidth: 150 }}
          >
            {loading ? (
              <><span className="spinner-border spinner-border-sm me-2" /> Generating...</>
            ) : (
              <><i className="fa fa-magic me-1" /> Generate SQL</>
            )}
          </button>
        </div>

        {/* ── Error display ──────────────────────────────────────── */}
        {error && (
          <div style={{
            marginTop: 12, padding: '10px 14px', borderRadius: 6,
            background: '#fef2f2', border: '1px solid #fecaca', color: '#dc2626',
            fontSize: 13,
          }}>
            <i className="fa fa-exclamation-triangle me-2" />
            {error}
            {generatedSql && (
              <button
                type="button"
                className="wb-btn wb-btn--outline"
                style={{ marginLeft: 12, fontSize: 11, padding: '2px 8px' }}
                onClick={() => handleFix(error)}
                disabled={loading}
              >
                <i className="fa fa-wrench me-1" /> Ask AI to Fix
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Generated SQL output ─────────────────────────────────── */}
      {generatedSql && (
        <div style={{ marginTop: 20 }}>
          <h4 className="wb-label">Generated SQL</h4>

          <pre style={{
            background: '#1e293b', color: '#e2e8f0', padding: '14px 16px',
            borderRadius: 8, fontSize: 12, lineHeight: 1.5,
            overflow: 'auto', maxHeight: 300,
            fontFamily: '"Fira Code", "Cascadia Code", monospace',
          }}>
            {generatedSql}
          </pre>

          {/* ── Column mapping ────────────────────────────────────── */}
          <div style={{
            marginTop: 8, padding: '8px 12px', borderRadius: 6,
            background: '#f8fafc', border: '1px solid #e2e8f0',
            fontSize: 12,
          }}>
            <strong>Column Mapping:</strong>
            <span style={{ marginLeft: 8 }}>
              X: <code>{xColumn || '(auto)'}</code>
              {yColumns && <>, Y: <code>{yColumns}</code></>}
              {seriesColumn && <>, Series: <code>{seriesColumn}</code></>}
            </span>
          </div>

          {/* ── AI explanation ────────────────────────────────────── */}
          {explanation && (
            <div style={{
              marginTop: 8, padding: '10px 14px', borderRadius: 6,
              background: '#f0fdf4', border: '1px solid #bbf7d0',
              fontSize: 12, color: '#166534',
            }}>
              <i className="fa fa-info-circle me-2" style={{ color: '#16a34a' }} />
              {explanation}
            </div>
          )}

          {/* ── Warnings ─────────────────────────────────────────── */}
          {warnings && warnings.length > 0 && (
            <div style={{
              marginTop: 8, padding: '8px 12px', borderRadius: 6,
              background: '#fffbeb', border: '1px solid #fde68a',
              fontSize: 12, color: '#92400e',
            }}>
              {warnings.map((w, i) => (
                <div key={i}><i className="fa fa-exclamation-triangle me-1" /> {w}</div>
              ))}
            </div>
          )}

          {/* ── Action buttons ────────────────────────────────────── */}
          <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="wb-btn wb-btn--outline"
              onClick={handleEditAsSql}
            >
              <i className="fa fa-pencil me-1" /> Edit as Custom SQL
            </button>
            <button
              type="button"
              className="wb-btn wb-btn--outline"
              onClick={handleRegenerate}
              disabled={loading}
            >
              <i className="fa fa-refresh me-1" /> Regenerate
            </button>
          </div>

          {/* ── Refine input ──────────────────────────────────────── */}
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                className="wb-input"
                placeholder="Refine: e.g., 'add LUPA rate' or 'make benchmarks county-level'"
                value={refinePrompt}
                onChange={e => setRefinePrompt(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleRefine()}
                style={{ flex: 1 }}
              />
              <button
                type="button"
                className="wb-btn wb-btn--outline"
                onClick={handleRefine}
                disabled={loading || !refinePrompt.trim()}
              >
                <i className="fa fa-magic me-1" /> Refine
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
