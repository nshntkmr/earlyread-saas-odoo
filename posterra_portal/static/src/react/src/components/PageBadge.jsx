import React from 'react'

/**
 * Presentational page annotation pill. Mirrors the markup produced by
 * BadgeBar (which is intentionally left UNCHANGED for the legacy path);
 * reused by the new placement components (BelowHeaderStart, HeaderActions).
 */
export default function PageBadge({ badge: b }) {
  // badge_style 'pill' (opt-in) → rounded chip; the text colour tints the
  // background via CSS color-mix. Absent/'text' → the unchanged markup.
  const pill = b.badge_style === 'pill'
  const cls = pill
    ? `pv-page-badge pv-page-badge--pill${b.text_color ? ' pv-page-badge--tinted' : ''}`
    : 'pv-page-badge'
  return (
    <span
      className={cls}
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
