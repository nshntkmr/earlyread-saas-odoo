import React, { useState, useRef, useEffect, useCallback } from 'react'

const POPOVER_WIDTH = 280

/**
 * WidgetInfoIcon — small (i) next to the widget title that reveals the
 * admin-configured info_text (dashboard.widget.info_text).
 *
 * Hover opens a transient popover; click pins it open (touch-friendly).
 * Same positioning model as WidgetDownloadButton's menu: position:fixed from
 * getBoundingClientRect, because .pv-widget-card clips absolute children.
 * Closes on outside mousedown, Escape, any scroll (capture) and resize.
 *
 * Text is rendered as a React text node (escaped, never HTML); newlines are
 * kept via white-space: pre-line in CSS.
 *
 * Props:
 *   text — resolved info text (already %(col)s-interpolated server-side)
 */
export default function WidgetInfoIcon({ text }) {
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const btnRef = useRef(null)
  const popRef = useRef(null)

  const close = useCallback(() => { setOpen(false); setPinned(false) }, [])

  const place = () => {
    const rect = btnRef.current?.getBoundingClientRect()
    if (rect) {
      setPos({
        top: rect.bottom + 6,
        left: Math.max(8, Math.min(rect.left - 12, window.innerWidth - POPOVER_WIDTH - 8)),
      })
    }
  }

  useEffect(() => {
    if (!open) return undefined
    const onMouseDown = (e) => {
      if (popRef.current?.contains(e.target) || btnRef.current?.contains(e.target)) return
      close()
    }
    const onKeyDown = (e) => { if (e.key === 'Escape') close() }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [open, close])

  if (!text) return null

  const handleClick = () => {
    if (pinned) { close(); return }
    place()
    setOpen(true)
    setPinned(true)
  }
  const handleEnter = () => {
    if (open) return
    place()
    setOpen(true)
  }
  const handleLeave = () => { if (!pinned) setOpen(false) }

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        className={`pv-widget-info-btn${open ? ' is-open' : ''}`}
        aria-label="About this widget"
        aria-expanded={open}
        onClick={handleClick}
        onMouseEnter={handleEnter}
        onMouseLeave={handleLeave}
        onFocus={handleEnter}
        onBlur={handleLeave}
      >
        <i className="fa fa-info-circle" aria-hidden="true" />
      </button>
      {open && (
        <div
          ref={popRef}
          className="pv-widget-info-popover"
          role="tooltip"
          style={{ top: pos.top, left: pos.left, width: POPOVER_WIDTH }}
        >
          {text}
        </div>
      )}
    </>
  )
}
