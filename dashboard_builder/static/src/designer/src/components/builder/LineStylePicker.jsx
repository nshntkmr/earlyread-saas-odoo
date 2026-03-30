import React from 'react'

/* ── Line variant definitions ──────────────────────────────────── */

const LINE_STYLES = [
  {
    key: 'basic',
    label: 'Basic Line',
    desc: 'Straight lines connecting data points',
  },
  {
    key: 'area',
    label: 'Area Chart',
    desc: 'Filled area under the line',
  },
  {
    key: 'stacked_line',
    label: 'Stacked Line',
    desc: 'Cumulative lines stacked vertically',
  },
  {
    key: 'stacked_area',
    label: 'Stacked Area',
    desc: 'Filled bands showing composition',
  },
  {
    key: 'waterfall',
    label: 'Waterfall / Bridge',
    desc: 'Sequential positive/negative deltas',
  },
  {
    key: 'combo',
    label: 'Combo (Bar + Line)',
    desc: 'Mixed bar and line from one query',
  },
  {
    key: 'benchmark',
    label: 'Trend + Benchmark',
    desc: 'Actual trend vs dashed target line',
  },
]

/* ── SVG icon components (40x40 stroke-based) ──────────────────── */

function IconBasicLine({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <polyline points="6,28 14,18 24,22 34,10" stroke={color} strokeWidth="2.5" fill="none" strokeLinejoin="round" />
      <circle cx="6" cy="28" r="2" fill={color} />
      <circle cx="14" cy="18" r="2" fill={color} />
      <circle cx="24" cy="22" r="2" fill={color} />
      <circle cx="34" cy="10" r="2" fill={color} />
    </svg>
  )
}

function IconArea({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <polygon points="6,28 14,16 24,20 34,8 34,34 6,34" fill={color} opacity="0.25" />
      <polyline points="6,28 14,16 24,20 34,8" stroke={color} strokeWidth="2.5" fill="none" strokeLinejoin="round" />
    </svg>
  )
}

function IconStackedLine({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <polyline points="6,30 14,22 24,26 34,16" stroke={color} strokeWidth="2" fill="none" strokeLinejoin="round" />
      <polyline points="6,22 14,14 24,18 34,8" stroke={color} strokeWidth="2" fill="none" strokeLinejoin="round" strokeDasharray="4 2" />
    </svg>
  )
}

function IconStackedArea({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <polygon points="6,32 14,24 24,28 34,18 34,34 6,34" fill={color} opacity="0.3" />
      <polygon points="6,24 14,16 24,20 34,10 34,18 24,28 14,24 6,32" fill={color} opacity="0.2" />
      <polyline points="6,32 14,24 24,28 34,18" stroke={color} strokeWidth="2" fill="none" />
      <polyline points="6,24 14,16 24,20 34,10" stroke={color} strokeWidth="2" fill="none" />
    </svg>
  )
}

function IconWaterfall({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <rect x="4" y="26" width="6" height="8" fill={color} rx="1" />
      <rect x="12" y="18" width="6" height="8" fill="#91cc75" rx="1" />
      <rect x="20" y="22" width="6" height="4" fill="#ee6666" rx="1" />
      <rect x="28" y="12" width="6" height="10" fill="#91cc75" rx="1" />
      <line x1="10" y1="26" x2="12" y2="26" stroke={color} strokeWidth="1" strokeDasharray="2 1" />
      <line x1="18" y1="18" x2="20" y2="18" stroke={color} strokeWidth="1" strokeDasharray="2 1" />
      <line x1="26" y1="22" x2="28" y2="22" stroke={color} strokeWidth="1" strokeDasharray="2 1" />
    </svg>
  )
}

function IconCombo({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <rect x="6" y="18" width="7" height="16" fill={color} opacity="0.4" rx="1" />
      <rect x="17" y="12" width="7" height="22" fill={color} opacity="0.4" rx="1" />
      <rect x="28" y="20" width="7" height="14" fill={color} opacity="0.4" rx="1" />
      <polyline points="9,14 20,8 31,16" stroke={color} strokeWidth="2.5" fill="none" strokeLinejoin="round" />
      <circle cx="9" cy="14" r="2" fill={color} />
      <circle cx="20" cy="8" r="2" fill={color} />
      <circle cx="31" cy="16" r="2" fill={color} />
    </svg>
  )
}

function IconBenchmark({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <polyline points="6,28 14,14 24,20 34,10" stroke={color} strokeWidth="2.5" fill="none" strokeLinejoin="round" />
      <circle cx="6" cy="28" r="2" fill={color} />
      <circle cx="14" cy="14" r="2" fill={color} />
      <circle cx="24" cy="20" r="2" fill={color} />
      <circle cx="34" cy="10" r="2" fill={color} />
      <line x1="4" y1="20" x2="36" y2="20" stroke="#ef4444" strokeWidth="1.5" strokeDasharray="4 2" />
      <text x="36" y="18" fontSize="7" fill="#ef4444" textAnchor="end">T</text>
    </svg>
  )
}

const ICON_MAP = {
  basic: IconBasicLine,
  area: IconArea,
  stacked_line: IconStackedLine,
  stacked_area: IconStackedArea,
  waterfall: IconWaterfall,
  combo: IconCombo,
  benchmark: IconBenchmark,
}

/* ── Inline styles ──────────────────────────────────────────────── */

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

/* ── Select option lists ────────────────────────────────────────── */

const STEP_TYPES = [
  { value: 'none',   label: 'None (diagonal)' },
  { value: 'start',  label: 'Step Start' },
  { value: 'middle', label: 'Step Middle' },
  { value: 'end',    label: 'Step End' },
]

const LEGEND_POSITIONS = [
  { value: 'top',    label: 'Top (horizontal)' },
  { value: 'bottom', label: 'Bottom (horizontal)' },
  { value: 'left',   label: 'Left (vertical)' },
  { value: 'right',  label: 'Right (vertical)' },
  { value: 'none',   label: 'Hidden' },
]

const BENCHMARK_MODES = [
  { value: 'static', label: 'Static Value' },
  { value: 'column', label: 'Column from Query' },
]

/* ── Helpers ────────────────────────────────────────────────────── */

function cfgVal(visualConfig, key, fallback) {
  if (visualConfig && key in visualConfig) return visualConfig[key]
  return fallback
}

/* ── Component ──────────────────────────────────────────────────── */

/**
 * Line style sub-panel shown inside ChartTypePicker when chart type is "line".
 *
 * Props:
 *   selectedStyle          — current line_style value (default 'basic')
 *   onStyleChange(style)   — callback when admin clicks a variant
 *   visualConfig           — object with current flag values
 *   onVisualConfigChange(key, value) — callback for config value changes
 */
export default function LineStylePicker({
  selectedStyle = 'basic',
  onStyleChange,
  visualConfig = {},
  onVisualConfigChange,
}) {
  const style = selectedStyle || 'basic'

  const handleCfg = (key, value) => {
    if (onVisualConfigChange) onVisualConfigChange(key, value)
  }

  /* Which variant-specific fields to show */
  const showLineAppearance = ['basic', 'area', 'stacked_line', 'stacked_area', 'benchmark'].includes(style)
  const showAreaSettings = ['area', 'stacked_area'].includes(style)
  const showStepType = ['basic', 'area', 'stacked_line', 'stacked_area'].includes(style)
  const showWaterfall = style === 'waterfall'
  const showCombo = style === 'combo'
  const showBenchmark = style === 'benchmark'

  return (
    <div>
      <h4 className="wb-label" style={{ marginBottom: 4 }}>Line Style</h4>

      {/* ── Variant grid ──────────────────────────────────── */}
      <div style={styles.grid}>
        {LINE_STYLES.map(ls => {
          const active = style === ls.key
          const color = active ? '#0d9488' : '#9ca3af'
          const Icon = ICON_MAP[ls.key]
          return (
            <button
              key={ls.key}
              type="button"
              className="wb-chart-card"
              style={{
                ...styles.card,
                ...(active ? styles.cardActive : {}),
              }}
              onClick={() => onStyleChange && onStyleChange(ls.key)}
            >
              {Icon && <Icon color={color} />}
              <div style={styles.cardTextWrap}>
                <span style={styles.cardName}>{ls.label}</span>
                <span style={styles.cardDesc}>{ls.desc}</span>
              </div>
            </button>
          )
        })}
      </div>

      {/* ── Variant-specific settings ─────────────────────── */}
      {(showAreaSettings || showWaterfall || showCombo || showBenchmark) && (
        <>
          <div style={styles.sectionTitle}>Variant Settings</div>

          {showAreaSettings && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Area Opacity (0-1)</label>
                <input
                  type="number"
                  className="wb-input wb-input--sm"
                  min="0" max="1" step="0.1"
                  placeholder="0.3"
                  value={cfgVal(visualConfig, 'area_opacity', '')}
                  onChange={e => {
                    const v = e.target.value
                    handleCfg('area_opacity', v === '' ? null : Number(v))
                  }}
                />
              </div>
              <div className="wb-toggle-group">
                <label className="wb-toggle-label">
                  <input
                    type="checkbox"
                    checked={cfgVal(visualConfig, 'area_gradient', false)}
                    onChange={e => handleCfg('area_gradient', e.target.checked)}
                  />
                  Gradient Fill
                </label>
                <span className="wb-flag-help">Vertical gradient from series color to transparent</span>
              </div>
            </>
          )}

          {showWaterfall && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Positive Color</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="#91cc75"
                  value={cfgVal(visualConfig, 'wf_positive_color', '')}
                  onChange={e => handleCfg('wf_positive_color', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Negative Color</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="#ee6666"
                  value={cfgVal(visualConfig, 'wf_negative_color', '')}
                  onChange={e => handleCfg('wf_negative_color', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Total Bar Color</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="#5470c6"
                  value={cfgVal(visualConfig, 'wf_total_color', '')}
                  onChange={e => handleCfg('wf_total_color', e.target.value)}
                />
              </div>
              <div className="wb-toggle-group">
                <label className="wb-toggle-label">
                  <input
                    type="checkbox"
                    checked={cfgVal(visualConfig, 'wf_show_connectors', true)}
                    onChange={e => handleCfg('wf_show_connectors', e.target.checked)}
                  />
                  Show Connector Lines
                </label>
              </div>
            </>
          )}

          {showCombo && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Bar Columns (comma-separated)</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. revenue, cost"
                  value={cfgVal(visualConfig, 'combo_bar_columns', '')}
                  onChange={e => handleCfg('combo_bar_columns', e.target.value)}
                />
                <span className="wb-flag-help">Which y_columns render as bars. Others render as lines.</span>
              </div>
              <div className="wb-toggle-group">
                <label className="wb-toggle-label">
                  <input
                    type="checkbox"
                    checked={cfgVal(visualConfig, 'combo_secondary_axis', false)}
                    onChange={e => handleCfg('combo_secondary_axis', e.target.checked)}
                  />
                  Dual Y-Axis
                </label>
                <span className="wb-flag-help">Lines use a second Y-axis on the right</span>
              </div>
            </>
          )}

          {showBenchmark && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Benchmark Source</label>
                <select
                  className="wb-select"
                  value={cfgVal(visualConfig, 'benchmark_mode', 'static')}
                  onChange={e => handleCfg('benchmark_mode', e.target.value)}
                >
                  {BENCHMARK_MODES.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              {cfgVal(visualConfig, 'benchmark_mode', 'static') === 'static' && (
                <div className="wb-field-row">
                  <label className="wb-field-label">Benchmark Value</label>
                  <input
                    type="number"
                    className="wb-input wb-input--sm"
                    placeholder="e.g. 500"
                    value={cfgVal(visualConfig, 'benchmark_value', '')}
                    onChange={e => {
                      const v = e.target.value
                      handleCfg('benchmark_value', v === '' ? null : Number(v))
                    }}
                  />
                </div>
              )}

              {cfgVal(visualConfig, 'benchmark_mode', 'static') === 'column' && (
                <div className="wb-field-row">
                  <label className="wb-field-label">Benchmark Column</label>
                  <input
                    type="text"
                    className="wb-input wb-input--sm"
                    placeholder="e.g. target_value"
                    value={cfgVal(visualConfig, 'benchmark_column', '')}
                    onChange={e => handleCfg('benchmark_column', e.target.value)}
                  />
                  <span className="wb-flag-help">Name of the y_column rendered as a dashed line</span>
                </div>
              )}

              <div className="wb-field-row">
                <label className="wb-field-label">Benchmark Label</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder="e.g. Target"
                  value={cfgVal(visualConfig, 'benchmark_label', '')}
                  onChange={e => handleCfg('benchmark_label', e.target.value)}
                />
              </div>
            </>
          )}
        </>
      )}

      {/* ── Line appearance ────────────────────────────────── */}
      {showLineAppearance && (
        <>
          <div style={styles.sectionTitle}>Line Appearance</div>

          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'smooth', false)}
                onChange={e => handleCfg('smooth', e.target.checked)}
              />
              Smooth Curves
            </label>
          </div>

          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'show_points', true)}
                onChange={e => handleCfg('show_points', e.target.checked)}
              />
              Show Data Points
            </label>
          </div>

          {cfgVal(visualConfig, 'show_points', true) && (
            <div className="wb-field-row">
              <label className="wb-field-label">Point Size (px)</label>
              <input
                type="number"
                className="wb-input wb-input--sm"
                min="1" max="20"
                placeholder="4"
                value={cfgVal(visualConfig, 'point_size', '')}
                onChange={e => {
                  const v = e.target.value
                  handleCfg('point_size', v === '' ? null : Number(v))
                }}
              />
            </div>
          )}

          <div className="wb-field-row">
            <label className="wb-field-label">Line Width (px)</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              min="1" max="10"
              placeholder="2"
              value={cfgVal(visualConfig, 'line_width', '')}
              onChange={e => {
                const v = e.target.value
                handleCfg('line_width', v === '' ? null : Number(v))
              }}
            />
          </div>

          {showStepType && (
            <div className="wb-field-row">
              <label className="wb-field-label">Step Function</label>
              <select
                className="wb-select"
                value={cfgVal(visualConfig, 'step_type', 'none')}
                onChange={e => handleCfg('step_type', e.target.value)}
              >
                {STEP_TYPES.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          )}
        </>
      )}

      {/* ── Common settings ───────────────────────────────── */}
      <div style={styles.sectionTitle}>Common Settings</div>

      <div className="wb-field-row">
        <label className="wb-field-label">Legend Position</label>
        <select
          className="wb-select"
          value={cfgVal(visualConfig, 'legend_position', 'top')}
          onChange={e => handleCfg('legend_position', e.target.value)}
        >
          {LEGEND_POSITIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      <div className="wb-toggle-group">
        <label className="wb-toggle-label">
          <input
            type="checkbox"
            checked={cfgVal(visualConfig, 'show_axis_labels', true)}
            onChange={e => handleCfg('show_axis_labels', e.target.checked)}
          />
          Show Axis Labels
        </label>
      </div>
    </div>
  )
}
