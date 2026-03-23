import React, { useState, useEffect, useCallback } from 'react'
import { designerFetch } from '../api/client'
import { sourcesUrl, sourceDetailUrl, templateUseUrl, appsUrl, appPagesUrl } from '../api/endpoints'

const FORMAT_TYPES = [
  { value: 'number', label: 'Number (e.g. 52,843)' },
  { value: 'percent', label: 'Percent (e.g. 12.5%)' },
  { value: 'currency', label: 'Currency (e.g. $1,200)' },
  { value: 'decimal', label: 'Decimal (e.g. 4.23)' },
]

/**
 * Resolve {{slot}} placeholders in text with values from a mapping.
 */
function resolveSlots(text, mapping) {
  if (!text) return ''
  return text.replace(/\{\{(\w+)\}\}/g, (m, key) => (key in mapping ? mapping[key] : m))
}

/**
 * TemplateConfigPanel — Inline configuration form for a parameterized template.
 *
 * Appears below the template card when admin clicks "Configure".
 * 5 inputs: Schema Source, Metric Column, Metric Name, Polarity, Format Type
 * + Placement (App/Page/Tab) + SQL Preview + Create button.
 */
export default function TemplateConfigPanel({ template, apiBase, appContext, onCreated, onClose }) {
  // Data sources
  const [sources, setSources] = useState([])
  const [columns, setColumns] = useState([])
  const [apps, setApps] = useState([])
  const [pages, setPages] = useState([])

  // Config form state
  const [schemaSourceId, setSchemaSourceId] = useState(null)
  const [schemaTableName, setSchemaTableName] = useState('')
  const [metricColumn, setMetricColumn] = useState('')
  const [metricName, setMetricName] = useState('')
  const [higherIsBetter, setHigherIsBetter] = useState(true)
  const [formatType, setFormatType] = useState('number')

  // Placement
  const [appId, setAppId] = useState(appContext?.app?.id || null)
  const [pageId, setPageId] = useState(appContext?.page?.id || null)
  const [tabId, setTabId] = useState(appContext?.tab?.id || null)

  // UI state
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)

  // ── Load schema sources ──────────────────────────────────────────────
  useEffect(() => {
    designerFetch(sourcesUrl(apiBase))
      .then(setSources)
      .catch(e => console.error('Sources load failed:', e))
  }, [apiBase])

  // ── Load apps ────────────────────────────────────────────────────────
  useEffect(() => {
    designerFetch(appsUrl(apiBase))
      .then(setApps)
      .catch(e => console.error('Apps load failed:', e))
  }, [apiBase])

  // ── Load pages when app changes ──────────────────────────────────────
  useEffect(() => {
    if (!appId) { setPages([]); return }
    designerFetch(appPagesUrl(apiBase, appId))
      .then(setPages)
      .catch(e => console.error('Pages load failed:', e))
  }, [apiBase, appId])

  // ── Load columns when source changes ─────────────────────────────────
  const handleSourceChange = useCallback(async (id) => {
    setSchemaSourceId(id)
    setMetricColumn('')
    if (!id) { setColumns([]); setSchemaTableName(''); return }
    try {
      const data = await designerFetch(sourceDetailUrl(apiBase, id))
      setColumns(data.columns || [])
      setSchemaTableName(data.table_name || '')
    } catch (e) {
      console.error('Source detail failed:', e)
    }
  }, [apiBase])

  // Measure columns only
  const measureColumns = columns.filter(c => c.is_measure)

  // ── Build resolved SQL preview ───────────────────────────────────────
  const getPreviewSql = () => {
    const mapping = {
      metric_column: metricColumn || '{{metric_column}}',
      schema_table: schemaTableName || '{{schema_table}}',
      metric_name: metricName || '{{metric_name}}',
      higher_is_better: higherIsBetter ? '1' : '0',
    }
    return resolveSlots(template.sql_pattern || '', mapping)
  }

  // ── Create widget ────────────────────────────────────────────────────
  const handleCreate = async () => {
    if (!pageId) { setError('Please select a Page.'); return }
    if (!schemaSourceId) { setError('Please select a Schema Source.'); return }
    if (!metricColumn) { setError('Please select a Metric Column.'); return }
    if (!metricName) { setError('Please enter a Metric Name.'); return }

    setCreating(true)
    setError(null)
    try {
      const body = {
        page_id: pageId,
        tab_id: tabId || undefined,
        schema_source_id: schemaSourceId,
        slot_mappings: {
          metric_column: metricColumn,
          metric_name: metricName,
          schema_table: schemaTableName,
          higher_is_better: higherIsBetter ? '1' : '0',
        },
      }
      const data = await designerFetch(templateUseUrl(apiBase, template.id), {
        method: 'POST',
        body: JSON.stringify(body),
      })
      const count = (data.widget_ids || []).length
      onCreated?.({ templateName: template.name, count })
    } catch (e) {
      setError(e.message || 'Failed to create widget')
    } finally {
      setCreating(false)
    }
  }

  const selectedPage = pages.find(p => p.id === pageId)
  const tabs = selectedPage?.tabs || []
  const previewSql = getPreviewSql()
  const hasUnresolved = previewSql.includes('{{')

  return (
    <div style={{
      background: '#f8fafc', border: '1px solid #e2e8f0', borderTop: 'none',
      borderRadius: '0 0 12px 12px', padding: '24px', marginTop: -1,
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h3 style={{ margin: 0, fontSize: 16, color: '#1e293b' }}>
          <i className="fa fa-cog me-2" style={{ color: '#6366f1' }} />
          Configure: {template.name}
        </h3>
        <button type="button" className="wb-btn wb-btn--ghost wb-btn--sm" onClick={onClose}>
          <i className="fa fa-times" /> Close
        </button>
      </div>

      {error && (
        <div className="wb-preview-error mb-3">
          <i className="fa fa-exclamation-triangle me-1" /> {error}
        </div>
      )}

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>

        {/* ── Left: Data Configuration ──────────────────────────── */}
        <div>
          <h4 style={{ fontSize: 13, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
            Data Configuration
          </h4>

          {/* Schema Source */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">Schema Source *</label>
            <select
              className="wb-select"
              value={schemaSourceId || ''}
              onChange={e => handleSourceChange(parseInt(e.target.value) || null)}
            >
              <option value="">— Select data source —</option>
              {sources.map(s => (
                <option key={s.id} value={s.id}>{s.name} ({s.table_name})</option>
              ))}
            </select>
          </div>

          {/* Metric Column */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">Metric Column *</label>
            <select
              className="wb-select"
              value={metricColumn}
              onChange={e => {
                const col = e.target.value
                setMetricColumn(col)
                // Auto-fill metric name from display_name
                if (!metricName && col) {
                  const found = columns.find(c => c.column_name === col)
                  if (found) setMetricName(found.display_name || col)
                }
              }}
              disabled={!schemaSourceId}
            >
              <option value="">— Select metric column —</option>
              {measureColumns.map(c => (
                <option key={c.column_name} value={c.column_name}>
                  {c.display_name} ({c.column_name})
                </option>
              ))}
            </select>
            {schemaSourceId && measureColumns.length === 0 && (
              <small className="text-muted">No measure columns found in this source.</small>
            )}
          </div>

          {/* Metric Name */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">Metric Name *</label>
            <input
              type="text"
              className="wb-input"
              placeholder="e.g. Total Admits"
              value={metricName}
              onChange={e => setMetricName(e.target.value)}
            />
          </div>

          {/* Polarity Toggle */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">Polarity</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className={`wb-btn wb-btn--sm ${higherIsBetter ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                onClick={() => setHigherIsBetter(true)}
              >
                <i className="fa fa-arrow-up me-1" /> Higher is Better
              </button>
              <button
                type="button"
                className={`wb-btn wb-btn--sm ${!higherIsBetter ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                onClick={() => setHigherIsBetter(false)}
              >
                <i className="fa fa-arrow-down me-1" /> Lower is Better
              </button>
            </div>
            <small className="text-muted" style={{ display: 'block', marginTop: 4, fontSize: 11 }}>
              {higherIsBetter
                ? 'UP trend = Green (e.g. Revenue, Volume)'
                : 'UP trend = Red (e.g. Mortality, Infections)'}
            </small>
          </div>

          {/* Format Type */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">Format Type</label>
            <select
              className="wb-select"
              value={formatType}
              onChange={e => setFormatType(e.target.value)}
            >
              {FORMAT_TYPES.map(ft => (
                <option key={ft.value} value={ft.value}>{ft.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* ── Right: Placement + Preview ────────────────────────── */}
        <div>
          <h4 style={{ fontSize: 13, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
            Placement
          </h4>

          {/* App */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">App</label>
            <select
              className="wb-select"
              value={appId || ''}
              onChange={e => {
                setAppId(parseInt(e.target.value) || null)
                setPageId(null)
                setTabId(null)
              }}
            >
              <option value="">— Select App —</option>
              {apps.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>

          {/* Page */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">Page *</label>
            <select
              className="wb-select"
              value={pageId || ''}
              onChange={e => {
                setPageId(parseInt(e.target.value) || null)
                setTabId(null)
              }}
              disabled={!appId}
            >
              <option value="">— Select Page —</option>
              {pages.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          {/* Tab */}
          <div style={{ marginBottom: 14 }}>
            <label className="wb-label">Tab</label>
            <select
              className="wb-select"
              value={tabId || ''}
              onChange={e => setTabId(parseInt(e.target.value) || null)}
              disabled={!pageId || tabs.length === 0}
            >
              <option value="">— No tab (page-level) —</option>
              {tabs.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          {/* SQL Preview */}
          <div style={{ marginTop: 8 }}>
            <label className="wb-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>SQL Preview</span>
              {hasUnresolved && (
                <span style={{ color: '#f59e0b', fontSize: 11 }}>
                  <i className="fa fa-warning me-1" /> Unresolved placeholders
                </span>
              )}
            </label>
            <pre style={{
              padding: 12, background: '#1e293b', color: '#e2e8f0',
              borderRadius: 8, fontSize: 11, lineHeight: 1.5,
              overflow: 'auto', maxHeight: 200, whiteSpace: 'pre-wrap',
              margin: 0,
            }}>
              {previewSql || '(no SQL pattern defined on this template)'}
            </pre>
          </div>
        </div>
      </div>

      {/* ── Footer: Create button ───────────────────────────────── */}
      <div style={{
        display: 'flex', justifyContent: 'flex-end', alignItems: 'center',
        marginTop: 20, paddingTop: 16, borderTop: '1px solid #e2e8f0',
        gap: 12,
      }}>
        <button type="button" className="wb-btn wb-btn--outline" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="wb-btn wb-btn--primary"
          onClick={handleCreate}
          disabled={creating || !pageId || !schemaSourceId || !metricColumn || !metricName || hasUnresolved}
        >
          {creating ? (
            <>
              <span className="spinner-border spinner-border-sm me-1" />
              Creating...
            </>
          ) : (
            <>
              <i className="fa fa-check me-1" />
              Create Widget
            </>
          )}
        </button>
      </div>
    </div>
  )
}
