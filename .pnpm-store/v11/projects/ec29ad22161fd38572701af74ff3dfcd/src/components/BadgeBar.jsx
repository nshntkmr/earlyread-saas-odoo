import React from 'react'

/**
 * BadgeBar — page-level header badges (SQL-driven).
 * Renders small KPI pills at the top of each dashboard page.
 * TODO: Full implementation with refresh-on-filter-apply.
 */
export default function BadgeBar({ initialBadges = [] }) {
  if (!initialBadges.length) return null

  return (
    <div className="pv-page-badges">
      {initialBadges.map(b => (
        <span
          key={b.id}
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
      ))}
    </div>
  )
}
