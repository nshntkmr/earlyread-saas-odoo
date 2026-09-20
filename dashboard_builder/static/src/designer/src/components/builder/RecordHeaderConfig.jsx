import React from 'react'

/**
 * RecordHeaderConfig — "Configure Header" step body for the record_header
 * widget (Custom SQL only). Everything is stored in visual_config
 * (state.visualFlags) and consumed by the shared record_header_formatter, so
 * the portal and the Designer preview agree.
 *
 * Keys written:
 *   header_layout    'classic' | 'scorecard'
 *   avatar_mode      'initials' | 'none'
 *   avatar_color     hex
 *   avatar_shape     'circle' | 'rounded'          (scorecard)
 *   label_overrides  {column: label}               (classic footer labels)
 *   subtitle_column  column name                   (scorecard)
 *   stats            [{column, label, icon, format}] (scorecard, 1..6)
 *   chips_column, chips_label, chip_color, chip_text_color (scorecard)
 *
 * Title (x_column) and classic footer columns (y_columns) stay in the SQL
 * step's column mapping; this panel lists the SQL result columns so the
 * admin can pick from them.
 */
const FORMATS = [
  { value: 'number',  label: 'Number (1,234)' },
  { value: 'percent', label: 'Percent (65.7%)' },
  { value: 'text',    label: 'Text (as is)' },
]

export default function RecordHeaderConfig({ columns = [], xColumn = '', yColumns = '', visualFlags = {}, onFlagChange }) {
  const vf = visualFlags || {}
  const set = (k, v) => onFlagChange(k, v)
  const layout = vf.header_layout || 'classic'
  const stats = Array.isArray(vf.stats) ? vf.stats : []
  const overrides = vf.label_overrides || {}
  const footerCols = String(yColumns || '').split(',').map(s => s.trim()).filter(Boolean)

  const setStat = (idx, patch) => set('stats', stats.map((s, i) => (i === idx ? { ...s, ...patch } : s)))
  const addStat = () => set('stats', [...stats, { column: '', label: '', icon: '', format: 'number' }])
  const removeStat = (idx) => set('stats', stats.filter((_, i) => i !== idx))

  const colOptions = (blankLabel) => (
    <>
      <option value="">{blankLabel}</option>
      {columns.map(c => <option key={c} value={c}>{c}</option>)}
    </>
  )

  return (
    <div className="wb-record-header-config">
      <h3 className="wb-step-title">Configure Header</h3>
      <div className="wb-step-skip" style={{ marginBottom: 12 }}>
        <i className="fa fa-info-circle me-2" />
        Title column = the X column and footer columns = the Y columns from the Custom SQL step.
        {columns.length === 0 && ' Run the SQL test in the previous step to list its columns here.'}
      </div>

      <div className="wb-field-row">
        <label className="wb-field-label">
          Layout
          <i className="fa fa-info-circle wb-flag-info"
             title="Classic: avatar + title + label/value footer (default). Scorecard: avatar + title + subtitle, stat tiles and a chip row, each from its own SQL column." />
        </label>
        <select className="wb-select wb-select--sm" value={layout} onChange={e => set('header_layout', e.target.value)}>
          <option value="classic">Classic (title + footer)</option>
          <option value="scorecard">Scorecard (tiles + chips)</option>
        </select>
      </div>

      <div className="wb-field-row">
        <label className="wb-field-label">Avatar</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select className="wb-select wb-select--sm" value={vf.avatar_mode || 'initials'} onChange={e => set('avatar_mode', e.target.value)}>
            <option value="initials">Initials</option>
            <option value="none">None</option>
          </select>
          <input type="text" className="wb-input wb-input--sm" placeholder="#087ad8" style={{ maxWidth: 120 }}
            value={vf.avatar_color || ''} onChange={e => set('avatar_color', e.target.value)} />
          {layout === 'scorecard' && (
            <select className="wb-select wb-select--sm" value={vf.avatar_shape || 'rounded'} onChange={e => set('avatar_shape', e.target.value)}>
              <option value="rounded">Rounded square</option>
              <option value="circle">Circle</option>
            </select>
          )}
        </div>
      </div>

      {layout === 'classic' && footerCols.length > 0 && (
        <div className="wb-field-row">
          <label className="wb-field-label">
            Footer Labels
            <i className="fa fa-info-circle wb-flag-info" title="Display label for each footer (Y) column. Blank = the column name." />
          </label>
          {footerCols.map(c => (
            <div key={c} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <code style={{ fontSize: 12, minWidth: 140 }}>{c}</code>
              <input type="text" className="wb-input wb-input--sm" placeholder={c}
                value={overrides[c] || ''}
                onChange={e => set('label_overrides', { ...overrides, [c]: e.target.value })} />
            </div>
          ))}
        </div>
      )}

      {layout === 'scorecard' && (
        <>
          <div className="wb-field-row">
            <label className="wb-field-label">
              Subtitle Column
              <i className="fa fa-info-circle wb-flag-info" title="Optional text shown under the title, e.g. 'Provider group · Humana MA'." />
            </label>
            <select className="wb-select wb-select--sm" value={vf.subtitle_column || ''} onChange={e => set('subtitle_column', e.target.value)}>
              {colOptions('(none)')}
            </select>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Stat Tiles
              <i className="fa fa-info-circle wb-flag-info" title="Up to 6 tiles. Column = SQL result column; Icon = Font Awesome class, e.g. fa-map-marker, fa-user-md, fa-users, fa-building." />
            </label>
            {stats.map((s, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 1fr 0.9fr auto', gap: 6, alignItems: 'center', marginBottom: 6 }}>
                <select className="wb-select wb-select--sm" value={s.column || ''} onChange={e => setStat(i, { column: e.target.value })}>
                  {colOptions('— column —')}
                </select>
                <input type="text" className="wb-input wb-input--sm" placeholder="Label" value={s.label || ''} onChange={e => setStat(i, { label: e.target.value })} />
                <input type="text" className="wb-input wb-input--sm" placeholder="fa-users" value={s.icon || ''} onChange={e => setStat(i, { icon: e.target.value })} />
                <select className="wb-select wb-select--sm" value={s.format || 'number'} onChange={e => setStat(i, { format: e.target.value })}>
                  {FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                </select>
                <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={() => removeStat(i)} aria-label="Remove tile">
                  <i className="fa fa-times" />
                </button>
              </div>
            ))}
            {stats.length < 6 && (
              <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={addStat}>
                <i className="fa fa-plus me-1" /> Add Tile
              </button>
            )}
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Chips Column
              <i className="fa fa-info-circle wb-flag-info" title="Column holding a comma-separated list or a JSON array, e.g. the state list. One chip per value." />
            </label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select className="wb-select wb-select--sm" value={vf.chips_column || ''} onChange={e => set('chips_column', e.target.value)}>
                {colOptions('(none)')}
              </select>
              <input type="text" className="wb-input wb-input--sm" placeholder="Chips label, e.g. Markets" style={{ maxWidth: 180 }}
                value={vf.chips_label || ''} onChange={e => set('chips_label', e.target.value)} />
              <input type="text" className="wb-input wb-input--sm" placeholder="Chip bg #e1f5ee" style={{ maxWidth: 140 }}
                value={vf.chip_color || ''} onChange={e => set('chip_color', e.target.value)} />
              <input type="text" className="wb-input wb-input--sm" placeholder="Chip text #085041" style={{ maxWidth: 140 }}
                value={vf.chip_text_color || ''} onChange={e => set('chip_text_color', e.target.value)} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
