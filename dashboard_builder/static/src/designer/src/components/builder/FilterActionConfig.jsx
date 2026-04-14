import React, { useState } from 'react'

const CLICK_ACTIONS = [
  { key: 'none',         label: 'No action',           icon: 'fa-ban' },
  { key: 'filter_page',  label: 'Filter this page',    icon: 'fa-filter' },
  { key: 'go_to_page',   label: 'Go to another page',  icon: 'fa-external-link' },
  { key: 'show_details', label: 'Show detail table',   icon: 'fa-table' },
  { key: 'open_url',     label: 'Open URL',            icon: 'fa-link' },
]

const FILTER_OPS = ['=', '!=', '>', '<', '>=', '<=', 'IN', 'NOT IN', 'LIKE', 'ILIKE']

/**
 * Step 4: Filters (visual mode) + Click actions (both modes).
 *
 * Designer version — no pages endpoint (placement is done via AppPagePicker).
 * The go_to_page action fields are free-text in designer since apps/pages
 * are resolved at placement time.
 *
 * Props:
 *   dataSourceMode  — 'visual' or 'custom_sql'
 *   sources         — selected sources (for visual mode WHERE builder)
 *   filters         — [{source_id, column, op, param}]
 *   clickAction     — string
 *   actionPageKey   — string
 *   actionTabKey    — string
 *   actionPassValueAs — string
 *   drillDetailColumns — string
 *   actionUrlTemplate — string
 *   onUpdate        — (updates) => void
 *   apiBase         — string
 */
export default function FilterActionConfig({
  dataSourceMode, sources, filters,
  clickAction, actionPageKey, actionTabKey, actionPassValueAs,
  drillDetailColumns, actionUrlTemplate,
  // Widget-Scoped Controls (optional)
  scopeMode, scopeUi, scopeQueryMode, scopeParamName,
  scopeLabel, scopeDefaultValue, scopeOptions,
  searchEnabled, searchPlaceholder,
  chartType,
  onUpdate, apiBase,
}) {
  // Flatten filterable columns
  const filterableCols = (sources || []).flatMap(src =>
    (src.columns || []).filter(c => c.is_filterable)
      .map(c => ({ ...c, source_id: src.id, source_name: src.name }))
  )

  const addFilter = () => {
    onUpdate({
      filters: [...(filters || []),
        { source_id: sources?.[0]?.id || null, column: '', op: '=', param: '' }
      ],
    })
  }

  const updateFilter = (idx, updates) => {
    const list = [...(filters || [])]
    list[idx] = { ...list[idx], ...updates }
    onUpdate({ filters: list })
  }

  const removeFilter = (idx) => {
    onUpdate({ filters: (filters || []).filter((_, i) => i !== idx) })
  }

  return (
    <div>
      <h3 className="wb-step-title">Filters & Actions</h3>

      {/* WHERE conditions (visual mode only) */}
      {dataSourceMode === 'visual' && (
        <div className="wb-section">
          <h4 className="wb-sub-title">WHERE Conditions</h4>
          {(filters || []).map((f, idx) => (
            <div key={idx} className="wb-filter-row">
              <select
                className="wb-select wb-select--sm"
                value={f.source_id && f.column ? `${f.source_id}:${f.column}` : ''}
                onChange={e => {
                  if (!e.target.value) return
                  const [sid, cname] = e.target.value.split(':')
                  updateFilter(idx, { source_id: Number(sid), column: cname, param: cname })
                }}
              >
                <option value="">-- Column --</option>
                {filterableCols.map(c => (
                  <option key={`${c.source_id}:${c.column_name}`} value={`${c.source_id}:${c.column_name}`}>
                    {c.display_name} ({c.column_name})
                  </option>
                ))}
              </select>

              <select
                className="wb-select wb-select--xs"
                value={f.op || '='}
                onChange={e => updateFilter(idx, { op: e.target.value })}
              >
                {FILTER_OPS.map(op => <option key={op} value={op}>{op}</option>)}
              </select>

              <input
                type="text"
                className="wb-input wb-input--sm"
                value={f.param || ''}
                onChange={e => updateFilter(idx, { param: e.target.value })}
                placeholder="param name"
              />

              <button type="button" className="wb-btn-icon" onClick={() => removeFilter(idx)}>
                <i className="fa fa-trash" />
              </button>
            </div>
          ))}

          <button type="button" className="wb-btn wb-btn--outline" onClick={addFilter}>
            <i className="fa fa-plus" /> Add Condition
          </button>
        </div>
      )}

      {/* Click Action */}
      <div className="wb-section">
        <h4 className="wb-sub-title">Click Action</h4>
        <div className="wb-action-radio">
          {CLICK_ACTIONS.map(a => (
            <label key={a.key} className={`wb-action-option ${clickAction === a.key ? 'wb-action-option--active' : ''}`}>
              <input
                type="radio"
                name="click_action"
                value={a.key}
                checked={clickAction === a.key}
                onChange={() => onUpdate({ clickAction: a.key })}
              />
              <i className={`fa ${a.icon}`} />
              <span>{a.label}</span>
            </label>
          ))}
        </div>

        {/* go_to_page config */}
        {clickAction === 'go_to_page' && (
          <div className="wb-action-config">
            <div className="wb-field-group">
              <label className="wb-label">Target Page Key</label>
              <input
                type="text"
                className="wb-input"
                value={actionPageKey || ''}
                onChange={e => onUpdate({ actionPageKey: e.target.value })}
                placeholder="e.g. overview"
              />
            </div>
            <div className="wb-field-group">
              <label className="wb-label">Pass clicked value as (filter param)</label>
              <input
                type="text"
                className="wb-input"
                value={actionPassValueAs || ''}
                onChange={e => onUpdate({ actionPassValueAs: e.target.value })}
                placeholder="e.g. hha_state"
              />
            </div>
            <div className="wb-field-group">
              <label className="wb-label">Target Tab Key (optional)</label>
              <input
                type="text"
                className="wb-input"
                value={actionTabKey || ''}
                onChange={e => onUpdate({ actionTabKey: e.target.value })}
                placeholder="e.g. overview"
              />
            </div>
          </div>
        )}

        {/* show_details config */}
        {clickAction === 'show_details' && (
          <div className="wb-action-config">
            <div className="wb-field-group">
              <label className="wb-label">Detail Columns (comma-separated, empty = all)</label>
              <input
                type="text"
                className="wb-input"
                value={drillDetailColumns || ''}
                onChange={e => onUpdate({ drillDetailColumns: e.target.value })}
                placeholder="e.g. hha_name, hha_state, total_admits"
              />
            </div>
          </div>
        )}

        {/* open_url config */}
        {clickAction === 'open_url' && (
          <div className="wb-action-config">
            <div className="wb-field-group">
              <label className="wb-label">URL Template</label>
              <input
                type="text"
                className="wb-input"
                value={actionUrlTemplate || ''}
                onChange={e => onUpdate({ actionUrlTemplate: e.target.value })}
                placeholder="/my/posterra/hha/{value}"
              />
              <p className="wb-hint">{'{value}'} will be replaced with the clicked value.</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Widget Controls (Optional) ─────────────────────────────────── */}
      <WidgetControlsSection
        scopeMode={scopeMode}
        scopeUi={scopeUi}
        scopeQueryMode={scopeQueryMode}
        scopeParamName={scopeParamName}
        scopeLabel={scopeLabel}
        scopeDefaultValue={scopeDefaultValue}
        scopeOptions={scopeOptions}
        searchEnabled={searchEnabled}
        searchPlaceholder={searchPlaceholder}
        chartType={chartType}
        sources={sources}
        onUpdate={onUpdate}
        apiBase={apiBase}
      />
    </div>
  )
}

// ── Widget Controls Collapsible Section ───────────────────────────────────────

function WidgetControlsSection({
  scopeMode, scopeUi, scopeQueryMode, scopeParamName,
  scopeLabel, scopeDefaultValue, scopeOptions,
  searchEnabled, searchPlaceholder, chartType,
  sources, onUpdate, apiBase,
}) {
  const [showControls, setShowControls] = useState(
    !!(scopeMode && scopeMode !== 'none') || !!searchEnabled
  )

  const updateScopeOption = (idx, field, value) => {
    const updated = [...(scopeOptions || [])]
    updated[idx] = { ...updated[idx], [field]: value }
    onUpdate({ scopeOptions: updated })
  }

  const removeScopeOption = (idx) => {
    const updated = (scopeOptions || []).filter((_, i) => i !== idx)
    onUpdate({ scopeOptions: updated })
  }

  const addScopeOption = () => {
    const updated = [...(scopeOptions || []), { label: '', value: '', icon: '', sql: '' }]
    onUpdate({ scopeOptions: updated })
  }

  return (
    <div className="wb-section" style={{ marginTop: 16 }}>
      <button
        className="wb-section-toggle"
        onClick={() => setShowControls(!showControls)}
        type="button"
      >
        <i className={`fa fa-chevron-${showControls ? 'down' : 'right'} me-2`} />
        Widget Controls (Optional)
      </button>

      {showControls && (
        <div className="wb-section-body">

          {/* ── Search ── */}
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
                placeholder="Search placeholder text..."
                value={searchPlaceholder || ''}
                onChange={e => onUpdate({ searchPlaceholder: e.target.value })}
                style={{ marginTop: 4 }}
              />
            )}
          </div>

          {/* ── Scope Control ── */}
          <div className="wb-field-group" style={{ marginTop: 12 }}>
            <label className="wb-label">Scope Control</label>
            <select
              className="wb-select"
              value={scopeMode || 'none'}
              onChange={e => onUpdate({ scopeMode: e.target.value })}
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

              {/* Query Mode */}
              <div className="wb-field-group" style={{ marginTop: 8 }}>
                <label className="wb-label">Query Mode</label>
                <select
                  className="wb-select"
                  value={scopeQueryMode || 'parameter'}
                  onChange={e => onUpdate({ scopeQueryMode: e.target.value })}
                >
                  <option value="parameter">Same SQL, Different Parameter</option>
                  <option value="query">Different SQL Per Option</option>
                </select>
              </div>

              {/* SQL Param Name (parameter mode only) */}
              {scopeQueryMode !== 'query' && (
                <div className="wb-field-group" style={{ marginTop: 8 }}>
                  <label className="wb-label">SQL Param Name</label>
                  <input
                    className="wb-input wb-input--sm"
                    placeholder="e.g. source_type"
                    value={scopeParamName || ''}
                    onChange={e => onUpdate({ scopeParamName: e.target.value })}
                  />
                  <p className="wb-hint">
                    Use [[AND col = %%(param_name)s]] in your SQL. Clause removed when "All" selected.
                  </p>
                </div>
              )}

              {/* Control Label */}
              <div className="wb-field-group" style={{ marginTop: 8 }}>
                <label className="wb-label">Control Label</label>
                <input
                  className="wb-input wb-input--sm"
                  placeholder="e.g. All States"
                  value={scopeLabel || ''}
                  onChange={e => onUpdate({ scopeLabel: e.target.value })}
                />
              </div>

              {/* ── Scope Options ── */}
              <div className="wb-field-group" style={{ marginTop: 12 }}>
                <label className="wb-label">Options</label>

                {(scopeOptions || []).map((opt, idx) => (
                  <div key={idx} className="wb-scope-option">
                    <div className="wb-scope-option-header">
                      <input
                        className="wb-input wb-input--sm"
                        placeholder="Label (e.g. Hospitals)"
                        value={opt.label || ''}
                        onChange={e => updateScopeOption(idx, 'label', e.target.value)}
                        style={{ flex: 2 }}
                      />
                      <input
                        className="wb-input wb-input--xs"
                        placeholder="Value (empty=All)"
                        value={opt.value || ''}
                        onChange={e => updateScopeOption(idx, 'value', e.target.value)}
                        style={{ flex: 1 }}
                      />
                      <input
                        className="wb-input wb-input--xs"
                        placeholder="fa-icon"
                        value={opt.icon || ''}
                        onChange={e => updateScopeOption(idx, 'icon', e.target.value)}
                        style={{ flex: 1 }}
                      />
                      <button
                        className="wb-btn-icon"
                        onClick={() => removeScopeOption(idx)}
                        type="button"
                        title="Remove option"
                      >
                        <i className="fa fa-trash-o" />
                      </button>
                    </div>

                    {/* Query mode: SQL editor per option */}
                    {scopeQueryMode === 'query' && (
                      <div className="wb-scope-option-sql">
                        <label className="wb-label" style={{ fontSize: 11 }}>
                          SQL Query for "{opt.label || `Option ${idx + 1}`}"
                        </label>
                        <textarea
                          className="wb-input"
                          rows={4}
                          placeholder="SELECT ... FROM ... WHERE {where_clause}"
                          value={opt.sql || opt.query_sql || ''}
                          onChange={e => updateScopeOption(idx, 'sql', e.target.value)}
                          style={{ fontFamily: 'monospace', fontSize: 12 }}
                        />
                        <p className="wb-hint" style={{ marginTop: 2 }}>
                          Leave empty to use the widget's main SQL. Use %%(param)s for filter values.
                        </p>

                        {/* Per-option column config: chart types get x/y/series, table gets JSON config */}
                        {chartType === 'table' ? (
                          <div style={{ marginTop: 8 }}>
                            <label className="wb-label" style={{ fontSize: 11 }}>
                              Table Column Config (JSON)
                            </label>
                            <textarea
                              className="wb-input"
                              rows={3}
                              placeholder='[{"field":"name","headerName":"Name","width":200},{"field":"admits","headerName":"Admits","width":100}]'
                              value={opt.tableColumnConfig ? (typeof opt.tableColumnConfig === 'string' ? opt.tableColumnConfig : JSON.stringify(opt.tableColumnConfig, null, 2)) : ''}
                              onChange={e => {
                                try {
                                  const parsed = JSON.parse(e.target.value)
                                  updateScopeOption(idx, 'tableColumnConfig', parsed)
                                } catch {
                                  updateScopeOption(idx, 'tableColumnConfig', e.target.value)
                                }
                              }}
                              style={{ fontFamily: 'monospace', fontSize: 11 }}
                            />
                            <p className="wb-hint">
                              AG Grid column definitions. Use the full TableConfigurator for complex setups, then copy the JSON here.
                            </p>
                          </div>
                        ) : (
                          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                            <div style={{ flex: 1 }}>
                              <label className="wb-label" style={{ fontSize: 11 }}>X Column</label>
                              <input
                                className="wb-input wb-input--sm"
                                placeholder="e.g. hha_state_cd"
                                value={opt.xColumn || ''}
                                onChange={e => updateScopeOption(idx, 'xColumn', e.target.value)}
                              />
                            </div>
                            <div style={{ flex: 1 }}>
                              <label className="wb-label" style={{ fontSize: 11 }}>Y Column(s)</label>
                              <input
                                className="wb-input wb-input--sm"
                                placeholder="e.g. total_admits"
                                value={opt.yColumns || ''}
                                onChange={e => updateScopeOption(idx, 'yColumns', e.target.value)}
                              />
                            </div>
                            <div style={{ flex: 1 }}>
                              <label className="wb-label" style={{ fontSize: 11 }}>Series</label>
                              <input
                                className="wb-input wb-input--sm"
                                placeholder="optional"
                                value={opt.seriesColumn || ''}
                                onChange={e => updateScopeOption(idx, 'seriesColumn', e.target.value)}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}

                <button
                  className="wb-btn wb-btn--outline wb-btn--sm"
                  onClick={addScopeOption}
                  type="button"
                  style={{ marginTop: 6 }}
                >
                  <i className="fa fa-plus me-1" /> Add Option
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
