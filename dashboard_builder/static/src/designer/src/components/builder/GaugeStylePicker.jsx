import React from 'react'

/* ── Gauge variant definitions ─────────────────────────────────── */

const GAUGE_STYLES = [
  {
    key: 'standard',
    label: 'Standard Arc (220°)',
    desc: 'Classic dial with needle & progress',
  },
  {
    key: 'half_arc',
    label: 'Half-Arc (180°)',
    desc: 'Semicircle for KPI tiles & hero metrics',
  },
  {
    key: 'three_quarter',
    label: 'Three-Quarter (270°)',
    desc: 'Cockpit-style with full scale labels',
  },
  {
    key: 'bullet',
    label: 'Bullet Gauge',
    desc: 'Horizontal bar with target & range zones',
  },
  {
    key: 'traffic_light_rag',
    label: 'Traffic Light / RAG',
    desc: 'R/A/G circles with status badge',
  },
  {
    key: 'percentile_rank',
    label: 'Percentile Rank',
    desc: 'Position on 0-100 scale with quartiles',
  },
  {
    key: 'multi_ring',
    label: 'Multi-Ring Nested',
    desc: 'Concentric rings for composite scores',
  },
]

/* ── SVG icon components (40x40 stroke-based) ─────────────────── */

function IconStandard({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* 220° arc */}
      <path d="M7 28 A15 15 0 1 1 33 28" stroke={color} strokeWidth="4" strokeLinecap="round" fill="none" />
      {/* Needle */}
      <line x1="20" y1="20" x2="12" y2="12" stroke={color} strokeWidth="2" strokeLinecap="round" />
      <circle cx="20" cy="20" r="2.5" fill={color} />
    </svg>
  )
}

function IconHalfArc({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* 180° semicircle */}
      <path d="M5 26 A15 15 0 0 1 35 26" stroke={color} strokeWidth="5" strokeLinecap="round" fill="none" />
      {/* Center value */}
      <text x="20" y="24" textAnchor="middle" fontSize="10" fontWeight="700" fill={color}>%</text>
      {/* Min/Max labels */}
      <text x="6" y="32" textAnchor="middle" fontSize="6" fill="#9ca3af">0</text>
      <text x="34" y="32" textAnchor="middle" fontSize="6" fill="#9ca3af">100</text>
    </svg>
  )
}

function IconThreeQuarter({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* 270° arc */}
      <path d="M15 34 A15 15 0 1 1 25 34" stroke={color} strokeWidth="4" strokeLinecap="round" fill="none" />
      {/* Needle */}
      <line x1="20" y1="20" x2="28" y2="10" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="20" cy="20" r="2" fill={color} />
    </svg>
  )
}

function IconBullet({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* Background range zones */}
      <rect x="3" y="16" width="34" height="8" rx="2" fill="#f3f4f6" />
      <rect x="3" y="16" width="11" height="8" rx="2" fill="#fecaca" />
      <rect x="14" y="16" width="10" height="8" fill="#fde68a" />
      <rect x="24" y="16" width="13" height="8" rx="2" fill="#bbf7d0" />
      {/* Actual value bar */}
      <rect x="3" y="18" width="22" height="4" rx="1" fill={color} />
      {/* Target marker */}
      <line x1="28" y1="14" x2="28" y2="26" stroke="#374151" strokeWidth="1.5" strokeDasharray="2 1" />
    </svg>
  )
}

function IconTrafficLight({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* Three circles */}
      <circle cx="10" cy="18" r="5" fill="#fecaca" stroke="#ef4444" strokeWidth="1" />
      <circle cx="20" cy="18" r="5" fill="#fde68a" stroke="#f59e0b" strokeWidth="1" />
      <circle cx="30" cy="18" r="6" fill="#10b981" stroke="#059669" strokeWidth="1.5" />
      {/* Active indicator on green */}
      <text x="20" y="32" textAnchor="middle" fontSize="7" fontWeight="600" fill={color}>OK</text>
    </svg>
  )
}

function IconPercentile({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* Gradient bar */}
      <rect x="3" y="22" width="34" height="5" rx="2.5" fill="#e5e7eb" />
      <rect x="3" y="22" width="26" height="5" rx="2.5" fill={color} />
      {/* Position marker */}
      <rect x="27" y="20" width="3" height="9" rx="1" fill="#1f2937" />
      {/* Quartile ticks */}
      <line x1="11.5" y1="28" x2="11.5" y2="31" stroke="#9ca3af" strokeWidth="1" />
      <line x1="20" y1="28" x2="20" y2="31" stroke="#9ca3af" strokeWidth="1" />
      <line x1="28.5" y1="28" x2="28.5" y2="31" stroke="#9ca3af" strokeWidth="1" />
      {/* Ordinal */}
      <text x="20" y="16" textAnchor="middle" fontSize="10" fontWeight="700" fill={color}>83</text>
    </svg>
  )
}

function IconMultiRing({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* Concentric arcs */}
      <path d="M8 30 A14 14 0 1 1 32 30" stroke={color} strokeWidth="3" strokeLinecap="round" fill="none" />
      <path d="M12 28 A10 10 0 1 1 28 28" stroke="#f59e0b" strokeWidth="3" strokeLinecap="round" fill="none" />
      <path d="M16 26 A6 6 0 1 1 24 26" stroke="#ef4444" strokeWidth="3" strokeLinecap="round" fill="none" />
      {/* Center dot */}
      <circle cx="20" cy="22" r="2" fill={color} />
    </svg>
  )
}

const ICON_MAP = {
  standard: IconStandard,
  half_arc: IconHalfArc,
  three_quarter: IconThreeQuarter,
  bullet: IconBullet,
  traffic_light_rag: IconTrafficLight,
  percentile_rank: IconPercentile,
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

/* ── Option lists ────────────────────────────────────────────────── */

const COLOR_MODES = [
  { value: 'single', label: 'Single Color (from palette)' },
  { value: 'traffic_light', label: 'Traffic Light (R/A/G zones)' },
]

const NUMBER_FORMATS = [
  { value: 'auto', label: 'Auto (% if 0-100)' },
  { value: 'percent', label: 'Percent (78.4%)' },
  { value: 'comma', label: 'Comma (1,234)' },
  { value: 'decimal1', label: '1 Decimal (78.4)' },
  { value: 'integer', label: 'Integer (78)' },
  { value: 'currency', label: 'Currency ($1,234)' },
]

const BULLET_ORIENTATIONS = [
  { value: 'horizontal', label: 'Horizontal' },
  { value: 'vertical', label: 'Vertical' },
]

/* ── Helpers ───────────────────────────────────────────────────── */

function cfgVal(vc, key, fallback) {
  if (vc && key in vc) return vc[key]
  return fallback
}

/* ── Component ─────────────────────────────────────────────────── */

export default function GaugeStylePicker({
  selectedStyle = 'standard',
  onStyleChange,
  visualConfig = {},
  onVisualConfigChange,
}) {
  const gs = selectedStyle || 'standard'
  const handleCfg = (key, value) => {
    if (onVisualConfigChange) onVisualConfigChange(key, value)
  }

  const isArc = ['standard', 'half_arc', 'three_quarter'].includes(gs)
  const isBullet = gs === 'bullet'
  const isRag = gs === 'traffic_light_rag'
  const isPercentile = gs === 'percentile_rank'
  const isMultiRing = gs === 'multi_ring'

  return (
    <div>
      <h4 className="wb-label" style={{ marginBottom: 4 }}>Gauge Style</h4>

      {/* ── Variant grid ─────────────────────────────────── */}
      <div style={styles.grid}>
        {GAUGE_STYLES.map(g => {
          const active = gs === g.key
          const color = active ? '#0d9488' : '#9ca3af'
          const Icon = ICON_MAP[g.key]
          return (
            <button
              key={g.key}
              type="button"
              className="wb-chart-card"
              style={{
                ...styles.card,
                ...(active ? styles.cardActive : {}),
              }}
              onClick={() => onStyleChange && onStyleChange(g.key)}
            >
              {Icon && <Icon color={color} />}
              <div style={styles.cardTextWrap}>
                <span style={styles.cardName}>{g.label}</span>
                <span style={styles.cardDesc}>{g.desc}</span>
              </div>
            </button>
          )
        })}
      </div>

      {/* ── Arc variant settings (standard, half_arc, three_quarter) ─── */}
      {isArc && (
        <>
          <div style={styles.sectionTitle}>Arc Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">Scale Min</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'gauge_min', 0)}
              onChange={e => handleCfg('gauge_min', e.target.value === '' ? 0 : Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Scale Max</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'gauge_max', 100)}
              onChange={e => handleCfg('gauge_max', e.target.value === '' ? 100 : Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Color Mode</label>
            <select
              className="wb-select"
              value={cfgVal(visualConfig, 'gauge_color_mode', 'single')}
              onChange={e => handleCfg('gauge_color_mode', e.target.value)}
            >
              {COLOR_MODES.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {cfgVal(visualConfig, 'gauge_color_mode', 'single') === 'traffic_light' && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Warning Threshold (%)</label>
                <input
                  type="number"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'gauge_warn_threshold', 50)}
                  onChange={e => handleCfg('gauge_warn_threshold', Number(e.target.value))}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Good Threshold (%)</label>
                <input
                  type="number"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'gauge_good_threshold', 70)}
                  onChange={e => handleCfg('gauge_good_threshold', Number(e.target.value))}
                />
              </div>
            </>
          )}

          <div className="wb-field-row">
            <label className="wb-field-label">Number Format</label>
            <select
              className="wb-select"
              value={cfgVal(visualConfig, 'gauge_number_format', 'auto')}
              onChange={e => handleCfg('gauge_number_format', e.target.value)}
            >
              {NUMBER_FORMATS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {(gs === 'standard' || gs === 'three_quarter') && (
            <div className="wb-toggle-group">
              <label className="wb-toggle-label">
                <input
                  type="checkbox"
                  checked={cfgVal(visualConfig, 'show_needle', true)}
                  onChange={e => handleCfg('show_needle', e.target.checked)}
                />
                Show Needle
              </label>
            </div>
          )}

          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'show_progress_bar', true)}
                onChange={e => handleCfg('show_progress_bar', e.target.checked)}
              />
              Show Progress Arc
            </label>
          </div>

          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'show_scale_labels', true)}
                onChange={e => handleCfg('show_scale_labels', e.target.checked)}
              />
              Show Scale Labels
            </label>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">Target Value</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              placeholder="Optional target marker"
              value={cfgVal(visualConfig, 'target_value', '') ?? ''}
              onChange={e => handleCfg('target_value', e.target.value === '' ? null : Number(e.target.value))}
            />
          </div>
          {cfgVal(visualConfig, 'target_value', null) != null && (
            <div className="wb-field-row">
              <label className="wb-field-label">Target Label</label>
              <input
                type="text"
                className="wb-input wb-input--sm"
                placeholder='e.g. "Target: ≥85%"'
                value={cfgVal(visualConfig, 'target_label', '')}
                onChange={e => handleCfg('target_label', e.target.value)}
              />
            </div>
          )}
        </>
      )}

      {/* ── Bullet gauge settings ─────────────────────────── */}
      {isBullet && (
        <>
          <div style={styles.sectionTitle}>Bullet Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">Scale Min</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'bullet_min', 0)}
              onChange={e => handleCfg('bullet_min', e.target.value === '' ? 0 : Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Scale Max</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'bullet_max', 100)}
              onChange={e => handleCfg('bullet_max', e.target.value === '' ? 100 : Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Orientation</label>
            <select
              className="wb-select"
              value={cfgVal(visualConfig, 'bullet_orientation', 'horizontal')}
              onChange={e => handleCfg('bullet_orientation', e.target.value)}
            >
              {BULLET_ORIENTATIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Target Value</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              placeholder="Target marker position"
              value={cfgVal(visualConfig, 'target_value', '') ?? ''}
              onChange={e => handleCfg('target_value', e.target.value === '' ? null : Number(e.target.value))}
            />
          </div>
          {cfgVal(visualConfig, 'target_value', null) != null && (
            <div className="wb-field-row">
              <label className="wb-field-label">Target Label</label>
              <input
                type="text"
                className="wb-input wb-input--sm"
                value={cfgVal(visualConfig, 'target_label', '')}
                onChange={e => handleCfg('target_label', e.target.value)}
              />
            </div>
          )}
          <div className="wb-field-row">
            <label className="wb-field-label">
              Range Zones (JSON)
              <i className="fa fa-info-circle wb-flag-info"
                 title='[{"to":70,"color":"#ef4444","label":"Poor <70"},{"to":85,"color":"#f59e0b","label":"At risk"},{"to":100,"color":"#10b981","label":"On target"}]' />
            </label>
            <textarea
              className="wb-input"
              rows={3}
              placeholder='Leave empty for auto R/A/G zones'
              value={cfgVal(visualConfig, 'bullet_ranges', '')}
              onChange={e => handleCfg('bullet_ranges', e.target.value)}
            />
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'bullet_show_labels', true)}
                onChange={e => handleCfg('bullet_show_labels', e.target.checked)}
              />
              Show Range Labels
            </label>
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Bar Height (px)</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'bullet_bar_height', 12)}
              onChange={e => handleCfg('bullet_bar_height', Number(e.target.value))}
            />
          </div>
        </>
      )}

      {/* ── Traffic Light / RAG settings ──────────────────── */}
      {isRag && (
        <>
          <div style={styles.sectionTitle}>Traffic Light Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">Red → Amber Threshold</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'rag_red_threshold', 70)}
              onChange={e => handleCfg('rag_red_threshold', Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Amber → Green Threshold</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'rag_green_threshold', 85)}
              onChange={e => handleCfg('rag_green_threshold', Number(e.target.value))}
            />
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'rag_invert', false)}
                onChange={e => handleCfg('rag_invert', e.target.checked)}
              />
              Lower is Better (invert thresholds)
            </label>
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'rag_show_badge', true)}
                onChange={e => handleCfg('rag_show_badge', e.target.checked)}
              />
              Show Status Badge
            </label>
          </div>
          {cfgVal(visualConfig, 'rag_show_badge', true) && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Green Badge Text</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'rag_badge_green', 'On target')}
                  onChange={e => handleCfg('rag_badge_green', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Amber Badge Text</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'rag_badge_amber', 'Watch')}
                  onChange={e => handleCfg('rag_badge_amber', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Red Badge Text</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'rag_badge_red', 'At risk')}
                  onChange={e => handleCfg('rag_badge_red', e.target.value)}
                />
              </div>
            </>
          )}
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'rag_show_thresholds', true)}
                onChange={e => handleCfg('rag_show_thresholds', e.target.checked)}
              />
              Show Threshold Text
            </label>
          </div>
        </>
      )}

      {/* ── Percentile Rank settings ──────────────────────── */}
      {isPercentile && (
        <>
          <div style={styles.sectionTitle}>Percentile Settings</div>

          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'percentile_show_quartiles', true)}
                onChange={e => handleCfg('percentile_show_quartiles', e.target.checked)}
              />
              Show Quartile Markers (25th, 50th, 75th)
            </label>
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'percentile_show_badge', true)}
                onChange={e => handleCfg('percentile_show_badge', e.target.checked)}
              />
              Show Quartile Badge
            </label>
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'percentile_invert', false)}
                onChange={e => handleCfg('percentile_invert', e.target.checked)}
              />
              Lower is Better (inverted rank)
            </label>
          </div>
        </>
      )}

      {/* ── Multi-Ring settings ───────────────────────────── */}
      {isMultiRing && (
        <>
          <div style={styles.sectionTitle}>Multi-Ring Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">Max Rings (2-6)</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              min={2}
              max={6}
              value={cfgVal(visualConfig, 'multi_ring_max_rings', 6)}
              onChange={e => handleCfg('multi_ring_max_rings', Number(e.target.value))}
            />
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'multi_ring_show_center', true)}
                onChange={e => handleCfg('multi_ring_show_center', e.target.checked)}
              />
              Show Center Label
            </label>
          </div>
          {cfgVal(visualConfig, 'multi_ring_show_center', true) && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Center Text</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder='e.g. "3.5 ★" or "B+"'
                  value={cfgVal(visualConfig, 'multi_ring_center_text', '')}
                  onChange={e => handleCfg('multi_ring_center_text', e.target.value)}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Center Subtitle</label>
                <input
                  type="text"
                  className="wb-input wb-input--sm"
                  placeholder='e.g. "Star rating"'
                  value={cfgVal(visualConfig, 'multi_ring_center_subtitle', '')}
                  onChange={e => handleCfg('multi_ring_center_subtitle', e.target.value)}
                />
              </div>
            </>
          )}
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'multi_ring_show_legend', true)}
                onChange={e => handleCfg('multi_ring_show_legend', e.target.checked)}
              />
              Show Legend
            </label>
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Arc Width (px)</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'multi_ring_arc_width', 10)}
              onChange={e => handleCfg('multi_ring_arc_width', Number(e.target.value))}
            />
          </div>
        </>
      )}
    </div>
  )
}
