import React, {
  useState, useRef, useEffect, useCallback, useMemo, useLayoutEffect,
} from 'react'
import { createPortal } from 'react-dom'
import { useFilters } from '../state/FilterContext'
import { apiFetch, ApiError } from '../api/client'
import { filterSearchUrl } from '../api/endpoints'

/**
 * RemoteAutocomplete — server-side PAGED typeahead for a `remote_autocomplete`
 * filter. NO roster is ever preloaded: it POSTs to /filters/<id>/search on
 * open (empty query browses the first page), on typing (debounced, honouring
 * search_min_chars), and on scroll-to-bottom (next offset). The selected value
 * is a single opaque key (e.g. an EID); its human label is hydrated on value
 * change (mount / select / Back-Forward) via the hydration shape of the same
 * endpoint.
 *
 * Props:
 *   filter   — the filter config dict (id, param_name, placeholder,
 *              search_page_size, search_min_chars, control_width_px)
 *   value    — the currently selected value ('' = none)
 *   onChange — (value) => void; '' clears
 */
const DEBOUNCE_MS = 250
const AbortErr = (e) => e && (e.name === 'AbortError' || e.code === 20)

export default function RemoteAutocomplete({ filter, value, onChange }) {
  const { config, filterValues, accessToken, refreshToken, apiBase } = useFilters()

  const param = filter.param_name || filter.field_name || ''
  const pageSize = filter.search_page_size || 50
  const minChars = filter.search_min_chars || 0
  const widthPx = filter.control_width_px || 0
  const placeholder = filter.placeholder || 'Search…'

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [options, setOptions] = useState([])
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const [selectedLabel, setSelectedLabel] = useState('')
  const [rect, setRect] = useState(null)

  const inputRef = useRef(null)
  const listRef = useRef(null)
  const sentinelRef = useRef(null)
  const abortRef = useRef(null)
  const seqRef = useRef(0)          // stale-response guard
  const nextOffsetRef = useRef(0)
  const debounceRef = useRef(null)
  const hydratedForRef = useRef(null)
  const blurTimerRef = useRef(null)

  // current_values = APPLIED values of OTHER active page filters (constraints).
  // Restricted to real page-filter params so the server never 400s on an
  // unknown key, and the remote filter's own value never self-constrains.
  const currentValues = useMemo(() => {
    const valid = new Set(
      (config.filters || [])
        .map(f => f.param_name || f.field_name)
        .filter(Boolean)
    )
    const cv = {}
    for (const [k, v] of Object.entries(filterValues || {})) {
      if (k !== param && v && valid.has(k)) cv[k] = v
    }
    return cv
  }, [config.filters, filterValues, param])

  // Keep a live ref so async callbacks read fresh constraints.
  const cvRef = useRef(currentValues)
  cvRef.current = currentValues

  const post = useCallback(async (body, signal) => {
    return apiFetch(filterSearchUrl(apiBase, filter.id), accessToken, {
      method: 'POST', body: JSON.stringify(body), signal,
    }, refreshToken)
  }, [apiBase, filter.id, accessToken, refreshToken])

  // ── Search (reset=true) / paginate (reset=false) ────────────────────────
  const runSearch = useCallback(async (q, reset) => {
    const trimmed = (q || '').trim()
    // Non-empty query below the minimum → show nothing, don't hit the server.
    if (trimmed && trimmed.length < minChars) {
      if (abortRef.current) abortRef.current.abort()
      setOptions([]); setHasMore(false); setLoading(false); setError(false)
      return
    }
    if (reset) nextOffsetRef.current = 0
    const offset = nextOffsetRef.current

    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const seq = ++seqRef.current
    setLoading(true); setError(false)
    try {
      const data = await post(
        { query: trimmed, limit: pageSize, offset, current_values: cvRef.current },
        controller.signal,
      )
      if (seq !== seqRef.current) return       // a newer request superseded us
      const incoming = data.options || []
      nextOffsetRef.current = offset + pageSize
      setHasMore(!!data.has_more)
      setOptions(prev => {
        if (reset) return incoming
        const seen = new Set(prev.map(o => o.value))
        return prev.concat(incoming.filter(o => !seen.has(o.value)))
      })
      if (reset) setActiveIdx(-1)
    } catch (e) {
      if (AbortErr(e) || seq !== seqRef.current) return
      setError(true); if (reset) { setOptions([]); setHasMore(false) }
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [minChars, pageSize, post])

  // Debounced query → reset search. Empty query browses immediately (no wait).
  useEffect(() => {
    if (!open) return undefined
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (query === '') { runSearch('', true); return undefined }
    debounceRef.current = setTimeout(() => runSearch(query, true), DEBOUNCE_MS)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query, open, runSearch])

  // ── Hydrate the selected label whenever the value changes (mount, select,
  //    Back/Forward). Uses the hydration shape of the same endpoint. ──────
  useEffect(() => {
    if (!value) { setSelectedLabel(''); hydratedForRef.current = ''; return undefined }
    if (hydratedForRef.current === value) return undefined
    hydratedForRef.current = value
    let cancelled = false
    ;(async () => {
      try {
        // Identity resolution ONLY — the server scopes this by the JWT user's
        // provider access (provider_ids), NOT by sibling filters. Sending
        // current_values here would blank the label of a legitimately-selected
        // value that doesn't match another filter's applied value.
        const data = await post({ values: [value] })
        if (cancelled) return
        const opt = (data.options || [])[0]
        setSelectedLabel(opt ? opt.label : value)   // fall back to the raw key
      } catch (e) {
        if (cancelled || AbortErr(e)) return
        setSelectedLabel(value)
        hydratedForRef.current = null   // transient failure → allow a later retry
      }
    })()
    return () => { cancelled = true }
  }, [value, post])

  // Abort in-flight work + clear timers on unmount; bump the search seq so a
  // late finally can't touch state after unmount.
  useEffect(() => () => {
    seqRef.current++
    if (abortRef.current) abortRef.current.abort()
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (blurTimerRef.current) clearTimeout(blurTimerRef.current)
  }, [])

  // ── Infinite scroll: fetch the next page when the sentinel is visible ────
  useEffect(() => {
    if (!open || !hasMore) return undefined
    const el = sentinelRef.current
    if (!el || typeof IntersectionObserver === 'undefined') return undefined
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore && !loading) {
        runSearch(query, false)
      }
    }, { root: listRef.current || null, rootMargin: '120px' })
    io.observe(el)
    return () => io.disconnect()
  }, [open, hasMore, loading, query, runSearch])

  // ── Dropdown position (fixed portal → never clipped by the header) ───────
  const measure = useCallback(() => {
    const el = inputRef.current
    if (el) setRect(el.getBoundingClientRect())
  }, [])
  useLayoutEffect(() => {
    if (!open) return undefined
    measure()
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)
    return () => {
      window.removeEventListener('scroll', measure, true)
      window.removeEventListener('resize', measure)
    }
  }, [open, measure])

  const openBox = useCallback(() => {
    if (blurTimerRef.current) { clearTimeout(blurTimerRef.current); blurTimerRef.current = null }
    setOpen(true)
  }, [])

  const closeBox = useCallback(() => {
    setOpen(false); setQuery(''); setActiveIdx(-1)
    if (abortRef.current) abortRef.current.abort()
  }, [])

  const select = useCallback((opt) => {
    if (!opt) return
    hydratedForRef.current = opt.value
    setSelectedLabel(opt.label)
    onChange(opt.value)
    closeBox()
  }, [onChange, closeBox])

  const clear = useCallback(() => {
    hydratedForRef.current = ''
    setSelectedLabel('')
    onChange('')
    setQuery(''); setActiveIdx(-1)
  }, [onChange])

  const onKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault(); openBox()
      setActiveIdx(i => Math.min((i < 0 ? -1 : i) + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      if (open && activeIdx >= 0 && options[activeIdx]) { e.preventDefault(); select(options[activeIdx]) }
    } else if (e.key === 'Escape') {
      if (open) { e.preventDefault(); e.stopPropagation(); closeBox() }
    }
  }, [open, activeIdx, options, openBox, select, closeBox])

  // Keep the active row in view during keyboard nav.
  useEffect(() => {
    if (!open || activeIdx < 0 || !listRef.current) return
    const row = listRef.current.querySelector(`[data-idx="${activeIdx}"]`)
    if (row && row.scrollIntoView) row.scrollIntoView({ block: 'nearest' })
  }, [activeIdx, open])

  const shortQuery = query.trim() && query.trim().length < minChars
  const displayText = open ? query : (selectedLabel || value || '')
  const style = widthPx ? { width: widthPx + 'px' } : undefined

  return (
    <div className="pv-remote-ac" style={style}>
      <i className="fa fa-search pv-remote-ac-icon" aria-hidden="true" />
      <input
        ref={inputRef}
        type="text"
        className="pv-remote-ac-input"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-label={filter.name || placeholder}
        placeholder={placeholder}
        value={displayText}
        data-filter-id={filter.id}
        data-field-name={param}
        onFocus={openBox}
        onChange={(e) => { setQuery(e.target.value); openBox() }}
        onKeyDown={onKeyDown}
        onBlur={() => { blurTimerRef.current = setTimeout(() => setOpen(false), 120) }}
      />
      {(value || selectedLabel) && !open && (
        <button type="button" className="pv-remote-ac-clear"
                aria-label="Clear" onMouseDown={(e) => e.preventDefault()}
                onClick={clear}>
          <i className="fa fa-times" aria-hidden="true" />
        </button>
      )}

      {open && rect && createPortal(
        <div
          className="pv-remote-ac-dropdown"
          style={{ position: 'fixed', top: rect.bottom + 2, left: rect.left, width: rect.width, zIndex: 3000 }}
          onMouseDown={(e) => e.preventDefault()}  /* keep input focus on click */
        >
          <div className="pv-remote-ac-list" ref={listRef}>
            {shortQuery ? (
              <div className="pv-remote-ac-hint">Type at least {minChars} characters…</div>
            ) : error ? (
              <div className="pv-remote-ac-hint pv-remote-ac-error">Search is temporarily unavailable.</div>
            ) : (
              <>
                {options.map((opt, idx) => (
                  <div
                    key={opt.value}
                    data-idx={idx}
                    className={`pv-remote-ac-option${idx === activeIdx ? ' is-active' : ''}${opt.value === value ? ' is-selected' : ''}`}
                    onMouseEnter={() => setActiveIdx(idx)}
                    onClick={() => select(opt)}
                  >
                    {opt.label}
                  </div>
                ))}
                {!loading && options.length === 0 && (
                  <div className="pv-remote-ac-hint">No matches</div>
                )}
                {hasMore && <div ref={sentinelRef} className="pv-remote-ac-sentinel" />}
                {loading && <div className="pv-remote-ac-hint pv-remote-ac-loading">Loading…</div>}
              </>
            )}
          </div>
        </div>,
        document.body,
      )}
    </div>
  )
}
