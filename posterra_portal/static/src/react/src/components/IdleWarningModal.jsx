import React, { useEffect, useRef } from 'react'
import { useToken } from '../state/TokenManager'

/**
 * IdleWarningModal — "Still there?" countdown shown at timeout − 60s idle.
 *
 * State lives in TokenProvider (via useIdleTimeout); this component only
 * renders it. While it is open, ordinary activity is ignored — the ONLY
 * ways to stay signed in are the button or Escape, both of which go
 * through the refresh-first path: the modal closes only after the server
 * confirms the extension. Countdown reaching zero → full logout.
 *
 * Accessibility: role="dialog", aria-modal, focus moved in on open and
 * restored on close, Tab trapped inside, countdown in an aria-live region.
 */
export default function IdleWarningModal({ primaryColor = '#0066cc' }) {
  const { idleWarning, staySignedIn } = useToken()
  const dialogRef = useRef(null)
  const buttonRef = useRef(null)
  const previousFocusRef = useRef(null)

  const visible = idleWarning?.visible

  // Focus management: move focus in on open, restore on close.
  useEffect(() => {
    if (visible) {
      previousFocusRef.current = document.activeElement
      buttonRef.current?.focus()
    } else if (previousFocusRef.current) {
      try { previousFocusRef.current.focus() } catch (_) { /* gone */ }
      previousFocusRef.current = null
    }
  }, [visible])

  // Keyboard: Escape = explicit Stay Signed In (NOT ordinary activity —
  // it goes through the same server-confirmed extension path). Tab is
  // trapped inside the dialog.
  useEffect(() => {
    if (!visible) return undefined
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        staySignedIn()
      } else if (e.key === 'Tab') {
        // Single-button dialog — keep focus on the button.
        e.preventDefault()
        buttonRef.current?.focus()
      }
    }
    // Capture phase so the trap wins over any page-level handlers.
    document.addEventListener('keydown', onKeyDown, true)
    return () => document.removeEventListener('keydown', onKeyDown, true)
  }, [visible, staySignedIn])

  if (!visible) return null

  const secs = idleWarning.secondsLeft

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 10000,
        background: 'rgba(15, 23, 42, 0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pv-idle-title"
        aria-describedby="pv-idle-desc"
        style={{
          background: '#fff', borderRadius: 12, padding: '28px 32px',
          maxWidth: 420, width: 'calc(100% - 32px)',
          boxShadow: '0 20px 50px rgba(0,0,0,0.3)',
          textAlign: 'center', fontFamily: 'inherit',
        }}
      >
        <div style={{ fontSize: 40, marginBottom: 8 }} aria-hidden="true">⏳</div>
        <h2 id="pv-idle-title" style={{ fontSize: 20, fontWeight: 700, margin: '0 0 8px', color: '#0f172a' }}>
          Still there?
        </h2>
        <p id="pv-idle-desc" style={{ fontSize: 14, color: '#475569', margin: '0 0 4px' }}>
          You&apos;ve been inactive for a while. For your security, you&apos;ll be
          signed out automatically.
        </p>
        <p aria-live="polite" style={{ fontSize: 15, fontWeight: 600, color: '#0f172a', margin: '0 0 20px' }}>
          Signing out in {secs} second{secs === 1 ? '' : 's'}…
        </p>
        <button
          ref={buttonRef}
          type="button"
          onClick={staySignedIn}
          style={{
            background: primaryColor, color: '#fff', border: 'none',
            borderRadius: 8, padding: '10px 24px', fontSize: 15,
            fontWeight: 600, cursor: 'pointer',
          }}
        >
          Stay Signed In
        </button>
      </div>
    </div>
  )
}
