import React from 'react'

/* ── SVG category icons (16×16, stroke-based, currentColor) ──────────── */

const IconUsers = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="6" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M1.5 14c0-2.5 2-4.5 4.5-4.5s4.5 2 4.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <circle cx="11.5" cy="5.5" r="1.8" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M11.5 9c1.8 0 3.2 1.4 3.2 3.2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
  </svg>
)

const IconHome = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M2 8l6-5.5L14 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M3.5 9v4.5a1 1 0 001 1h7a1 1 0 001-1V9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M6.5 14.5v-4h3v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const IconHeartbeat = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M1 8h3l1.5-3 2 6 1.5-3H12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx="13.5" cy="8" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
  </svg>
)

const IconDollar = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M8 1.5v13M10.5 4.5c0-1.1-1.1-2-2.5-2s-2.5.9-2.5 2 1.1 2 2.5 2 2.5.9 2.5 2-1.1 2-2.5 2-2.5-.9-2.5-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const IconStar = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M8 1.5l2 4 4.5.7-3.2 3.1.8 4.4L8 11.5l-4.1 2.2.8-4.4L1.5 6.2l4.5-.7z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
  </svg>
)

const IconChart = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M1.5 13.5l4-5 3 3 6-8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M11 3.5h3.5v3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const IconCalendar = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="1.5" y="3" width="13" height="11" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M1.5 7h13M5 1.5v3M11 1.5v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
)

const IconClipboard = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="3" y="2.5" width="10" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M6 2.5V2a2 2 0 014 0v.5M6 7h4M6 9.5h4M6 12h2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
  </svg>
)

const ICON_MAP = {
  users:     IconUsers,
  home:      IconHome,
  heartbeat: IconHeartbeat,
  dollar:    IconDollar,
  star:      IconStar,
  chart:     IconChart,
  calendar:  IconCalendar,
  clipboard: IconClipboard,
}

/**
 * Renders a category icon by name.
 * @param {{ name: string }} props
 */
export default function CategoryIcon({ name }) {
  const Icon = ICON_MAP[name]
  if (!Icon) return null
  return <Icon />
}
