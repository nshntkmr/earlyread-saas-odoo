import React, { useState, useMemo, useCallback } from 'react'
import { SmartTable } from '@posterra/grid-utils'
import { designerFetch } from '../../api/client'
import { libraryPlaceUrl } from '../../api/endpoints'

/**
 * SmartTableConfigurator
 *
 * Configures chart_type='smart_table' widgets. Form-driven (no JSON
 * editing required). Per-column card with a Cell Type dropdown that
 * reveals one of five recipe-specific option forms.
 *
 * Schema produced (smart_table_config):
 *   {
 *     columns: [
 *       {field, label, width?, align?, sortable?,
 *        cell: {type, ...recipe options}}
 *     ],
 *     table: {density?, height?, stickyHeader?, zebraRows?, sortable?}
 *   }
 *
 * Props:
 *   customSql           — {sql, testResult, ...} from the active scope option
 *   smartTableConfig    — current config object
 *   onUpdate(cfg)       — replace the entire config
 *   onSave()            — promise that creates/updates the widget
 *   saving              — boolean
 *   appearance, onAppearanceChange — for the widget name input
 *   apiBase, appContext, editId — wizard plumbing
 */

const VARIANTS = [
  { value: 'success', label: 'Success (green)' },
  { value: 'warning', label: 'Warning (amber)' },
  { value: 'danger',  label: 'Danger (red)' },
  { value: 'neutral', label: 'Neutral (gray)' },
  { value: 'muted',   label: 'Muted (light gray)' },
]

const FORMATS = [
  { value: 'number',   label: 'Number (1,234)' },
  { value: 'decimal',  label: 'Decimal (1,234.5)' },
  { value: 'currency', label: 'Currency ($1,234)' },
  { value: 'percent',  label: 'Percent (12.3%)' },
  { value: 'pp',       label: 'Percentage Points (+1.7pp)' },
  { value: 'text',     label: 'Plain Text' },
]

const CELL_TYPES = [
  { value: 'text',              label: 'Text' },
  { value: 'metric',            label: 'Number / Currency / Percent' },
  { value: 'metric_with_delta', label: 'Metric with Comparison' },
  { value: 'badge',             label: 'Status Badge' },
  { value: 'composite',         label: 'Composite (multi-line)' },
]

const OPS = [
  { value: 'gte',     label: '≥' },
  { value: 'gt',      label: '>' },
  { value: 'lte',     label: '≤' },
  { value: 'lt',      label: '<' },
  { value: 'eq',      label: '=' },
  { value: 'ne',      label: '≠' },
  { value: 'between', label: 'between' },
  { value: 'is_null', label: 'is empty' },
]

// ── Helpers ──────────────────────────────────────────────────────────

function emptyColumn(field = '') {
  return {
    field,
    label: field,
    width: null,
    align: 'left',
    sortable: true,
    cell: { type: 'text', truncate: false, style: 'default' },
  }
}

function reorder(arr, from, to) {
  if (to < 0 || to >= arr.length) return arr
  const out = [...arr]
  const [item] = out.splice(from, 1)
  out.splice(to, 0, item)
  return out
}

// ── Main configurator ───────────────────────────────────────────────

export default function SmartTableConfigurator({
  customSql = {},
  smartTableConfig,
  onUpdate,
  onSave,
  saving,
  appearance = {},
  onAppearanceChange,
  apiBase,
  appContext,
  editId,
}) {
  const cfg = smartTableConfig || { columns: [], table: {} }
  const columns = cfg.columns || []
  const tableOpts = cfg.table || {}

  // Available SQL columns from the master query test result. Empty until
  // admin runs Test Query in the Data Source step.
  const availableColumns = customSql?.testResult?.columns || []

  // ── Save & Place state (mirrors TableConfigurator pattern) ────
  const [placing, setPlacing] = useState(false)
  const [placeSuccess, setPlaceSuccess] = useState(false)
  const hasPageContext = !!appContext?.page?.id

  // Save & Place: persist the definition, then create an instance on
  // the current page (when admin opened the builder from a page).
  // Mirrors TableConfigurator.handleSaveAndPlace.
  const handleSaveAndPlace = useCallback(async () => {
    setPlaceSuccess(false)
    const result = await onSave()
    if (!result?.id || !hasPageContext) return
    // When editing, library_update already synced all instances —
    // calling place_on_page would create a duplicate.
    if (editId) {
      setPlaceSuccess(true)
      return
    }
    setPlacing(true)
    try {
      await designerFetch(libraryPlaceUrl(apiBase, result.id), {
        method: 'POST',
        body: JSON.stringify({
          page_id: appContext.page.id,
          tab_id: appContext?.tab?.id || null,
          // smart_table v1 doesn't support Mode B scope_options
        }),
      })
      setPlaceSuccess(true)
    } catch (err) {
      // Definition saved successfully; placement failed. User can place
      // from Widget Library afterward — surface the error subtly.
      console.warn('place_on_page failed:', err)
    } finally {
      setPlacing(false)
    }
  }, [onSave, hasPageContext, editId, apiBase, appContext])

  // ── Mutations ──────────────────────────────────────────────────
  const updateCfg = (partial) => onUpdate({ ...cfg, ...partial })

  const setTableOpt = (key, value) =>
    updateCfg({ table: { ...tableOpts, [key]: value } })

  const setColumn = (idx, partial) => {
    const next = [...columns]
    next[idx] = { ...next[idx], ...partial }
    updateCfg({ columns: next })
  }

  const setColumnCell = (idx, partial) => {
    const next = [...columns]
    next[idx] = { ...next[idx], cell: { ...(next[idx].cell || {}), ...partial } }
    updateCfg({ columns: next })
  }

  const replaceColumnCell = (idx, newCell) => {
    const next = [...columns]
    next[idx] = { ...next[idx], cell: newCell }
    updateCfg({ columns: next })
  }

  const addColumn = () => {
    const defaultField = availableColumns[0] || ''
    updateCfg({ columns: [...columns, emptyColumn(defaultField)] })
  }

  const removeColumn = (idx) =>
    updateCfg({ columns: columns.filter((_, i) => i !== idx) })

  const moveColumn = (idx, dir) =>
    updateCfg({ columns: reorder(columns, idx, idx + dir) })

  const duplicateColumn = (idx) => {
    const copy = JSON.parse(JSON.stringify(columns[idx]))
    copy.label = `${copy.label} (copy)`
    const next = [...columns]
    next.splice(idx + 1, 0, copy)
    updateCfg({ columns: next })
  }

  // ── Live-preview rowData built from customSql.testResult ──────
  // Reuses the portal's SmartTable component so preview is 1:1 with
  // runtime render. Only first 5 rows shown to keep the preview tight.
  const previewData = useMemo(() => {
    const tr = customSql?.testResult
    if (!tr || !Array.isArray(tr.columns) || !Array.isArray(tr.rows)) return null
    const cols = tr.columns
    const rowData = tr.rows.slice(0, 5).map(r => {
      const obj = {}
      cols.forEach((c, i) => { obj[c] = r[i] !== undefined ? r[i] : '' })
      return obj
    })
    return {
      type: 'smart_table',
      rowData,
      columns,
      table: tableOpts,
      row_count: rowData.length,
    }
  }, [customSql?.testResult, columns, tableOpts])

  // Validation banner
  const validationErrors = useMemo(() => {
    const errs = []
    if (columns.length === 0) {
      errs.push('Add at least one column.')
    }
    columns.forEach((c, i) => {
      if (!c.field) errs.push(`Column #${i + 1}: pick a Field.`)
      if (!c.label) errs.push(`Column #${i + 1}: enter a Label.`)
      if (c.cell?.type === 'metric_with_delta' && !c.cell?.main?.field && !c.field) {
        errs.push(`Column #${i + 1}: Metric with Comparison needs a main field.`)
      }
    })
    return errs
  }, [columns])

  const canSave = !!(appearance.title || '').trim() && validationErrors.length === 0

  return (
    <div className="wb-smart-table-configurator">
      <h3 className="wb-step-title">Configure Smart Table</h3>
      <p className="wb-step-hint">
        Build the columns and pick a cell type for each. Cell types map to
        rendering recipes — text, number/currency/percent, metric with
        comparison, status badge, or composite multi-line.
      </p>

      {availableColumns.length === 0 && (
        <div className="wb-warn-banner" style={{
          padding: 10, marginBottom: 16, background: '#fff7ed',
          border: '1px solid #fed7aa', borderRadius: 6, fontSize: 13,
        }}>
          ⚠ Run the master query test (in <strong>Data Source</strong>) so the
          column picker can populate.
        </div>
      )}

      {/* ── Table-level options ──────────────────────────────────── */}
      <section className="wb-section" style={{ marginBottom: 20 }}>
        <h4 className="wb-sub-title">Table Options</h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            Density:
            <select
              className="wb-select wb-select--sm"
              value={tableOpts.density || 'comfortable'}
              onChange={e => setTableOpt('density', e.target.value)}
            >
              <option value="compact">Compact</option>
              <option value="comfortable">Comfortable</option>
              <option value="spacious">Spacious</option>
            </select>
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            Max Height (px):
            <input
              type="number"
              className="wb-input wb-input--sm"
              style={{ width: 80 }}
              value={tableOpts.height ?? ''}
              placeholder="auto"
              onChange={e => setTableOpt('height', e.target.value ? Number(e.target.value) : null)}
            />
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={tableOpts.sortable !== false}
              onChange={e => setTableOpt('sortable', e.target.checked)}
            />
            Sortable headers
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={tableOpts.stickyHeader !== false}
              onChange={e => setTableOpt('stickyHeader', e.target.checked)}
            />
            Sticky header
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <input
              type="checkbox"
              checked={!!tableOpts.zebraRows}
              onChange={e => setTableOpt('zebraRows', e.target.checked)}
            />
            Zebra rows
          </label>
        </div>
      </section>

      {/* ── Columns list ─────────────────────────────────────────── */}
      <section className="wb-section">
        <h4 className="wb-sub-title">Columns ({columns.length})</h4>

        {columns.map((col, idx) => (
          <ColumnCard
            key={idx}
            idx={idx}
            col={col}
            availableColumns={availableColumns}
            isFirst={idx === 0}
            isLast={idx === columns.length - 1}
            onChangeColumn={(partial) => setColumn(idx, partial)}
            onChangeCell={(partial) => setColumnCell(idx, partial)}
            onReplaceCell={(newCell) => replaceColumnCell(idx, newCell)}
            onMove={(dir) => moveColumn(idx, dir)}
            onDuplicate={() => duplicateColumn(idx)}
            onRemove={() => removeColumn(idx)}
          />
        ))}

        <button
          type="button"
          className="wb-btn wb-btn--sm"
          onClick={addColumn}
          disabled={availableColumns.length === 0}
          style={{ marginTop: 8 }}
        >
          + Add Column
        </button>
      </section>

      {/* ── Live preview ─────────────────────────────────────────── */}
      <section className="wb-section" style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #e5e7eb' }}>
        <h4 className="wb-sub-title">Live Preview</h4>
        {!previewData ? (
          <div style={{
            padding: 12, background: '#f8fafc', border: '1px dashed #cbd5e1',
            borderRadius: 6, fontSize: 13, color: '#64748b',
          }}>
            Run the master query test (in <strong>Data Source</strong>) to see a preview.
          </div>
        ) : columns.length === 0 ? (
          <div style={{
            padding: 12, background: '#f8fafc', border: '1px dashed #cbd5e1',
            borderRadius: 6, fontSize: 13, color: '#64748b',
          }}>
            Add at least one column to preview the table.
          </div>
        ) : (
          <>
            <p className="wb-step-hint" style={{ marginBottom: 8 }}>
              Showing first {previewData.rowData.length} of {customSql?.testResult?.rows?.length || 0} test rows.
              Live re-renders as you tweak columns above.
            </p>
            <div style={{ border: '1px solid #e5e7eb', borderRadius: 6, overflow: 'hidden' }}>
              <SmartTable data={previewData} />
            </div>
          </>
        )}
      </section>

      {/* ── Footer (name + save) ─────────────────────────────────── */}
      <section className="wb-section" style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid #e5e7eb' }}>
        <h4 className="wb-sub-title">Save</h4>

        {/* Page-context hint: tells admin where Save & Place will land */}
        {hasPageContext && (
          <p className="wb-step-hint" style={{ marginBottom: 8 }}>
            {editId
              ? `Editing — saving updates all existing instances.`
              : `You can save & place directly on ${appContext.page.name}${appContext.tab ? ` → ${appContext.tab.name}` : ''}.`
            }
          </p>
        )}

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block' }}>
            Widget Name <span style={{ color: '#ef4444' }}>*</span>
            <input
              type="text"
              className="wb-input"
              style={{ width: '100%', maxWidth: 480 }}
              value={appearance.title || ''}
              placeholder="e.g. MDC Competition Detail"
              onChange={e => onAppearanceChange?.({ ...appearance, title: e.target.value })}
            />
          </label>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {placeSuccess && (
            <span style={{ color: '#15803d', fontSize: 13, marginRight: 4 }}>
              <i className="fa fa-check me-1" /> Placed on page!
            </span>
          )}
          <button
            type="button"
            className="wb-btn wb-btn--outline"
            onClick={onSave}
            disabled={!canSave || saving || placing}
            title={canSave ? 'Save the widget definition to the library' : (validationErrors[0] || 'Enter a widget name')}
          >
            {saving ? 'Saving…' : (editId ? 'Update Widget' : 'Save to Library')}
          </button>
          {hasPageContext && (
            <button
              type="button"
              className="wb-btn wb-btn--primary"
              onClick={handleSaveAndPlace}
              disabled={!canSave || saving || placing}
              title={canSave ? `Save and place on ${appContext.page.name}` : (validationErrors[0] || 'Enter a widget name')}
            >
              {placing ? 'Placing…' : (editId ? 'Update & Sync Instances' : 'Save & Place on Page')}
            </button>
          )}
        </div>

        {validationErrors.length > 0 && (
          <ul style={{ marginTop: 10, fontSize: 12, color: '#b91c1c' }}>
            {validationErrors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        )}
      </section>
    </div>
  )
}

// ── Per-column card ─────────────────────────────────────────────────

function ColumnCard({
  idx, col, availableColumns, isFirst, isLast,
  onChangeColumn, onChangeCell, onReplaceCell, onMove, onDuplicate, onRemove,
}) {
  const cell = col.cell || { type: 'text' }

  // When the cell type changes, replace the entire cell object with sensible
  // defaults for the new type. Prevents stale fields from previous types.
  const handleCellTypeChange = (newType) => {
    const defaults = {
      text:              { type: 'text',              truncate: false, style: 'default' },
      metric:            { type: 'metric',            format: 'number', decimals: 0, muteZero: false, rules: [] },
      metric_with_delta: { type: 'metric_with_delta',
                           main:  { field: col.field, format: 'number', decimals: 0 },
                           delta: { field: '',        format: 'pp',     decimals: 1, showSign: true },
                           color: { basis: 'delta', lowerIsBetter: false } },
      badge:             { type: 'badge',             field: col.field, rules: [], defaultVariant: 'neutral' },
      composite:         { type: 'composite',         layout: 'vertical', items: [] },
    }
    onReplaceCell(defaults[newType] || { type: 'text' })
  }

  return (
    <div
      className="wb-column-card"
      style={{
        border: '1px solid #e2e8f0', borderRadius: 6,
        padding: 12, marginBottom: 8, background: '#fafbfc',
      }}
    >
      {/* Header row: field, label, controls */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <span style={{ color: '#6b7280', fontSize: 12, minWidth: 56 }}>Column {idx + 1}</span>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Field:
          <select
            className="wb-select wb-select--sm"
            value={col.field || ''}
            onChange={e => {
              const f = e.target.value
              // Auto-fill label from field name if label was empty or matched old field
              const newLabel = (!col.label || col.label === col.field) ? f : col.label
              onChangeColumn({ field: f, label: newLabel })
            }}
          >
            <option value="">Pick column…</option>
            {availableColumns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, flex: 1 }}>
          Label:
          <input
            type="text"
            className="wb-input wb-input--sm"
            style={{ flex: 1, minWidth: 80 }}
            value={col.label || ''}
            onChange={e => onChangeColumn({ label: e.target.value })}
          />
        </label>
        <button type="button" className="wb-btn wb-btn--sm wb-btn--ghost" disabled={isFirst} onClick={() => onMove(-1)} title="Move up">↑</button>
        <button type="button" className="wb-btn wb-btn--sm wb-btn--ghost" disabled={isLast}  onClick={() => onMove(+1)} title="Move down">↓</button>
        <button type="button" className="wb-btn wb-btn--sm wb-btn--ghost" onClick={onDuplicate} title="Duplicate column"><i className="fa fa-clone" /></button>
        <button type="button" className="wb-btn wb-btn--sm wb-btn--ghost" onClick={onRemove} title="Remove column"><i className="fa fa-times" /></button>
      </div>

      {/* Width + align + sortable */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Width (px):
          <input type="number" className="wb-input wb-input--sm" style={{ width: 70 }}
            value={col.width ?? ''} placeholder="auto"
            onChange={e => onChangeColumn({ width: e.target.value ? Number(e.target.value) : null })} />
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Align:
          <select className="wb-select wb-select--sm" value={col.align || 'left'}
            onChange={e => onChangeColumn({ align: e.target.value })}>
            <option value="left">left</option>
            <option value="center">center</option>
            <option value="right">right</option>
          </select>
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={col.sortable !== false}
            onChange={e => onChangeColumn({ sortable: e.target.checked })} />
          Sortable
        </label>
      </div>

      {/* Cell Type dropdown */}
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <strong>Cell Type:</strong>
          <select
            className="wb-select wb-select--sm"
            value={cell.type || 'text'}
            onChange={e => handleCellTypeChange(e.target.value)}
          >
            {CELL_TYPES.map(ct => (
              <option key={ct.value} value={ct.value}>{ct.label}</option>
            ))}
          </select>
        </label>
      </div>

      {/* Recipe-specific options */}
      <CellOptionsForm
        cell={cell}
        column={col}
        availableColumns={availableColumns}
        onChange={onChangeCell}
      />
    </div>
  )
}

// ── Cell options dispatcher ────────────────────────────────────────

function CellOptionsForm({ cell, column, availableColumns, onChange }) {
  switch (cell.type) {
    case 'text':              return <TextOptions cell={cell} onChange={onChange} />
    case 'metric':            return <MetricOptions cell={cell} onChange={onChange} />
    case 'metric_with_delta': return <MetricWithDeltaOptions cell={cell} availableColumns={availableColumns} onChange={onChange} />
    case 'badge':             return <BadgeOptions cell={cell} availableColumns={availableColumns} onChange={onChange} />
    case 'composite':         return <CompositeOptions cell={cell} availableColumns={availableColumns} onChange={onChange} />
    default: return null
  }
}

// ── 1. Text ────────────────────────────────────────────────────────

function TextOptions({ cell, onChange }) {
  return (
    <div style={{ paddingLeft: 12, borderLeft: '2px solid #e5e7eb' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={!!cell.truncate}
            onChange={e => onChange({ truncate: e.target.checked })} />
          Truncate with ellipsis
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Style:
          <select className="wb-select wb-select--sm" value={cell.style || 'default'}
            onChange={e => onChange({ style: e.target.value })}>
            <option value="default">Default</option>
            <option value="primary">Primary (bold)</option>
            <option value="muted">Muted (small gray)</option>
            <option value="bold">Bold</option>
          </select>
        </label>
      </div>
    </div>
  )
}

// ── 2. Metric (number/currency/percent + rules) ────────────────────

function MetricOptions({ cell, onChange }) {
  const rules = cell.rules || []
  const setRules = (next) => onChange({ rules: next })
  const addRule = () => setRules([...rules, { op: 'gte', value: 0, variant: 'warning' }])
  const updateRule = (i, partial) => {
    const next = [...rules]; next[i] = { ...next[i], ...partial }; setRules(next)
  }
  const removeRule = (i) => setRules(rules.filter((_, j) => j !== i))

  return (
    <div style={{ paddingLeft: 12, borderLeft: '2px solid #e5e7eb' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Format:
          <select className="wb-select wb-select--sm" value={cell.format || 'number'}
            onChange={e => onChange({ format: e.target.value })}>
            {FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Decimals:
          <input type="number" className="wb-input wb-input--sm" style={{ width: 50 }}
            value={cell.decimals ?? 0} min={0} max={6}
            onChange={e => onChange({ decimals: Number(e.target.value) })} />
        </label>
        {cell.format === 'currency' && (
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            Currency:
            <input type="text" className="wb-input wb-input--sm" style={{ width: 60 }}
              value={cell.currency || 'USD'}
              onChange={e => onChange({ currency: e.target.value })} />
          </label>
        )}
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={!!cell.muteZero}
            onChange={e => onChange({ muteZero: e.target.checked })} />
          Mute zero values
        </label>
      </div>

      <details style={{ marginTop: 8 }}>
        <summary style={{ cursor: 'pointer', fontWeight: 500, fontSize: 13 }}>
          Conditional Formatting ({rules.length})
        </summary>
        <div style={{ paddingTop: 8, paddingLeft: 8 }}>
          {rules.map((r, i) => (
            <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4, fontSize: 13 }}>
              <span>When value</span>
              <select className="wb-select wb-select--sm" value={r.op || 'gte'}
                onChange={e => updateRule(i, { op: e.target.value })}>
                {OPS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              {r.op !== 'is_null' && (
                <input type="text" className="wb-input wb-input--sm" style={{ width: 80 }}
                  value={r.op === 'between' ? (Array.isArray(r.value) ? r.value.join(',') : '') : (r.value ?? '')}
                  placeholder={r.op === 'between' ? 'low,high' : '0'}
                  onChange={e => {
                    if (r.op === 'between') {
                      const parts = e.target.value.split(',').map(s => Number(s.trim()))
                      updateRule(i, { value: parts.length === 2 ? parts : e.target.value })
                    } else {
                      updateRule(i, { value: e.target.value })
                    }
                  }} />
              )}
              <span>→</span>
              <select className="wb-select wb-select--sm" value={r.variant || 'neutral'}
                onChange={e => updateRule(i, { variant: e.target.value })}>
                {VARIANTS.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
              </select>
              <button type="button" className="wb-btn wb-btn--sm wb-btn--ghost" onClick={() => removeRule(i)}>×</button>
            </div>
          ))}
          <button type="button" className="wb-btn wb-btn--sm" onClick={addRule}>+ Add Rule</button>
          <p style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
            ℹ Rules evaluate top-to-bottom. First match wins.
          </p>
        </div>
      </details>
    </div>
  )
}

// ── 3. Metric with Delta ────────────────────────────────────────────

function MetricWithDeltaOptions({ cell, availableColumns, onChange }) {
  const main = cell.main || {}
  const delta = cell.delta || {}
  const color = cell.color || {}
  const setMain = (partial) => onChange({ main: { ...main, ...partial } })
  const setDelta = (partial) => onChange({ delta: { ...delta, ...partial } })
  const setColor = (partial) => onChange({ color: { ...color, ...partial } })

  return (
    <div style={{ paddingLeft: 12, borderLeft: '2px solid #e5e7eb', fontSize: 13 }}>
      <div style={{ marginBottom: 6, fontWeight: 500 }}>Main value</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
        <label>Field:
          <select className="wb-select wb-select--sm" value={main.field || ''}
            onChange={e => setMain({ field: e.target.value })}>
            <option value="">Pick…</option>
            {availableColumns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Format:
          <select className="wb-select wb-select--sm" value={main.format || 'number'}
            onChange={e => setMain({ format: e.target.value })}>
            {FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>
        <label>Decimals:
          <input type="number" className="wb-input wb-input--sm" style={{ width: 50 }}
            value={main.decimals ?? 0} min={0} max={6}
            onChange={e => setMain({ decimals: Number(e.target.value) })} />
        </label>
      </div>

      <div style={{ marginBottom: 6, fontWeight: 500 }}>Delta (optional)</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
        <label>Field:
          <select className="wb-select wb-select--sm" value={delta.field || ''}
            onChange={e => setDelta({ field: e.target.value })}>
            <option value="">— None —</option>
            {availableColumns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Format:
          <select className="wb-select wb-select--sm" value={delta.format || 'pp'}
            onChange={e => setDelta({ format: e.target.value })}>
            {FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
        </label>
        <label>Decimals:
          <input type="number" className="wb-input wb-input--sm" style={{ width: 50 }}
            value={delta.decimals ?? 1} min={0} max={6}
            onChange={e => setDelta({ decimals: Number(e.target.value) })} />
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={delta.showSign !== false}
            onChange={e => setDelta({ showSign: e.target.checked })} />
          Show sign (+/−)
        </label>
      </div>

      <div style={{ marginBottom: 6, fontWeight: 500 }}>Color</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <label>Color basis:
          <select className="wb-select wb-select--sm" value={color.basis || 'delta'}
            onChange={e => setColor({ basis: e.target.value })}>
            <option value="delta">Delta</option>
            <option value="main">Main value</option>
          </select>
        </label>
        <label>Direction:
          <select className="wb-select wb-select--sm" value={color.lowerIsBetter ? 'lower' : 'higher'}
            onChange={e => setColor({ lowerIsBetter: e.target.value === 'lower' })}>
            <option value="higher">Higher is better</option>
            <option value="lower">Lower is better</option>
          </select>
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          <input type="checkbox" checked={!!cell.muteZero}
            onChange={e => onChange({ muteZero: e.target.checked })} />
          Mute zero
        </label>
      </div>
    </div>
  )
}

// ── 4. Badge ────────────────────────────────────────────────────────

function BadgeOptions({ cell, availableColumns, onChange }) {
  const rules = cell.rules || []
  const setRules = (next) => onChange({ rules: next })
  const addRule = () => setRules([...rules, { match: '', label: '', variant: 'neutral' }])
  const updateRule = (i, partial) => {
    const next = [...rules]; next[i] = { ...next[i], ...partial }; setRules(next)
  }
  const removeRule = (i) => setRules(rules.filter((_, j) => j !== i))

  return (
    <div style={{ paddingLeft: 12, borderLeft: '2px solid #e5e7eb', fontSize: 13 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
        <label>Field:
          <select className="wb-select wb-select--sm" value={cell.field || ''}
            onChange={e => onChange({ field: e.target.value })}>
            <option value="">— Use column field —</option>
            {availableColumns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Default variant:
          <select className="wb-select wb-select--sm" value={cell.defaultVariant || 'neutral'}
            onChange={e => onChange({ defaultVariant: e.target.value })}>
            {VARIANTS.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
          </select>
        </label>
      </div>

      <div style={{ marginBottom: 6, fontWeight: 500 }}>Match rules ({rules.length})</div>
      {rules.map((r, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
          <span>When value =</span>
          <input type="text" className="wb-input wb-input--sm" style={{ width: 100 }}
            value={r.match ?? ''} placeholder="e.g. better"
            onChange={e => updateRule(i, { match: e.target.value })} />
          <span>show</span>
          <input type="text" className="wb-input wb-input--sm" style={{ width: 100 }}
            value={r.label ?? ''} placeholder="display label"
            onChange={e => updateRule(i, { label: e.target.value })} />
          <span>as</span>
          <select className="wb-select wb-select--sm" value={r.variant || 'neutral'}
            onChange={e => updateRule(i, { variant: e.target.value })}>
            {VARIANTS.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
          </select>
          <button type="button" className="wb-btn wb-btn--sm wb-btn--ghost" onClick={() => removeRule(i)}>×</button>
        </div>
      ))}
      <button type="button" className="wb-btn wb-btn--sm" onClick={addRule}>+ Add Rule</button>
    </div>
  )
}

// ── 5. Composite ────────────────────────────────────────────────────

function CompositeOptions({ cell, availableColumns, onChange }) {
  const items = cell.items || []
  const setItems = (next) => onChange({ items: next })
  const addItem = () => setItems([...items, { field: '', format: 'text', style: 'default' }])
  const updateItem = (i, partial) => {
    const next = [...items]; next[i] = { ...next[i], ...partial }; setItems(next)
  }
  const removeItem = (i) => setItems(items.filter((_, j) => j !== i))

  return (
    <div style={{ paddingLeft: 12, borderLeft: '2px solid #e5e7eb', fontSize: 13 }}>
      <div style={{ marginBottom: 8 }}>
        <label>Layout:
          <select className="wb-select wb-select--sm" value={cell.layout || 'vertical'}
            onChange={e => onChange({ layout: e.target.value })}>
            <option value="vertical">Vertical (stacked)</option>
            <option value="horizontal">Horizontal (inline)</option>
          </select>
        </label>
      </div>

      <div style={{ marginBottom: 6, fontWeight: 500 }}>Items ({items.length})</div>
      {items.map((it, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
          <label>Field:
            <select className="wb-select wb-select--sm" value={it.field || ''}
              onChange={e => updateItem(i, { field: e.target.value })}>
              <option value="">Pick…</option>
              {availableColumns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label>Format:
            <select className="wb-select wb-select--sm" value={it.format || 'text'}
              onChange={e => updateItem(i, { format: e.target.value })}>
              <option value="text">Text</option>
              <option value="number">Number</option>
              <option value="percent">Percent</option>
              <option value="currency">Currency</option>
              <option value="badge">Badge</option>
            </select>
          </label>
          {it.format === 'badge' ? (
            <label>Variant:
              <select className="wb-select wb-select--sm" value={it.variant || 'neutral'}
                onChange={e => updateItem(i, { variant: e.target.value })}>
                {VARIANTS.map(v => <option key={v.value} value={v.value}>{v.label}</option>)}
              </select>
            </label>
          ) : (
            <label>Style:
              <select className="wb-select wb-select--sm" value={it.style || 'default'}
                onChange={e => updateItem(i, { style: e.target.value })}>
                <option value="default">Default</option>
                <option value="primary">Primary</option>
                <option value="muted">Muted</option>
                <option value="bold">Bold</option>
              </select>
            </label>
          )}
          <button type="button" className="wb-btn wb-btn--sm wb-btn--ghost" onClick={() => removeItem(i)}>×</button>
        </div>
      ))}
      <button type="button" className="wb-btn wb-btn--sm" onClick={addItem}>+ Add Item</button>
    </div>
  )
}
