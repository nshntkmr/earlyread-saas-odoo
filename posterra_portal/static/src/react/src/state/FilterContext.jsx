import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { useToken } from './TokenManager'
import { apiFetch } from '../api/client'
import { filterStateSaveUrl, filterStateLoadUrl } from '../api/endpoints'

const FilterContext = createContext(null)

/** Push filter values + tab to URL as query params (standard flow). */
function _pushUrlParams(filterValues, currentTabKey, hiddenKeys) {
  const params = new URLSearchParams()
  Object.entries(filterValues).forEach(([k, v]) => {
    if (v && v !== '' && !hiddenKeys.has(k)) params.set(k, v)
  })
  if (currentTabKey) params.set('tab', currentTabKey)
  const qs = params.toString()
  window.history.pushState({ filterValues, currentTabKey }, '', qs ? '?' + qs : window.location.pathname)
}

/**
 * FilterProvider
 *
 * Manages:
 *   - filterValues  — the last *applied* filter values (triggers widget refetch)
 *   - pendingValues — values being edited in the filter bar (not yet applied)
 *   - currentTabKey — active tab
 *   - URL sync      — applied filters + tab reflected in query params (shareable links)
 *   - popstate      — browser back/forward restores filter state
 *   - permalink     — server-side state storage for complex filter configs
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
    // Skip the 'state' key — it's the permalink token, not a filter value
    const params = new URLSearchParams(window.location.search)
    params.forEach((v, k) => {
      if (k !== 'state') defaults[k] = v
    })
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

  // ── Permalink: load server-side state on mount if ?state=<key> ──────────────
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const stateKey = params.get('state')
    if (!stateKey || !accessToken) return

    ;(async () => {
      try {
        const url = filterStateLoadUrl(apiBase, stateKey)
        const data = await apiFetch(url, accessToken, {}, refreshToken)
        const config = data.filter_config || {}
        if (Object.keys(config).length > 0) {
          console.debug('[PERMALINK] Loaded state from key:', stateKey, config)
          setFilterValues(prev => ({ ...prev, ...config }))
          setPendingValues(prev => ({ ...prev, ...config }))
        }
      } catch (err) {
        console.warn('[PERMALINK] Failed to load state for key:', stateKey, err)
      }
    })()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── URL sync ─────────────────────────────────────────────────────────────────
  // Hidden (auto-fill-only) filters are resolved server-side; keep them out of the URL
  // to avoid stale values overriding the server-derived auto-fill.
  const hiddenKeys = React.useMemo(() => new Set(
    (pageConfig.filters || [])
      .filter(f => f.is_visible === false)
      .map(f => f.param_name || f.field_name)
      .filter(Boolean)
  ), [pageConfig])

  /** Determine if filter state is complex enough to warrant a permalink.
   *  Threshold: >2000 chars when encoded as URL params. */
  const shouldUsePermalink = useCallback((values) => {
    const params = new URLSearchParams()
    Object.entries(values).forEach(([k, v]) => {
      if (v && v !== '' && !hiddenKeys.has(k)) params.set(k, v)
    })
    return params.toString().length > 2000
  }, [hiddenKeys])

  useEffect(() => {
    if (!isMounted.current) {
      isMounted.current = true
      return
    }

    // If state is complex, save server-side and use short URL
    if (shouldUsePermalink(filterValues) && accessToken && pageConfig.page?.id) {
      ;(async () => {
        try {
          const url = filterStateSaveUrl(apiBase)
          const data = await apiFetch(url, accessToken, {
            method: 'POST',
            body: JSON.stringify({
              page_id: pageConfig.page.id,
              filter_config: filterValues,
            }),
          }, refreshToken)
          const params = new URLSearchParams()
          params.set('state', data.key)
          if (currentTabKey) params.set('tab', currentTabKey)
          const qs = params.toString()
          window.history.pushState({ filterValues, currentTabKey }, '', '?' + qs)
          console.debug('[PERMALINK] Saved state, key:', data.key)
        } catch (err) {
          console.warn('[PERMALINK] Save failed, falling back to URL params:', err)
          // Fallback: put all params in URL
          _pushUrlParams(filterValues, currentTabKey, hiddenKeys)
        }
      })()
    } else {
      _pushUrlParams(filterValues, currentTabKey, hiddenKeys)
    }
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
