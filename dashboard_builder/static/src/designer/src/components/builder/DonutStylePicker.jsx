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
  { value: 'none', label: 'None (data order)' },
  { value: 'desc', label: 'Descending' },
  { value: 'asc', label: 'Ascending' },
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
  const showRadii = ['standard', 'label_center', 'rounded', 'rose'].includes(style)
  const showCenterText = ['standard', 'label_center', 'rounded'].includes(style)
  const showRoseType = style === 'rose'

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
      {(showRadii || showCenterText || showRoseType) && (
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
            <div className="wb-field-row">
              <label className="wb-field-label">Center Static Text</label>
              <input
                type="text"
                className="wb-input wb-input--sm"
                placeholder="e.g. Total"
                value={cfgVal(visualConfig, 'center_text', '')}
                onChange={e => handleCfg('center_text', e.target.value)}
              />
            </div>
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

      <div className="wb-toggle-group">
        <label className="wb-toggle-label">
          <input
            type="checkbox"
            checked={cfgVal(visualConfig, 'show_percentage', true)}
            onChange={e => handleCfg('show_percentage', e.target.checked)}
          />
          Show Percentage
        </label>
      </div>

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
          value={cfgVal(visualConfig, 'sort_slices', 'none')}
          onChange={e => handleCfg('sort_slices', e.target.value)}
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
          value={cfgVal(visualConfig, 'max_slices', '')}
          onChange={e => {
            const v = e.target.value
            handleCfg('max_slices', v === '' ? null : Number(v))
          }}
        />
      </div>
    </div>
  )
}
