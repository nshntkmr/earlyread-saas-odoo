import React from 'react'

/* ── Inline SVG trend arrows (clean, modern) ─────────────────────────── */

export const TrendUp = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M2.5 11L11 2.5M11 2.5H5M11 2.5V9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

export const TrendDown = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M2.5 3L11 11.5M11 11.5H5M11 11.5V5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

export const TrendNeutral = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M2.5 7H11.5M11.5 7L8.5 4M11.5 7L8.5 10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

export const TrendWarning = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M7 3V8M7 10.5V11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
  </svg>
)

/** Pick the arrow SVG.
 *
 * Direction comes from `iconClass` (the server's numeric-direction field:
 * fa-arrow-up / fa-arrow-down / fa-minus) when provided, so the arrow reflects
 * whether the value ROSE or FELL — independent of good/bad color. Falls back to
 * `statusCss` for callers that don't pass an icon_class (backward compatible:
 * where the two agree, behavior is unchanged). Color is applied by the parent
 * badge via `status_css`, so e.g. a lower-is-better metric that rose renders an
 * UP arrow in RED. */
export function TrendIcon({ statusCss, iconClass }) {
  const src = iconClass || statusCss
  if (!src) return null
  if (src.includes('up'))      return <TrendUp />
  if (src.includes('down'))    return <TrendDown />
  if (src.includes('warning')) return <TrendWarning />
  return <TrendNeutral />
}
