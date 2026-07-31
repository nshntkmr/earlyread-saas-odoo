import React from 'react'
import PageBadge from './PageBadge'

/**
 * Opt-in below-header START (left-aligned) annotations. Only rendered when an
 * admin configures a `below_header_start` annotation; the legacy BadgeBar path
 * (`below_header_end`) is untouched.
 */
export default function BelowHeaderStart({ badges = [] }) {
  if (!badges.length) return null
  return (
    <div className="pv-page-badges-start">
      {badges.map(b => <PageBadge key={b.id} badge={b} />)}
    </div>
  )
}
