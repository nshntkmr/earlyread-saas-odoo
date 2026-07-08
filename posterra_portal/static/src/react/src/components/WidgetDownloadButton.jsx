import React, { useState, useRef, useEffect, useCallback } from 'react'

const MENU_WIDTH = 150

/**
 * WidgetDownloadButton — admin-gated per-widget data export trigger.
 *
 * Rendered in the widget card header by WidgetGrid when the widget's
 * download config is enabled. A single allowed format renders a plain icon
 * button; formats === 'both' opens a two-item CSV/Excel menu.
 *
 * The menu uses position:fixed coordinates from getBoundingClientRect —
 * .pv-widget-card clips absolutely-positioned children (overflow:hidden +
 * container-type), so an absolute menu would be cut off on short cards.
 * It closes on outside mousedown, Escape, any scroll (capture) and resize.
 *
 * Props:
 *   download    — { formats, position, icon_color, custom_sql } from page config
 *   position    — 'header_right' | 'header_left' (CSS placement modifier)
 *   downloading — true while this widget's download request is in flight
 *   onDownload  — (format: 'csv'|'xlsx') => void
 */
export default function WidgetDownloadButton({ download, position, downloading, onDownload }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 })
  const btnRef = useRef(null)
  const menuRef = useRef(null)

  const closeMenu = useCallback(() => setMenuOpen(false), [])

  useEffect(() => {
    if (!menuOpen) return undefined
    const onMouseDown = (e) => {
      if (menuRef.current?.contains(e.target) || btnRef.current?.contains(e.target)) return
      closeMenu()
    }
    const onKeyDown = (e) => { if (e.key === 'Escape') closeMenu() }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('scroll', closeMenu, true)
    window.addEventListener('resize', closeMenu)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('scroll', closeMenu, true)
      window.removeEventListener('resize', closeMenu)
    }
  }, [menuOpen, closeMenu])

  if (!download) return null
  const formats = download.formats || 'csv'
  const iconStyle = download.icon_color ? { color: download.icon_color } : undefined
  const posClass = position === 'header_left'
    ? ' pv-widget-download-btn--left'
    : ' pv-widget-download-btn--right'

  const handleClick = () => {
    if (downloading) return
    if (formats !== 'both') {
      onDownload(formats)
      return
    }
    if (menuOpen) {
      closeMenu()
      return
    }
    const rect = btnRef.current?.getBoundingClientRect()
    if (rect) {
      setMenuPos({
        top: rect.bottom + 4,
        left: Math.max(8, Math.min(rect.left, window.innerWidth - MENU_WIDTH - 8)),
      })
    }
    setMenuOpen(true)
  }

  const pick = (fmt) => {
    closeMenu()
    onDownload(fmt)
  }

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={`pv-widget-download-btn${posClass}`}
        title="Download data"
        aria-label="Download data"
        aria-haspopup={formats === 'both' ? 'menu' : undefined}
        aria-expanded={formats === 'both' ? menuOpen : undefined}
        disabled={!!downloading}
        onClick={handleClick}
        style={iconStyle}
      >
        {downloading
          ? <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
          : <i className="fa fa-download" aria-hidden="true" />}
      </button>
      {menuOpen && (
        <div
          ref={menuRef}
          className="pv-widget-download-menu"
          role="menu"
          style={{ top: menuPos.top, left: menuPos.left, width: MENU_WIDTH }}
        >
          <button type="button" role="menuitem" onClick={() => pick('csv')}>
            <i className="fa fa-file-text-o" aria-hidden="true" /> CSV
          </button>
          <button type="button" role="menuitem" onClick={() => pick('xlsx')}>
            <i className="fa fa-file-excel-o" aria-hidden="true" /> Excel (.xlsx)
          </button>
        </div>
      )}
    </>
  )
}
