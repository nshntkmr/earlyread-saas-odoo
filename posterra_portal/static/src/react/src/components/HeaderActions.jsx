import React from 'react'
import { createPortal } from 'react-dom'
import PageBadge from './PageBadge'

/**
 * Portals page-header annotations into the server-rendered QWeb header slots
 * (#pv-page-header-actions-start / -end). Those slots only exist when the
 * server flagged the page as having header annotations, so we GUARD on target
 * existence before portaling. Each group is sorted by `sequence` explicitly.
 */
const bySeq = (a, b) => (a.sequence || 0) - (b.sequence || 0)

export default function HeaderActions({ badges = [] }) {
  if (typeof document === 'undefined') return null

  const startEl = document.getElementById('pv-page-header-actions-start')
  const endEl = document.getElementById('pv-page-header-actions-end')

  const startBadges = badges.filter(b => b.placement === 'page_header_start').slice().sort(bySeq)
  const endBadges = badges.filter(b => b.placement === 'page_header_end').slice().sort(bySeq)

  return (
    <>
      {startEl && createPortal(
        startBadges.map(b => <PageBadge key={b.id} badge={b} />), startEl)}
      {endEl && createPortal(
        endBadges.map(b => <PageBadge key={b.id} badge={b} />), endEl)}
    </>
  )
}
