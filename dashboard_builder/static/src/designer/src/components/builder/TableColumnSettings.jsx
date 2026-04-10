import React, { useState, useCallback } from 'react'

// ── Column type presets ─────────────────────────────────────────────────────
const COLUMN_TYPES = [
  { value: '',               label: 'Auto' },
  { value: 'text',           label: 'Text' },
  { value: 'numericColumn',  label: 'Numeric' },
  { value: 'currency',       label: 'Currency' },
  { value: 'percentage',     label: 'Percentage' },
  { value: 'date',           label: 'Date' },
]

const FORMATTER_OPTIONS = [
  { value: '',           label: 'None' },
  { value: 'number',     label: 'Number (1,234)' },
  { value: 'currency',   label: 'Currency ($1,234)' },
  { value: 'percentage', label: 'Percentage (44.1%)' },
  { value: 'decimal',    label: 'Decimal (0.94)' },
  { value: 'date',       label: 'Date' },
]

const RENDERER_OPTIONS = [
  { value: '',           label: 'None (text)' },
  { value: 'pctColored', label: 'Colored Percentage' },
  { value: 'badge',      label: 'Badge' },
  { value: 'sparkline',  label: 'Sparkline' },
  { value: 'starRating', label: 'Star Rating' },
  { value: 'barInline',  label: 'Inline Bar' },
  { value: 'composite',  label: 'Composite (multi-field)' },
  { value: 'dualValue',  label: 'Dual Value (value + %)' },
]

const FILTER_OPTIONS = [
  { value: '',                      label: 'None' },
  { value: 'agTextColumnFilter',    label: 'Text' },
  { value: 'agNumberColumnFilter',  label: 'Number' },
  { value: 'agDateColumnFilter',    label: 'Date' },
]

const PINNED_OPTIONS = [
  { value: '',      label: 'None' },
  { value: 'left',  label: 'Left' },
  { value: 'right', label: 'Right' },
]

const SORT_OPTIONS = [
  { value: '',     label: 'None' },
  { value: 'asc',  label: 'Ascending' },
  { value: 'desc', label: 'Descending' },
]

const CSS_CLASS_OPTIONS = [
  { value: 'cell-good',  label: 'Good (green)' },
  { value: 'cell-bad',   label: 'Bad (red)' },
  { value: 'cell-warn',  label: 'Warning (amber)' },
  { value: 'cell-muted', label: 'Muted (gray)' },
]

const CLICK_OPTIONS = [
  { value: 'none',        label: 'No action' },
  { value: 'go_to_page',  label: 'Go to page' },
  { value: 'filter_page', label: 'Filter this page' },
  { value: 'open_url',    label: 'Open URL' },
]

// ── Type → auto-fill mapping ────────────────────────────────────────────────
const TYPE_AUTO_FILL = {
  text:          { width: 200, formatter: '',          filter: 'agTextColumnFilter',   align: 'left' },
  numericColumn: { width: 110, formatter: 'number',    filter: 'agNumberColumnFilter', align: 'right' },
  currency:      { width: 120, formatter: 'currency',  filter: 'agNumberColumnFilter', align: 'right' },
  percentage:    { width: 100, formatter: 'percentage', filter: 'agNumberColumnFilter', align: 'right' },
  date:          { width: 120, formatter: 'date',      filter: 'agDateColumnFilter',   align: 'left' },
}

/**
 * TableColumnSettings — Expandable settings panel for one AG Grid column.
 *
 * Props:
 *   column     — current column config object
 *   allColumns — available columns from source (for tooltip field dropdown)
 *   onChange   — (changes) => void
 */
export default function TableColumnSettings({ column, allColumns = [], onChange }) {
  const [showBehavior, setShowBehavior] = useState(false)
  const [showFormatting, setShowFormatting] = useState(false)
  const [showClickAction, setShowClickAction] = useState(false)

  const set = (key, val) => onChange({ [key]: val })
  const setMulti = (obj) => onChange(obj)

  // Handle column type change → auto-fill related settings
  const handleTypeChange = (typeVal) => {
    const fill = TYPE_AUTO_FILL[typeVal]
    if (fill) {
      setMulti({
        type: typeVal || null,
        width: fill.width,
        valueFormatter: fill.formatter || null,
        filter: fill.filter,
        cellStyle: fill.align !== 'left' ? { textAlign: fill.align } : null,
      })
    } else {
      set('type', typeVal || null)
    }
  }

  // ── Conditional formatting rules ───────────────────────────────────────────
  const rules = Object.entries(column.cellClassRules || {})
  const addRule = () => {
    const existing = column.cellClassRules || {}
    const presets = ['cell-good', 'cell-bad', 'cell-warn', 'cell-muted']
    let newClass = presets.find(c => !(c in existing))
    if (!newClass) {
      let n = 1
      while (`cell-custom-${n}` in existing) n++
      newClass = `cell-custom-${n}`
    }
    set('cellClassRules', { ...existing, [newClass]: 'x >= 0' })
  }
  const updateRule = (oldClass, newClass, condition) => {
    const updated = { ...(column.cellClassRules || {}) }
    if (oldClass !== newClass) delete updated[oldClass]
    updated[newClass] = condition
    set('cellClassRules', updated)
  }
  const removeRule = (cls) => {
    const updated = { ...(column.cellClassRules || {}) }
    delete updated[cls]
    set('cellClassRules', updated)
  }

  return (
    <div className="tcs-panel">

      {/* ═══ BASIC (always visible) ═══ */}
      <div className="tcs-section">
        <div className="tcs-row">
          <label className="tcs-label">Header Label</label>
          <input
            type="text" className="tcs-input"
            value={column.headerName || ''}
            onChange={e => set('headerName', e.target.value)}
            placeholder={column.field}
          />
        </div>

        <div className="tcs-row">
          <label className="tcs-label">Column Type</label>
          <select className="tcs-select"
            value={column.type || ''}
            onChange={e => handleTypeChange(e.target.value)}
          >
            {COLUMN_TYPES.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        <div className="tcs-row-inline">
          <div>
            <label className="tcs-label">Width (px)</label>
            <input
              type="number" className="tcs-input tcs-input--narrow"
              value={column.flex ? '' : (column.width || '')}
              onChange={e => set('width', Number(e.target.value) || null)}
              disabled={!!column.flex}
              min={40} max={600}
            />
          </div>
          <div>
            <label className="tcs-label tcs-label--inline">
              <input
                type="checkbox"
                checked={!!column.flex}
                onChange={e => setMulti(e.target.checked
                  ? { flex: 1, width: null }
                  : { flex: null, width: 150 }
                )}
              />
              Auto-flex
            </label>
          </div>
        </div>
      </div>

      {/* ═══ DISPLAY ═══ */}
      <div className="tcs-section">
        <div className="tcs-row-inline">
          <div>
            <label className="tcs-label">Formatter</label>
            <select className="tcs-select"
              value={column.valueFormatter || ''}
              onChange={e => set('valueFormatter', e.target.value || null)}
            >
              {FORMATTER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label className="tcs-label">Renderer</label>
            <select className="tcs-select"
              value={column.cellRenderer || ''}
              onChange={e => set('cellRenderer', e.target.value || null)}
            >
              {RENDERER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>

        {/* Renderer-specific params */}
        {column.cellRenderer === 'pctColored' && (
          <div className="tcs-renderer-params">
            <div className="tcs-row-inline">
              <div>
                <label className="tcs-label">Good above</label>
                <input type="number" className="tcs-input tcs-input--narrow"
                  value={column.cellRendererParams?.goodAbove ?? ''}
                  onChange={e => set('cellRendererParams', {
                    ...column.cellRendererParams,
                    goodAbove: Number(e.target.value),
                  })}
                />
              </div>
              <div>
                <label className="tcs-label">Bad below</label>
                <input type="number" className="tcs-input tcs-input--narrow"
                  value={column.cellRendererParams?.badBelow ?? ''}
                  onChange={e => set('cellRendererParams', {
                    ...column.cellRendererParams,
                    badBelow: Number(e.target.value),
                  })}
                />
              </div>
            </div>
          </div>
        )}

        {/* Bar Inline renderer params */}
        {column.cellRenderer === 'barInline' && (
          <div className="tcs-renderer-params">
            <div className="tcs-row-inline">
              <div>
                <label className="tcs-label">Max (100% reference)</label>
                <input type="number" className="tcs-input tcs-input--narrow"
                  placeholder="auto"
                  value={column.cellRendererParams?.max ?? ''}
                  onChange={e => {
                    const raw = e.target.value
                    set('cellRendererParams', {
                      ...column.cellRendererParams,
                      max: raw === '' ? null : Number(raw),
                    })
                  }}
                />
              </div>
              <div>
                <label className="tcs-label">Bar color (hex)</label>
                <input type="text" className="tcs-input"
                  placeholder="#3b82f6"
                  value={column.cellRendererParams?.color ?? ''}
                  onChange={e => set('cellRendererParams', {
                    ...column.cellRendererParams,
                    color: e.target.value || null,
                  })}
                />
              </div>
              <div>
                <label className="tcs-label">Multiply by 100</label>
                <input type="checkbox"
                  checked={column.cellRendererParams?.multiply === true}
                  onChange={e => set('cellRendererParams', {
                    ...column.cellRendererParams,
                    multiply: e.target.checked,
                  })}
                />
              </div>
            </div>
            <div className="tcs-help-text">
              Value / Max = bar fill percentage. Leave Max empty to use 100 (values are already percentages) or set the column's expected maximum (e.g. 250000 for visit counts).
            </div>
          </div>
        )}

        {/* Composite renderer params — line config */}
        {column.cellRenderer === 'composite' && (
          <CompositeParamsEditor
            lines={column.cellRendererParams?.lines || []}
            allColumns={allColumns}
            onChange={lines => set('cellRendererParams', { ...column.cellRendererParams, lines })}
          />
        )}

        {/* Dual Value renderer params */}
        {column.cellRenderer === 'dualValue' && (
          <div className="tcs-renderer-params">
            <div className="tcs-row">
              <label className="tcs-label">Secondary Field</label>
              <select className="tcs-select"
                value={column.cellRendererParams?.secondaryField || ''}
                onChange={e => set('cellRendererParams', {
                  ...column.cellRendererParams,
                  secondaryField: e.target.value || null,
                })}
              >
                <option value="">(none)</option>
                {allColumns.map(c => (
                  <option key={c.column_name} value={c.column_name}>
                    {c.display_name || c.column_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="tcs-row-inline">
              <div>
                <label className="tcs-label">Format</label>
                <select className="tcs-select"
                  value={column.cellRendererParams?.secondaryFormat || 'pct'}
                  onChange={e => set('cellRendererParams', {
                    ...column.cellRendererParams,
                    secondaryFormat: e.target.value,
                  })}
                >
                  <option value="pct">Percentage</option>
                  <option value="number">Number</option>
                  <option value="raw">Raw text</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Alignment */}
        <div className="tcs-row">
          <label className="tcs-label">Alignment</label>
          <div className="tcs-btn-group">
            {['left', 'center', 'right'].map(a => (
              <button key={a} type="button"
                className={`tcs-btn-toggle ${(column.cellStyle?.textAlign || 'left') === a ? 'tcs-btn-toggle--active' : ''}`}
                onClick={() => set('cellStyle', a !== 'left' ? { textAlign: a } : null)}
              >
                {a.charAt(0).toUpperCase() + a.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="tcs-row">
          <label className="tcs-label">Pinned</label>
          <select className="tcs-select"
            value={column.pinned || ''}
            onChange={e => set('pinned', e.target.value || null)}
          >
            {PINNED_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      {/* ═══ BEHAVIOR (collapsible) ═══ */}
      <div className="tcs-section-collapsible">
        <button type="button" className="tcs-section-toggle"
          onClick={() => setShowBehavior(!showBehavior)}>
          <i className={`fa fa-chevron-${showBehavior ? 'down' : 'right'} me-1`} />
          Behavior
        </button>
        {showBehavior && (
          <div className="tcs-section-body">
            <div className="tcs-row-inline">
              <label className="tcs-label tcs-label--inline">
                <input type="checkbox" checked={column.sortable !== false}
                  onChange={e => set('sortable', e.target.checked)} />
                Sortable
              </label>
              <label className="tcs-label tcs-label--inline">
                <input type="checkbox" checked={column.resizable !== false}
                  onChange={e => set('resizable', e.target.checked)} />
                Resizable
              </label>
              <label className="tcs-label tcs-label--inline">
                <input type="checkbox" checked={!column.hide}
                  onChange={e => set('hide', !e.target.checked)} />
                Visible
              </label>
              <label className="tcs-label tcs-label--inline">
                <input type="checkbox" checked={!!column.wrapText}
                  onChange={e => set('wrapText', e.target.checked)} />
                Wrap Text
              </label>
            </div>
            <div className="tcs-row-inline">
              <div>
                <label className="tcs-label">Default Sort</label>
                <select className="tcs-select"
                  value={column.sort || ''}
                  onChange={e => set('sort', e.target.value || null)}
                >
                  {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="tcs-label">Filter</label>
                <select className="tcs-select"
                  value={column.filter || ''}
                  onChange={e => set('filter', e.target.value || false)}
                >
                  {FILTER_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>
            <div className="tcs-row">
              <label className="tcs-label">Tooltip Field</label>
              <select className="tcs-select"
                value={column.tooltipField || ''}
                onChange={e => set('tooltipField', e.target.value || null)}
              >
                <option value="">(none)</option>
                {allColumns.map(c => (
                  <option key={c.column_name} value={c.column_name}>
                    {c.display_name || c.column_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="tcs-row">
              <label className="tcs-label">Header Tooltip</label>
              <input type="text" className="tcs-input"
                placeholder="Info text shown on column header hover"
                value={column.headerTooltip || ''}
                onChange={e => set('headerTooltip', e.target.value || null)}
              />
            </div>
          </div>
        )}
      </div>

      {/* ═══ CONDITIONAL FORMATTING (collapsible) ═══ */}
      <div className="tcs-section-collapsible">
        <button type="button" className="tcs-section-toggle"
          onClick={() => setShowFormatting(!showFormatting)}>
          <i className={`fa fa-chevron-${showFormatting ? 'down' : 'right'} me-1`} />
          Conditional Formatting {rules.length > 0 && `(${rules.length})`}
        </button>
        {showFormatting && (
          <div className="tcs-section-body">
            {rules.map(([cls, cond], ri) => (
              <div key={ri} className="tcs-rule-row">
                <select className="tcs-select tcs-select--sm"
                  value={cls}
                  onChange={e => updateRule(cls, e.target.value, cond)}
                >
                  {CSS_CLASS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <span className="tcs-rule-when">when</span>
                <input type="text" className="tcs-input tcs-input--sm"
                  value={cond}
                  onChange={e => updateRule(cls, cls, e.target.value)}
                  placeholder="x >= 70"
                />
                <button type="button" className="tcs-remove-btn"
                  onClick={() => removeRule(cls)}>
                  <i className="fa fa-times" />
                </button>
              </div>
            ))}
            <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={addRule}>
              <i className="fa fa-plus me-1" /> Add Rule
            </button>
          </div>
        )}
      </div>

      {/* ═══ CLICK ACTION (collapsible) ═══ */}
      <div className="tcs-section-collapsible">
        <button type="button" className="tcs-section-toggle"
          onClick={() => setShowClickAction(!showClickAction)}>
          <i className={`fa fa-chevron-${showClickAction ? 'down' : 'right'} me-1`} />
          Click Action {column.clickAction !== 'none' && column.clickAction ? `(${column.clickAction})` : ''}
        </button>
        {showClickAction && (
          <div className="tcs-section-body">
            <div className="tcs-row">
              <label className="tcs-label">On Click</label>
              <select className="tcs-select"
                value={column.clickAction || 'none'}
                onChange={e => set('clickAction', e.target.value)}
              >
                {CLICK_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            {column.clickAction === 'go_to_page' && (
              <>
                <div className="tcs-row">
                  <label className="tcs-label">Target Page Key</label>
                  <input type="text" className="tcs-input"
                    value={column.actionPageKey || ''}
                    onChange={e => set('actionPageKey', e.target.value)}
                    placeholder="e.g. hha_detail"
                  />
                </div>
                <div className="tcs-row">
                  <label className="tcs-label">Pass Value As</label>
                  <input type="text" className="tcs-input"
                    value={column.actionFilterParam || ''}
                    onChange={e => set('actionFilterParam', e.target.value)}
                    placeholder="e.g. hha_ccn"
                  />
                </div>
                <div className="tcs-row">
                  <label className="tcs-label">Value Field (from row data)</label>
                  <input type="text" className="tcs-input"
                    value={column.actionValueField || ''}
                    onChange={e => set('actionValueField', e.target.value)}
                    placeholder="Leave empty to use cell value"
                  />
                </div>
              </>
            )}
            {column.clickAction === 'filter_page' && (
              <>
                <div className="tcs-row">
                  <label className="tcs-label">Filter Param (URL key)</label>
                  <input type="text" className="tcs-input"
                    value={column.actionFilterParam || ''}
                    onChange={e => set('actionFilterParam', e.target.value)}
                    placeholder="e.g. hha_ccn"
                  />
                </div>
                <div className="tcs-row">
                  <label className="tcs-label">Value Field (from row data)</label>
                  <input type="text" className="tcs-input"
                    value={column.actionValueField || ''}
                    onChange={e => set('actionValueField', e.target.value)}
                    placeholder="Leave empty to use cell value"
                  />
                  <div className="tcs-help-text">
                    Read the click value from a different SQL column in the row.
                    E.g., display shows "147000 - VNA HEALTH CARE" but set this
                    to hha_ccn to pass just "147000" as the filter value.
                  </div>
                </div>
              </>
            )}
            {column.clickAction === 'open_url' && (
              <div className="tcs-row">
                <label className="tcs-label">URL Template</label>
                <input type="text" className="tcs-input"
                  value={column.actionUrlTemplate || ''}
                  onChange={e => set('actionUrlTemplate', e.target.value)}
                  placeholder="/my/posterra/hha/{value}"
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Composite Renderer: Line Editor ─────────────────────────────────────────
// Lets admin configure multi-line composite cell: add/remove lines, pick
// fields per line, set separator, bold/muted flags.
function CompositeParamsEditor({ lines, allColumns, onChange }) {
  const addLine = useCallback(() => {
    onChange([...lines, { fields: [], separator: ' · ', bold: false, muted: false }])
  }, [lines, onChange])

  const removeLine = useCallback((index) => {
    onChange(lines.filter((_, i) => i !== index))
  }, [lines, onChange])

  const updateLine = useCallback((index, key, value) => {
    const updated = lines.map((line, i) =>
      i === index ? { ...line, [key]: value } : line
    )
    onChange(updated)
  }, [lines, onChange])

  const toggleField = useCallback((lineIndex, fieldName) => {
    const line = lines[lineIndex]
    const fields = line.fields || []
    const next = fields.includes(fieldName)
      ? fields.filter(f => f !== fieldName)
      : [...fields, fieldName]
    updateLine(lineIndex, 'fields', next)
  }, [lines, updateLine])

  return (
    <div className="tcs-renderer-params">
      <label className="tcs-label" style={{ marginBottom: 4 }}>Lines</label>
      {lines.map((line, li) => (
        <div key={li} className="tcs-composite-line">
          <div className="tcs-composite-line-header">
            <span className="tcs-label" style={{ fontSize: 11 }}>Line {li + 1}</span>
            <button type="button" className="tcs-remove-btn" onClick={() => removeLine(li)}>
              <i className="fa fa-times" />
            </button>
          </div>
          <div className="tcs-row" style={{ marginBottom: 4 }}>
            <label className="tcs-label" style={{ fontSize: 11 }}>Fields (click to toggle)</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
              {allColumns.map(c => {
                const active = (line.fields || []).includes(c.column_name)
                return (
                  <button
                    key={c.column_name}
                    type="button"
                    className={`tcs-btn-toggle ${active ? 'tcs-btn-toggle--active' : ''}`}
                    style={{ fontSize: 10, padding: '1px 6px' }}
                    onClick={() => toggleField(li, c.column_name)}
                  >
                    {c.display_name || c.column_name}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="tcs-row-inline" style={{ gap: 6 }}>
            <div>
              <label className="tcs-label" style={{ fontSize: 11 }}>Separator</label>
              <input type="text" className="tcs-input tcs-input--narrow"
                value={line.separator || ''}
                onChange={e => updateLine(li, 'separator', e.target.value)}
                placeholder=" · "
              />
            </div>
            <div>
              <label className="tcs-label" style={{ fontSize: 11 }}>Prefix</label>
              <input type="text" className="tcs-input tcs-input--narrow"
                value={line.prefix || ''}
                onChange={e => updateLine(li, 'prefix', e.target.value)}
                placeholder="CCN "
              />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 3 }}>
            <label style={{ fontSize: 11, cursor: 'pointer' }}>
              <input type="checkbox" checked={!!line.bold}
                onChange={e => updateLine(li, 'bold', e.target.checked)} /> Bold
            </label>
            <label style={{ fontSize: 11, cursor: 'pointer' }}>
              <input type="checkbox" checked={!!line.muted}
                onChange={e => updateLine(li, 'muted', e.target.checked)} /> Muted
            </label>
            <label style={{ fontSize: 11, cursor: 'pointer' }}>
              <input type="checkbox" checked={!!line.small}
                onChange={e => updateLine(li, 'small', e.target.checked)} /> Small
            </label>
          </div>
        </div>
      ))}
      <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={addLine}>
        <i className="fa fa-plus me-1" /> Add Line
      </button>
    </div>
  )
}
