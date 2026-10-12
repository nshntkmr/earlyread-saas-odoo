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
 *   empty_text       placeholder when the query returns no row (both layouts)
 *   label_overrides  {column: label}               (classic footer labels)
 *   subtitle_column  column name                   (scorecard)
 *   subtitle_items   [{column, icon}]              (scorecard; replaces subtitle)
 *   title_status_column, title_status_tone_column  (scorecard; pill by the title)
 *   badges           [{column, label, copy}]       (scorecard; identifier pills)
 *   stats_style      'tiles' | 'panel'             (scorecard)
 *   stats            [{column, label, icon, format, caption_column,
 *                      status_column, status_tone_column,
 *                      color_value_by_status, ...}] (scorecard, 1..6)
 *   chips_column, chips_label, chip_color, chip_text_color (scorecard)
 *
 * Tone columns return a word: success | warning | danger | info | neutral.
 * Every key here is opt-in: a blank value emits nothing, so a header saved
 * before a key existed renders exactly as it did.
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

const TONE_HELP = 'Tone column: the SQL returns success, warning, danger, info or neutral — the colour comes from the palette, never from SQL.'

export default function RecordHeaderConfig({ columns = [], xColumn = '', yColumns = '', visualFlags = {}, onFlagChange }) {
  const vf = visualFlags || {}
  const set = (k, v) => onFlagChange(k, v)
  const layout = vf.header_layout || 'classic'
  const stats = Array.isArray(vf.stats) ? vf.stats : []
  const badges = Array.isArray(vf.badges) ? vf.badges : []
  const subtitleItems = Array.isArray(vf.subtitle_items) ? vf.subtitle_items : []
  const overrides = vf.label_overrides || {}
  const footerCols = String(yColumns || '').split(',').map(s => s.trim()).filter(Boolean)

  const setStat = (idx, patch) => set('stats', stats.map((s, i) => (i === idx ? { ...s, ...patch } : s)))
  const addStat = () => set('stats', [...stats, { column: '', label: '', icon: '', format: 'number' }])
  const removeStat = (idx) => set('stats', stats.filter((_, i) => i !== idx))

  const setBadge = (idx, patch) => set('badges', badges.map((b, i) => (i === idx ? { ...b, ...patch } : b)))
  const addBadge = () => set('badges', [...badges, { column: '', label: '', copy: true }])
  const removeBadge = (idx) => set('badges', badges.filter((_, i) => i !== idx))

  const setItem = (idx, patch) => set('subtitle_items', subtitleItems.map((it, i) => (i === idx ? { ...it, ...patch } : it)))
  const addItem = () => set('subtitle_items', [...subtitleItems, { column: '', icon: '' }])
  const removeItem = (idx) => set('subtitle_items', subtitleItems.filter((_, i) => i !== idx))

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

      <div className="wb-field-row">
        <label className="wb-field-label">
          Empty State Text
          <i className="fa fa-info-circle wb-flag-info"
             title="Shown as a quiet placeholder when the query returns no row (e.g. no record selected yet). Blank = the header is hidden, as before." />
        </label>
        <input type="text" className="wb-input wb-input--sm" placeholder="e.g. Find a member to begin" style={{ maxWidth: 360 }}
          value={vf.empty_text || ''} onChange={e => set('empty_text', e.target.value)} />
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
              Title Status Chip
              <i className="fa fa-info-circle wb-flag-info"
                 title={`Optional coloured pill beside the title, e.g. "Currently eligible". Text column = the words; ${TONE_HELP}`} />
            </label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select className="wb-select wb-select--sm" value={vf.title_status_column || ''} onChange={e => set('title_status_column', e.target.value)}>
                {colOptions('— status text column (none) —')}
              </select>
              <select className="wb-select wb-select--sm" value={vf.title_status_tone_column || ''} onChange={e => set('title_status_tone_column', e.target.value)}>
                {colOptions('— tone column (neutral) —')}
              </select>
            </div>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Subtitle Column
              <i className="fa fa-info-circle wb-flag-info" title="Optional text shown under the title, e.g. 'Provider group · Humana MA'. Ignored when Subtitle Items are set." />
            </label>
            <select className="wb-select wb-select--sm" value={vf.subtitle_column || ''} onChange={e => set('subtitle_column', e.target.value)}>
              {colOptions('(none)')}
            </select>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Subtitle Items (with icons)
              <i className="fa fa-info-circle wb-flag-info"
                 title="Optional: one column per item, shown as 'icon value' separated by dots (e.g. fa-user Male · fa-calendar 80 yrs). Replaces the Subtitle Column when any item is set. A blank value hides its item." />
            </label>
            {subtitleItems.map((it, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr auto', gap: 6, alignItems: 'center', marginBottom: 6 }}>
                <select className="wb-select wb-select--sm" value={it.column || ''} onChange={e => setItem(i, { column: e.target.value })}>
                  {colOptions('— column —')}
                </select>
                <input type="text" className="wb-input wb-input--sm" placeholder="fa-user" value={it.icon || ''} onChange={e => setItem(i, { icon: e.target.value })} />
                <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={() => removeItem(i)} aria-label="Remove item">
                  <i className="fa fa-times" />
                </button>
              </div>
            ))}
            <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={addItem}>
              <i className="fa fa-plus me-1" /> Add Item
            </button>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Identifier Badges
              <i className="fa fa-info-circle wb-flag-info"
                 title="Optional pills under the subtitle: small label + value (e.g. MEMBER ID 362905714), with a click-to-copy button when Copy is on. A NULL value hides its badge. Label blank = the column name." />
            </label>
            {badges.map((b, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr auto auto', gap: 6, alignItems: 'center', marginBottom: 6 }}>
                <select className="wb-select wb-select--sm" value={b.column || ''} onChange={e => setBadge(i, { column: e.target.value })}>
                  {colOptions('— column —')}
                </select>
                <input type="text" className="wb-input wb-input--sm" placeholder="Label" value={b.label || ''} onChange={e => setBadge(i, { label: e.target.value })} />
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                  <input type="checkbox" checked={b.copy !== false && b.copy !== 'false'}
                    onChange={e => setBadge(i, { copy: e.target.checked })} />
                  Copy
                </label>
                <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={() => removeBadge(i)} aria-label="Remove badge">
                  <i className="fa fa-times" />
                </button>
              </div>
            ))}
            <button type="button" className="wb-btn wb-btn--outline wb-btn--sm" onClick={addBadge}>
              <i className="fa fa-plus me-1" /> Add Badge
            </button>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Stats Style
              <i className="fa fa-info-circle wb-flag-info"
                 title="Tiles: each stat in its own rounded tile (default). Panel: one grey panel beside the identity with hairline dividers; 4 across, then 2×2, then a full-width band as the card narrows." />
            </label>
            <select className="wb-select wb-select--sm" value={vf.stats_style || 'tiles'} onChange={e => set('stats_style', e.target.value)}>
              <option value="tiles">Tiles (default)</option>
              <option value="panel">Panel (prototype look)</option>
            </select>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Tile Colors (defaults for every tile)
              <i className="fa fa-info-circle wb-flag-info" title="CSS colors. Blank keeps the built-in greys. Each tile below can override any of them." />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
              <input type="text" className="wb-input wb-input--sm" placeholder="Icon color #0f6e56" value={vf.stat_icon_color || ''} onChange={e => set('stat_icon_color', e.target.value)} />
              <input type="text" className="wb-input wb-input--sm" placeholder="Label color #6b7280" value={vf.stat_label_color || ''} onChange={e => set('stat_label_color', e.target.value)} />
              <input type="text" className="wb-input wb-input--sm" placeholder="Value color #111827" value={vf.stat_value_color || ''} onChange={e => set('stat_value_color', e.target.value)} />
              <input type="text" className="wb-input wb-input--sm" placeholder="Tile background #f6f7f9" value={vf.stat_bg || ''} onChange={e => set('stat_bg', e.target.value)} />
            </div>
          </div>

          <div className="wb-field-row">
            <label className="wb-field-label">
              Stat Tiles
              <i className="fa fa-info-circle wb-flag-info" title="Up to 6 tiles. Column = SQL result column; Icon = Font Awesome class, e.g. fa-map-marker, fa-user-md, fa-users, fa-building. Prior column (optional) adds an up/down arrow with the delta vs that column; 'Higher is better' decides which direction is green." />
            </label>
            {stats.map((s, i) => (
              <div key={i} style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: 6, marginBottom: 8 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr 1fr 0.9fr auto', gap: 6, alignItems: 'center' }}>
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
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, marginTop: 6 }}>
                  <input type="text" className="wb-input wb-input--sm" placeholder="Icon color" value={s.icon_color || ''} onChange={e => setStat(i, { icon_color: e.target.value })} />
                  <input type="text" className="wb-input wb-input--sm" placeholder="Label color" value={s.label_color || ''} onChange={e => setStat(i, { label_color: e.target.value })} />
                  <input type="text" className="wb-input wb-input--sm" placeholder="Value color" value={s.value_color || ''} onChange={e => setStat(i, { value_color: e.target.value })} />
                  <input type="text" className="wb-input wb-input--sm" placeholder="Tile background" value={s.bg || ''} onChange={e => setStat(i, { bg: e.target.value })} />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: 6, marginTop: 6, alignItems: 'center' }}>
                  <select className="wb-select wb-select--sm" value={s.prior_column || ''} onChange={e => setStat(i, { prior_column: e.target.value })}>
                    {colOptions('— no trend arrow (prior column) —')}
                  </select>
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
                    <input type="checkbox" checked={s.higher_is_better !== false}
                      onChange={e => setStat(i, { higher_is_better: e.target.checked })} />
                    Higher is better (green when up)
                  </label>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 6, marginTop: 6, alignItems: 'center' }}
                     title={`Caption = small text after the value (e.g. a month). Status = pill text after the value. ${TONE_HELP}`}>
                  <select className="wb-select wb-select--sm" value={s.caption_column || ''} onChange={e => setStat(i, { caption_column: e.target.value })}>
                    {colOptions('— caption column —')}
                  </select>
                  <select className="wb-select wb-select--sm" value={s.status_column || ''} onChange={e => setStat(i, { status_column: e.target.value })}>
                    {colOptions('— status text column —')}
                  </select>
                  <select className="wb-select wb-select--sm" value={s.status_tone_column || ''} onChange={e => setStat(i, { status_tone_column: e.target.value })}>
                    {colOptions('— status tone column —')}
                  </select>
                  <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, whiteSpace: 'nowrap' }}>
                    <input type="checkbox" checked={s.color_value_by_status === true || s.color_value_by_status === 'true'}
                      onChange={e => setStat(i, { color_value_by_status: e.target.checked })} />
                    Colour value by status
                  </label>
                </div>
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
