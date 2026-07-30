import React from 'react'

const PALETTES = [
  { key: 'healthcare', label: 'Healthcare', colors: ['#0d9488','#14b8a6','#2dd4bf','#6ee7b7','#34d399','#059669'] },
  { key: 'ocean',      label: 'Ocean',      colors: ['#1d4ed8','#3b82f6','#60a5fa','#93c5fd','#0ea5e9','#38bdf8'] },
  { key: 'warm',       label: 'Warm',       colors: ['#ea580c','#f97316','#fb923c','#fbbf24','#f59e0b','#d97706'] },
  { key: 'mono',       label: 'Monochrome', colors: ['#374151','#6b7280','#9ca3af','#d1d5db','#e5e7eb','#f3f4f6'] },
  { key: 'default',    label: 'Default',    colors: ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#fc8452'] },
]

const WIDTHS = [
  { value: 25,  label: '25%' },
  { value: 33,  label: '33%' },
  { value: 50,  label: '50%' },
  { value: 67,  label: '67%' },
  { value: 100, label: '100%' },
]

/**
 * Step 5: Appearance configuration.
 *
 * Props:
 *   appearance  — { title, colorPalette, colSpan, chartHeight, showLegend, showAxisLabels, showDataLabels }
 *   chartType   — string
 *   onUpdate    — (appearance) => void
 */
export default function AppearanceConfig({ appearance, chartType, onUpdate }) {
  const update = (key, val) => onUpdate({ ...appearance, [key]: val })

  const showHeightControl = !['battle_card', 'insight_panel'].includes(chartType)
  const showChartToggles = ['bar', 'line', 'pie', 'donut', 'radar', 'scatter'].includes(chartType)

  return (
    <div>
      <h3 className="wb-step-title">Appearance</h3>

      {/* Title */}
      <div className="wb-field-group">
        <label className="wb-label">Widget Title</label>
        <input
          type="text"
          className="wb-input"
          value={appearance.title || ''}
          onChange={e => update('title', e.target.value)}
          placeholder="e.g. Top HHAs by Total Admits"
        />
      </div>

      {/* Color palette */}
      <div className="wb-field-group">
        <label className="wb-label">Color Palette</label>
        <div className="wb-palette-grid">
          {PALETTES.map(p => (
            <button
              key={p.key}
              type="button"
              className={`wb-palette-card ${appearance.colorPalette === p.key ? 'wb-palette-card--active' : ''}`}
              onClick={() => update('colorPalette', p.key)}
            >
              <div className="wb-palette-swatches">
                {p.colors.slice(0, 4).map((c, i) => (
                  <span key={i} className="wb-swatch" style={{ backgroundColor: c }} />
                ))}
              </div>
              <span className="wb-palette-label">{p.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Width */}
      <div className="wb-field-group">
        <label className="wb-label">Width</label>
        <div className="wb-width-options">
          {WIDTHS.map(w => (
            <button
              key={w.value}
              type="button"
              className={`wb-width-btn ${Number(appearance.colSpan) === w.value ? 'wb-width-btn--active' : ''}`}
              onClick={() => update('colSpan', w.value)}
            >
              {w.label}
            </button>
          ))}
        </div>
        <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <label className="wb-label" style={{ margin: 0, whiteSpace: 'nowrap' }}>Custom:</label>
          <input
            type="number"
            className="wb-input"
            style={{ width: 80 }}
            min={1}
            max={100}
            value={appearance.colSpan || 50}
            onChange={e => update('colSpan', Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
          />
          <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>%</span>
        </div>
      </div>

      {/* Height */}
      {showHeightControl && (
        <div className="wb-field-group">
          <label className="wb-label">Height: {appearance.chartHeight || 350}px</label>
          <input
            type="range"
            className="wb-range"
            min={200}
            max={600}
            step={25}
            value={appearance.chartHeight || 350}
            onChange={e => update('chartHeight', Number(e.target.value))}
          />
        </div>
      )}

      {/* Row Span — for tall widgets like maps */}
      <div className="wb-field-group">
        <label className="wb-label">Row Span</label>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="number"
            className="wb-input"
            style={{ width: 80 }}
            min={1}
            max={4}
            value={appearance.rowSpan || 1}
            onChange={e => update('rowSpan', Math.min(4, Math.max(1, Number(e.target.value) || 1)))}
          />
          <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
            {(appearance.rowSpan || 1) === 1 ? 'row (default)' : 'rows'}
          </span>
        </div>
      </div>

      {/* Bar-specific options */}
      {chartType === 'bar' && (
        <div className="wb-field-group">
          <label className="wb-label">Bar Options</label>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={appearance.barStack === true}
                onChange={e => update('barStack', e.target.checked)}
              />
              Stack bars (series on top of each other)
            </label>
          </div>
        </div>
      )}

      {/* Chart toggles */}
      {showChartToggles && (
        <div className="wb-field-group">
          <label className="wb-label">Options</label>
          <div className="wb-toggle-group">
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={appearance.showLegend !== false}
                onChange={e => update('showLegend', e.target.checked)}
              />
              Show legend
            </label>
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={appearance.showAxisLabels !== false}
                onChange={e => update('showAxisLabels', e.target.checked)}
              />
              Show axis labels
            </label>
            <label className="wb-toggle-label">
              <input
                type="checkbox"
                checked={appearance.showDataLabels === true}
                onChange={e => update('showDataLabels', e.target.checked)}
              />
              Show data labels
            </label>
          </div>
        </div>
      )}
    </div>
  )
}
