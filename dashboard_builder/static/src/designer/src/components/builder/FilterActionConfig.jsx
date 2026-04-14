import React from 'react'

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

    </div>
  )
}
// (Widget Controls section moved to WidgetControlsStep.jsx as a separate step)
