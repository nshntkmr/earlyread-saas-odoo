import React from 'react'

/**
 * Designer-local preview for the record_header widget. Renders the SAME payload
 * the portal RecordHeader consumes (produced by the shared
 * record_header_formatter), with inline styles because the portal's
 * posterra.css is not in the designer bundle. Keep visually in sync with
 * `.pv-record-header` in posterra.css.
 */
export default function RecordHeaderPreview({ data = {} }) {
  if (!data || data.empty || !data.title) return null
  const avatar = data.avatar || {}
  const fields = Array.isArray(data.fields) ? data.fields : []
  const showAvatar = avatar.mode !== 'none' && !!avatar.text
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
