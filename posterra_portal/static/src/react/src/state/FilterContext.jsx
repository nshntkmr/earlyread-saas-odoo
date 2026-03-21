import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { useToken } from './TokenManager'

const FilterContext = createContext(null)

/**
 * FilterProvider
 *
 * Manages:
 *   - filterValues  — the last *applied* filter values (triggers widget refetch)
 *   - pendingValues — values being edited in the filter bar (not yet applied)
 *   - currentTabKey — active tab
 *   - URL sync      — applied filters + tab reflected in query params (shareable links)
 *   - popstate      — browser back/forward restores filter state
 */
export function FilterProvider({ children, pageConfig, apiBase }) {
  const { token: accessToken, refreshToken } = useToken()
  // ── Helpers ─────────────────────────────────────────────────────────────────

  /** Build initial values from config defaults + current URL params */
  const buildDefaults = useCallback(() => {
    const defaults = {}
    ;(pageConfig.filters || []).forEach(f => {
      if (f.is_visible === false) return          // hidden (auto-fill-only) filters are server-side only
      const key = f.param_name || f.field_name
      if (!key) return                             // skip filters with no param key
      defaults[key] = f.default_value || ''
    })
    // Override with URL query params (deep link support)
    const params = new URLSearchParams(window.location.search)
    params.forEach((v, k) => { defaults[k] = v })
    return defaults
  }, [pageConfig])

  const buildInitialTab = useCallback(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('tab') || pageConfig.current_tab_key || (pageConfig.tabs?.[0]?.key || '')
  }, [pageConfig])

  // ── State ────────────────────────────────────────────────────────────────────
  const [filterValues,  setFilterValues]  = useState(buildDefaults)
  const [pendingValues, setPendingValues] = useState(buildDefaults)
  const [currentTabKey, setCurrentTabKey] = useState(buildInitialTab)

  // Track whether this is the first mount (skip history push on init)
  const isMounted = useRef(false)

  // ── URL sync ─────────────────────────────────────────────────────────────────
  // Hidden (auto-fill-only) filters are resolved server-side; keep them out of the URL
  // to avoid stale values overriding the server-derived auto-fill.
  const hiddenKeys = React.useMemo(() => new Set(
    (pageConfig.filters || [])
      .filter(f => f.is_visible === false)
      .map(f => f.param_name || f.field_name)
      .filter(Boolean)
  ), [pageConfig])

  useEffect(() => {
    if (!isMounted.current) {
      isMounted.current = true
      return
    }
    const params = new URLSearchParams()
    Object.entries(filterValues).forEach(([k, v]) => {
      if (v && v !== '' && !hiddenKeys.has(k)) params.set(k, v)
    })
    if (currentTabKey) params.set('tab', currentTabKey)
    const qs = params.toString()
    window.history.pushState({ filterValues, currentTabKey }, '', qs ? '?' + qs : window.location.pathname)
  }, [filterValues, currentTabKey, hiddenKeys]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Browser back/forward ─────────────────────────────────────────────────────
  useEffect(() => {
    const onPop = (e) => {
      if (e.state?.filterValues) {
        setFilterValues(e.state.filterValues)
        setPendingValues(e.state.filterValues)
        setCurrentTabKey(e.state.currentTabKey || '')
      }
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  // ── Actions ──────────────────────────────────────────────────────────────────

  /** Called when the user clicks Apply in the filter bar */
  const applyFilters = useCallback(() => {
    setFilterValues({ ...pendingValues })
  }, [pendingValues])

  /** Update a single pending (unapplied) filter value */
  const setPendingFilter = useCallback((fieldName, value) => {
    setPendingValues(prev => ({ ...prev, [fieldName]: value }))
  }, [])

  return (
    <FilterContext.Provider value={{
      config:          pageConfig,
      filterValues,
      pendingValues,
      setPendingFilter,
      applyFilters,
      currentTabKey,
      setCurrentTabKey,
      accessToken,
      refreshToken,
      apiBase,
    }}>
      {children}
    </FilterContext.Provider>
  )
}

/** Hook for consuming filter context */
export const useFilters = () => {
  const ctx = useContext(FilterContext)
  if (!ctx) throw new Error('useFilters must be used inside <FilterProvider>')
  return ctx
}
