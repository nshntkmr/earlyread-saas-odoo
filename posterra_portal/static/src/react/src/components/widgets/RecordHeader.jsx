import React, { useEffect, useRef, useState } from 'react'

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
 * Opt-in scorecard extras — each exists in the payload ONLY when its
 * visual_config key is set, so older headers render exactly as before:
 *   • title_status   {text, color, background} → coloured pill by the title
 *   • subtitle_items [{icon, value}]           → "icon value" items instead of
 *                                                the plain subtitle
 *   • badges         [{key, label, value, copy}] → identifier pills under the
 *                                                subtitle, click-to-copy
 *   • stat.caption / stat.status               → small text / coloured pill
 *                                                after a tile value
 *   • stats_style = 'panel'                    → tiles become one grey panel
 *   • empty_text (on the empty payload)        → placeholder card instead of
 *                                                vanishing
 *
 * Rendered CHROMELESS — WidgetGrid suppresses the standard card header,
 * subtitle, and footnote for this type. WidgetGrid owns the error UI (via the
 * data.error key) and filters settled-empty headers (unless they carry
 * empty_text) before render; this component defensively renders nothing when
 * empty.
 */
const NEUTRAL = { color: '#6b7280', background: '#f3f4f6' }

function pillStyle(status) {
  return {
    color: (status && status.color) || NEUTRAL.color,
    background: (status && status.background) || NEUTRAL.background,
  }
}

export default function RecordHeader({ data = {} }) {
  // Click-to-copy feedback for identifier badges: one tick at a time.
  const [copiedKey, setCopiedKey] = useState('')
  const copyTimer = useRef(null)
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current) }, [])
  const copyBadge = (key, value) => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(String(value)).catch(() => {})
      }
    } catch (_) { /* clipboard unavailable (http / permissions) — the tick still confirms the click */ }
    setCopiedKey(key)
    if (copyTimer.current) clearTimeout(copyTimer.current)
    copyTimer.current = setTimeout(() => setCopiedKey(''), 1500)
  }

  if (!data) return null
  if (data.empty) {
    // Opt-in placeholder (visual_config.empty_text). Without it the grid
    // never mounts an empty header (WidgetGrid.isTrulyEmptyHeader).
    if (!data.empty_text) return null
    return (
      <div className="pv-record-header pv-record-header--empty" role="status">
        <i className="fa fa-search" aria-hidden="true" />
        <span>{data.empty_text}</span>
      </div>
    )
  }
  if (!data.title) return null

  const avatar = data.avatar || {}
  const fields = Array.isArray(data.fields) ? data.fields : []
  const showAvatar = avatar.mode !== 'none' && !!avatar.text

  if (data.layout === 'scorecard') {
    const stats = Array.isArray(data.stats) ? data.stats : []
    const chips = Array.isArray(data.chips) ? data.chips : []
    const badges = Array.isArray(data.badges) ? data.badges : []
    const subtitleItems = Array.isArray(data.subtitle_items) ? data.subtitle_items : []
    const panel = data.stats_style === 'panel'
    const chipStyle = (data.chip_color || data.chip_text_color)
      ? { ...(data.chip_color && { background: data.chip_color }), ...(data.chip_text_color && { color: data.chip_text_color }) }
      : undefined
    return (
      <div className={`pv-record-header pv-record-header--scorecard${panel ? ' pv-record-header--panel' : ''}`}>
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
            {data.title_status ? (
              <div className="pv-record-header-title-row">
                <div className="pv-record-header-title">{data.title}</div>
                <span className="pv-record-header-status" style={pillStyle(data.title_status)}>
                  {data.title_status.text}
                </span>
              </div>
            ) : (
              <div className="pv-record-header-title">{data.title}</div>
            )}
            {subtitleItems.length > 0 ? (
              <div className="pv-record-header-subtitle pv-record-header-subtitle--items">
                {subtitleItems.map((it, i) => (
                  <span key={i} className="pv-record-header-subtitle-item">
                    {it.icon ? <i className={`fa ${it.icon}`} aria-hidden="true" /> : null}
                    {it.value}
                  </span>
                ))}
              </div>
            ) : (data.subtitle ? <div className="pv-record-header-subtitle">{data.subtitle}</div> : null)}
            {badges.length > 0 && (
              <div className="pv-record-header-badges">
                {badges.map((b, i) => {
                  const key = `${b.key || 'badge'}-${i}`
                  const inner = (
                    <>
                      <span className="pv-record-header-badge-label">{b.label}</span>
                      <span className="pv-record-header-badge-value">{b.value}</span>
                    </>
                  )
                  if (!b.copy) return <span key={key} className="pv-record-header-badge">{inner}</span>
                  const copied = copiedKey === key
                  return (
                    <button
                      key={key}
                      type="button"
                      className={`pv-record-header-badge pv-record-header-badge--copy${copied ? ' is-copied' : ''}`}
                      title="Click to copy"
                      aria-label={`Copy ${b.label} ${b.value}`}
                      onClick={() => copyBadge(key, b.value)}
                    >
                      {inner}
                      <i className={`fa ${copied ? 'fa-check' : 'fa-clone'}`} aria-hidden="true" />
                    </button>
                  )
                })}
                <span className="visually-hidden" aria-live="polite">{copiedKey ? 'Copied' : ''}</span>
              </div>
            )}
          </div>
        </div>
        {stats.length > 0 && (
          <div
            className={`pv-record-header-stats${panel ? ' pv-record-header-stats--panel' : ''}`}
            style={{ '--pv-rh-stats': stats.length }}
          >
            {stats.map((s, i) => (
              <div key={s.key || i} className="pv-record-header-stat" style={s.bg ? { background: s.bg } : undefined}>
                <div className="pv-record-header-stat-label" style={s.label_color ? { color: s.label_color } : undefined}>
                  {s.icon ? <i className={`fa ${s.icon}`} aria-hidden="true" style={s.icon_color ? { color: s.icon_color } : undefined} /> : null}
                  <span>{s.label}</span>
                </div>
                <div className="pv-record-header-stat-value" style={s.value_color ? { color: s.value_color } : undefined}>
                  {s.value === '' ? '—' : s.value}
                  {s.trend && (
                    <span className={`pv-record-header-stat-trend pv-record-header-stat-trend--${s.trend.status}`}
                          title={`${s.trend.delta} vs prior`}>
                      <i className={`fa ${s.trend.dir === 'up' ? 'fa-arrow-up' : s.trend.dir === 'down' ? 'fa-arrow-down' : 'fa-minus'}`} aria-hidden="true" />
                      {s.trend.delta}
                    </span>
                  )}
                  {s.caption ? <span className="pv-record-header-stat-caption">{s.caption}</span> : null}
                  {s.status ? (
                    <span className="pv-record-header-stat-status" style={pillStyle(s.status)}>{s.status.text}</span>
                  ) : null}
                </div>
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
