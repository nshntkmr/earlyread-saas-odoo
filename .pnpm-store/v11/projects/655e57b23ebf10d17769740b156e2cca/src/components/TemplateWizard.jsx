import React, { useReducer, useState, useCallback, useEffect } from 'react'
import { designerFetch } from '../api/client'
import { sourcesUrl, sourceDetailUrl, templateUseUrl, appsUrl, appPagesUrl } from '../api/endpoints'

// ── Steps ────────────────────────────────────────────────────────────────────
const STEPS = [
  { key: 'source',    label: 'Schema Source' },
  { key: 'columns',   label: 'Column Mapping' },
  { key: 'placement', label: 'Placement' },
  { key: 'preview',   label: 'Preview & Create' },
]

// ── State ────────────────────────────────────────────────────────────────────
const initialState = {
  step: 0,
  schemaSourceId: null,
  schemaSourceName: '',
  columns: [],         // [{column_name, display_name, data_type, is_measure, is_dimension}]
  slotValues: {},      // {slot_name: value}
  instances: [],       // [{slot_name: value, ...}]
  // Placement
  appId: null,
  pageId: null,
  tabId: null,
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_STEP':     return { ...state, step: action.step }
    case 'NEXT':         return { ...state, step: Math.min(state.step + 1, STEPS.length - 1) }
    case 'PREV':         return { ...state, step: Math.max(state.step - 1, 0) }
    case 'SET_SOURCE':   return { ...state, ...action.value }
    case 'SET_SLOT':     return { ...state, slotValues: { ...state.slotValues, [action.key]: action.value } }
    case 'SET_INSTANCES':return { ...state, instances: action.value }
    case 'SET_INSTANCE_SLOT': {
      const instances = [...state.instances]
      instances[action.idx] = { ...instances[action.idx], [action.key]: action.value }
      return { ...state, instances }
    }
    case 'ADD_INSTANCE': return { ...state, instances: [...state.instances, {}] }
    case 'REMOVE_INSTANCE': {
      const instances = state.instances.filter((_, i) => i !== action.idx)
      return { ...state, instances }
    }
    case 'SET_PLACEMENT': return { ...state, ...action.value }
    case 'RESET':        return { ...initialState }
    default:             return state
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Replace {{slot}} in text with values from a mapping */
function resolveSlots(text, mapping) {
  if (!text) return ''
  return text.replace(/\{\{(\w+)\}\}/g, (match, key) => {
    return key in mapping ? mapping[key] : match
  })
}

/** Filter columns based on slot's column_filter */
function filterColumns(columns, columnFilter) {
  if (!columnFilter || columnFilter === 'any') return columns
  if (columnFilter === 'measure') return columns.filter(c => c.is_measure)
  if (columnFilter === 'dimension') return columns.filter(c => c.is_dimension)
  return columns
}

// ═════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═════════════════════════════════════════════════════════════════════════════

export default function TemplateWizard({ template, apiBase, appContext, onClose, onComplete }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [sources, setSources] = useState([])
  const [apps, setApps] = useState([])
  const [pages, setPages] = useState([])
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  const slots = template.slots || []
  const isMultiInstance = (template.multi_instance_configs || []).length > 0

  // ── Load sources on mount ────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const data = await designerFetch(sourcesUrl(apiBase))
        setSources(data)
      } catch (e) { console.error('Failed to load sources:', e) }
    }
    load()
  }, [apiBase])

  // ── Load apps ────────────────────────────────────────────────────────
  useEffect(() => {
    const load = async () => {
      try {
        const data = await designerFetch(appsUrl(apiBase))
        setApps(data)
      } catch (e) { console.error('Failed to load apps:', e) }
    }
    load()
  }, [apiBase])

  // ── Pre-fill placement from appContext ────────────────────────────────
  useEffect(() => {
    if (appContext) {
      dispatch({
        type: 'SET_PLACEMENT',
        value: {
          appId: appContext.app?.id || null,
          pageId: appContext.page?.id || null,
          tabId: appContext.tab?.id || null,
        },
      })
    }
  }, [appContext])

  // ── Load pages when app changes ──────────────────────────────────────
  useEffect(() => {
    if (!state.appId) { setPages([]); return }
    const load = async () => {
      try {
        const data = await designerFetch(appPagesUrl(apiBase, state.appId))
        setPages(data)
      } catch (e) { console.error('Failed to load pages:', e) }
    }
    load()
  }, [apiBase, state.appId])

  // ── Pre-fill instances from template ─────────────────────────────────
  useEffect(() => {
    if (isMultiInstance && state.instances.length === 0) {
      dispatch({ type: 'SET_INSTANCES', value: [...template.multi_instance_configs] })
    }
  }, [template])

  // ── Fetch columns when source is selected ────────────────────────────
  const handleSourceSelect = useCallback(async (sourceId) => {
    if (!sourceId) return
    try {
      const data = await designerFetch(sourceDetailUrl(apiBase, sourceId))
      dispatch({
        type: 'SET_SOURCE',
        value: {
          schemaSourceId: sourceId,
          schemaSourceName: data.name || '',
          columns: data.columns || [],
        },
      })
    } catch (e) {
      console.error('Failed to load source detail:', e)
    }
  }, [apiBase])

  // ── Create widgets ───────────────────────────────────────────────────
  const handleCreate = useCallback(async () => {
    if (!state.pageId) { setError('Please select a page.'); return }

    setCreating(true)
    setError(null)
    try {
      const body = {
        page_id: state.pageId,
        tab_id: state.tabId || undefined,
        schema_source_id: state.schemaSourceId,
        slot_mappings: state.slotValues,
      }
      if (isMultiInstance && state.instances.length > 0) {
        body.instances = state.instances
      }

      const data = await designerFetch(templateUseUrl(apiBase, template.id), {
        method: 'POST',
        body: JSON.stringify(body),
      })

      const count = (data.widget_ids || []).length
      setSuccess(`Created ${count} widget${count !== 1 ? 's' : ''} from "${template.name}"`)

      // After 1.5s, go back to library
      setTimeout(() => {
        onComplete?.()
      }, 1500)
    } catch (e) {
      setError(e.message || 'Failed to create widgets')
    } finally {
      setCreating(false)
    }
  }, [state, template, apiBase, isMultiInstance, onComplete])

  // ── Resolve SQL preview ──────────────────────────────────────────────
  const getPreviewSql = () => {
    // For multi-instance, show first instance's SQL
    const mapping = isMultiInstance && state.instances.length > 0
      ? { ...state.slotValues, ...state.instances[0] }
      : { ...state.slotValues }
    if (state.schemaSourceName) {
      // Find the source table_name
      const src = sources.find(s => s.id === state.schemaSourceId)
      if (src) mapping.schema_table = src.table_name
    }
    return resolveSlots(template.sql_pattern || '', mapping)
  }

  const getPreviewTitle = () => {
    const mapping = isMultiInstance && state.instances.length > 0
      ? { ...state.slotValues, ...state.instances[0] }
      : { ...state.slotValues }
    return resolveSlots(template.title_pattern || '', mapping)
  }

  // ── Render ───────────────────────────────────────────────────────────
  const currentStep = STEPS[state.step]
  const selectedPage = pages.find(p => p.id === state.pageId)
  const tabs = selectedPage?.tabs || []

  return (
    <div className="dd-page">
      <div className="dd-wizard">
        {/* Header */}
        <div className="dd-wizard-header">
          <div className="dd-wizard-header-left">
            <div className="dd-wizard-icon">
              <i className="fa fa-magic" />
            </div>
            <div>
              <h2 className="dd-wizard-title">Use Template: {template.name}</h2>
              <p className="dd-wizard-subtitle">
                Step {state.step + 1} of {STEPS.length} &mdash; {currentStep.label}
              </p>
            </div>
          </div>
          <button type="button" className="wb-btn wb-btn--ghost" onClick={onClose}>
            <i className="fa fa-times" />
          </button>
        </div>

        {/* Step tabs */}
        <div className="dd-wizard-tabs">
          {STEPS.map((s, i) => (
            <button
              key={s.key}
              type="button"
              className={`dd-wizard-tab ${i === state.step ? 'dd-wizard-tab--active' : ''} ${i < state.step ? 'dd-wizard-tab--done' : ''}`}
              onClick={() => dispatch({ type: 'SET_STEP', step: i })}
            >
              {i < state.step && <i className="fa fa-check me-1" style={{ color: '#28a745' }} />}
              {s.label}
            </button>
          ))}
        </div>

        {/* Instruction */}
        <div className="dd-wizard-instruction">
          {state.step === 0 && 'Select the materialized view (data source) this widget will query.'}
          {state.step === 1 && 'Map columns from the data source to the template\'s slots.'}
          {state.step === 2 && 'Choose where to place the generated widget(s).'}
          {state.step === 3 && 'Review the generated SQL and create the widgets.'}
        </div>

        {/* Body */}
        <div className="dd-wizard-body">
          {error && (
            <div className="wb-preview-error mb-3">
              <i className="fa fa-exclamation-triangle me-1" />
              {error}
              <button type="button" className="ms-2" style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setError(null)}>
                <i className="fa fa-times" />
              </button>
            </div>
          )}
          {success && (
            <div className="dd-result-banner dd-result-banner--success">
              <i className="fa fa-check-circle me-2" />
              {success}
            </div>
          )}

          {/* ── Step 1: Schema Source ──────────────────────────────── */}
          {state.step === 0 && (
            <div>
              <h3 className="wb-step-title">Schema Source</h3>
              <div className="wb-field-group">
                <label className="wb-label">Materialized View / Table</label>
                <select
                  className="wb-select"
                  value={state.schemaSourceId || ''}
                  onChange={e => {
                    const id = parseInt(e.target.value) || null
                    if (id) handleSourceSelect(id)
                  }}
                >
                  <option value="">— Select a data source —</option>
                  {sources.map(s => (
                    <option key={s.id} value={s.id}>{s.name} ({s.table_name})</option>
                  ))}
                </select>
              </div>

              {state.columns.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4 className="wb-step-title" style={{ fontSize: 14 }}>
                    Available Columns ({state.columns.length})
                  </h4>
                  <div style={{ maxHeight: 300, overflow: 'auto', border: '1px solid #e5e7eb', borderRadius: 8 }}>
                    <table className="wb-preview-table" style={{ width: '100%', fontSize: 13 }}>
                      <thead>
                        <tr>
                          <th style={{ padding: '8px 12px' }}>Column</th>
                          <th style={{ padding: '8px 12px' }}>Display Name</th>
                          <th style={{ padding: '8px 12px' }}>Type</th>
                          <th style={{ padding: '8px 12px' }}>Role</th>
                        </tr>
                      </thead>
                      <tbody>
                        {state.columns.map(c => (
                          <tr key={c.column_name}>
                            <td style={{ padding: '6px 12px', fontFamily: 'monospace' }}>{c.column_name}</td>
                            <td style={{ padding: '6px 12px' }}>{c.display_name}</td>
                            <td style={{ padding: '6px 12px' }}>
                              <span className="dd-badge dd-badge--type">{c.data_type}</span>
                            </td>
                            <td style={{ padding: '6px 12px' }}>
                              {c.is_measure && <span className="dd-badge dd-badge--cat" style={{ marginRight: 4 }}>Measure</span>}
                              {c.is_dimension && <span className="dd-badge dd-badge--cat">Dimension</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Step 2: Column Mapping ────────────────────────────── */}
          {state.step === 1 && (
            <div>
              <h3 className="wb-step-title">Column Mapping</h3>

              {!isMultiInstance ? (
                /* Single-instance: simple slot form */
                <div className="wb-field-group">
                  {slots.map(slot => (
                    <div key={slot.slot_name} style={{ marginBottom: 12 }}>
                      <label className="wb-label">
                        {slot.label}
                        {slot.required && <span style={{ color: '#dc3545' }}> *</span>}
                        {slot.help_text && (
                          <span className="text-muted ms-2" style={{ fontSize: 12 }}>({slot.help_text})</span>
                        )}
                      </label>
                      {slot.slot_type === 'column' ? (
                        <select
                          className="wb-select"
                          value={state.slotValues[slot.slot_name] || slot.default_value || ''}
                          onChange={e => dispatch({ type: 'SET_SLOT', key: slot.slot_name, value: e.target.value })}
                        >
                          <option value="">— Select column —</option>
                          {filterColumns(state.columns, slot.column_filter).map(c => (
                            <option key={c.column_name} value={c.column_name}>
                              {c.display_name} ({c.column_name})
                            </option>
                          ))}
                        </select>
                      ) : slot.slot_type === 'number' ? (
                        <input
                          type="number"
                          className="wb-input"
                          value={state.slotValues[slot.slot_name] || slot.default_value || ''}
                          onChange={e => dispatch({ type: 'SET_SLOT', key: slot.slot_name, value: e.target.value })}
                        />
                      ) : (
                        <input
                          type="text"
                          className="wb-input"
                          placeholder={slot.default_value || ''}
                          value={state.slotValues[slot.slot_name] || ''}
                          onChange={e => dispatch({ type: 'SET_SLOT', key: slot.slot_name, value: e.target.value })}
                        />
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                /* Multi-instance: editable table */
                <div>
                  <p className="text-muted mb-2">
                    This template creates <strong>{state.instances.length}</strong> widget{state.instances.length !== 1 ? 's' : ''}.
                    Each row becomes one widget.
                  </p>
                  <div style={{ overflow: 'auto', border: '1px solid #e5e7eb', borderRadius: 8 }}>
                    <table className="wb-preview-table" style={{ width: '100%', fontSize: 13 }}>
                      <thead>
                        <tr>
                          <th style={{ padding: '8px 12px', width: 40 }}>#</th>
                          {slots.map(slot => (
                            <th key={slot.slot_name} style={{ padding: '8px 12px' }}>
                              {slot.label}
                              {slot.required && <span style={{ color: '#dc3545' }}> *</span>}
                            </th>
                          ))}
                          <th style={{ padding: '8px 12px', width: 60 }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {state.instances.map((inst, idx) => (
                          <tr key={idx}>
                            <td style={{ padding: '6px 12px', textAlign: 'center', color: '#6b7280' }}>{idx + 1}</td>
                            {slots.map(slot => (
                              <td key={slot.slot_name} style={{ padding: '4px 8px' }}>
                                {slot.slot_type === 'column' ? (
                                  <select
                                    className="wb-select"
                                    style={{ fontSize: 12, padding: '4px 8px' }}
                                    value={inst[slot.slot_name] || slot.default_value || ''}
                                    onChange={e => dispatch({
                                      type: 'SET_INSTANCE_SLOT',
                                      idx, key: slot.slot_name, value: e.target.value,
                                    })}
                                  >
                                    <option value="">—</option>
                                    {filterColumns(state.columns, slot.column_filter).map(c => (
                                      <option key={c.column_name} value={c.column_name}>
                                        {c.display_name} ({c.column_name})
                                      </option>
                                    ))}
                                  </select>
                                ) : (
                                  <input
                                    type={slot.slot_type === 'number' ? 'number' : 'text'}
                                    className="wb-input"
                                    style={{ fontSize: 12, padding: '4px 8px' }}
                                    value={inst[slot.slot_name] || ''}
                                    onChange={e => dispatch({
                                      type: 'SET_INSTANCE_SLOT',
                                      idx, key: slot.slot_name, value: e.target.value,
                                    })}
                                  />
                                )}
                              </td>
                            ))}
                            <td style={{ padding: '4px 8px', textAlign: 'center' }}>
                              <button
                                type="button"
                                className="wb-btn wb-btn--ghost wb-btn--sm"
                                onClick={() => dispatch({ type: 'REMOVE_INSTANCE', idx })}
                                title="Remove row"
                              >
                                <i className="fa fa-trash-o" style={{ color: '#dc3545' }} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <button
                    type="button"
                    className="wb-btn wb-btn--outline wb-btn--sm mt-2"
                    onClick={() => dispatch({ type: 'ADD_INSTANCE' })}
                  >
                    <i className="fa fa-plus me-1" /> Add Widget
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Step 3: Placement ─────────────────────────────────── */}
          {state.step === 2 && (
            <div>
              <h3 className="wb-step-title">Placement</h3>
              <div className="wb-field-group">
                <label className="wb-label">App</label>
                <select
                  className="wb-select"
                  value={state.appId || ''}
                  onChange={e => {
                    const id = parseInt(e.target.value) || null
                    dispatch({ type: 'SET_PLACEMENT', value: { appId: id, pageId: null, tabId: null } })
                  }}
                >
                  <option value="">— Select App —</option>
                  {apps.map(a => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>

              <div className="wb-field-group">
                <label className="wb-label">Page <span style={{ color: '#dc3545' }}>*</span></label>
                <select
                  className="wb-select"
                  value={state.pageId || ''}
                  onChange={e => {
                    const id = parseInt(e.target.value) || null
                    dispatch({ type: 'SET_PLACEMENT', value: { pageId: id, tabId: null } })
                  }}
                  disabled={!state.appId}
                >
                  <option value="">— Select Page —</option>
                  {pages.map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>

              <div className="wb-field-group">
                <label className="wb-label">Tab (optional)</label>
                <select
                  className="wb-select"
                  value={state.tabId || ''}
                  onChange={e => dispatch({ type: 'SET_PLACEMENT', value: { tabId: parseInt(e.target.value) || null } })}
                  disabled={!state.pageId || tabs.length === 0}
                >
                  <option value="">— No tab (page-level) —</option>
                  {tabs.map(t => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>

              <div style={{ marginTop: 24, padding: 16, background: '#f0f9ff', borderRadius: 8, border: '1px solid #bae6fd' }}>
                <h4 style={{ margin: 0, fontSize: 14, color: '#0369a1' }}>
                  <i className="fa fa-info-circle me-1" /> Summary
                </h4>
                <p style={{ margin: '8px 0 0', fontSize: 13, color: '#374151' }}>
                  <strong>Template:</strong> {template.name}<br/>
                  <strong>Chart type:</strong> {template.chart_type}<br/>
                  <strong>Creates:</strong> {isMultiInstance ? state.instances.length : 1} widget{(isMultiInstance ? state.instances.length : 1) !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
          )}

          {/* ── Step 4: Preview & Create ──────────────────────────── */}
          {state.step === 3 && (
            <div>
              <h3 className="wb-step-title">Preview & Create</h3>

              {/* Title preview */}
              <div className="wb-field-group">
                <label className="wb-label">Widget Title (first instance)</label>
                <div style={{ padding: '8px 12px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 6, fontSize: 14, fontWeight: 600 }}>
                  {getPreviewTitle() || '(no title)'}
                </div>
              </div>

              {/* SQL preview */}
              <div className="wb-field-group">
                <label className="wb-label">Generated SQL (first instance)</label>
                <pre style={{
                  padding: 16, background: '#1e293b', color: '#e2e8f0',
                  borderRadius: 8, fontSize: 12, lineHeight: 1.6,
                  overflow: 'auto', maxHeight: 400, whiteSpace: 'pre-wrap',
                }}>
                  {getPreviewSql() || '(no SQL pattern)'}
                </pre>
              </div>

              {/* Unresolved check */}
              {getPreviewSql().includes('{{') && (
                <div className="wb-preview-error mb-3">
                  <i className="fa fa-exclamation-triangle me-1" />
                  Some <code>{'{{slot}}'}</code> placeholders are still unresolved.
                  Go back to Column Mapping to fill them in.
                </div>
              )}

              {/* Create button */}
              <div style={{ textAlign: 'center', marginTop: 24 }}>
                <p className="text-muted mb-2" style={{ fontSize: 13 }}>
                  <i className="fa fa-info-circle me-1" />
                  After saving, you can place this widget on any app's dashboard.
                </p>
                <button
                  type="button"
                  className="wb-btn wb-btn--primary"
                  style={{ padding: '12px 32px', fontSize: 16 }}
                  onClick={handleCreate}
                  disabled={creating || !state.pageId || getPreviewSql().includes('{{')}
                >
                  {creating ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <i className="fa fa-check me-2" />
                      Create {isMultiInstance ? state.instances.length : 1} Widget{(isMultiInstance ? state.instances.length : 1) !== 1 ? 's' : ''}
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Footer navigation */}
        <div className="dd-wizard-footer">
          <button
            type="button"
            className="dd-wizard-btn dd-wizard-btn--outline"
            onClick={() => state.step === 0 ? onClose() : dispatch({ type: 'PREV' })}
          >
            {state.step === 0 ? 'Cancel' : '← Previous'}
          </button>
          <div className="dd-wizard-dots">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`dd-wizard-dot ${i === state.step ? 'dd-wizard-dot--active' : ''}`}
              />
            ))}
          </div>
          {state.step < STEPS.length - 1 && (
            <button
              type="button"
              className="dd-wizard-btn dd-wizard-btn--primary"
              onClick={() => dispatch({ type: 'NEXT' })}
              disabled={state.step === 0 && !state.schemaSourceId}
            >
              Next →
            </button>
          )}
          {state.step === STEPS.length - 1 && (
            <div style={{ width: 100 }} /> /* spacer */
          )}
        </div>
      </div>
    </div>
  )
}
