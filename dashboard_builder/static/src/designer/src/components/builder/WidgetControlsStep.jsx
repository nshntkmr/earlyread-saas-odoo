import React from 'react'

/**
 * WidgetControlsStep — Step 1 of the builder wizard.
 *
 * Lets the user define:
 * - Whether the widget has controls (scope_mode: none / independent)
 * - UI style (toggle buttons / dropdown)
 * - Search bar (enabled + placeholder)
 * - Toggle/dropdown options (label, value, icon per option)
 *
 * When options are added/removed, optionConfigs array grows/shrinks to match.
 * When scope_mode = 'none', subsequent steps work as single config (no tabs).
 */

// Factory for a new option's default config.
//
// IMPORTANT: returns a FRESH object every call so nested arrays/objects
// are NOT shared across options. Previously this was a module-level
// constant spread into new options (`{...DEFAULT_OPTION_CONFIG, ...}`).
// Only customSql was deep-copied, so every option ended up sharing the
// same `tableColumnConfig`, `sources`, `joins`, `filters`, and `aiState`
// references. That let per-tab mutations leak across tabs — e.g. a
// formatter change on the Admits tab could appear on the Therapy Share
// tab because both tabs' tableColumnConfig pointed to the same array.
function createDefaultOptionConfig() {
  return {
    dataMode: 'custom_sql',
    sources: [],
    joins: [],
    customSql: { sql: '', xColumn: '', yColumns: '', seriesColumn: '', testResult: null, testParams: {} },
    xColumn: '',
    columns: [],
    seriesColumn: '',
    orderBy: '',
    limit: '',
    filters: [],
    clickAction: 'none',
    actionPageKey: '',
    actionTabKey: '',
    actionPassValueAs: '',
    drillDetailColumns: '',
    actionUrlTemplate: '',
    tableColumnConfig: [],
    generatedSql: '',
    aiState: { prompt: '', generatedSql: '', xColumn: '', yColumns: '', explanation: '', warnings: [] },
  }
}

export default function WidgetControlsStep({
  chartType,
  scopeMode, scopeUi, scopeQueryMode, scopeParamName, scopeLabel,
  searchEnabled, searchPlaceholder,
  scopeOptions, optionConfigs,
  onUpdate,
}) {
  // Composite widgets only support parameter-mode scope — the model bans
  // scope_query_mode='query' (_check_composite_no_scope_query). Hide the
  // query-mode choice and pin the value.
  const isComposite = chartType === 'composite'
  const effectiveQueryMode = isComposite ? 'parameter' : (scopeQueryMode || 'query')
  const addOption = () => {
    const newOpt = { label: '', value: '', icon: '' }
    const newConfig = createDefaultOptionConfig()
    onUpdate({
      scopeOptions: [...(scopeOptions || []), newOpt],
      optionConfigs: [...(optionConfigs || []), newConfig],
    })
  }

  const updateOption = (idx, field, value) => {
    const updated = [...(scopeOptions || [])]
    updated[idx] = { ...updated[idx], [field]: value }
    onUpdate({ scopeOptions: updated })
  }

  const removeOption = (idx) => {
    const updatedOpts = (scopeOptions || []).filter((_, i) => i !== idx)
    const updatedConfigs = (optionConfigs || []).filter((_, i) => i !== idx)
    onUpdate({ scopeOptions: updatedOpts, optionConfigs: updatedConfigs })
  }

  return (
    <div className="wb-controls-step">
      <h3 className="wb-step-title">Widget Controls</h3>
      <p className="wb-step-hint">
        Add toggle buttons, dropdown filters, or a search bar to this widget.
        Leave as "None" if the widget doesn't need controls.
      </p>

      {/* ── Search Bar ── */}
      <div className="wb-section">
        <h4 className="wb-sub-title">Search</h4>
        <div className="wb-field-group">
          <label className="wb-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={!!searchEnabled}
              onChange={e => onUpdate({ searchEnabled: e.target.checked })}
            />
            Enable Search Bar
          </label>
          {searchEnabled && (
            <input
              className="wb-input wb-input--sm"
              placeholder="Placeholder text..."
              value={searchPlaceholder || ''}
              onChange={e => onUpdate({ searchPlaceholder: e.target.value })}
              style={{ marginTop: 4, maxWidth: 300 }}
            />
          )}
        </div>
      </div>

      {/* ── Scope Control ── */}
      <div className="wb-section" style={{ marginTop: 16 }}>
        <h4 className="wb-sub-title">Scope Control</h4>

        <div className="wb-field-group">
          <label className="wb-label">Mode</label>
          <select
            className="wb-select"
            value={scopeMode || 'none'}
            onChange={e => {
              const mode = e.target.value
              onUpdate({ scopeMode: mode })
              // When switching to independent and no options exist, add 2 defaults
              if (mode === 'independent' && (!scopeOptions || scopeOptions.length === 0)) {
                onUpdate({
                  scopeMode: mode,
                  scopeOptions: [
                    { label: 'Option 1', value: 'opt1', icon: '' },
                    { label: 'All', value: '', icon: 'fa-users' },
                  ],
                  optionConfigs: [
                    createDefaultOptionConfig(),
                    createDefaultOptionConfig(),
                  ],
                })
              }
            }}
          >
            <option value="none">None</option>
            <option value="independent">Toggle / Dropdown</option>
          </select>
        </div>

        {scopeMode === 'independent' && (
          <>
            {/* UI Style */}
            <div className="wb-field-group" style={{ marginTop: 8 }}>
              <label className="wb-label">UI Style</label>
              <select
                className="wb-select"
                value={scopeUi || 'toggle'}
                onChange={e => onUpdate({ scopeUi: e.target.value })}
              >
                <option value="toggle">Toggle Buttons</option>
                <option value="dropdown">Dropdown</option>
              </select>
            </div>

            {/* Toggle Query Mode — composite is parameter-only (model constraint) */}
            {isComposite ? (
              <p className="wb-hint" style={{ marginTop: 8, fontSize: 12, color: '#6c757d' }}>
                Composite widgets use <strong>Same SQL, Different Parameter</strong> mode:
                one scope param (e.g. <code>{'%(plan)s'}</code>) feeds the parent SQL and
                every child query. Prefer the optional-clause pattern
                {' '}<code>{'WHERE 1=1 [[AND plan = %(plan)s]]'}</code> — a blank/"all"
                option omits the clause.
              </p>
            ) : (
              <div className="wb-field-group" style={{ marginTop: 8 }}>
                <label className="wb-label">Toggle Query Mode</label>
                <select
                  className="wb-select"
                  value={scopeQueryMode || 'query'}
                  onChange={e => onUpdate({ scopeQueryMode: e.target.value })}
                >
                  <option value="query">Different SQL Per Option</option>
                  <option value="parameter">Same SQL, Different Parameter</option>
                </select>
                <p className="wb-hint" style={{ marginTop: 4, fontSize: 12, color: '#6c757d' }}>
                  {(scopeQueryMode || 'query') === 'parameter'
                    ? 'One shared SQL query with a %(param)s placeholder that changes per option.'
                    : 'Each option has its own SQL query (configured in the Data Source step).'}
                </p>
              </div>
            )}

            {/* Scope SQL Param (parameter mode only) */}
            {effectiveQueryMode === 'parameter' && (
              <div className="wb-field-group" style={{ marginTop: 8 }}>
                <label className="wb-label">Scope SQL Param</label>
                <input
                  className="wb-input wb-input--sm"
                  placeholder="e.g. ffs_ma"
                  value={scopeParamName || ''}
                  onChange={e => onUpdate({ scopeParamName: e.target.value })}
                />
                <p className="wb-hint" style={{ marginTop: 4, fontSize: 12, color: '#6c757d' }}>
                  Use <code>{'%(param_name)s'}</code> in your SQL WHERE clause.
                </p>
              </div>
            )}

            {/* Control Label (for dropdown) */}
            {scopeUi === 'dropdown' && (
              <div className="wb-field-group" style={{ marginTop: 8 }}>
                <label className="wb-label">Dropdown Label</label>
                <input
                  className="wb-input wb-input--sm"
                  placeholder="e.g. All States"
                  value={scopeLabel || ''}
                  onChange={e => onUpdate({ scopeLabel: e.target.value })}
                />
              </div>
            )}

            {/* ── Options List ── */}
            <div className="wb-field-group" style={{ marginTop: 12 }}>
              <label className="wb-label">Options</label>

              {(scopeOptions || []).map((opt, idx) => (
                <div key={idx} className="wb-scope-option">
                  <div className="wb-scope-option-header">
                    <span className="wb-scope-option-num">{idx + 1}</span>
                    <input
                      className="wb-input wb-input--sm"
                      placeholder="Label (e.g. Hospitals)"
                      value={opt.label || ''}
                      onChange={e => updateOption(idx, 'label', e.target.value)}
                      style={{ flex: 2 }}
                    />
                    <input
                      className="wb-input wb-input--xs"
                      placeholder="Value (empty=All)"
                      value={opt.value || ''}
                      onChange={e => updateOption(idx, 'value', e.target.value)}
                      style={{ flex: 1 }}
                    />
                    <input
                      className="wb-input wb-input--xs"
                      placeholder="fa-icon"
                      value={opt.icon || ''}
                      onChange={e => updateOption(idx, 'icon', e.target.value)}
                      style={{ flex: 1 }}
                    />
                    <button
                      className="wb-btn-icon"
                      onClick={() => removeOption(idx)}
                      type="button"
                      title="Remove option"
                      disabled={(scopeOptions || []).length <= 1}
                    >
                      <i className="fa fa-trash-o" />
                    </button>
                  </div>
                </div>
              ))}

              <button
                className="wb-btn wb-btn--outline wb-btn--sm"
                onClick={addOption}
                type="button"
                style={{ marginTop: 6 }}
              >
                <i className="fa fa-plus me-1" /> Add Option
              </button>
            </div>

            <p className="wb-hint" style={{ marginTop: 8 }}>
              Each option will have its own Data Source, Columns, Filters & Actions configuration
              in the following steps. Use the option tabs at the top of each step to switch between them.
            </p>
          </>
        )}
      </div>
    </div>
  )
}

export { createDefaultOptionConfig }
