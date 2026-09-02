import React, { useEffect, useMemo, useState } from 'react'
import { designerFetch } from '../../api/client'
import { pageFiltersUrl, sourcesUrl } from '../../api/endpoints'

/**
 * WidgetFiltersSection — "Widget Filters" editor on the Controls step.
 *
 * A widget can carry N independent filters (dropdown / multi-select / toggle)
 * rendered in its own header and bound ONLY into its SQL. Three option modes:
 *   - static  → typed value|Label lines, own param
 *   - schema  → DISTINCT values of a schema-source column, own param
 *   - mirror  → borrows a PAGE filter's options + param; the widget value
 *               overrides the page value for this widget only, blank inherits
 *
 * Items are plain dicts in the exact wire shape the server stores
 * (dashboard.widget.filter.to_config_dict / sync_for_widgets), so the same
 * array round-trips through library create/update/place and page templates.
 */

const MODES = [
  ['static', 'Static list'],
  ['schema', 'Schema source column'],
  ['mirror', 'Mirror page filter'],
]
const UIS = [
  ['dropdown', 'Dropdown'],
  ['multiselect', 'Multi-select'],
  ['toggle', 'Toggle buttons'],
]

export function createDefaultWidgetFilter() {
  return {
    label: '',
    param_name: '',
    ui_type: 'dropdown',
    is_searchable: false,
    options_mode: 'static',
    manual_options: '',
    schema_source_id: null,
    schema_source_table: '',
    value_column: '',
    label_column: '',
    page_filter_param: '',
    default_value: '',
    include_all_option: true,
    is_active: true,
  }
}

const IDENT_RE = /^[A-Za-z_][A-Za-z0-9_]*$/

export default function WidgetFiltersSection({ widgetFilters = [], onUpdate, apiBase, appContext }) {
  const [pageFilters, setPageFilters] = useState([])
  const [sources, setSources] = useState([])

  // Page filters (for mirror mode + collision hints) — same endpoint the SQL
  // editor uses for its Insert Filter Param pills.
  useEffect(() => {
    if (!appContext?.page?.id) { setPageFilters([]); return }
    let cancelled = false
    designerFetch(pageFiltersUrl(apiBase, appContext.page.id))
      .then(list => { if (!cancelled) setPageFilters(Array.isArray(list) ? list : []) })
      .catch(() => { if (!cancelled) setPageFilters([]) })
    return () => { cancelled = true }
  }, [apiBase, appContext?.page?.id])

  // Schema sources (for schema mode). No connection filter — any source the
  // app can see is a valid options source; the executor dispatches per source.
  useEffect(() => {
    let cancelled = false
    designerFetch(sourcesUrl(apiBase, { app_id: appContext?.app?.id }))
      .then(list => { if (!cancelled) setSources(Array.isArray(list) ? list : []) })
      .catch(() => { if (!cancelled) setSources([]) })
    return () => { cancelled = true }
  }, [apiBase, appContext?.app?.id])

  const list = Array.isArray(widgetFilters) ? widgetFilters : []
  const pageParams = useMemo(
    () => new Set(pageFilters.map(f => f.param_name).filter(Boolean)),
    [pageFilters],
  )

  const setList = next => onUpdate({ widgetFilters: next })
  const patch = (idx, p) => {
    const next = [...list]
    next[idx] = { ...next[idx], ...p }
    setList(next)
  }
  const add = () => setList([...list, createDefaultWidgetFilter()])
  const remove = idx => setList(list.filter((_, i) => i !== idx))

  const onMirrorPick = (idx, param) => {
    const pf = pageFilters.find(f => f.param_name === param)
    patch(idx, {
      page_filter_param: param,
      param_name: param,
      label: list[idx].label || pf?.label || param,
    })
  }

  return (
    <div className="wb-section" style={{ marginTop: 16 }}>
      <h4 className="wb-sub-title">Widget Filters</h4>
      <p className="wb-step-hint">
        Filters shown in this widget's header and applied to this widget only. Reference
        each one in the SQL like a page filter — <code>{'[[ AND col = %(param)s ]]'}</code>.
        Mirror a page filter to override its value for this widget (blank = page value);
        use a static list or a schema column for a dimension the page doesn't have.
      </p>

      {list.map((wf, idx) => {
        const mode = wf.options_mode || 'static'
        const param = (wf.param_name || '').trim()
        const collides = mode !== 'mirror' && param && pageParams.has(param)
        const badIdent = mode !== 'mirror' && param && !IDENT_RE.test(param)
        return (
          <div key={idx} className="wb-scope-option" style={{ marginBottom: 10 }}>
            <div className="wb-scope-option-header">
              <span className="wb-scope-option-num">{idx + 1}</span>
              <input
                className="wb-input wb-input--sm"
                placeholder="Label (e.g. Age Group)"
                value={wf.label || ''}
                onChange={e => patch(idx, { label: e.target.value })}
                style={{ flex: 2 }}
              />
              <select
                className="wb-select wb-input--sm"
                value={mode}
                onChange={e => patch(idx, { options_mode: e.target.value })}
                style={{ flex: 1.4 }}
              >
                {MODES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <select
                className="wb-select wb-input--sm"
                value={wf.ui_type || 'dropdown'}
                onChange={e => patch(idx, { ui_type: e.target.value })}
                style={{ flex: 1 }}
              >
                {UIS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <button
                className="wb-btn-icon"
                onClick={() => remove(idx)}
                type="button"
                title="Remove filter"
              >
                <i className="fa fa-trash-o" />
              </button>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-start',
                          marginTop: 8, paddingLeft: 28 }}>
              {/* Param (own dimension) or page filter picker (mirror) */}
              {mode === 'mirror' ? (
                <div style={{ minWidth: 220 }}>
                  <label className="wb-label" style={{ fontSize: 11 }}>Page filter</label>
                  <select
                    className="wb-select wb-input--sm"
                    value={wf.page_filter_param || ''}
                    onChange={e => onMirrorPick(idx, e.target.value)}
                  >
                    <option value="">— pick a page filter —</option>
                    {pageFilters.filter(f => f.param_name).map(f => (
                      <option key={f.param_name} value={f.param_name}>
                        {f.label || f.param_name} ({f.param_name})
                      </option>
                    ))}
                  </select>
                  {!pageFilters.length && (
                    <p className="wb-hint" style={{ fontSize: 11, marginTop: 4 }}>
                      Select a page in the Context bar to list its filters.
                    </p>
                  )}
                </div>
              ) : (
                <div style={{ minWidth: 200 }}>
                  <label className="wb-label" style={{ fontSize: 11 }}>SQL Param</label>
                  <input
                    className="wb-input wb-input--sm"
                    placeholder="e.g. age_group"
                    value={wf.param_name || ''}
                    onChange={e => patch(idx, { param_name: e.target.value })}
                  />
                  {collides && (
                    <p style={{ color: '#b91c1c', fontSize: 11, marginTop: 4 }}>
                      This page already has a <code>%({param})s</code> filter — use
                      Mirror page filter mode, or pick a different param name.
                    </p>
                  )}
                  {badIdent && (
                    <p style={{ color: '#b91c1c', fontSize: 11, marginTop: 4 }}>
                      Use letters, digits and underscores only.
                    </p>
                  )}
                </div>
              )}

              {/* Default + flags */}
              <div style={{ minWidth: 160 }}>
                <label className="wb-label" style={{ fontSize: 11 }}>Default value</label>
                <input
                  className="wb-input wb-input--sm"
                  placeholder={mode === 'mirror' ? 'blank = page value' : 'blank = All'}
                  value={wf.default_value || ''}
                  onChange={e => patch(idx, { default_value: e.target.value })}
                />
              </div>
              <label className="wb-label" style={{ fontSize: 11, display: 'inline-flex',
                                                   alignItems: 'center', gap: 4, marginTop: 18 }}>
                <input
                  type="checkbox"
                  checked={wf.include_all_option !== false}
                  onChange={e => patch(idx, { include_all_option: e.target.checked })}
                />
                Include "All"
              </label>
              <label className="wb-label" style={{ fontSize: 11, display: 'inline-flex',
                                                   alignItems: 'center', gap: 4, marginTop: 18 }}>
                <input
                  type="checkbox"
                  checked={!!wf.is_searchable}
                  onChange={e => patch(idx, { is_searchable: e.target.checked })}
                />
                Searchable
              </label>
            </div>

            {/* Mode-specific option sources */}
            {mode === 'static' && (
              <div style={{ marginTop: 8, paddingLeft: 28 }}>
                <label className="wb-label" style={{ fontSize: 11 }}>
                  Options — one per line: <code>value</code> or <code>value|Label</code>
                </label>
                <textarea
                  className="wb-textarea"
                  rows={3}
                  placeholder={'AD|Atopic Dermatitis\nVitiligo'}
                  value={wf.manual_options || ''}
                  onChange={e => patch(idx, { manual_options: e.target.value })}
                  style={{ maxWidth: 480 }}
                />
              </div>
            )}
            {mode === 'schema' && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 8, paddingLeft: 28 }}>
                <div style={{ minWidth: 260 }}>
                  <label className="wb-label" style={{ fontSize: 11 }}>Schema source</label>
                  <select
                    className="wb-select wb-input--sm"
                    value={wf.schema_source_id || ''}
                    onChange={e => {
                      const id = e.target.value ? parseInt(e.target.value, 10) : null
                      const src = sources.find(s => s.id === id)
                      patch(idx, { schema_source_id: id, schema_source_table: src?.table_name || '' })
                    }}
                  >
                    <option value="">— Select source —</option>
                    {sources.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.name}{s.table_name && s.table_name !== s.name ? ` (${s.table_name})` : ''}
                        {s.engine && s.engine !== 'postgres_local' ? ` · ${s.engine}` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ minWidth: 160 }}>
                  <label className="wb-label" style={{ fontSize: 11 }}>Value column</label>
                  <input
                    className="wb-input wb-input--sm"
                    placeholder="e.g. age_group"
                    value={wf.value_column || ''}
                    onChange={e => patch(idx, { value_column: e.target.value })}
                  />
                </div>
                <div style={{ minWidth: 160 }}>
                  <label className="wb-label" style={{ fontSize: 11 }}>Label column (optional)</label>
                  <input
                    className="wb-input wb-input--sm"
                    placeholder="e.g. age_group_label"
                    value={wf.label_column || ''}
                    onChange={e => patch(idx, { label_column: e.target.value })}
                  />
                </div>
              </div>
            )}
          </div>
        )
      })}

      <button
        className="wb-btn wb-btn--outline wb-btn--sm"
        onClick={add}
        type="button"
        style={{ marginTop: 6 }}
      >
        <i className="fa fa-plus me-1" /> Add Widget Filter
      </button>
    </div>
  )
}
