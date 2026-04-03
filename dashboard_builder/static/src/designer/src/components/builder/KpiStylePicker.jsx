import React from 'react'

/* ── KPI variant definitions ──────────────────────────────────────── */

const KPI_STYLES = [
  {
    key: 'stat_card',
    label: 'Stat Card',
    desc: 'Value + trend badge (up/down vs prior)',
  },
  {
    key: 'sparkline',
    label: 'Stat + Sparkline',
    desc: 'Trend line in the corner for trajectory',
  },
  {
    key: 'progress',
    label: 'Progress Bar',
    desc: 'Value vs target with horizontal bar',
  },
  {
    key: 'mini_gauge',
    label: 'Mini Gauge Ring',
    desc: 'Compact donut ring with rate metric',
  },
  {
    key: 'comparison',
    label: 'Comparison Card',
    desc: 'Side-by-side current vs prior period',
  },
  {
    key: 'rag_status',
    label: 'RAG Status Card',
    desc: 'Colored border with status badge',
  },
  {
    key: 'strip',
    label: 'KPI Strip',
    desc: 'Compact horizontal row of metrics',
  },
]

/* ── SVG icon components (40x40 stroke-based) ────────────────────── */

function IconStatCard({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <text x="20" y="18" textAnchor="middle" fontSize="14" fontWeight="700" fill={color}>42</text>
      <rect x="12" y="24" width="16" height="6" rx="3" fill={color} opacity=".2" />
      <path d="M16 27 L19 25 L22 28 L25 26" stroke={color} strokeWidth="1.2" strokeLinecap="round" fill="none" />
    </svg>
  )
}

function IconSparkline({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <text x="14" y="20" textAnchor="middle" fontSize="12" fontWeight="700" fill={color}>48</text>
      <polyline points="24,12 27,16 30,10 33,14 36,8" stroke={color} strokeWidth="1.5" strokeLinecap="round" fill="none" />
      <rect x="6" y="26" width="14" height="4" rx="2" fill={color} opacity=".2" />
      <text x="13" y="29" textAnchor="middle" fontSize="4" fill={color}>-26%</text>
    </svg>
  )
}

function IconProgress({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <text x="20" y="16" textAnchor="middle" fontSize="11" fontWeight="700" fill={color}>68%</text>
      <text x="20" y="23" textAnchor="middle" fontSize="5" fill="#9ca3af">TARGET: 80%</text>
      <rect x="5" y="27" width="30" height="5" rx="2.5" fill="#e5e7eb" />
      <rect x="5" y="27" width="20" height="5" rx="2.5" fill={color} />
      <line x1="29" y1="26" x2="29" y2="33" stroke="#374151" strokeWidth="1" strokeDasharray="1.5 1" />
    </svg>
  )
}

function IconMiniGauge({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* Donut ring */}
      <circle cx="14" cy="20" r="9" stroke="#e5e7eb" strokeWidth="3" fill="none" />
      <circle cx="14" cy="20" r="9" stroke={color} strokeWidth="3" fill="none"
        strokeDasharray="42 57" strokeDashoffset="14" strokeLinecap="round" />
      <text x="14" y="22" textAnchor="middle" fontSize="6" fontWeight="700" fill={color}>68</text>
      {/* Label */}
      <text x="30" y="17" textAnchor="middle" fontSize="5" fill="#9ca3af">TIMELY</text>
      <text x="30" y="23" textAnchor="middle" fontSize="5" fill="#374151">IP ref</text>
      <text x="30" y="30" textAnchor="middle" fontSize="4" fill="#ef4444">Below</text>
    </svg>
  )
}

function IconComparison({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <text x="7" y="10" textAnchor="start" fontSize="4" fill="#9ca3af">2024</text>
      <text x="28" y="10" textAnchor="start" fontSize="4" fill="#9ca3af">2023</text>
      <text x="7" y="20" textAnchor="start" fontSize="10" fontWeight="700" fill={color}>488</text>
      <text x="28" y="20" textAnchor="start" fontSize="10" fontWeight="600" fill="#6b7280">684</text>
      <line x1="24" y1="6" x2="24" y2="22" stroke="#e5e7eb" strokeWidth="0.5" />
      <rect x="5" y="26" width="30" height="7" rx="3" fill="#fff1f2" />
      <text x="20" y="31" textAnchor="middle" fontSize="5" fontWeight="600" fill="#e11d48">-196 (-29%)</text>
    </svg>
  )
}

function IconRagStatus({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      <rect x="4" y="6" width="32" height="28" rx="4" fill="none" stroke="#e5e7eb" strokeWidth="1" />
      <rect x="4" y="6" width="3" height="28" rx="1.5" fill={color} />
      <text x="22" y="18" textAnchor="middle" fontSize="10" fontWeight="700" fill={color}>82%</text>
      <text x="22" y="25" textAnchor="middle" fontSize="5" fill="#9ca3af">TIMELY</text>
      <rect x="14" y="28" width="16" height="4" rx="2" fill={color} opacity=".15" />
      <text x="22" y="31" textAnchor="middle" fontSize="4" fontWeight="600" fill={color}>On target</text>
    </svg>
  )
}

function IconStrip({ color }) {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
      {/* 3 compact metrics in a row */}
      <rect x="2" y="10" width="10" height="20" rx="2" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
      <text x="7" y="20" textAnchor="middle" fontSize="6" fontWeight="700" fill={color}>488</text>
      <text x="7" y="26" textAnchor="middle" fontSize="3" fill="#9ca3af">ADM</text>
      <rect x="15" y="10" width="10" height="20" rx="2" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
      <text x="20" y="20" textAnchor="middle" fontSize="6" fontWeight="700" fill={color}>75</text>
      <text x="20" y="26" textAnchor="middle" fontSize="3" fill="#9ca3af">ADC</text>
      <rect x="28" y="10" width="10" height="20" rx="2" fill="none" stroke="#e5e7eb" strokeWidth="0.5" />
      <text x="33" y="20" textAnchor="middle" fontSize="6" fontWeight="700" fill={color}>18%</text>
      <text x="33" y="26" textAnchor="middle" fontSize="3" fill="#9ca3af">MKT</text>
    </svg>
  )
}

const ICON_MAP = {
  stat_card: IconStatCard,
  sparkline: IconSparkline,
  progress: IconProgress,
  mini_gauge: IconMiniGauge,
  comparison: IconComparison,
  rag_status: IconRagStatus,
  strip: IconStrip,
}

/* ── Inline styles ────────────────────────────────────────────────── */

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

/* ── Option lists ─────────────────────────────────────────────────── */

const COLOR_MODES = [
  { value: 'single', label: 'Single Color (from palette)' },
  { value: 'traffic_light', label: 'Traffic Light (R/A/G zones)' },
]

/* ── Helpers ──────────────────────────────────────────────────────── */

function cfgVal(vc, key, fallback) {
  if (vc && key in vc) return vc[key]
  return fallback
}

/* ── Component ────────────────────────────────────────────────────── */

export default function KpiStylePicker({
  selectedStyle = 'stat_card',
  onStyleChange,
  visualConfig = {},
  onVisualConfigChange,
}) {
  const ks = selectedStyle || 'stat_card'
  const handleCfg = (key, value) => {
    if (onVisualConfigChange) onVisualConfigChange(key, value)
  }

  const isSparkline = ks === 'sparkline'
  const isProgress = ks === 'progress'
  const isMiniGauge = ks === 'mini_gauge'
  const isComparison = ks === 'comparison'
  const isRag = ks === 'rag_status'

  return (
    <div>
      <h4 className="wb-label" style={{ marginBottom: 4 }}>KPI Style</h4>

      {/* ── Variant grid ──────────────────────────────────── */}
      <div style={styles.grid}>
        {KPI_STYLES.map(k => {
          const active = ks === k.key
          const color = active ? '#0d9488' : '#9ca3af'
          const Icon = ICON_MAP[k.key]
          return (
            <button
              key={k.key}
              type="button"
              className="wb-chart-card"
              style={{
                ...styles.card,
                ...(active ? styles.cardActive : {}),
              }}
              onClick={() => onStyleChange && onStyleChange(k.key)}
            >
              {Icon && <Icon color={color} />}
              <div style={styles.cardTextWrap}>
                <span style={styles.cardName}>{k.label}</span>
                <span style={styles.cardDesc}>{k.desc}</span>
              </div>
            </button>
          )
        })}
      </div>

      {/* ── Common settings (all variants) ────────────────── */}
      <div style={styles.sectionTitle}>Common Settings</div>
      <div className="wb-field-row">
        <label className="wb-field-label">
          Card Label (optional)
          <i className="fa fa-info-circle wb-flag-info"
             title="Text shown inside the KPI card body. Leave empty to avoid duplicating the widget title (card header already shows the title). Enter custom text for a different label inside the card." />
        </label>
        <input
          type="text"
          className="wb-input wb-input--sm"
          placeholder="Leave empty — card header shows widget title"
          value={cfgVal(visualConfig, 'kpi_label', '')}
          onChange={e => handleCfg('kpi_label', e.target.value)}
        />
      </div>
      <div className="wb-field-row">
        <label className="wb-field-label">
          Value Format
          <i className="fa fa-info-circle wb-flag-info"
             title="How the primary value is formatted. Number: 1,234. Currency: $1,234. Percent: 68.5%. Decimal: 2.36." />
        </label>
        <select
          className="wb-select"
          value={cfgVal(visualConfig, 'kpi_format', 'number')}
          onChange={e => handleCfg('kpi_format', e.target.value)}
        >
          <option value="number">Number (1,234)</option>
          <option value="currency">Currency ($1,234)</option>
          <option value="percent">Percent (68.5%)</option>
          <option value="decimal">Decimal (2.36)</option>
        </select>
      </div>

      {/* ── Common trend settings (all variants with directional semantics) */}
      {(ks === 'stat_card' || isSparkline || isComparison || isProgress || isMiniGauge) && (
        <>
          <div style={styles.sectionTitle}>Trend Settings</div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'trend_invert', false)}
                onChange={e => handleCfg('trend_invert', e.target.checked)}
              />
              Lower is Better
              <i className="fa fa-info-circle wb-flag-info"
                 title="Invert trend colors: decrease = green (improving), increase = red (worsening). Use for metrics like hospitalization rate, mortality rate, rehospitalization rate." />
            </label>
          </div>
        </>
      )}

      {/* ── Sparkline settings ────────────────────────────── */}
      {isSparkline && (
        <>
          <div style={styles.sectionTitle}>Sparkline Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Sparkline Color
              <i className="fa fa-info-circle wb-flag-info"
                 title="Color for the sparkline trend line. Leave empty to use palette primary." />
            </label>
            <input
              type="text"
              className="wb-input wb-input--sm"
              placeholder="e.g. #0d9488 or leave empty"
              value={cfgVal(visualConfig, 'sparkline_color', '')}
              onChange={e => handleCfg('sparkline_color', e.target.value)}
            />
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'sparkline_fill', true)}
                onChange={e => handleCfg('sparkline_fill', e.target.checked)}
              />
              Fill Area Under Line
            </label>
          </div>
        </>
      )}

      {/* ── Value display (progress + mini_gauge) ──────────── */}
      {(isProgress || isMiniGauge) && (
        <div className="wb-field-row" style={{ marginTop: 12 }}>
          <label className="wb-field-label">
            Value Display
            <i className="fa fa-info-circle wb-flag-info"
               title="'Percentage' shows the value as % of target (e.g. 68%). 'Numeric' shows the actual value (e.g. 2.36) with 'vs benchmark' annotation. Use Numeric for non-percentage metrics like risk scores, dollar amounts, or counts." />
          </label>
          <select
            className="wb-select"
            value={cfgVal(visualConfig, 'value_display', 'percentage')}
            onChange={e => handleCfg('value_display', e.target.value)}
          >
            <option value="percentage">Percentage (68% of target)</option>
            <option value="numeric">Numeric (actual value: 2.36)</option>
          </select>
        </div>
      )}

      {/* ── Benchmark label (progress + mini_gauge) ────────── */}
      {(isProgress || isMiniGauge) && (
        <div className="wb-field-row" style={{ marginTop: 8 }}>
          <label className="wb-field-label">
            Benchmark Label (optional)
            <i className="fa fa-info-circle wb-flag-info"
               title="Static label for the benchmark annotation (e.g. 'vs State Avg', 'vs ACO Target'). If your SQL returns a 'benchmark_label' column, that takes priority (dynamic). Leave empty for default 'vs benchmark'." />
          </label>
          <input
            type="text"
            className="wb-input wb-input--sm"
            placeholder="e.g. vs State Avg, vs ACO Target"
            value={cfgVal(visualConfig, 'benchmark_label', '')}
            onChange={e => handleCfg('benchmark_label', e.target.value)}
          />
        </div>
      )}

      {/* ── Progress bar settings ─────────────────────────── */}
      {isProgress && (
        <>
          <div style={styles.sectionTitle}>Progress Bar Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Target Source
              <i className="fa fa-info-circle wb-flag-info"
                 title="'From SQL' reads the target from a 'target' column in your SQL query (dynamic benchmarks like state average). 'Static Value' uses a fixed number you enter below." />
            </label>
            <select
              className="wb-select"
              value={cfgVal(visualConfig, 'target_source', 'from_sql')}
              onChange={e => handleCfg('target_source', e.target.value)}
            >
              <option value="from_sql">From SQL (dynamic benchmark)</option>
              <option value="static">Static Value</option>
            </select>
          </div>

          {cfgVal(visualConfig, 'target_source', 'from_sql') === 'static' && (
            <div className="wb-field-row">
              <label className="wb-field-label">Static Target Value</label>
              <input
                type="number"
                className="wb-input wb-input--sm"
                placeholder="e.g. 85 for 85% target"
                value={cfgVal(visualConfig, 'static_target_value', '')}
                onChange={e => handleCfg('static_target_value', e.target.value === '' ? '' : Number(e.target.value))}
              />
            </div>
          )}

          <div className="wb-field-row">
            <label className="wb-field-label">Color Mode</label>
            <select
              className="wb-select"
              value={cfgVal(visualConfig, 'progress_color_mode', 'traffic_light')}
              onChange={e => handleCfg('progress_color_mode', e.target.value)}
            >
              {COLOR_MODES.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {cfgVal(visualConfig, 'progress_color_mode', 'traffic_light') === 'traffic_light' && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">
                  Warning Zone (% of target)
                  <i className="fa fa-info-circle wb-flag-info"
                     title="Value below this percentage of the target = red zone. Default: 80% means if your value is below 80% of the target, it shows red." />
                </label>
                <input
                  type="number"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'progress_warn_threshold', 80)}
                  onChange={e => handleCfg('progress_warn_threshold', Number(e.target.value))}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">
                  Good Zone (% of target)
                  <i className="fa fa-info-circle wb-flag-info"
                     title="Value at or above this percentage of the target = green zone. Default: 100% means meeting the target = green." />
                </label>
                <input
                  type="number"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'progress_good_threshold', 100)}
                  onChange={e => handleCfg('progress_good_threshold', Number(e.target.value))}
                />
              </div>
            </>
          )}

          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'progress_show_target_label', true)}
                onChange={e => handleCfg('progress_show_target_label', e.target.checked)}
              />
              Show Target Label
            </label>
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Bar Height (px)</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'progress_bar_height', 8)}
              onChange={e => handleCfg('progress_bar_height', Number(e.target.value))}
            />
          </div>
        </>
      )}

      {/* ── Mini gauge ring settings ──────────────────────── */}
      {isMiniGauge && (
        <>
          <div style={styles.sectionTitle}>Mini Gauge Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">Ring Size (px)</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'mini_gauge_size', 64)}
              onChange={e => handleCfg('mini_gauge_size', Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Ring Thickness (px)</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'mini_gauge_thickness', 6)}
              onChange={e => handleCfg('mini_gauge_thickness', Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Color Mode</label>
            <select
              className="wb-select"
              value={cfgVal(visualConfig, 'mini_gauge_color_mode', 'traffic_light')}
              onChange={e => handleCfg('mini_gauge_color_mode', e.target.value)}
            >
              {COLOR_MODES.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {cfgVal(visualConfig, 'mini_gauge_color_mode', 'traffic_light') === 'traffic_light' && (
            <>
              <div className="wb-field-row">
                <label className="wb-field-label">Warning Threshold (%)</label>
                <input
                  type="number"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'mini_gauge_warn_threshold', 50)}
                  onChange={e => handleCfg('mini_gauge_warn_threshold', Number(e.target.value))}
                />
              </div>
              <div className="wb-field-row">
                <label className="wb-field-label">Good Threshold (%)</label>
                <input
                  type="number"
                  className="wb-input wb-input--sm"
                  value={cfgVal(visualConfig, 'mini_gauge_good_threshold', 80)}
                  onChange={e => handleCfg('mini_gauge_good_threshold', Number(e.target.value))}
                />
              </div>
            </>
          )}

        </>
      )}

      {/* ── Comparison card settings ──────────────────────── */}
      {isComparison && (
        <>
          <div style={styles.sectionTitle}>Comparison Settings</div>

          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'comparison_show_absolute', true)}
                onChange={e => handleCfg('comparison_show_absolute', e.target.checked)}
              />
              Show Absolute Difference
            </label>
          </div>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={cfgVal(visualConfig, 'comparison_show_pct', true)}
                onChange={e => handleCfg('comparison_show_pct', e.target.checked)}
              />
              Show Percentage Change
            </label>
          </div>
        </>
      )}

      {/* ── RAG status card settings ──────────────────────── */}
      {isRag && (
        <>
          <div style={styles.sectionTitle}>RAG Status Settings</div>

          <div className="wb-field-row">
            <label className="wb-field-label">Red &rarr; Amber Threshold</label>
            <input
              type="number"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'rag_red_threshold', 70)}
              onChange={e => handleCfg('rag_red_threshold', Number(e.target.value))}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Amber &rarr; Green Threshold</label>
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
              value={cfgVal(visualConfig, 'rag_badge_amber', 'At risk')}
              onChange={e => handleCfg('rag_badge_amber', e.target.value)}
            />
          </div>
          <div className="wb-field-row">
            <label className="wb-field-label">Red Badge Text</label>
            <input
              type="text"
              className="wb-input wb-input--sm"
              value={cfgVal(visualConfig, 'rag_badge_red', 'Critical')}
              onChange={e => handleCfg('rag_badge_red', e.target.value)}
            />
          </div>
        </>
      )}
    </div>
  )
}
