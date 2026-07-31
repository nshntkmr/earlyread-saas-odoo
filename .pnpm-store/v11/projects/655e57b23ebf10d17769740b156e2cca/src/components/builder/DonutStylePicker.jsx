import React from 'react'

/* ── Donut variant definitions ─────────────────────────────────── */

const DONUT_STYLES = [
  {
    key: 'standard',
    label: 'Standard Donut',
    desc: 'Payer mix, source mix proportions',
  },
  {
    key: 'label_center',
    label: 'Center Label',
    desc: 'Hover shows name in center hole',
  },
  {
    key: 'rounded',
    label: 'Rounded Corners',
    desc: 'Rounded slice edges with gaps',
  },
  {
    key: 'semi',
    label: 'Half Donut',
    desc: 'Semicircle for binary splits',
  },
  {
    key: 'rose',
    label: 'Rose / Nightingale',
    desc: 'Variable radius by value',
  },
  {
    key: 'nested',
    label: 'Nested (2 rings)',
    desc: 'Parent/child hierarchy',
  },
  {
    key: 'multi_ring',
    label: 'Multi-Ring Comparison',
    desc: 'Side-by-side ring groups',
  },
]

/* ── SVG icon components (40x40 stroke-based) ─────────────────── */

function IconStandard({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="14" stroke={color} strokeWidth="5" />
    </svg>
  )
}

function IconLabelCenter({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="14" stroke={color} strokeWidth="5" />
      <text x="20" y="24" textAnchor="middle" fontSize="11" fontWeight="600" fill={color}>%</text>
    </svg>
  )
}

function IconRounded({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <path
        d="M20 6 A14 14 0 1 1 8.2 28"
        stroke={color} strokeWidth="5" strokeLinecap="round" fill="none"
      />
    </svg>
  )
}

function IconSemi({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <path
        d="M6 24 A14 14 0 0 1 34 24"
        stroke={color} strokeWidth="5" strokeLinecap="round" fill="none"
      />
    </svg>
  )
}

function IconRose({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="14" stroke={color} strokeWidth="2" strokeDasharray="4 3" />
      <path d="M20 6 L20 12" stroke={color} strokeWidth="3" strokeLinecap="round" />
      <path d="M34 20 L28 20" stroke={color} strokeWidth="5" strokeLinecap="round" />
      <path d="M20 34 L20 26" stroke={color} strokeWidth="4" strokeLinecap="round" />
      <path d="M6 20 L13 20" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

function IconNested({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <circle cx="20" cy="20" r="15" stroke={color} strokeWidth="3" />
      <circle cx="20" cy="20" r="9" stroke={color} strokeWidth="3" />
    </svg>
  )
}

function IconMultiRing({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <circle cx="14" cy="20" r="8" stroke={color} strokeWidth="3.5" />
      <circle cx="27" cy="20" r="8" stroke={color} strokeWidth="3.5" />
    </svg>
  )
}

const ICON_MAP = {
  standard: IconStandard,
  label_center: IconLabelCenter,
  rounded: IconRounded,
  semi: IconSemi,
  rose: IconRose,
  nested: IconNested,
  multi_ring: IconMultiRing,
}

/* ── Inline styles ─────────────────────────────────────────────── */

const styles = {
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: 10,
    marginTop: 8,
  },
  card: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    background: '#fff',
    cursor: 'pointer',
    textAlign: 'left',
    transition: 'border-color .15s, box-shadow .15s',
  },
  cardActive: {
    borderColor: '#0d9488',
    boxShadow: '0 0 0 2px rgba(13,148,136,.25)',
  },
  cardTextWrap: {
    display: 'flex',
    flexDirection: 'column',
    minWidth: 0,
  },
  cardName: {
    fontWeight: 600,
    fontSize: 13,
    color: '#1f2937',
    lineHeight: 1.3,
  },
  cardDesc: {
    fontSize: 11,
    color: '#6b7280',
    lineHeight: 1.3,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: 600,
    color: '#6b7280',
    textTransform: 'uppercase',
    letterSpacing: '.05em',
    marginTop: 18,
    marginBottom: 8,
    borderBottom: '1px solid #e5e7eb',
    paddingBottom: 4,
  },
}

/* ── Legend position / label position / sort options ────────────── */

const LABEL_POSITIONS = [
  { value: 'outside', label: 'Outside' },
  { value: 'inside', label: 'Inside' },
]

const LEGEND_POSITIONS = [
  { value: 'bottom', label: 'Bottom' },
  { value: 'top', label: 'Top' },
  { value: 'left', label: 'Left' },
  { value: 'right', label: 'Right' },
  { value: 'none', label: 'Hidden' },
]

const SORT_OPTIONS = [
  { value: 'none', label: 'SQL Order (default)' },
  { value: 'value_desc', label: 'Largest First' },
  { value: 'value_asc', label: 'Smallest First' },
]

const LABEL_FORMATS = [
  { value: 'name', label: 'Name only' },
  { value: 'name_value', label: 'Name + Value' },
  { value: 'name_percent', label: 'Name + Percentage' },
  { value: 'name_value_percent', label: 'Name + Value + Percentage' },
]

const CENTER_MODES = [
  { value: 'none', label: 'None' },
  { value: 'auto_total', label: 'Auto Total (computed from slices)' },
  { value: 'static', label: 'Static Text' },
]

const ROSE_TYPES = [
  { value: 'area', label: 'Area' },
  { value: 'radius', label: 'Radius' },
]

/* ── Helpers ───────────────────────────────────────────────────── */

function cfgVal(visualConfig, key, fallback) {
  if (visualConfig && key in visualConfig) return visualConfig[key]
  return fallback
}

/* ── Component ─────────────────────────────────────────────────── */

/**
 * Donut style sub-panel shown inside ChartTypePicker when chart type is "donut".
 *
 * Props:
 *   selectedStyle          — current donut_style value (default 'standard')
 *   onStyleChange(style)   — callback when admin clicks a variant
 *   visualConfig           — object with current flag values
 *   onVisualConfigChange(key, value) — callback for config value changes
 */
export default function DonutStylePicker({
  selectedStyle = 'standard',
  onStyleChange,
  visualConfig = {},
  onVisualConfigChange,
}) {
  const style = selectedStyle || 'standard'

  const handleCfg = (key, value) => {
    if (onVisualConfigChange) onVisualConfigChange(key, value)
  }

  /* Which variant-specific fields to show */
  const showRadii = ['standard', 'label_center', 'rounded', 'rose', 'multi_ring'].includes(style)
  const showCenterText = ['standard', 'label_center', 'rounded', 'multi_ring'].includes(style)
  const showRoseType = style === 'rose'
  const showNested = style === 'nested'

  return (
    <div>
      <h4 className="wb-label" style={{ marginBottom: 4 }}>Donut Style</h4>

      {/* ── Variant grid ─────────────────────────────────── */}
      <div style={styles.grid}>
        {DONUT_STYLES.map(ds => {
          const active = style === ds.key
          const color = active ? '#0d9488' : '#9ca3af'
          const Icon = ICON_MAP[ds.key]
          return (
            <button
              key={ds.key}
              type="button"
              className="wb-chart-card"
              style={{
                ...styles.card,
                ...(active ? styles.cardActive : {}),
              }}
              onClick={() => onStyleChange && onStyleChange(ds.key)}
            >
              {Icon && <Icon color={color} />}
              <div style={styles.cardTextWrap}>
                <span style={styles.cardName}>{ds.label}</span>
                <span style={styles.cardDesc}>{ds.desc}</span>
              </div>
            </button>
          )
        })}
      </div>

      {/* ── Variant-specific settings ────────────────────── */}
      {(showRadii || showCenterText || showRoseType || showNested) && (
        <>
          <div style={styles.sectionTitle}>Variant Settings</div>

          {showRoseType && (
            <div className="wb-field-row">
              <label className="wb-field-label">Rose Type</label>
              <select
                className="wb-select"
                value={cfgVal(visualConfig, 'rose_type', 'area')}
                onChange={e => handleCfg('rose_type', e.target.value)}
              >
                {ROSE_TYPES.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          )}

          {showRadii && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Inner Radius</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. 40%"
                  value={cfgVal(visualConfig, 'inner_radius', '')}
                  onChange={e => handleCfg('inner_radius', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Outer Radius</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. 75%"
                  value={cfgVal(visualConfig, 'outer_radius', '')}
                  onChange={e => handleCfg('outer_radius', e.target.value)}
                />
              </div>
            </>
          )}

          {showCenterText && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Center Display</label>
                <select
                  className="wb-select"
                  value={cfgVal(visualConfig, 'center_mode', 'none')}
                  onChange={e => handleCfg('center_mode', e.target.value)}
                >
                  {CENTER_MODES.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {cfgVal(visualConfig, 'center_mode', 'none') === 'auto_total' && (
                <div className="wb-field-row">
                  <label className="wb-field-label">Center Label</label>
                  <input
                    type="text"
                    className="wb-input wb-input--sm"
                    placeholder='e.g. "Total" or "Admits"'
                    value={cfgVal(visualConfig, 'center_text', '')}
                    onChange={e => handleCfg('center_text', e.target.value)}
                  />
                </div>
              )}

              {cfgVal(visualConfig, 'center_mode', 'none') === 'static' && (
                <div className="wb-field-row">
                  <label className="wb-field-label">Center Static Text</label>
                  <input
                    type="text"
                    className="wb-input wb-input--sm"
                    placeholder='e.g. "Market Share" or "74%"'
                    value={cfgVal(visualConfig, 'center_static_text', '')}
                    onChange={e => handleCfg('center_static_text', e.target.value)}
                  />
                </div>
              )}
            </>
          )}

          {showNested && (
            <>
              {/* ── Inner Ring ── */}
              <div style={{ ...styles.sectionTitle, fontSize: 11, marginTop: 12, color: '#6b7280' }}>
                Inner Ring
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Radius Start</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. 0"
                  value={cfgVal(visualConfig, 'nested_inner_radius_start', '')}
                  onChange={e => handleCfg('nested_inner_radius_start', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Radius End</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. 30"
                  value={cfgVal(visualConfig, 'nested_inner_radius_end', '')}
                  onChange={e => handleCfg('nested_inner_radius_end', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Label Position</label>
                <select
                  className="wb-select"
                  value={cfgVal(visualConfig, 'nested_inner_label_pos', 'inner')}
                  onChange={e => handleCfg('nested_inner_label_pos', e.target.value)}
                >
                  <option value="inner">Inner</option>
                  <option value="inside">Inside</option>
                  <option value="outside">Outside</option>
                </select>
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Label Format</label>
                <select
                  className="wb-select"
                  value={cfgVal(visualConfig, 'nested_inner_label_format', 'name')}
                  onChange={e => handleCfg('nested_inner_label_format', e.target.value)}
                >
                  {LABEL_FORMATS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {/* ── Outer Ring ── */}
              <div style={{ ...styles.sectionTitle, fontSize: 11, marginTop: 12, color: '#6b7280' }}>
                Outer Ring
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Radius Start</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. 40"
                  value={cfgVal(visualConfig, 'nested_outer_radius_start', '')}
                  onChange={e => handleCfg('nested_outer_radius_start', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Radius End</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. 65"
                  value={cfgVal(visualConfig, 'nested_outer_radius_end', '')}
                  onChange={e => handleCfg('nested_outer_radius_end', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Label Position</label>
                <select
                  className="wb-select"
                  value={cfgVal(visualConfig, 'nested_outer_label_pos', 'outside')}
                  onChange={e => handleCfg('nested_outer_label_pos', e.target.value)}
                >
                  <option value="outside">Outside</option>
                  <option value="inside">Inside</option>
                  <option value="inner">Inner</option>
                </select>
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Label Format</label>
                <select
                  className="wb-select"
                  value={cfgVal(visualConfig, 'nested_outer_label_format', 'name')}
                  onChange={e => handleCfg('nested_outer_label_format', e.target.value)}
                >
                  {LABEL_FORMATS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
            </>
          )}
        </>
      )}

      {/* ── Common settings ──────────────────────────────── */}
      <div style={styles.sectionTitle}>Common Settings</div>

      <div className="wb-toggle-group">
        <label className="wb-toggle-label">
          <input
            type="checkbox"
            checked={cfgVal(visualConfig, 'show_labels', true)}
            onChange={e => handleCfg('show_labels', e.target.checked)}
          />
          Show Labels
        </label>
      </div>

      {cfgVal(visualConfig, 'show_labels', true) && (
        <div className="wb-field-row">
          <label className="wb-field-label">Label Position</label>
          <select
            className="wb-select"
            value={cfgVal(visualConfig, 'label_position', 'outside')}
            onChange={e => handleCfg('label_position', e.target.value)}
          >
            {LABEL_POSITIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      {cfgVal(visualConfig, 'show_labels', true) && (
        <div className="wb-field-row">
          <label className="wb-field-label">Label Format</label>
          <select
            className="wb-select"
            value={cfgVal(visualConfig, 'label_format', 'name')}
            onChange={e => handleCfg('label_format', e.target.value)}
          >
            {LABEL_FORMATS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      <div className="wb-field-row">
        <label className="wb-field-label">Legend Position</label>
        <select
          className="wb-select"
          value={cfgVal(visualConfig, 'legend_position', 'bottom')}
          onChange={e => handleCfg('legend_position', e.target.value)}
        >
          {LEGEND_POSITIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      <div className="wb-field-row">
        <label className="wb-field-label">Sort Slices</label>
        <select
          className="wb-select"
          value={cfgVal(visualConfig, 'sort', 'none')}
          onChange={e => handleCfg('sort', e.target.value)}
        >
          {SORT_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      <div className="wb-field-row">
        <label className="wb-field-label">Max Slices</label>
        <input
          type="number"
          className="wb-input wb-input--sm"
          min="0"
          placeholder="0 = no limit"
          value={cfgVal(visualConfig, 'limit', '')}
          onChange={e => {
            const v = e.target.value
            handleCfg('limit', v === '' ? null : Number(v))
          }}
        />
      </div>
    </div>
  )
}
