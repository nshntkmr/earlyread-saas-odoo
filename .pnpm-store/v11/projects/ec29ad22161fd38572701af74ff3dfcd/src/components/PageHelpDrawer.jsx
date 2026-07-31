import React, { useEffect, useState, useCallback } from 'react'
import './PageHelpDrawer.css'

/**
 * PageHelpDrawer
 *
 * Slide-in drawer for rich page-level help content, triggered by clicking
 * the page header's help icon (rendered server-side by dashboard_templates.xml).
 *
 * The icon span carries `data-help-content` and `data-help-title` attributes
 * when the page's `help_text` is long or contains HTML — short help_text
 * keeps the existing Bootstrap tooltip behavior.
 *
 * Lifecycle:
 *   • On mount, this component scans the DOM for `[data-help-content]`
 *     elements and attaches click listeners that open the drawer with
 *     that element's content.
 *   • The drawer slides in from the right (CSS transform), backdrop fades
 *     in over the page content.
 *   • Close: ✕ button, click backdrop, or Esc key.
 *
 * Content rendering:
 *   • Treats `help_content` as HTML (admins control the markup).
 *   • Wrapped in dangerouslySetInnerHTML — the content is admin-saved
 *     (not user-supplied), so XSS risk is bounded by the access model.
 *     If you ever expose this field to non-admin users, run through
 *     DOMPurify or similar first.
 */
export default function PageHelpDrawer() {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  // ── Open the drawer with content from a triggering element ─────────
  const openDrawer = useCallback((titleText, contentHtml) => {
    setTitle(titleText || 'Help')
    setContent(contentHtml || '')
    setOpen(true)
  }, [])

  const closeDrawer = useCallback(() => {
    setOpen(false)
  }, [])

  // ── Attach click listeners to all help icons rendered server-side ─
  //
  // The XML template marks long-help icons with both `data-help-content`
  // and `data-help-title` plus role=button. We listen to clicks on them
  // and open the drawer with their content.
  useEffect(() => {
    const handleClick = (e) => {
      // Find the closest ancestor with the data attribute (covers clicks
      // on the inner <i> icon as well as the wrapper <span>)
      const trigger = e.target.closest('[data-help-content]')
      if (!trigger) return
      e.preventDefault()
      const contentHtml = trigger.getAttribute('data-help-content') || ''
      const titleText = trigger.getAttribute('data-help-title') || 'Help'
      openDrawer(titleText, contentHtml)
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [openDrawer])

  // ── Esc key closes drawer ─────────────────────────────────────────
  useEffect(() => {
    if (!open) return
    const handleKey = (e) => { if (e.key === 'Escape') closeDrawer() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, closeDrawer])

  // ── Lock body scroll while drawer is open ─────────────────────────
  useEffect(() => {
    if (!open) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prevOverflow }
  }, [open])

  // Always render — drawer is hidden via CSS class. This avoids
  // mount/unmount jank during open/close transitions.
  return (
    <>
      {/* Backdrop — click to close */}
      <div
        className={`pv-help-backdrop ${open ? 'pv-help-backdrop--open' : ''}`}
        onClick={closeDrawer}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <aside
        className={`pv-help-drawer ${open ? 'pv-help-drawer--open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pv-help-drawer-title"
        aria-hidden={!open}
      >
        <header className="pv-help-drawer__header">
          <h3 id="pv-help-drawer-title" className="pv-help-drawer__title">
            <i className="fa fa-book me-2" aria-hidden="true" />
            {title}
          </h3>
          <button
            type="button"
            className="pv-help-drawer__close"
            onClick={closeDrawer}
            aria-label="Close help"
          >
            <i className="fa fa-times" aria-hidden="true" />
          </button>
        </header>

        <div
          className="pv-help-drawer__body"
          // Admin-saved HTML — see component header comment for the
          // security model. If exposing to non-admin authoring later,
          // sanitise with DOMPurify before rendering.
          dangerouslySetInnerHTML={{ __html: content }}
        />
      </aside>
    </>
  )
}
