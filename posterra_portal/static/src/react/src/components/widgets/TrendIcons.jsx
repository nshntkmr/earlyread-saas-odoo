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

/** Pick the right SVG based on status_css class */
export function TrendIcon({ statusCss }) {
  if (!statusCss) return null
  if (statusCss.includes('up'))      return <TrendUp />
  if (statusCss.includes('down'))    return <TrendDown />
  if (statusCss.includes('warning')) return <TrendWarning />
  return <TrendNeutral />
}
