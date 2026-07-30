import React, { useMemo } from 'react'

/**
 * MasterRowLayoutStep
 *
 * Visual layout builder for ranked_detail_list widgets. Admin toggles each
 * element on/off and picks the SQL column that feeds it. No raw JSON.
 *
 * Also used inside DetailConfigStep for the Sub-List section — the schema
 * is identical so admins learn one pattern.
 *
 * Props:
 *   config        — the current layout config (v2 ranked_master_config shape)
 *   onChange      — (partial) => void  — shallow-merges into config
 *   columns       — ['col1', 'col2', ...]  (from SQL test result)
 *   sampleRow     — { col: value, ... }  (first row of SQL test result, optional)
 *   title         — section title (default 'Master Row Layout')
 *   hideActions   — hide navigation/external/expand toggles (for sub-list use)
 */
export default function MasterRowLayoutStep({
  config = {},
  onChange,
  columns = [],
  sampleRow = null,
  title = 'Master Row Layout',
  hideActions = false,
}) {
  const cfg = config || {}

  // Helper: update one sub-section (e.g., badge) while leaving others intact
  const updateSection = (key, partial) => {
    const current = cfg[key] || {}
    onChange({ [key]: { ...current, ...partial } })
  }

  // Helper: dropdown of SQL columns
  const ColumnPicker = ({ value, onChange: setVal, placeholder = 'Pick column…' }) => (
    <select
      className="wb-select wb-select--sm"
      value={value || ''}
      onChange={e => setVal(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {columns.map(c => (
        <option key={c} value={c}>{c}</option>
      ))}
    </select>
  )

  // Helper: checkbox row
  const ToggleRow = ({ checked, onToggle, label, children }) => (
    <div className="wb-field-group" style={{ marginBottom: 12 }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500, marginBottom: 6 }}>
        <input
          type="checkbox"
          checked={!!checked}
          onChange={e => onToggle(e.target.checked)}
        />
        {label}
      </label>
      {checked && (
        <div style={{ paddingLeft: 24 }}>{children}</div>
      )}
    </div>
  )

  // Live preview (compact, uses sampleRow if available)
  const preview = useMemo(() => {
    if (!sampleRow) return null
    const rankCfg = cfg.rank || {}
    const nameCol = cfg.name?.column
    const badgeCfg = cfg.badge || {}
    const subtitleCfg = cfg.subtitle || {}
    const sparkCfg = cfg.sparkline || {}
    const primaryCfg = cfg.primaryMetric || {}
    const secondaryCfg = cfg.secondaryMetric || {}
    const navCfg = cfg.navigationArrow || {}
    const expandCfg = cfg.expandChevron || {}
    return (
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 14px', border: '1px solid #e2e8f0',
          borderRadius: 6, background: '#fafbfc', marginBottom: 16,
        }}
      >
        {rankCfg.enabled !== false && (
          <div style={{ width: 24, color: '#64748b', fontWeight: 500 }}>1</div>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontWeight: 600 }}>
              {nameCol ? String(sampleRow[nameCol] ?? '') : '<name>'}
            </span>
            {badgeCfg.enabled && (
              <span
                style={{
                  padding: '1px 6px', borderRadius: 3, background: badgeCfg.color || '#dbeafe',
                  color: '#1e40af', fontSize: 10, fontWeight: 600,
                  textTransform: 'uppercase',
                }}
              >
                {badgeCfg.source === 'static'
                  ? (badgeCfg.text || 'BADGE')
                  : (badgeCfg.column ? String(sampleRow[badgeCfg.column] ?? '') : 'BADGE')}
              </span>
            )}
          </div>
          {subtitleCfg.enabled && subtitleCfg.column && (
            <div style={{ fontSize: 11, color: '#6b7280' }}>
              {String(sampleRow[subtitleCfg.column] ?? '')}
            </div>
          )}
        </div>
        {sparkCfg.enabled && <span style={{ color: '#10b981', fontSize: 14 }}>╱╲</span>}
        {primaryCfg.column && (
          <strong>{String(sampleRow[primaryCfg.column] ?? '')}</strong>
        )}
        {secondaryCfg.enabled && secondaryCfg.column && (
          <span style={{ color: '#6b7280', fontSize: 12 }}>
            {String(sampleRow[secondaryCfg.column] ?? '')}
          </span>
        )}
        {!hideActions && navCfg.enabled && <i className="fa fa-arrow-right" style={{ color: '#94a3b8' }} />}
        {!hideActions && expandCfg.enabled && <i className="fa fa-chevron-down" style={{ color: '#94a3b8' }} />}
      </div>
    )
  }, [cfg, sampleRow, hideActions])

  return (
    <div className="wb-master-row-layout">
      <h3 className="wb-step-title">{title}</h3>
      <p className="wb-step-hint">
        Toggle each element on/off and pick the SQL column that feeds it.
        Required: Primary Name and Primary Metric.
      </p>

      {preview}

      {/* ── Rank ─────────────────────────────── */}
      <ToggleRow
        label="Rank number"
        checked={cfg.rank?.enabled !== false}
        onToggle={v => updateSection('rank', { enabled: v })}
      >
        <label style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          Style:
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <input
              type="radio"
              checked={(cfg.rank?.style || 'number') === 'number'}
              onChange={() => updateSection('rank', { style: 'number' })}
            />
            Numbers (1, 2, 3…)
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            <input
              type="radio"
              checked={cfg.rank?.style === 'medal'}
              onChange={() => updateSection('rank', { style: 'medal' })}
            />
            Medals (🥇🥈🥉 top 3)
          </label>
        </label>
      </ToggleRow>

      {/* ── Primary Name (required) ─────────── */}
      <div className="wb-field-group" style={{ marginBottom: 12 }}>
        <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>
          Primary Name <span style={{ color: '#ef4444' }}>*</span>
        </label>
        <div style={{ paddingLeft: 24 }}>
          <ColumnPicker
            value={cfg.name?.column}
            onChange={v => onChange({ name: { column: v } })}
            placeholder="Pick name column…"
          />
        </div>
      </div>

      {/* ── Type Badge ──────────────────────── */}
      <ToggleRow
        label="Type badge"
        checked={!!cfg.badge?.enabled}
        onToggle={v => updateSection('badge', { enabled: v })}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            Source:
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <input
                type="radio"
                checked={(cfg.badge?.source || 'column') === 'column'}
                onChange={() => updateSection('badge', { source: 'column' })}
              />
              From SQL column
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <input
                type="radio"
                checked={cfg.badge?.source === 'static'}
                onChange={() => updateSection('badge', { source: 'static' })}
              />
              Static text
            </label>
          </label>
          {(cfg.badge?.source || 'column') === 'column' ? (
            <ColumnPicker
              value={cfg.badge?.column}
              onChange={v => updateSection('badge', { column: v })}
              placeholder="Pick badge column…"
            />
          ) : (
            <input
              className="wb-input wb-input--sm"
              placeholder="e.g. HOSPITAL"
              value={cfg.badge?.text || ''}
              onChange={e => updateSection('badge', { text: e.target.value })}
            />
          )}
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Color:
            <input
              type="color"
              value={cfg.badge?.color || '#dbeafe'}
              onChange={e => updateSection('badge', { color: e.target.value })}
            />
          </label>
        </div>
      </ToggleRow>

      {/* ── Subtitle ────────────────────────── */}
      <ToggleRow
        label="Subtitle line"
        checked={!!cfg.subtitle?.enabled}
        onToggle={v => updateSection('subtitle', { enabled: v })}
      >
        <ColumnPicker
          value={cfg.subtitle?.column}
          onChange={v => updateSection('subtitle', { column: v })}
          placeholder="Pick subtitle column…"
        />
        <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
          Tip: in your SQL, use <code>CONCAT(...)</code> to combine fields into one string
          (e.g. <code>{'CONCAT(\'CCN \', ccn, \' · \', city)'}</code>).
        </div>
      </ToggleRow>

      {/* ── Sparkline ───────────────────────── */}
      <ToggleRow
        label="Sparkline"
        checked={!!cfg.sparkline?.enabled}
        onToggle={v => updateSection('sparkline', { enabled: v })}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <ColumnPicker
            value={cfg.sparkline?.column}
            onChange={v => updateSection('sparkline', { column: v })}
            placeholder="Pick sparkline column (JSON array)…"
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Variant:
            <select
              className="wb-select wb-select--sm"
              value={cfg.sparkline?.variant || 'line'}
              onChange={e => updateSection('sparkline', { variant: e.target.value })}
            >
              <option value="line">Line</option>
              <option value="bar">Bar</option>
              <option value="area">Area</option>
              <option value="winloss">Win / Loss</option>
              <option value="bullet">Bullet</option>
            </select>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Color:
            <select
              className="wb-select wb-select--sm"
              value={cfg.sparkline?.color || 'auto'}
              onChange={e => updateSection('sparkline', { color: e.target.value })}
            >
              <option value="auto">Auto (green up / red down)</option>
              <option value="fixed">Fixed color</option>
            </select>
            {cfg.sparkline?.color === 'fixed' && (
              <input
                type="color"
                value={cfg.sparkline?.fixedColor || '#0d9488'}
                onChange={e => updateSection('sparkline', { fixedColor: e.target.value, color: e.target.value })}
              />
            )}
          </label>
        </div>
      </ToggleRow>

      {/* ── Inline Mini-Chart ───────────────── */}
      <ToggleRow
        label="Inline mini-chart (bar / line / KPI)"
        checked={!!cfg.inlineChart?.enabled}
        onToggle={v => updateSection('inlineChart', { enabled: v })}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <ColumnPicker
            value={cfg.inlineChart?.column}
            onChange={v => updateSection('inlineChart', { column: v })}
            placeholder="Pick data column…"
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Type:
            <select
              className="wb-select wb-select--sm"
              value={cfg.inlineChart?.type || 'bar'}
              onChange={e => updateSection('inlineChart', { type: e.target.value })}
            >
              <option value="bar">Bar</option>
              <option value="line">Line</option>
              <option value="kpi">KPI</option>
            </select>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Size:
            <select
              className="wb-select wb-select--sm"
              value={cfg.inlineChart?.size || 'small'}
              onChange={e => updateSection('inlineChart', { size: e.target.value })}
            >
              <option value="small">Small (80px)</option>
              <option value="medium">Medium (150px)</option>
            </select>
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            Color:
            <input
              type="color"
              value={cfg.inlineChart?.color || '#0d9488'}
              onChange={e => updateSection('inlineChart', { color: e.target.value })}
            />
          </label>
        </div>
      </ToggleRow>

      {/* ── Primary Metric (required) ──────── */}
      <div className="wb-field-group" style={{ marginBottom: 12 }}>
        <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>
          Primary Metric <span style={{ color: '#ef4444' }}>*</span>
        </label>
        <div style={{ paddingLeft: 24, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <ColumnPicker
            value={cfg.primaryMetric?.column}
            onChange={v => updateSection('primaryMetric', { column: v })}
            placeholder="Pick metric column…"
          />
          <MetricFormatControls
            value={cfg.primaryMetric}
            onChange={partial => updateSection('primaryMetric', partial)}
          />
        </div>
      </div>

      {/* ── Secondary Metric ──────────────── */}
      <ToggleRow
        label="Secondary metric"
        checked={!!cfg.secondaryMetric?.enabled}
        onToggle={v => updateSection('secondaryMetric', { enabled: v })}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <ColumnPicker
            value={cfg.secondaryMetric?.column}
            onChange={v => updateSection('secondaryMetric', { column: v })}
            placeholder="Pick secondary column…"
          />
          <MetricFormatControls
            value={cfg.secondaryMetric}
            onChange={partial => updateSection('secondaryMetric', partial)}
            defaultFormat="percentage"
          />
        </div>
      </ToggleRow>

      {/* ── Actions (navigation / external / expand) ────── */}
      {!hideActions && (
        <div style={{ marginTop: 16, padding: 12, background: '#f8fafc', borderRadius: 6 }}>
          <div style={{ fontWeight: 500, marginBottom: 8 }}>Row actions</div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <input
              type="checkbox"
              checked={!!cfg.navigationArrow?.enabled}
              onChange={e => updateSection('navigationArrow', { enabled: e.target.checked })}
            />
            Navigation arrow (→) — configure target in next step
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <input
              type="checkbox"
              checked={!!cfg.externalLink?.enabled}
              onChange={e => updateSection('externalLink', { enabled: e.target.checked })}
            />
            External link (🔗) — configure URL in next step
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={cfg.expandChevron?.enabled !== false}
              onChange={e => updateSection('expandChevron', { enabled: e.target.checked })}
            />
            Expand chevron (∨) — enables detail panel configuration
          </label>
        </div>
      )}
    </div>
  )
}

// ── Metric format controls (shared by primary + secondary) ─────────────
function MetricFormatControls({ value = {}, onChange, defaultFormat = 'number' }) {
  const fmt = value.format || defaultFormat
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        Format:
        <select
          className="wb-select wb-select--sm"
          value={fmt}
          onChange={e => onChange({ format: e.target.value })}
        >
          <option value="number">Number</option>
          <option value="percentage">Percentage</option>
          <option value="currency">Currency</option>
          <option value="decimal">Decimal</option>
        </select>
      </label>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        Decimals:
        <input
          type="number"
          className="wb-input wb-input--xs"
          style={{ width: 48 }}
          min={0} max={4}
          value={value.decimals ?? 0}
          onChange={e => onChange({ decimals: Number(e.target.value) })}
        />
      </label>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        Prefix:
        <input
          type="text"
          className="wb-input wb-input--xs"
          style={{ width: 50 }}
          value={value.prefix || ''}
          onChange={e => onChange({ prefix: e.target.value })}
        />
      </label>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        Suffix:
        <input
          type="text"
          className="wb-input wb-input--xs"
          style={{ width: 50 }}
          value={value.suffix || ''}
          onChange={e => onChange({ suffix: e.target.value })}
        />
      </label>
    </div>
  )
}
