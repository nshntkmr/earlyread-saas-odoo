import React from 'react'

/**
 * Designer-local preview for the record_header widget. Renders the SAME payload
 * the portal RecordHeader consumes (produced by the shared
 * record_header_formatter), with inline styles because the portal's
 * posterra.css is not in the designer bundle. Keep visually in sync with
 * `.pv-record-header` / `.pv-record-header--scorecard` in posterra.css.
 */
export default function RecordHeaderPreview({ data = {} }) {
  if (!data || data.empty || !data.title) return null
  const avatar = data.avatar || {}
  const fields = Array.isArray(data.fields) ? data.fields : []
  const showAvatar = avatar.mode !== 'none' && !!avatar.text

  if (data.layout === 'scorecard') {
    const stats = Array.isArray(data.stats) ? data.stats : []
    const chips = Array.isArray(data.chips) ? data.chips : []
    const chipStyle = {
      fontSize: 11, padding: '2px 8px', borderRadius: 10, whiteSpace: 'nowrap',
      background: data.chip_color || '#e1f5ee', color: data.chip_text_color || '#085041',
    }
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 18px', padding: '14px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: '1 1 260px', minWidth: 0 }}>
          {showAvatar && (
            <div style={{
              flex: '0 0 auto', width: 48, height: 48,
              borderRadius: avatar.shape === 'circle' ? '50%' : 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: avatar.color || '#087ad8', color: '#fff', fontWeight: 700, fontSize: 16,
            }}>{avatar.text}</div>
          )}
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>{data.title}</div>
            {data.subtitle ? <div style={{ fontSize: 12, color: '#6b7280', marginTop: 3 }}>{data.subtitle}</div> : null}
          </div>
        </div>
        {stats.length > 0 && (
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${stats.length}, minmax(96px, 1fr))`, gap: 8, flex: '2 1 420px', minWidth: 0 }}>
            {stats.map((s, i) => (
              <div key={s.key || i} style={{ background: '#f6f7f9', borderRadius: 8, padding: '8px 10px', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#6b7280', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {s.icon ? <i className={`fa ${s.icon}`} style={{ fontSize: 12 }} /> : null}
                  <span>{s.label}</span>
                </div>
                <div style={{ fontSize: 20, fontWeight: 600, lineHeight: 1.2, marginTop: 2, color: '#111827' }}>{s.value === '' ? '—' : s.value}</div>
              </div>
            ))}
          </div>
        )}
        {chips.length > 0 && (
          <div style={{ flexBasis: '100%', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6, paddingTop: 8, borderTop: '1px solid #eef2f7' }}>
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
