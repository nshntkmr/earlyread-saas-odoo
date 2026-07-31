// AttributeGridConfigurator — the complete structured editor for
// attribute_grid_config (canonical v1). Odoo's form only offers the raw JSON
// under Advanced; THIS is the authoring surface.
//
// State contract: `config` is the raw (possibly partial) config object held
// in builder state; every edit calls onChange(nextConfig). Normalization/
// preview happen downstream through the SAME shared normalizer + formatter
// the portal uses.

import React from 'react'
import {
  normalizeAttributeGrid, DATA_SHAPES, ATTR_FORMAT_TYPES, LINK_TYPES,
} from '@posterra/grid-utils'
import IconKeyPicker from './IconKeyPicker'

const LAYOUTS = ['stacked', 'inline']
const FIELD_LAYOUTS = ['inherit', 'stacked', 'inline']
const EMPHASES = ['normal', 'strong']
const LV_MODES = ['none', 'icon', 'initials']
const ICON_MODES = ['none', 'static', 'column']

const ROW_ROLES = [
  ['item_key_column', 'Item key'],
  ['label_column', 'Label *'],
  ['value_column', 'Value *'],
  ['secondary_value_column', 'Secondary value'],
  ['icon_key_column', 'Icon key'],
  ['style_key_column', 'Style token'],
  ['row_order_column', 'Row order'],
  ['column_start_column', 'Column start'],
  ['column_span_column', 'Column span'],
  ['layout_column', 'Layout'],
  ['emphasis_column', 'Emphasis'],
  ['divider_before_column', 'Divider before'],
  ['format_type_column', 'Format type'],
  ['decimals_column', 'Decimals'],
  ['display_multiplier_column', 'Display multiplier'],
  ['prefix_column', 'Prefix'],
  ['suffix_column', 'Suffix'],
  ['null_text_column', 'Null text'],
  ['link_type_column', 'Link type'],
  ['link_value_column', 'Link value'],
  ['is_visible_column', 'Visible flag'],
]

function Sel({ value, options, onChange, style }) {
  return (
    <select className="form-select form-select-sm" style={style}
      value={value} onChange={e => onChange(e.target.value)}>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}

function Txt({ value, onChange, placeholder, style, mono }) {
  return (
    <input className="form-control form-control-sm" style={{ ...(mono ? { fontFamily: 'monospace' } : {}), ...style }}
      value={value ?? ''} placeholder={placeholder}
      onChange={e => onChange(e.target.value)} />
  )
}

function Num({ value, onChange, min, max, style }) {
  return (
    <input type="number" className="form-control form-control-sm" style={style}
      value={value ?? ''} min={min} max={max}
      onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
  )
}

function CsvList({ value, onChange, placeholder }) {
  // allowed_keys editor: comma-separated in UI, array in config.
  return (
    <Txt mono value={(value || []).join(',')} placeholder={placeholder}
      onChange={v => onChange(v.split(',').map(s => s.trim()).filter(Boolean))} />
  )
}

export default function AttributeGridConfigurator({ config, onChange, apiBase }) {
  const cfg = normalizeAttributeGrid(config || {})
  const set = (patch) => onChange({ ...(config || {}), version: 1, ...patch })
  const setNested = (key, patch) => set({ [key]: { ...cfg[key], ...patch } })

  const setField = (idx, patch) => {
    const fields = cfg.fields.map((f, i) => (i === idx ? { ...f, ...patch } : f))
    set({ fields })
  }
  const setFieldNested = (idx, key, patch) =>
    setField(idx, { [key]: { ...cfg.fields[idx][key], ...patch } })

  const addField = () => set({
    fields: [...cfg.fields, {
      key: `field_${cfg.fields.length + 1}`, label: '', value_column: '',
    }],
  })
  const removeField = (idx) => set({ fields: cfg.fields.filter((_, i) => i !== idx) })
  const moveField = (idx, dir) => {
    const fields = [...cfg.fields]
    const j = idx + dir
    if (j < 0 || j >= fields.length) return
    ;[fields[idx], fields[j]] = [fields[j], fields[idx]]
    set({ fields })
  }

  const styleKeys = Object.keys(cfg.styles)
  const setStyle = (key, part, val) =>
    set({ styles: { ...cfg.styles, [key]: { ...cfg.styles[key], [part]: val } } })

  return (
    <div className="wb-agc">
      {/* ── Shape + grid ── */}
      <div className="d-flex flex-wrap gap-3 align-items-end mb-3">
        <div>
          <label className="form-label small mb-1">Data shape</label>
          <Sel value={cfg.data_shape} options={DATA_SHAPES}
            onChange={v => set({ data_shape: v })} style={{ width: 170 }} />
          <div className="form-text" style={{ maxWidth: 340 }}>
            {cfg.data_shape === 'attribute_rows'
              ? 'One SQL row per displayed attribute — SQL alone reorders, hides, or repositions fields.'
              : 'One wide SQL row; each configured field maps a result column.'}
          </div>
        </div>
        <div>
          <label className="form-label small mb-1">Columns (1–8)</label>
          <Num value={cfg.columns} min={1} max={8} style={{ width: 90 }}
            onChange={v => set({ columns: v })} />
        </div>
        <div>
          <label className="form-label small mb-1">Density</label>
          <Sel value={cfg.density} options={['comfortable', 'compact']}
            onChange={v => set({ density: v })} style={{ width: 140 }} />
        </div>
        <div>
          <label className="form-label small mb-1">Default layout</label>
          <Sel value={cfg.default_layout} options={LAYOUTS}
            onChange={v => set({ default_layout: v })} style={{ width: 130 }} />
        </div>
        <div>
          <label className="form-label small mb-1">Empty text</label>
          <Txt value={cfg.empty_text} onChange={v => set({ empty_text: v })}
            style={{ width: 220 }} />
        </div>
      </div>

      {/* ── Style palette ── */}
      <details className="mb-3">
        <summary className="small fw-bold">Style palette (tokens → colors; SQL returns tokens, never CSS)</summary>
        <div className="mt-2 d-flex flex-column gap-1">
          {styleKeys.map(k => (
            <div key={k} className="d-flex align-items-center gap-2">
              <code style={{ width: 110 }}>{k}</code>
              <input type="color" value={cfg.styles[k].foreground}
                onChange={e => setStyle(k, 'foreground', e.target.value)} title="foreground" />
              <input type="color" value={cfg.styles[k].background}
                onChange={e => setStyle(k, 'background', e.target.value)} title="background" />
            </div>
          ))}
          <div className="d-flex align-items-center gap-2 mt-1">
            <Txt placeholder="new token key (a-z0-9_-)" style={{ width: 180 }} mono
              value={cfg._newStyleKey || ''}
              onChange={v => set({ _newStyleKey: v })} />
            <button type="button" className="btn btn-sm btn-outline-secondary"
              onClick={() => {
                const k = (config?._newStyleKey || '').trim()
                if (!k || cfg.styles[k]) return
                const { _newStyleKey, ...rest } = config || {}
                onChange({
                  ...rest, version: 1,
                  styles: { ...cfg.styles, [k]: { foreground: '#087ad8', background: '#e7f1fb' } },
                })
              }}>Add token</button>
          </div>
          <div className="d-flex align-items-center gap-2 mt-1">
            <span className="small">Default token:</span>
            <Sel value={cfg.default_style_key || ''} options={['', ...styleKeys]}
              onChange={v => set({ default_style_key: v })} style={{ width: 140 }} />
          </div>
        </div>
      </details>

      {/* ── Leading visual ── */}
      <details className="mb-3">
        <summary className="small fw-bold">Leading visual</summary>
        <div className="mt-2 d-flex flex-wrap gap-3 align-items-end">
          <div>
            <label className="form-label small mb-1">Mode</label>
            <Sel value={cfg.leading_visual.mode} options={LV_MODES}
              onChange={v => setNested('leading_visual', { mode: v })} style={{ width: 120 }} />
          </div>
          {cfg.leading_visual.mode === 'icon' && (
            <div>
              <label className="form-label small mb-1">Icon</label>
              <IconKeyPicker apiBase={apiBase} value={cfg.leading_visual.icon_key}
                onChange={v => setNested('leading_visual', { icon_key: v })} allowEmpty={false} />
            </div>
          )}
          {cfg.leading_visual.mode === 'initials' && (
            <div>
              <label className="form-label small mb-1">Source column (SQL alias)</label>
              <Txt mono value={cfg.leading_visual.source_column}
                onChange={v => setNested('leading_visual', { source_column: v })} style={{ width: 170 }} />
            </div>
          )}
          {cfg.leading_visual.mode !== 'none' && (
            <>
              <div>
                <label className="form-label small mb-1">Foreground</label>
                <input type="color" value={cfg.leading_visual.foreground}
                  onChange={e => setNested('leading_visual', { foreground: e.target.value })} />
              </div>
              <div>
                <label className="form-label small mb-1">Background</label>
                <input type="color" value={cfg.leading_visual.background}
                  onChange={e => setNested('leading_visual', { background: e.target.value })} />
              </div>
            </>
          )}
        </div>
      </details>

      {/* ── single_record: fields editor ── */}
      {cfg.data_shape === 'single_record' && (
        <div className="mb-3">
          <div className="d-flex align-items-center justify-content-between mb-2">
            <span className="small fw-bold">Fields ({cfg.fields.length}/40)</span>
            <button type="button" className="btn btn-sm btn-primary" onClick={addField}>
              <i className="fa fa-plus me-1" />Add field
            </button>
          </div>
          {cfg.fields.length === 0 && (
            <div className="text-muted small">No fields yet — a single-record grid needs at least one.</div>
          )}
          <div className="d-flex flex-column gap-2">
            {cfg.fields.map((f, i) => (
              <div key={i} className="border rounded p-2">
                <div className="d-flex flex-wrap gap-2 align-items-end">
                  <div>
                    <label className="form-label small mb-1">Key</label>
                    <Txt mono value={f.key} onChange={v => setField(i, { key: v })} style={{ width: 130 }} />
                  </div>
                  <div>
                    <label className="form-label small mb-1">Label</label>
                    <Txt value={f.label} onChange={v => setField(i, { label: v })} style={{ width: 150 }} />
                  </div>
                  <div>
                    <label className="form-label small mb-1">Value column (SQL alias)</label>
                    <Txt mono value={f.value_column} onChange={v => setField(i, { value_column: v })} style={{ width: 150 }} />
                  </div>
                  <div>
                    <label className="form-label small mb-1">Span</label>
                    <Num value={f.span} min={1} max={cfg.columns} style={{ width: 70 }}
                      onChange={v => setField(i, { span: v })} />
                  </div>
                  <div>
                    <label className="form-label small mb-1">Layout</label>
                    <Sel value={f.layout} options={FIELD_LAYOUTS}
                      onChange={v => setField(i, { layout: v })} style={{ width: 110 }} />
                  </div>
                  <div>
                    <label className="form-label small mb-1">Emphasis</label>
                    <Sel value={f.emphasis} options={EMPHASES}
                      onChange={v => setField(i, { emphasis: v })} style={{ width: 110 }} />
                  </div>
                  <div>
                    <label className="form-label small mb-1">Style token</label>
                    <Sel value={f.style_key || ''} options={['', ...styleKeys]}
                      onChange={v => setField(i, { style_key: v })} style={{ width: 110 }} />
                  </div>
                  <div className="form-check mt-3">
                    <input className="form-check-input" type="checkbox" checked={f.divider_before}
                      id={`agc-div-${i}`}
                      onChange={e => setField(i, { divider_before: e.target.checked })} />
                    <label className="form-check-label small" htmlFor={`agc-div-${i}`}>Divider before</label>
                  </div>
                  <div className="ms-auto d-flex gap-1">
                    <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => moveField(i, -1)}>↑</button>
                    <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => moveField(i, +1)}>↓</button>
                    <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => removeField(i)}>
                      <i className="fa fa-trash" />
                    </button>
                  </div>
                </div>
                <div className="d-flex flex-wrap gap-2 align-items-end mt-2">
                  <div>
                    <label className="form-label small mb-1">Icon mode</label>
                    <Sel value={f.icon.mode} options={ICON_MODES}
                      onChange={v => setFieldNested(i, 'icon', { mode: v })} style={{ width: 100 }} />
                  </div>
                  {f.icon.mode === 'static' && (
                    <div>
                      <label className="form-label small mb-1">Icon</label>
                      <IconKeyPicker apiBase={apiBase} value={f.icon.key}
                        onChange={v => setFieldNested(i, 'icon', { key: v })} allowEmpty={false} />
                    </div>
                  )}
                  {f.icon.mode === 'column' && (
                    <>
                      <div>
                        <label className="form-label small mb-1">Icon column</label>
                        <Txt mono value={f.icon.column} style={{ width: 130 }}
                          onChange={v => setFieldNested(i, 'icon', { column: v })} />
                      </div>
                      <div>
                        <label className="form-label small mb-1">Allowed keys * (CSV — export bundles exactly these)</label>
                        <CsvList value={f.icon.allowed_keys} placeholder="clock,users"
                          onChange={v => setFieldNested(i, 'icon', { allowed_keys: v })} />
                      </div>
                      <div>
                        <label className="form-label small mb-1">Fallback</label>
                        <IconKeyPicker apiBase={apiBase} value={f.icon.fallback_key}
                          onChange={v => setFieldNested(i, 'icon', { fallback_key: v })} />
                      </div>
                    </>
                  )}
                  <div>
                    <label className="form-label small mb-1">Format</label>
                    <Sel value={f.format.type} options={ATTR_FORMAT_TYPES}
                      onChange={v => setFieldNested(i, 'format', { type: v })} style={{ width: 110 }} />
                  </div>
                  {['integer', 'decimal', 'percent', 'currency'].includes(f.format.type) && (
                    <>
                      <div>
                        <label className="form-label small mb-1">Decimals</label>
                        <Num value={f.format.decimals} min={0} max={6} style={{ width: 70 }}
                          onChange={v => setFieldNested(i, 'format', { decimals: v })} />
                      </div>
                      <div>
                        <label className="form-label small mb-1">× Multiplier</label>
                        <Num value={f.format.display_multiplier} style={{ width: 90 }}
                          onChange={v => setFieldNested(i, 'format', { display_multiplier: v })} />
                      </div>
                      <div>
                        <label className="form-label small mb-1">Prefix</label>
                        <Txt value={f.format.prefix} style={{ width: 70 }}
                          onChange={v => setFieldNested(i, 'format', { prefix: v })} />
                      </div>
                      <div>
                        <label className="form-label small mb-1">Suffix</label>
                        <Txt value={f.format.suffix} style={{ width: 70 }}
                          onChange={v => setFieldNested(i, 'format', { suffix: v })} />
                      </div>
                    </>
                  )}
                  <div>
                    <label className="form-label small mb-1">Null text</label>
                    <Txt value={f.format.null_text} style={{ width: 80 }}
                      onChange={v => setFieldNested(i, 'format', { null_text: v })} />
                  </div>
                  <div>
                    <label className="form-label small mb-1">Link</label>
                    <Sel value={f.link.type} options={LINK_TYPES}
                      onChange={v => setFieldNested(i, 'link', { type: v })} style={{ width: 100 }} />
                  </div>
                  {f.link.type !== 'none' && (
                    <>
                      <div style={{ minWidth: 220, flex: 1 }}>
                        <label className="form-label small mb-1">
                          Template (placeholders = SQL aliases; URL contents are admin-controlled)
                        </label>
                        <Txt mono value={f.link.template} placeholder="/member?eid={EID}"
                          onChange={v => setFieldNested(i, 'link', { template: v })} />
                        {/(\{)(mbi|dob|ssn)(\})/i.test(f.link.template || '') && (
                          <div className="form-text text-warning">
                            Heads up: this placeholder looks sensitive. Allowed — but URLs may be
                            retained by browsers, proxies, and referrer headers.
                          </div>
                        )}
                      </div>
                      <div className="form-check mt-3">
                        <input className="form-check-input" type="checkbox" checked={f.link.new_tab}
                          id={`agc-nt-${i}`}
                          onChange={e => setFieldNested(i, 'link', { new_tab: e.target.checked })} />
                        <label className="form-check-label small" htmlFor={`agc-nt-${i}`}>New tab</label>
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── attribute_rows: role mapping ── */}
      {cfg.data_shape === 'attribute_rows' && (
        <div className="mb-3">
          <div className="small fw-bold mb-2">
            Semantic role → SQL alias mapping (Label + Value required; blank = unused)
          </div>
          <div className="d-flex flex-wrap gap-2">
            {ROW_ROLES.map(([role, label]) => (
              <div key={role}>
                <label className="form-label small mb-1">{label}</label>
                <Txt mono value={cfg.row_mapping[role]} style={{ width: 150 }}
                  onChange={v => setNested('row_mapping', { [role]: v })} />
              </div>
            ))}
          </div>
          <div className="d-flex flex-wrap gap-3 align-items-end mt-3">
            {cfg.row_mapping.icon_key_column && (
              <>
                <div>
                  <label className="form-label small mb-1">Allowed icon keys * (CSV)</label>
                  <CsvList value={cfg.row_icon.allowed_keys} placeholder="clock,users,hospital"
                    onChange={v => setNested('row_icon', { allowed_keys: v })} />
                </div>
                <div>
                  <label className="form-label small mb-1">Fallback icon</label>
                  <IconKeyPicker apiBase={apiBase} value={cfg.row_icon.fallback_key}
                    onChange={v => setNested('row_icon', { fallback_key: v })} />
                </div>
              </>
            )}
            <div>
              <label className="form-label small mb-1">Default format</label>
              <Sel value={cfg.row_default_format.type} options={ATTR_FORMAT_TYPES}
                onChange={v => setNested('row_default_format', { type: v })} style={{ width: 110 }} />
            </div>
            <div>
              <label className="form-label small mb-1">Null text</label>
              <Txt value={cfg.row_default_format.null_text} style={{ width: 80 }}
                onChange={v => setNested('row_default_format', { null_text: v })} />
            </div>
            <div>
              <label className="form-label small mb-1">Row link type</label>
              <Sel value={cfg.row_link.type} options={LINK_TYPES}
                onChange={v => setNested('row_link', { type: v })} style={{ width: 100 }} />
            </div>
            {cfg.row_link.type !== 'none' && (
              <div style={{ minWidth: 240, flex: 1 }}>
                <label className="form-label small mb-1">Row link template ({'{link_value}'} = the row's link value)</label>
                <Txt mono value={cfg.row_link.template} placeholder="{link_value}"
                  onChange={v => setNested('row_link', { template: v })} />
              </div>
            )}
          </div>
          <div className="form-text mt-2">
            A row renders a link only when its Link value is non-null; the Link type column
            (allow-listed: none/url/tel/mailto/internal) overrides the row link type per row.
          </div>
        </div>
      )}
    </div>
  )
}
