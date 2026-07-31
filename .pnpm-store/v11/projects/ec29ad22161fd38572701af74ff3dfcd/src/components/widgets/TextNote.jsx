import React from 'react'
import CategoryIcon from './CategoryIcons'

/**
 * TextNote — static info callout, typically used as the footer of a
 * composite widget. No SQL execution; body text and icon are configured
 * on the composite_item record.
 *
 * Data shape (from dashboard.widget._build_text_note_data):
 *   { type: 'text_note', body: '...', icon_name: 'user-check' | 'none' }
 *
 * Line breaks in body are preserved via white-space: pre-wrap CSS.
 */
export default function TextNote({ data }) {
  const body = data?.body || ''
  const iconName = data?.icon_name
  return (
    <div className="pv-text-note">
      {iconName && iconName !== 'none' && (
        <span className="pv-text-note-icon">
          <CategoryIcon name={iconName} />
        </span>
      )}
      <div className="pv-text-note-body">{body}</div>
    </div>
  )
}
