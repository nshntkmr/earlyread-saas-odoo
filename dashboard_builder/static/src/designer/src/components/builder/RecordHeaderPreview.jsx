import React from 'react'

/**
 * Designer-local preview for the record_header widget. Renders the SAME payload
 * the portal RecordHeader consumes (produced by the shared
 * record_header_formatter), with inline styles because the portal's
 * posterra.css is not in the designer bundle. Keep visually in sync with
 * `.pv-record-header` / `.pv-record-header--scorecard` (and the opt-in
 * `--panel`, badges, status pill, subtitle items, empty state) in posterra.css.
 * The portal's responsive panel steps (4 → 2×2 → band) are not mirrored here;
 * the preview shows the wide layout.
 */
const NEUTRAL = { color: '#6b7280', background: '#f3f4f6' }

function pill(status, extra) {
  return {
    display: 'inline-flex', alignItems: 'center', fontWeight: 600, borderRadius: 999, whiteSpace: 'nowrap',
    color: (status && status.color) || NEUTRAL.color,
    background: (status && status.background) || NEUTRAL.background,
    ...extra,
  }
}

export default function RecordHeaderPreview({ data = {} }) {
  if (!data) return null
  if (data.empty) {
    if (!data.empty_text) return null
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '26px 18px', color: '#6b7280', fontSize: 14 }}>
        <i className="fa fa-search" style={{ fontSize: 18, color: '#9ca3af' }} />
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
    const chipStyle = {
      fontSize: 11, padding: '2px 8px', borderRadius: 10, whiteSpace: 'nowrap',
      background: data.chip_color || '#e1f5ee', color: data.chip_text_color || '#085041',
    }
    const rootStyle = panel
      ? { display: 'flex', flexWrap: 'wrap', alignItems: 'stretch' }
      : { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 18px', padding: '14px 18px' }
    const identityStyle = panel
      ? { display: 'flex', alignItems: 'center', gap: 12, flex: '1 1 auto', minWidth: 0, padding: '14px 18px' }
      : { display: 'flex', alignItems: 'center', gap: 12, flex: '1 1 260px', minWidth: 0 }
    const statsStyle = panel
      ? { display: 'grid', gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))`, gap: 0, flex: '3 1 420px', minWidth: 0,
          padding: '10px 8px', background: '#f8fafc', borderLeft: '1px solid #eef1f5', alignContent: 'center' }
      : { display: 'grid', gridTemplateColumns: `repeat(${stats.length}, minmax(96px, 1fr))`, gap: 8, flex: '2 1 420px', minWidth: 0 }
    const tileStyle = (s, i) => panel
      ? { background: s.bg || 'transparent', padding: '6px 12px', minWidth: 0, borderLeft: i ? '1px solid #e3e8ef' : 0 }
      : { background: s.bg || '#f6f7f9', borderRadius: 8, padding: '8px 10px', minWidth: 0 }
    const chipsStyle = panel
      ? { flexBasis: '100%', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, padding: '10px 18px 12px', borderTop: '1px solid #eef2f7' }
      : { flexBasis: '100%', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, paddingTop: 8, borderTop: '1px solid #eef2f7' }
    return (
      <div style={rootStyle}>
        <div style={identityStyle}>
          {showAvatar && (
            <div style={{
              flex: '0 0 auto', width: 48, height: 48,
              borderRadius: avatar.shape === 'circle' ? '50%' : 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: avatar.color || '#087ad8', color: '#fff', fontWeight: 700, fontSize: 16,
            }}>{avatar.text}</div>
          )}
          <div style={{ minWidth: 0 }}>
            {data.title_status ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '4px 10px' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>{data.title}</div>
                <span style={pill(data.title_status, { fontSize: 12, padding: '3px 10px' })}>{data.title_status.text}</span>
              </div>
            ) : (
              <div style={{ fontSize: 18, fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>{data.title}</div>
            )}
            {subtitleItems.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2px 14px', fontSize: 13, color: '#4b5563', marginTop: 3 }}>
                {subtitleItems.map((it, i) => (
                  <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    {it.icon ? <i className={`fa ${it.icon}`} style={{ fontSize: 12, color: '#6b7280' }} /> : null}
                    {it.value}
                  </span>
                ))}
              </div>
            ) : (data.subtitle ? <div style={{ fontSize: 12, color: '#6b7280', marginTop: 3 }}>{data.subtitle}</div> : null)}
            {badges.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 8px', marginTop: 6 }}>
                {badges.map((b, i) => (
                  <span key={`${b.key || 'badge'}-${i}`} title={b.copy ? 'Click to copy' : undefined} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6, height: 26, padding: '0 10px',
                    borderRadius: 999, background: '#eef2f7', color: '#111827', whiteSpace: 'nowrap',
                  }}>
                    <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase', color: '#6b7280' }}>{b.label}</span>
                    <span style={{ fontSize: 12.5, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{b.value}</span>
                    {b.copy ? <i className="fa fa-clone" style={{ fontSize: 11, color: '#94a0b2' }} /> : null}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
        {stats.length > 0 && (
          <div style={statsStyle}>
            {stats.map((s, i) => {
              const trendColor = s.trend ? ({ good: '#059669', bad: '#dc2626' }[s.trend.status] || '#9ca3af') : null
              const arrow = s.trend ? (s.trend.dir === 'up' ? 'fa-arrow-up' : s.trend.dir === 'down' ? 'fa-arrow-down' : 'fa-minus') : ''
              return (
                <div key={s.key || i} style={tileStyle(s, i)}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: s.label_color || '#6b7280', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {s.icon ? <i className={`fa ${s.icon}`} style={{ fontSize: 12, color: s.icon_color || undefined }} /> : null}
                    <span>{s.label}</span>
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 600, lineHeight: 1.2, marginTop: 2, color: s.value_color || '#111827' }}>
                    {s.value === '' ? '—' : s.value}
                    {s.trend && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, marginLeft: 6, fontSize: 11, fontWeight: 600, color: trendColor, verticalAlign: 'middle', whiteSpace: 'nowrap' }}>
                        <i className={`fa ${arrow}`} style={{ fontSize: 10 }} />{s.trend.delta}
                      </span>
                    )}
                    {s.caption ? (
                      <span style={{ marginLeft: 6, fontSize: 12, fontWeight: 400, color: '#6b7280', whiteSpace: 'nowrap', verticalAlign: 'middle' }}>{s.caption}</span>
                    ) : null}
                    {s.status ? (
                      <span style={pill(s.status, { marginLeft: 8, fontSize: 11, padding: '2px 8px', verticalAlign: 'middle' })}>{s.status.text}</span>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        )}
        {chips.length > 0 && (
          <div style={chipsStyle}>
            {data.chips_label ? <span style={{ fontSize: 11, color: '#9ca3af', marginRight: 4 }}>{data.chips_label}</span> : null}
            {chips.map((c, i) => <span key={i} style={chipStyle}>{c}</span>)}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px' }}>
      {showAvatar && (
        <div style={{
          flex: '0 0 auto', width: 56, height: 56, borderRadius: '50%',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: avatar.color || '#087ad8', color: '#fff',
          fontWeight: 700, fontSize: 20,
        }}>{avatar.text}</div>
      )}
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>{data.title}</div>
        {fields.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 20px', marginTop: 4, fontSize: 13 }}>
            {fields.map((f, i) => (
              <span key={f.key || i} style={{ display: 'inline-flex', alignItems: 'baseline', gap: 6 }}>
                <span style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: '0.4px', color: '#9ca3af', fontWeight: 600 }}>{f.label}</span>
                <span style={{ color: '#374151' }}>{f.value}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
