import React, { useState } from 'react'
import CustomSqlEditor from './CustomSqlEditor'
import DonutStylePicker from './DonutStylePicker'
import LineStylePicker from './LineStylePicker'
import GaugeStylePicker from './GaugeStylePicker'
import KpiStylePicker from './KpiStylePicker'
import TableColumnSettings from './TableColumnSettings'
// Smart Table column editor — reused verbatim from the standalone configurator
import { ColumnCard, emptyColumn } from './SmartTableConfigurator'
import {
  COMPOSITE_CHILD_TYPES,
  createCompositeChild,
  applyChildTypeSwitch,
} from './compositeUtils'

const TYPE_META = Object.fromEntries(COMPOSITE_CHILD_TYPES.map(t => [t.key, t]))

const WIDTH_PRESETS = [
  { label: '¼', span: 3 },
  { label: '⅓', span: 4 },
  { label: '½', span: 6 },
  { label: '⅔', span: 8 },
  { label: 'Full', span: 12 },
]

const BLOCK_COLORS = ['#14b8a6', '#60a5fa', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981', '#6366f1']

const styles = {
  canvas: {
    display: 'grid',
    gridTemplateColumns: 'repeat(12, 1fr)',
    gap: 6,
    padding: 10,
    border: '1px dashed #cbd5e1',
    borderRadius: 8,
    background: '#f8fafc',
    marginBottom: 4,
  },
  canvasRuler: {
    display: 'grid',
    gridTemplateColumns: 'repeat(12, 1fr)',
    gap: 6,
    padding: '0 10px',
    marginBottom: 2,
  },
  rulerCell: { fontSize: 9, color: '#94a3b8', textAlign: 'center' },
  block: {
    borderRadius: 6,
    padding: '8px 10px',
    fontSize: 12,
    fontWeight: 600,
    color: '#0f172a',
    cursor: 'pointer',
    border: '1px solid transparent',
    minHeight: 44,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    overflow: 'hidden',
    whiteSpace: 'nowrap',
    textOverflow: 'ellipsis',
  },
  card: {
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    background: '#fff',
    marginTop: 10,
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 12px',
  },
  num: {
    width: 22, height: 22, borderRadius: '50%', background: '#f1f5f9',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 11, fontWeight: 700, color: '#475569', flexShrink: 0,
  },
  badge: {
    fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 10,
    whiteSpace: 'nowrap',
  },
  stepper: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    fontSize: 12, color: '#475569',
  },
  stepBtn: {
    width: 22, height: 22, border: '1px solid #e5e7eb', borderRadius: 4,
    background: '#fff', cursor: 'pointer', fontSize: 11, lineHeight: 1,
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  },
  cardBody: { borderTop: '1px solid #f1f5f9', padding: '12px 14px' },
  sectionTitle: {
    fontSize: 11, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase',
    letterSpacing: '.05em', margin: '14px 0 6px', borderBottom: '1px solid #f1f5f9',
    paddingBottom: 3,
  },
}

function Stepper({ label, value, min, max, onChange }) {
  const clamp = v => Math.max(min, Math.min(max, v))
  return (
    <span style={styles.stepper}>
      <span style={{ color: '#94a3b8' }}>{label}</span>
      <button type="button" style={styles.stepBtn} onClick={() => onChange(clamp(Number(value) - 1))}>
        <i className="fa fa-caret-left" />
      </button>
      <strong style={{ minWidth: 16, textAlign: 'center' }}>{value}</strong>
      <button type="button" style={styles.stepBtn} onClick={() => onChange(clamp(Number(value) + 1))}>
        <i className="fa fa-caret-right" />
      </button>
    </span>
  )
}

/**
 * Composite body for the Columns step — "Composite Layout & Children".
 * Zone A: live 12-column grid mini-canvas (steppers + width presets write
 *         col_start / col_span / row_start / row_span — drag/resize is a
 *         planned fast-follow).
 * Zone B: child cards — layout controls in the header, full per-child
 *         config (type, data mode, own SQL, columns, style) expands in place.
 *
 * Props:
 *   items            — state.compositeChildren array
 *   strategy         — 'shared' | 'own' (data strategy default)
 *   connectionId     — step-3 connection (children are limited to it)
 *   parentColumns    — column names from the parent SQL test (for table config)
 *   onUpdate         — (nextItems) => void
 *   apiBase, appContext — passthrough for CustomSqlEditor
 */
export default function CompositeLayoutChildren({
  items = [],
  strategy = 'shared',
  connectionId = 'local_pg',
  parentColumns = [],
  onUpdate,
  apiBase,
  appContext,
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const [expandedUid, setExpandedUid] = useState(null)
  const [selectedColIdx, setSelectedColIdx] = useState({})  // per-child table col expand

  const update = (idx, changes) => {
    const next = [...items]
    next[idx] = { ...next[idx], ...changes }
    onUpdate(next)
  }

  const addChild = (typeKey) => {
    const child = createCompositeChild(typeKey, strategy, items.length)
    onUpdate([...items, child])
    setPickerOpen(false)
    setExpandedUid(child._uid)
  }

  const removeChild = (idx) => {
    onUpdate(items.filter((_, i) => i !== idx))
  }

  const moveChild = (idx, dir) => {
    const to = idx + dir
    if (to < 0 || to >= items.length) return
    const next = [...items]
    const [moved] = next.splice(idx, 1)
    next.splice(to, 0, moved)
    onUpdate(next)
  }

  const switchType = (idx, newType) => {
    update(idx, applyChildTypeSwitch(items[idx], newType))
  }

  // Columns available to a child's table config / mapping hints:
  // own-SQL child → its own test columns; inherit child → parent SQL columns.
  const columnsFor = (child) => {
    const own = child._testResult?.columns
    if (child.data_mode === 'own_sql' && Array.isArray(own) && own.length) return own
    return parentColumns || []
  }

  return (
    <div>
      <h3 className="wb-step-title">Composite Layout &amp; Children</h3>

      {/* ── Zone A: live 12-column grid canvas ─────────────────────────── */}
      <div style={styles.canvasRuler}>
        {Array.from({ length: 12 }, (_, i) => (
          <span key={i} style={styles.rulerCell}>{i + 1}</span>
        ))}
      </div>
      <div style={styles.canvas}>
        {items.length === 0 && (
          <div style={{ gridColumn: '1 / span 12', textAlign: 'center', color: '#94a3b8', fontSize: 13, padding: 16 }}>
            No child blocks yet — click <strong>Add Child</strong> below.
          </div>
        )}
        {items.map((c, idx) => {
          const color = BLOCK_COLORS[idx % BLOCK_COLORS.length]
          const meta = TYPE_META[c.chart_type] || {}
          return (
            <div
              key={c._uid}
              style={{
                ...styles.block,
                gridColumn: `${c.col_start} / span ${c.col_span}`,
                ...(Number(c.row_start) > 0
                  ? { gridRow: `${c.row_start} / span ${c.row_span}` }
                  : { gridRow: `span ${c.row_span}` }),
                background: `${color}22`,
                borderColor: expandedUid === c._uid ? color : 'transparent',
                opacity: c.is_active === false ? 0.4 : 1,
              }}
              onClick={() => setExpandedUid(expandedUid === c._uid ? null : c._uid)}
              title={`${meta.label || c.chart_type} — cols ${c.col_start}-${c.col_start + c.col_span - 1}`}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                <i className={`fa ${meta.icon || 'fa-square-o'} me-1`} style={{ color }} />
                {idx + 1}. {c.name || meta.label || c.chart_type}
              </span>
              <span style={{ fontSize: 10, fontWeight: 400, color: '#64748b' }}>
                {c.col_span}/12{c.row_span > 1 ? ` · ${c.row_span} rows` : ''}
              </span>
            </div>
          )
        })}
      </div>

      {/* ── Add child ──────────────────────────────────────────────────── */}
      <div style={{ marginTop: 10 }}>
        <button
          type="button"
          className="wb-btn wb-btn--outline wb-btn--sm"
          onClick={() => setPickerOpen(!pickerOpen)}
        >
          <i className="fa fa-plus me-1" /> Add Child
        </button>
        {pickerOpen && (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
            gap: 8, marginTop: 8, padding: 10, border: '1px solid #e5e7eb',
            borderRadius: 8, background: '#fff',
          }}>
            {COMPOSITE_CHILD_TYPES.map(t => (
              <button
                key={t.key}
                type="button"
                className="wb-btn wb-btn--outline wb-btn--sm"
                style={{ justifyContent: 'flex-start', textAlign: 'left' }}
                onClick={() => addChild(t.key)}
              >
                <i className={`fa ${t.icon} me-1`} /> {t.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Zone B: child cards ────────────────────────────────────────── */}
      {items.map((c, idx) => {
        const meta = TYPE_META[c.chart_type] || {}
        const expanded = expandedUid === c._uid
        const inherits = (c.data_mode || 'inherit_parent') === 'inherit_parent'
        const isText = c.chart_type === 'text_note'
        const availCols = columnsFor(c)
        // TableColumnSettings expects {column_name, display_name} objects (its
        // dropdowns read c.column_name); columnsFor returns plain strings.
        const tableColumnOptions = availCols.map(col =>
          typeof col === 'string' ? { column_name: col, display_name: col } : col
        )
        const childTcc = Array.isArray(c.table_column_config) ? c.table_column_config : []
        return (
          <div key={c._uid} style={styles.card}>
            <div style={styles.cardHeader}>
              <span style={styles.num}>{idx + 1}</span>
              <i className={`fa ${meta.icon || 'fa-square-o'}`} style={{ color: BLOCK_COLORS[idx % BLOCK_COLORS.length] }} />
              <input
                className="wb-input wb-input--sm"
                placeholder={`${meta.label || c.chart_type} title (optional)`}
                value={c.name || ''}
                onChange={e => update(idx, { name: e.target.value })}
                style={{ flex: 1, minWidth: 120 }}
              />
              {/* Width presets */}
              <span style={{ display: 'inline-flex', gap: 2 }}>
                {WIDTH_PRESETS.map(p => (
                  <button
                    key={p.span}
                    type="button"
                    className={`wb-btn wb-btn--sm ${Number(c.col_span) === p.span ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                    style={{ padding: '2px 7px', fontSize: 11 }}
                    onClick={() => update(idx, { col_span: p.span })}
                    title={`${p.span} of 12 columns`}
                  >
                    {p.label}
                  </button>
                ))}
              </span>
              <Stepper
                label="start"
                value={c.col_start}
                min={1}
                max={13 - Number(c.col_span || 1)}
                onChange={v => update(idx, { col_start: v })}
              />
              {!isText && (
                <span style={{
                  ...styles.badge,
                  background: inherits ? '#ecfdf5' : '#eff6ff',
                  color: inherits ? '#047857' : '#1d4ed8',
                }}>
                  {inherits ? 'Inherit' : 'Own SQL'}
                </span>
              )}
              <button type="button" style={styles.stepBtn} title="Move up"
                onClick={() => moveChild(idx, -1)} disabled={idx === 0}>
                <i className="fa fa-arrow-up" />
              </button>
              <button type="button" style={styles.stepBtn} title="Move down"
                onClick={() => moveChild(idx, +1)} disabled={idx === items.length - 1}>
                <i className="fa fa-arrow-down" />
              </button>
              <button type="button" style={styles.stepBtn} title="Remove block"
                onClick={() => removeChild(idx)}>
                <i className="fa fa-trash-o" />
              </button>
              <button
                type="button"
                className="wb-btn wb-btn--outline wb-btn--sm"
                onClick={() => setExpandedUid(expanded ? null : c._uid)}
              >
                Configure <i className={`fa fa-chevron-${expanded ? 'up' : 'down'} ms-1`} />
              </button>
            </div>

            {expanded && (
              <div style={styles.cardBody}>
                {/* Type + layout advanced */}
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                  <div>
                    <label className="wb-label">Block Type</label>
                    <select
                      className="wb-select"
                      value={c.chart_type}
                      onChange={e => switchType(idx, e.target.value)}
                      title="Switching keeps title, layout, and SQL; type-specific styling is reset."
                    >
                      {COMPOSITE_CHILD_TYPES.map(t => (
                        <option key={t.key} value={t.key}>{t.label}</option>
                      ))}
                    </select>
                  </div>
                  <Stepper label="row start (0=auto)" value={c.row_start} min={0} max={20}
                    onChange={v => update(idx, { row_start: v })} />
                  <Stepper label="row span" value={c.row_span} min={1} max={6}
                    onChange={v => update(idx, { row_span: v })} />
                  <div>
                    <label className="wb-label">Min Height (px)</label>
                    <input
                      type="number"
                      className="wb-input wb-input--sm"
                      style={{ width: 90 }}
                      value={c.min_height_px}
                      onChange={e => update(idx, { min_height_px: Number(e.target.value) || 240 })}
                    />
                  </div>
                  <label className="wb-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <input
                      type="checkbox"
                      checked={c.is_active !== false}
                      onChange={e => update(idx, { is_active: e.target.checked })}
                    />
                    Active
                  </label>
                </div>

                {/* Content alignment — generic, applies to every child type.
                    Stretch/Stretch = original behavior (no styles emitted). */}
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginTop: 6 }}>
                  <div>
                    <label className="wb-label">Vertical Align</label>
                    <select
                      className="wb-select"
                      value={c.content_vertical_align || 'stretch'}
                      onChange={e => update(idx, { content_vertical_align: e.target.value })}
                    >
                      <option value="stretch">Stretch</option>
                      <option value="top">Top</option>
                      <option value="center">Center</option>
                      <option value="bottom">Bottom</option>
                    </select>
                  </div>
                  <div>
                    <label className="wb-label">Horizontal Align</label>
                    <select
                      className="wb-select"
                      value={c.content_horizontal_align || 'stretch'}
                      onChange={e => update(idx, { content_horizontal_align: e.target.value })}
                    >
                      <option value="stretch">Stretch</option>
                      <option value="left">Left</option>
                      <option value="center">Center</option>
                      <option value="right">Right</option>
                    </select>
                  </div>
                  <p className="wb-hint" style={{ fontSize: 11, color: '#94a3b8', margin: 0 }}>
                    Tables work best with Stretch; lists/KPIs/notes can be centered.
                  </p>
                </div>

                {/* Text note body */}
                {isText && (
                  <>
                    <div style={styles.sectionTitle}>Note Text</div>
                    <textarea
                      className="wb-input"
                      rows={3}
                      placeholder="Static note shown in this block…"
                      value={c.text_note_body || ''}
                      onChange={e => update(idx, { text_note_body: e.target.value })}
                    />
                  </>
                )}

                {/* Data (non-text blocks) */}
                {!isText && (
                  <>
                    <div style={styles.sectionTitle}>Data</div>
                    <div className="wb-mode-toggle" style={{ marginBottom: 8 }}>
                      <button
                        type="button"
                        className={`wb-btn wb-btn--sm ${inherits ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                        onClick={() => update(idx, { data_mode: 'inherit_parent', dataModeOverridden: true })}
                      >
                        <i className="fa fa-level-up me-1" /> Inherit Parent
                      </button>
                      <button
                        type="button"
                        className={`wb-btn wb-btn--sm ${!inherits ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                        onClick={() => update(idx, { data_mode: 'own_sql', dataModeOverridden: true })}
                      >
                        <i className="fa fa-code me-1" /> Own SQL
                      </button>
                    </div>

                    {!inherits && (
                      <CustomSqlEditor
                        sql={c.query_sql || ''}
                        xColumn={c.x_column || ''}
                        yColumns={c.y_columns || ''}
                        seriesColumn={c.series_column || ''}
                        schemaSourceId={c.schema_source_id || null}
                        testResult={c._testResult || null}
                        testParams={c._testParams || {}}
                        onUpdate={v => {
                          const changes = {}
                          if (v.sql !== undefined) changes.query_sql = v.sql
                          if (v.xColumn !== undefined) changes.x_column = v.xColumn
                          if (v.yColumns !== undefined) changes.y_columns = v.yColumns
                          if (v.seriesColumn !== undefined) changes.series_column = v.seriesColumn
                          if (v.schemaSourceId !== undefined) changes.schema_source_id = v.schemaSourceId
                          if (v.testResult !== undefined) changes._testResult = v.testResult
                          if (v.testParams !== undefined) changes._testParams = v.testParams
                          update(idx, changes)
                        }}
                        apiBase={apiBase}
                        appContext={appContext}
                        connectionId={connectionId || 'local_pg'}
                        chartType={c.chart_type}
                      />
                    )}

                    {inherits && c.chart_type !== 'smart_table' && (
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: 140 }}>
                          <label className="wb-label">X / Label Column</label>
                          <input
                            className="wb-input wb-input--sm"
                            placeholder={c.chart_type === 'legend_list' ? 'e.g. label' : 'e.g. Date'}
                            value={c.x_column || ''}
                            onChange={e => update(idx, { x_column: e.target.value })}
                          />
                        </div>
                        <div style={{ flex: 2, minWidth: 180 }}>
                          <label className="wb-label">Y / Value Column(s)</label>
                          <input
                            className="wb-input wb-input--sm"
                            placeholder={c.chart_type === 'legend_list' ? 'value[,pct]' : 'comma-separated'}
                            value={c.y_columns || ''}
                            onChange={e => update(idx, { y_columns: e.target.value })}
                          />
                        </div>
                        {['bar', 'line'].includes(c.chart_type) && (
                          <div style={{ flex: 1, minWidth: 140 }}>
                            <label className="wb-label">Series Column</label>
                            <input
                              className="wb-input wb-input--sm"
                              value={c.series_column || ''}
                              onChange={e => update(idx, { series_column: e.target.value })}
                            />
                          </div>
                        )}
                        {['kpi', 'status_kpi', 'kpi_strip'].includes(c.chart_type) && (
                          <div style={{ flex: 1, minWidth: 140 }}>
                            <label className="wb-label">Status Column</label>
                            <input
                              className="wb-input wb-input--sm"
                              value={c.status_column || ''}
                              onChange={e => update(idx, { status_column: e.target.value })}
                            />
                          </div>
                        )}
                        {parentColumns?.length > 0 && (
                          <p className="wb-hint" style={{ flexBasis: '100%', fontSize: 11, color: '#94a3b8', margin: 0 }}>
                            Parent columns: {parentColumns.join(', ')}
                          </p>
                        )}
                      </div>
                    )}

                    {/* KPI extras */}
                    {['kpi', 'status_kpi', 'kpi_strip', 'gauge_kpi'].includes(c.chart_type) && (
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
                        <div>
                          <label className="wb-label">Value Format</label>
                          <select
                            className="wb-select"
                            value={c.kpi_format || 'number'}
                            onChange={e => update(idx, { kpi_format: e.target.value })}
                          >
                            <option value="number">Number</option>
                            <option value="currency">Currency</option>
                            <option value="percent">Percent</option>
                            <option value="decimal">Decimal</option>
                          </select>
                        </div>
                        <div>
                          <label className="wb-label">Prefix</label>
                          <input className="wb-input wb-input--sm" style={{ width: 70 }}
                            value={c.kpi_prefix || ''}
                            onChange={e => update(idx, { kpi_prefix: e.target.value })} />
                        </div>
                        <div>
                          <label className="wb-label">Suffix</label>
                          <input className="wb-input wb-input--sm" style={{ width: 70 }}
                            value={c.kpi_suffix || ''}
                            onChange={e => update(idx, { kpi_suffix: e.target.value })} />
                        </div>
                        <div>
                          <label className="wb-label">Metric Direction</label>
                          <select
                            className="wb-select"
                            value={c.metric_direction || ''}
                            onChange={e => update(idx, { metric_direction: e.target.value })}
                          >
                            <option value="">Default</option>
                            <option value="higher_better">Higher is Better</option>
                            <option value="lower_better">Lower is Better</option>
                            <option value="neutral">Neutral</option>
                          </select>
                        </div>
                      </div>
                    )}

                    {/* Style — existing pickers per type */}
                    {['donut', 'line', 'gauge', 'kpi', 'status_kpi', 'kpi_strip'].includes(c.chart_type) && (
                      <div style={styles.sectionTitle}>Style</div>
                    )}
                    {c.chart_type === 'donut' && (
                      <DonutStylePicker
                        selectedStyle={c.visual_config?.donut_style || 'standard'}
                        onStyleChange={v => update(idx, { visual_config: { ...(c.visual_config || {}), donut_style: v } })}
                        visualConfig={c.visual_config || {}}
                        onVisualConfigChange={(key, value) =>
                          update(idx, { visual_config: { ...(c.visual_config || {}), [key]: value } })}
                      />
                    )}
                    {c.chart_type === 'line' && (
                      <LineStylePicker
                        selectedStyle={c.visual_config?.line_style || 'basic'}
                        onStyleChange={v => update(idx, { visual_config: { ...(c.visual_config || {}), line_style: v } })}
                        visualConfig={c.visual_config || {}}
                        onVisualConfigChange={(key, value) =>
                          update(idx, { visual_config: { ...(c.visual_config || {}), [key]: value } })}
                      />
                    )}
                    {c.chart_type === 'gauge' && (
                      <GaugeStylePicker
                        selectedStyle={c.visual_config?.gauge_style || 'standard'}
                        onStyleChange={v => update(idx, { visual_config: { ...(c.visual_config || {}), gauge_style: v } })}
                        visualConfig={c.visual_config || {}}
                        onVisualConfigChange={(key, value) =>
                          update(idx, { visual_config: { ...(c.visual_config || {}), [key]: value } })}
                      />
                    )}
                    {['kpi', 'status_kpi', 'kpi_strip'].includes(c.chart_type) && (
                      <KpiStylePicker
                        selectedStyle={c.visual_config?.kpi_style || 'stat_card'}
                        onStyleChange={v => update(idx, { visual_config: { ...(c.visual_config || {}), kpi_style: v } })}
                        visualConfig={c.visual_config || {}}
                        onVisualConfigChange={(key, value) =>
                          update(idx, { visual_config: { ...(c.visual_config || {}), [key]: value } })}
                      />
                    )}

                    {/* Table children: per-column config (AG Grid renderers incl. dualValue) */}
                    {c.chart_type === 'table' && (
                      <>
                        <div style={styles.sectionTitle}>Table Columns</div>
                        {childTcc.map((col, colIdx) => (
                          <div key={colIdx} style={{ border: '1px solid #f1f5f9', borderRadius: 6, marginBottom: 6 }}>
                            <div
                              style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', cursor: 'pointer' }}
                              onClick={() => setSelectedColIdx({
                                ...selectedColIdx,
                                [c._uid]: selectedColIdx[c._uid] === colIdx ? null : colIdx,
                              })}
                            >
                              <i className="fa fa-columns" style={{ color: '#94a3b8' }} />
                              <strong style={{ fontSize: 12 }}>{col.headerName || col.field || `Column ${colIdx + 1}`}</strong>
                              <span style={{ fontSize: 11, color: '#94a3b8' }}>{col.field}</span>
                              <span style={{ flex: 1 }} />
                              <button
                                type="button" style={styles.stepBtn} title="Remove column"
                                onClick={e => {
                                  e.stopPropagation()
                                  update(idx, { table_column_config: childTcc.filter((_, i) => i !== colIdx) })
                                }}
                              >
                                <i className="fa fa-times" />
                              </button>
                            </div>
                            {selectedColIdx[c._uid] === colIdx && (
                              <TableColumnSettings
                                column={col}
                                allColumns={tableColumnOptions}
                                onChange={changes => {
                                  const nextCols = [...childTcc]
                                  nextCols[colIdx] = { ...nextCols[colIdx], ...changes }
                                  update(idx, { table_column_config: nextCols })
                                }}
                              />
                            )}
                          </div>
                        ))}
                        <button
                          type="button"
                          className="wb-btn wb-btn--outline wb-btn--sm"
                          onClick={() => update(idx, {
                            table_column_config: [
                              ...childTcc,
                              // Insert the field NAME (string), never the option object
                              { field: tableColumnOptions[childTcc.length]?.column_name || '', headerName: '', flex: 1 },
                            ],
                          })}
                        >
                          <i className="fa fa-plus me-1" /> Add Column
                        </button>
                      </>
                    )}

                    {/* Smart Table children: SAME per-column recipe cards as the
                        standalone Smart Table configurator (ColumnCard reused —
                        metric_with_delta, badges, composite cells, etc.) */}
                    {c.chart_type === 'smart_table' && (() => {
                      const stc = c.smart_table_config || { columns: [], table: {} }
                      const stCols = stc.columns || []
                      const setStCols = nextCols =>
                        update(idx, { smart_table_config: { ...stc, columns: nextCols } })
                      return (
                        <>
                          <div style={styles.sectionTitle}>Smart Table Columns</div>
                          {availCols.length > 0 && (
                            <p className="wb-hint" style={{ fontSize: 11, color: '#94a3b8', margin: '0 0 6px' }}>
                              Available fields: {availCols.join(', ')}
                            </p>
                          )}
                          {stCols.map((col, colIdx) => (
                            <ColumnCard
                              key={colIdx}
                              idx={colIdx}
                              col={col}
                              availableColumns={availCols}
                              isFirst={colIdx === 0}
                              isLast={colIdx === stCols.length - 1}
                              onChangeColumn={partial => {
                                const next = [...stCols]
                                next[colIdx] = { ...next[colIdx], ...partial }
                                setStCols(next)
                              }}
                              onChangeCell={partial => {
                                const next = [...stCols]
                                next[colIdx] = {
                                  ...next[colIdx],
                                  cell: { ...(next[colIdx].cell || { type: 'text' }), ...partial },
                                }
                                setStCols(next)
                              }}
                              onReplaceCell={newCell => {
                                const next = [...stCols]
                                next[colIdx] = { ...next[colIdx], cell: newCell }
                                setStCols(next)
                              }}
                              onMove={dir => {
                                const to = colIdx + dir
                                if (to < 0 || to >= stCols.length) return
                                const next = [...stCols]
                                const [moved] = next.splice(colIdx, 1)
                                next.splice(to, 0, moved)
                                setStCols(next)
                              }}
                              onDuplicate={() => {
                                const next = [...stCols]
                                next.splice(colIdx + 1, 0,
                                  JSON.parse(JSON.stringify(stCols[colIdx])))
                                setStCols(next)
                              }}
                              onRemove={() => setStCols(stCols.filter((_, i) => i !== colIdx))}
                            />
                          ))}
                          <button
                            type="button"
                            className="wb-btn wb-btn--outline wb-btn--sm"
                            disabled={availCols.length === 0}
                            title={availCols.length === 0
                              ? 'Run the parent (or own-SQL) Test Query first so fields are known'
                              : ''}
                            onClick={() => setStCols([
                              ...stCols,
                              emptyColumn(availCols[stCols.length] || availCols[0] || ''),
                            ])}
                          >
                            <i className="fa fa-plus me-1" /> Add Column
                          </button>
                        </>
                      )
                    })()}

                    {/* Custom colors — exact donut/legend sync uses the same JSON */}
                    {['donut', 'pie', 'bar', 'line', 'legend_list'].includes(c.chart_type) && (
                      <>
                        <div style={styles.sectionTitle}>Custom Colors (optional)</div>
                        <input
                          className="wb-input wb-input--sm"
                          placeholder='e.g. ["#1a7f37","#7fb800","#f7c948","#f08c00","#d64545"]'
                          value={c.color_custom_json || ''}
                          onChange={e => update(idx, { color_custom_json: e.target.value })}
                        />
                        <p className="wb-hint" style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>
                          JSON array of hex colors. Use the SAME list on a donut and its legend list
                          so dot colors match slice colors exactly.
                        </p>
                      </>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
