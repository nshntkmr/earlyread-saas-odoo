import React from 'react'

/**
 * RecordHeader — generic SQL-driven identity header: avatar (initials) + a
 * large title + a footer row of label/value pairs. ALL content comes from the
 * backend payload (dashboard_builder.services.record_header_formatter), so the
 * portal and the designer preview render identically.
 *
 * Two layouts, chosen by the payload's `layout` (formatter reads
 * visual_config.header_layout):
 *   • classic   (default) — avatar + title + label/value footer (unchanged)
 *   • scorecard — avatar + title + subtitle, a grid of stat tiles
 *                 ({label, value, icon}) and a row of chips.
 *
 * Rendered CHROMELESS — WidgetGrid suppresses the standard card header,
 * subtitle, and footnote for this type. WidgetGrid owns the error UI (via the
 * data.error key) and filters settled-empty headers before render; this
 * component defensively renders nothing when empty.
 */
export default function RecordHeader({ data = {} }) {
  if (!data || data.empty || !data.title) return null

  const avatar = data.avatar || {}
  const fields = Array.isArray(data.fields) ? data.fields : []
  const showAvatar = avatar.mode !== 'none' && !!avatar.text

  if (data.layout === 'scorecard') {
    const stats = Array.isArray(data.stats) ? data.stats : []
    const chips = Array.isArray(data.chips) ? data.chips : []
    const chipStyle = (data.chip_color || data.chip_text_color)
      ? { ...(data.chip_color && { background: data.chip_color }), ...(data.chip_text_color && { color: data.chip_text_color }) }
      : undefined
    return (
      <div className="pv-record-header pv-record-header--scorecard">
        <div className="pv-record-header-identity">
          {showAvatar && (
            <div
              className={`pv-record-header-avatar${avatar.shape === 'circle' ? '' : ' pv-record-header-avatar--rounded'}`}
              style={{ backgroundColor: avatar.color || '#087ad8' }}
            >
              {avatar.text}
            </div>
          )}
          <div className="pv-record-header-body">
            <div className="pv-record-header-title">{data.title}</div>
            {data.subtitle ? <div className="pv-record-header-subtitle">{data.subtitle}</div> : null}
          </div>
        </div>
        {stats.length > 0 && (
          <div className="pv-record-header-stats" style={{ '--pv-rh-stats': stats.length }}>
            {stats.map((s, i) => (
              <div key={s.key || i} className="pv-record-header-stat">
                <div className="pv-record-header-stat-label">
                  {s.icon ? <i className={`fa ${s.icon}`} aria-hidden="true" /> : null}
                  <span>{s.label}</span>
                </div>
                <div className="pv-record-header-stat-value">{s.value === '' ? '—' : s.value}</div>
              </div>
            ))}
          </div>
        )}
        {chips.length > 0 && (
          <div className="pv-record-header-chips">
            {data.chips_label ? <span className="pv-record-header-chips-label">{data.chips_label}</span> : null}
            {chips.map((c, i) => (
              <span key={i} className="pv-record-header-chip" style={chipStyle}>{c}</span>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="pv-record-header">
      {showAvatar && (
        <div
          className="pv-record-header-avatar"
          style={{ backgroundColor: avatar.color || '#087ad8' }}
        >
          {avatar.text}
        </div>
      )}
      <div className="pv-record-header-body">
        <div className="pv-record-header-title">{data.title}</div>
        {fields.length > 0 && (
          <div className="pv-record-header-fields">
            {fields.map((f, i) => (
              <span key={f.key || i} className="pv-record-header-field">
                <span className="pv-record-header-field-label">{f.label}</span>
                <span className="pv-record-header-field-value">{f.value}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
