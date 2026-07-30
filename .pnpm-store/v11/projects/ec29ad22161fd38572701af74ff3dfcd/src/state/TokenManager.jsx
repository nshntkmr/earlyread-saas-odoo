import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react'
import { useIdleTimeout, storageKey, safeSet } from './useIdleTimeout'

const TokenContext = createContext(null)

/**
 * How far before expiry (in ms) to proactively refresh.
 * 5 minutes before a 1-hour TTL → refresh at ~55 min. For shorter
 * per-app TTLs the margin adapts to 20% of the TTL so a 5-min token
 * doesn't try to refresh every 30 seconds.
 */
const REFRESH_MARGIN_MS = 5 * 60 * 1000

/**
 * TokenProvider
 *
 * Manages the JWT access token lifecycle:
 *   1. Proactive refresh — schedules a timer to silently fetch a new token
 *      before the current one expires.
 *   2. 401 safety net   — exposes refreshToken() so apiFetch can retry on 401.
 *   3. Per-app idle timeout — when the app has session_idle_timeout_mins > 0,
 *      refreshToken() is GATED on fresh real user activity (an idle tab makes
 *      zero refresh calls and its token lapses), and useIdleTimeout drives the
 *      warning modal + logout. The gate lives HERE, inside refreshToken()
 *      itself, because apiFetch's 401 retry also lands here — a background
 *      widget retry must never revive an idle session.
 */
export function TokenProvider({
  children,
  initialToken,
  appKey,
  apiBase,
  initialExpiresIn,
  idleTimeoutMins = 0,
  userId = 0,
}) {
  const [token, setToken] = useState(initialToken || '')
  const timerRef = useRef(null)
  const refreshingRef = useRef(null) // dedup concurrent refresh calls

  // Server-stamp bookkeeping for the idle watcher. The boot token was
  // just stamped server-side by app_dashboard, so mount = fresh stamp.
  const lastServerStampAtRef = useRef(Date.now())
  // Populated by useIdleTimeout with { activityFresh, enabled }.
  const idleApiRef = useRef(null)

  const idleEnabled = (idleTimeoutMins || 0) > 0
  const serverStampKey = storageKey('server_stamp', appKey, userId)

  const recordServerStamp = useCallback(() => {
    const now = Date.now()
    lastServerStampAtRef.current = now
    // Shared cross-tab so sibling tabs don't fire duplicate stamp
    // refreshes — and so a sibling's modal can dismiss on SERVER-
    // CONFIRMED activity (it only trusts this key, never the activity key).
    safeSet(serverStampKey, now)
  }, [serverStampKey])

  /**
   * Fetch a fresh token from the session-refresh endpoint.
   *
   * @param {object}  opts
   * @param {boolean} opts.explicit — Stay Signed In / Escape path: bypasses
   *   the activity-recency gate (the user's explicit action IS the proof of
   *   presence; the server still enforces its own stamp gap).
   */
  const refreshToken = useCallback(async ({ explicit = false } = {}) => {
    // ── Idle activity gate (inside refreshToken on purpose) ──────────
    // Non-explicit refreshes (proactive timer, visibility, apiFetch 401
    // retry) are refused with NO network call unless real user activity
    // is fresh. An untouched tab therefore never refreshes and cannot
    // slide the server's idle stamp.
    if (idleEnabled && !explicit) {
      const gate = idleApiRef.current
      if (!gate || !gate.activityFresh()) return null
    }

    // Dedup: if a refresh is already in flight, reuse its promise
    if (refreshingRef.current) return refreshingRef.current

    const promise = (async () => {
      try {
        const params = appKey ? `?app_key=${encodeURIComponent(appKey)}` : ''
        const res = await fetch(`${apiBase}/auth/session-refresh${params}`, {
          method: 'POST',
          credentials: 'same-origin', // send the Odoo session cookie
          headers: {
            'Content-Type': 'application/json',
            // Same-origin proof — required by the server for idle-enabled
            // apps (this csrf=False endpoint doubles as the activity stamp).
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
        if (!res.ok) {
          // Fail closed on any "this session cannot be extended" status:
          //   401/303 — session expired or killed by the idle check
          //   403     — refresh refused (header rejected, access revoked)
          // All three go to the BRANDED login via the same logout path as
          // the manual Sign Out button (a bare reload could land on Odoo's
          // generic redirect). Leaving PHI on screen after a refusal is
          // never acceptable. Network errors / 5xx stay transient (thrown
          // + logged below): a server blip must not kick out an active
          // user — the idle clock and the server backstop still enforce.
          if (res.status === 401 || res.status === 303 || res.status === 403) {
            window.location.href = '/web/session/logout?redirect=/login'
            return null
          }
          throw new Error(`Token refresh failed: ${res.status}`)
        }
        const data = await res.json()
        const newToken = data.access_token
        const expiresIn = data.expires_in || 3600
        setToken(newToken)
        recordServerStamp()
        scheduleRefresh(expiresIn)
        return newToken
      } catch (err) {
        console.error('[TokenManager] refresh error:', err)
        return null
      } finally {
        refreshingRef.current = null
      }
    })()

    refreshingRef.current = promise
    return promise
  }, [appKey, apiBase, idleEnabled, recordServerStamp]) // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Fire-and-forget server activity stamp for hide/unload (keepalive).
   * Deliberately does NOT touch refreshingRef (a concurrent apiFetch
   * retry must never receive this discarded promise), does not setToken,
   * and schedules nothing — React state and timers are unreliable during
   * unload; the point is only the server-side stamp.
   */
  const flushActivityStamp = useCallback(() => {
    try {
      const params = appKey ? `?app_key=${encodeURIComponent(appKey)}` : ''
      fetch(`${apiBase}/auth/session-refresh${params}`, {
        method: 'POST',
        credentials: 'same-origin',
        keepalive: true,
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
        },
      }).catch(() => {})
    } catch (_) { /* unload paths must never throw */ }
  }, [appKey, apiBase])

  /** Schedule the next proactive refresh (margin adapts to short TTLs). */
  const scheduleRefresh = useCallback((expiresInSec) => {
    if (timerRef.current) clearTimeout(timerRef.current)
    const margin = Math.min(REFRESH_MARGIN_MS, expiresInSec * 1000 * 0.2)
    const delayMs = Math.max((expiresInSec * 1000) - margin, 30_000)
    timerRef.current = setTimeout(() => { refreshToken() }, delayMs)
  }, [refreshToken])

  // On mount: schedule the first proactive refresh from the REAL initial
  // TTL (per-app — a 15-min-timeout app issues 15-min boot tokens; the
  // old hardcoded 3600 would let that token die long before the refresh).
  useEffect(() => {
    if (token) {
      scheduleRefresh(initialExpiresIn || 3600)
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Handle tab visibility: refresh immediately when tab becomes visible
  // after being backgrounded (browser may have throttled the timer).
  // For idle-enabled apps the useIdleTimeout resume check runs its own
  // logout-first check; this refresh is gated anyway (idle → no-op).
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        refreshToken()
      }
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [refreshToken])

  // ── Idle watcher — owns activity tracking, warning modal, logout ──────
  // Invoked inside the provider so the gate and the refs share one owner.
  // No-op when idleTimeoutMins is 0.
  const { idleWarning, staySignedIn } = useIdleTimeout({
    timeoutMins: idleTimeoutMins,
    appKey,
    userId,
    refreshToken,
    flushActivityStamp,
    lastServerStampAtRef,
    idleApiRef,
  })

  return (
    <TokenContext.Provider value={{ token, refreshToken, idleWarning, staySignedIn }}>
      {children}
    </TokenContext.Provider>
  )
}

/** Hook to access the current token and refresh function. */
export const useToken = () => {
  const ctx = useContext(TokenContext)
  if (!ctx) throw new Error('useToken must be used inside <TokenProvider>')
  return ctx
}
