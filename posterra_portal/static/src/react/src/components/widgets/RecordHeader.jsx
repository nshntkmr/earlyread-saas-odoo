import React from 'react'

/**
 * RecordHeader — generic SQL-driven identity header: avatar (initials) + a
 * large title + a footer row of label/value pairs. ALL content comes from the
 * backend payload (dashboard_builder.services.record_header_formatter), so the
 * portal and the designer preview render identically.
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
