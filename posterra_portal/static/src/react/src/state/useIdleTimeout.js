import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * useIdleTimeout — per-app idle timeout for the portal SPA.
 *
 * Invoked INSIDE TokenProvider (TokenManager.jsx) so the refresh gate and
 * the activity refs live in the same component. The hook is pure logic;
 * the provider owns the state and exposes the modal through its context.
 *
 * Design contract (see plan "Per-App Configurable Idle Timeout"):
 *  - The client never sends a timestamp. It calls session-refresh ONLY
 *    when real user activity is fresh; the server stamps its own clock.
 *  - An untouched tab makes ZERO refresh calls: token lapses, warning
 *    modal at timeout − 60s, logout at timeout.
 *  - While the warning modal is open, ordinary activity is IGNORED.
 *    Only Stay Signed In / Escape (explicit, server-confirmed) or an
 *    advance of the shared server-stamp key (a sibling tab's confirmed
 *    refresh) extends the session.
 */

// ── Constants — internally consistent, keep the invariants ──────────────────
export const TICK_MS = 15_000            // watcher interval (stamp sync ONLY)
export const WARNING_LEAD_MS = 60_000    // modal shows at timeout − 60s idle
// Min spacing between server stamps while active. MUST be ≤ WARNING_LEAD_MS.
export const STAMP_INTERVAL_MS = 60_000
// Refresh-gate recency window. MUST be ≥ STAMP_INTERVAL_MS + 2×TICK_MS so the
// trailing-edge stamp lands before freshness expires.
export const ACTIVITY_FRESH_MS = 90_000

const ACTIVITY_WRITE_THROTTLE_MS = 30_000  // localStorage write throttle
const LOGOUT_URL = '/web/session/logout?redirect=/login'

const ACTIVITY_EVENTS = [
  'mousemove', 'keydown', 'click', 'scroll', 'touchstart',
  'pointerdown', 'wheel', 'input',
]

// ── Safe storage — secure browser modes can throw on localStorage ───────────
// Degrades to per-tab in-memory behavior (cross-tab sync off, all else works).

export function safeGet(key) {
  try {
    const v = window.localStorage.getItem(key)
    return v === null ? null : Number(v) || 0
  } catch (_) {
    return null
  }
}

export function safeSet(key, value) {
  try {
    window.localStorage.setItem(key, String(value))
    return true
  } catch (_) {
    return false
  }
}

/** Single key helper — always app AND user scoped, no bare variants. */
export function storageKey(kind, appKey, userId) {
  return `pp_${kind}_${appKey}_${userId}`
}

/**
 * @param {object}   opts
 * @param {number}   opts.timeoutMins        app's idle timeout (0 = disabled)
 * @param {string}   opts.appKey
 * @param {number}   opts.userId
 * @param {Function} opts.refreshToken       provider's refreshToken({explicit})
 * @param {Function} opts.flushActivityStamp fire-and-forget keepalive stamp
 * @param {object}   opts.lastServerStampAtRef ref owned by TokenProvider,
 *                   updated on every successful refresh (epoch ms)
 * @param {object}   opts.idleApiRef         ref the hook populates with
 *                   { activityFresh } for the provider's refresh gate
 */
export function useIdleTimeout({
  timeoutMins,
  appKey,
  userId,
  refreshToken,
  flushActivityStamp,
  lastServerStampAtRef,
  idleApiRef,
}) {
  const enabled = (timeoutMins || 0) > 0
  const timeoutMs = (timeoutMins || 0) * 60_000

  const activityKey = storageKey('activity', appKey, userId)
  const serverStampKey = storageKey('server_stamp', appKey, userId)

  // ── Two separate signals (plan r7 P1) ─────────────────────────────────
  // Idle clock: drives warning/logout. Seeded in-memory on mount — the
  // seed is NEVER written to storage (no phantom cross-tab events).
  const lastActivityRef = useRef(0)
  // Sync signal: drives stamp-sync + the refresh gate. Set ONLY by
  // markActivity() (real input) or storage events (a sibling's real-
  // activity write). 0 on mount — an untouched tab has no real activity.
  const lastRealActivityAtRef = useRef(0)

  const modalOpenRef = useRef(false)
  const [idleWarning, setIdleWarning] = useState({ visible: false, secondsLeft: 0 })

  // Throttle state for the activity storage write (leading + trailing).
  const lastWriteAtRef = useRef(0)
  const trailingWriteTimerRef = useRef(null)

  const warningTimerRef = useRef(null)
  const countdownIntervalRef = useRef(null)
  const tickIntervalRef = useRef(null)

  // Shared server stamp from sibling tabs (via storage events).
  const sharedServerStampRef = useRef(0)

  /** Server stamp = max(own ref, shared key) — avoids duplicate pings. */
  const serverStampAt = useCallback(() => {
    return Math.max(
      lastServerStampAtRef.current || 0,
      sharedServerStampRef.current || 0,
      safeGet(serverStampKey) || 0,
    )
  }, [lastServerStampAtRef, serverStampKey])

  const doLogout = useCallback(() => {
    window.location.href = LOGOUT_URL
  }, [])

  // ── Warning / logout timers — lazy-exact, never throttled ─────────────
  // One setTimeout armed from lastActivityRef; on fire, re-read the ref
  // and re-arm for the remainder if activity moved. Exact without
  // rescheduling on every mousemove.

  const openWarningRef = useRef(() => {})
  const armWarningTimer = useCallback(() => {
    if (!enabled) return
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current)
    const fireAt = lastActivityRef.current + timeoutMs - WARNING_LEAD_MS
    const delay = Math.max(fireAt - Date.now(), 0)
    warningTimerRef.current = setTimeout(() => {
      const remaining = lastActivityRef.current + timeoutMs - WARNING_LEAD_MS - Date.now()
      if (remaining > 500) {
        armWarningTimer() // activity moved — re-arm for the remainder
      } else {
        openWarningRef.current()
      }
    }, delay)
  }, [enabled, timeoutMs])

  const closeWarning = useCallback(() => {
    modalOpenRef.current = false
    setIdleWarning({ visible: false, secondsLeft: 0 })
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current)
      countdownIntervalRef.current = null
    }
  }, [])

  const openWarning = useCallback(() => {
    if (modalOpenRef.current) return
    modalOpenRef.current = true
    const logoutAt = lastActivityRef.current + timeoutMs
    const secs = Math.max(Math.ceil((logoutAt - Date.now()) / 1000), 0)
    setIdleWarning({ visible: true, secondsLeft: secs })
    // 1s interval ONLY while the modal is open — countdown display + logout.
    countdownIntervalRef.current = setInterval(() => {
      const left = Math.ceil((logoutAt - Date.now()) / 1000)
      if (left <= 0) {
        doLogout()
      } else {
        setIdleWarning({ visible: true, secondsLeft: left })
      }
    }, 1000)
  }, [timeoutMs, doLogout])
  openWarningRef.current = openWarning

  /** Reset the idle clock after a SERVER-CONFIRMED extension. */
  const resetIdleClock = useCallback((now) => {
    lastActivityRef.current = now
    lastRealActivityAtRef.current = now
    closeWarning()
    armWarningTimer()
  }, [closeWarning, armWarningTimer])

  // ── Activity storage write — leading + trailing throttle ─────────────
  // A leading-only throttle would drop the last activity inside the
  // window; sibling tabs read this key for their countdown and would
  // warn/logout up to 30s early.
  const writeActivity = useCallback((ts) => {
    lastWriteAtRef.current = Date.now()
    safeSet(activityKey, ts)
  }, [activityKey])

  const flushPendingActivityWrite = useCallback(() => {
    if (trailingWriteTimerRef.current) {
      clearTimeout(trailingWriteTimerRef.current)
      trailingWriteTimerRef.current = null
      writeActivity(lastRealActivityAtRef.current || lastActivityRef.current)
    }
  }, [writeActivity])

  const throttledWriteActivity = useCallback((ts) => {
    const now = Date.now()
    if (now - lastWriteAtRef.current >= ACTIVITY_WRITE_THROTTLE_MS) {
      writeActivity(ts) // leading edge
    } else if (!trailingWriteTimerRef.current) {
      const wait = ACTIVITY_WRITE_THROTTLE_MS - (now - lastWriteAtRef.current)
      trailingWriteTimerRef.current = setTimeout(() => {
        trailingWriteTimerRef.current = null
        // trailing edge — flush the LATEST activity timestamp
        writeActivity(lastRealActivityAtRef.current || ts)
      }, wait)
    }
  }, [writeActivity])

  // ── markActivity — real input in THIS tab ─────────────────────────────
  const markActivity = useCallback((force = false) => {
    const now = Date.now()
    // In-memory refs update on EVERY event — never throttled (throttled
    // refs would log users out up to 30s early).
    lastActivityRef.current = now
    lastRealActivityAtRef.current = now
    if (force) {
      writeActivity(now)
    } else {
      throttledWriteActivity(now)
    }
    // Immediate activity ping (r14): don't wait up to 15s for the tick —
    // a user returning at timeout − 2s from a throttled tab would
    // otherwise cross the server deadline. The gate passes (activity is
    // fresh by construction).
    if (enabled && now - serverStampAt() >= STAMP_INTERVAL_MS) {
      refreshToken()
    }
  }, [enabled, writeActivity, throttledWriteActivity, serverStampAt, refreshToken])

  // ── Stay Signed In — extend only AFTER the refresh succeeds (r15) ─────
  const staySignedIn = useCallback(async () => {
    const newToken = await refreshToken({ explicit: true })
    if (newToken) {
      const now = Date.now()
      // Server confirmed: NOW reset refs, write storage past the
      // throttle, close the modal.
      writeActivity(now)
      resetIdleClock(now)
    }
    // Failure: fail closed — countdown keeps running; a 401 already
    // redirected via the standard handler.
  }, [refreshToken, writeActivity, resetIdleClock])

  // Expose the gate reading to the provider's refreshToken().
  useEffect(() => {
    if (idleApiRef) {
      idleApiRef.current = {
        // Refresh gate: real activity within the freshness window. Reads
        // the sync signal — NEVER the seeded idle clock.
        activityFresh: () =>
          lastRealActivityAtRef.current > 0 &&
          Date.now() - lastRealActivityAtRef.current <= ACTIVITY_FRESH_MS,
        enabled,
      }
    }
  }, [idleApiRef, enabled])

  // ── Main effect: listeners + timers ───────────────────────────────────
  useEffect(() => {
    // Armed-state beacon — instant field check that the RUNNING bundle
    // has the idle watcher and what config it received (a stale cached
    // bundle prints nothing).
    if (!enabled) {
      console.info('[idle] disabled (timeout=0)')
      return undefined
    }
    console.info(
      `[idle] timeout active: ${timeoutMins} min — warning at ${timeoutMins - 1}:00, logout at ${timeoutMins}:00`
    )

    // Seed the idle clock (in-memory ONLY — no storage write, no phantom
    // events). Stale stored value from a previous session is ignored.
    const now = Date.now()
    const stored = safeGet(activityKey)
    lastActivityRef.current =
      stored && now - stored < timeoutMs ? Math.max(stored, 0) : now
    // Sync signal stays 0 — an untouched tab makes zero refresh calls.

    const onActivity = () => {
      // Activity is IGNORED while the modal is open (r13): only the
      // explicit Stay Signed In / Escape path extends.
      if (modalOpenRef.current) return
      markActivity(false)
    }
    ACTIVITY_EVENTS.forEach((ev) =>
      window.addEventListener(ev, onActivity, { passive: true })
    )

    // Cross-tab sync via storage events.
    const onStorage = (e) => {
      if (e.key === serverStampKey) {
        const ts = Number(e.newValue) || 0
        if (ts > sharedServerStampRef.current) sharedServerStampRef.current = ts
        // A sibling's SERVER-CONFIRMED refresh may dismiss our modal
        // (r14/r20: server-stamp proof required, never the activity key).
        if (modalOpenRef.current && ts > 0) {
          resetIdleClock(Date.now())
        }
        return
      }
      if (e.key === activityKey) {
        // r20: while the modal is open, activity-key events are ignored
        // for BOTH the idle clock and the refresh gate — a sibling's
        // activity write may arrive before its server stamp, and a 401
        // retry here must not extend the session without server proof.
        if (modalOpenRef.current) return
        const ts = Number(e.newValue) || 0
        if (ts > lastActivityRef.current) lastActivityRef.current = ts
        if (ts > lastRealActivityAtRef.current) lastRealActivityAtRef.current = ts
      }
    }
    window.addEventListener('storage', onStorage)

    // Watcher tick — STAMP SYNC ONLY (no role in warning/logout timing).
    // Fires refreshToken() iff: unsynced real activity, still fresh, and
    // the rate limit elapsed. The 90s freshness window outlives the 60s
    // rate limit + tick slack, so one final tick lands AFTER the user's
    // last input (trailing-edge stamp → late Stay Signed In can never be
    // stale on the server).
    tickIntervalRef.current = setInterval(() => {
      const t = Date.now()
      const lastReal = lastRealActivityAtRef.current
      const stamp = serverStampAt()
      if (
        lastReal > stamp &&
        t - lastReal <= ACTIVITY_FRESH_MS &&
        t - stamp >= STAMP_INTERVAL_MS
      ) {
        refreshToken()
      }
    }, TICK_MS)

    // Immediate idle check on resume — BEFORE any refresh attempt. After
    // laptop sleep / frozen tab, PHI must not stay on screen for another
    // tick. (TokenManager's visibility refresh is gated anyway — an idle
    // tab's refresh is a no-op — but the logout must not wait.)
    const onResume = () => {
      if (document.visibilityState && document.visibilityState !== 'visible') return
      if (Date.now() - lastActivityRef.current >= timeoutMs) {
        doLogout()
      }
    }
    document.addEventListener('visibilitychange', onResume)
    window.addEventListener('focus', onResume)
    window.addEventListener('pageshow', onResume)

    // Hide/unload: flush the pending throttled activity write FIRST
    // (sibling tabs count down from this key — r18), then the keepalive
    // server stamp for unsynced fresh activity (r7).
    const onHide = () => {
      flushPendingActivityWrite()
      const t = Date.now()
      const lastReal = lastRealActivityAtRef.current
      if (
        lastReal > serverStampAt() &&
        t - lastReal <= ACTIVITY_FRESH_MS
      ) {
        flushActivityStamp()
      }
    }
    const onVisHidden = () => {
      if (document.visibilityState === 'hidden') onHide()
    }
    document.addEventListener('visibilitychange', onVisHidden)
    window.addEventListener('pagehide', onHide)

    armWarningTimer()

    return () => {
      ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity))
      window.removeEventListener('storage', onStorage)
      document.removeEventListener('visibilitychange', onResume)
      window.removeEventListener('focus', onResume)
      window.removeEventListener('pageshow', onResume)
      document.removeEventListener('visibilitychange', onVisHidden)
      window.removeEventListener('pagehide', onHide)
      onHide() // hook cleanup counts as hide — flush pending write
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current)
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current)
      if (tickIntervalRef.current) clearInterval(tickIntervalRef.current)
      if (trailingWriteTimerRef.current) clearTimeout(trailingWriteTimerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, timeoutMs, appKey, userId])

  return { idleWarning, staySignedIn }
}
