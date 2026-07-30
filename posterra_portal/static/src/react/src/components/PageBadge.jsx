import React from 'react'

/**
 * Presentational page annotation pill. Mirrors the markup produced by
 * BadgeBar (which is intentionally left UNCHANGED for the legacy path);
 * reused by the new placement components (BelowHeaderStart, HeaderActions).
 */
export default function PageBadge({ badge: b }) {
  return (
    <span
      className="pv-page-badge"
      style={{
        ...(b.font_size ? { fontSize: b.font_size } : {}),
        ...(b.text_color ? { color: b.text_color } : {}),
      }}
    >
      {b.icon && (
        <i
          className={`fa ${b.icon} me-1`}
          style={b.icon_color ? { color: b.icon_color } : undefined}
        />
      )}
      {b.value}
    </span>
  )
}
