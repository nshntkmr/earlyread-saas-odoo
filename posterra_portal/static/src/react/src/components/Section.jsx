import { useState, useEffect, useRef, useCallback } from 'react'
import { useFilters } from '../state/FilterContext'
import { useToken } from '../state/TokenManager'
import ScopeDropdown from './ScopeDropdown'
import ComparisonBar from './ComparisonBar'
import LeaderboardTable from './LeaderboardTable'

/**
 * Section — interactive dashboard section with optional scoping dropdown.
 *
 * Initialised with server-rendered data (no loading flash).  When the scope
 * dropdown or page filters change, re-fetches data from the section API.
 *
 * Props:
 *   config — section config object from initialSections JSON
 *   apiBase — API base URL (e.g. "/api/v1")
 */
export default function Section({ config, apiBase }) {
  const { filterValues, config: pageConfig } = useFilters()
  const { token } = useToken()
  const [sectionData, setSectionData] = useState(config.data || {})
  const [scopeValue, setScopeValue] = useState('')
  const [loading, setLoading] = useState(false)
  const mountedRef = useRef(true)
  const initialRender = useRef(true)

  const scope = config.scope || { mode: 'none' }

  // Build scope dropdown options
  const scopeOptions = (() => {
    if (scope.mode === 'dependent' && scope.filter_id) {
      // Read options from the linked page filter in pageConfig
      const linkedFilter = (pageConfig?.filters || []).find(
        f => f.id === scope.filter_id
      )
      return linkedFilter?.options || []
    }
    if (scope.mode === 'independent') {
      return scope.options || []
    }
    return []
  })()

  // Initialise scope value from defaults or linked filter
  useEffect(() => {
    if (scope.mode === 'dependent' && scope.filter_param) {
      const filterVal = filterValues[scope.filter_param] || ''
      setScopeValue(scope.default_value || filterVal)
    } else if (scope.mode === 'independent') {
      setScopeValue(scope.default_value || '')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch section data from API
  const fetchSectionData = useCallback(async (currentScopeValue) => {
    if (!token) return

    // Build query params from current filter values
    const params = new URLSearchParams()
    for (const [key, val] of Object.entries(filterValues)) {
      if (val !== '' && val !== null && val !== undefined) {
        params.set(key, val)
      }
    }
    // Add scope override if set
    if (currentScopeValue && scope.param_name) {
      params.set(scope.param_name, currentScopeValue)
    }

    const url = `${apiBase}/section/${config.id}/data?${params.toString()}`
    setLoading(true)
    try {
      const resp = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const json = await resp.json()
      if (mountedRef.current && json.data) {
        setSectionData(json.data)
      }
    } catch (err) {
      console.error(`Section ${config.id} fetch error:`, err)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [filterValues, scope.param_name, config.id, apiBase, token])

  // Re-fetch when page filters change (after Apply)
  useEffect(() => {
    if (initialRender.current) {
      initialRender.current = false
      return
    }
    fetchSectionData(scopeValue)
  }, [filterValues]) // eslint-disable-line react-hooks/exhaustive-deps

  // Sync dependent scope with filter changes
  useEffect(() => {
    if (scope.mode !== 'dependent' || !scope.filter_param) return
    if (initialRender.current) return
    const filterVal = filterValues[scope.filter_param] || ''
    if (filterVal !== scopeValue) {
      setScopeValue(filterVal)
    }
  }, [filterValues]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => { mountedRef.current = false }
  }, [])

  // Handle scope dropdown change
  const handleScopeChange = (newValue) => {
    setScopeValue(newValue)
    fetchSectionData(newValue)
  }

  const hasError = sectionData?.error
  const icon = config.icon || (config.section_type === 'leaderboard_table' ? 'fa-trophy' : 'fa-bar-chart')

  return (
    <div className="pv-section">
      <div className="pv-section-header">
        <div className="pv-section-title">
          <i className={`fa ${icon} me-2`} />
          {config.name}
        </div>
        {scope.mode !== 'none' ? (
          <ScopeDropdown
            label={scope.label}
            options={scopeOptions}
            value={scopeValue}
            onChange={handleScopeChange}
          />
        ) : (
          config.action_label && (
            <span className="pv-section-tag">{config.action_label}</span>
          )
        )}
      </div>

      {config.subtitle && (
        <div className="pv-section-subtitle text-muted small">{config.subtitle}</div>
      )}
      {config.description && (
        <p className="pv-section-desc text-muted small mb-2">{config.description}</p>
      )}

      {loading && <div className="pv-section-loading text-muted small">Loading...</div>}

      {!hasError && config.section_type === 'comparison_bar' && (
        <ComparisonBar data={sectionData} />
      )}
      {!hasError && config.section_type === 'leaderboard_table' && (
        <LeaderboardTable data={sectionData} />
      )}

      {config.footnote && (
        <div className="pv-section-footnote text-muted small mt-2 pt-2 border-top">
          {config.footnote}
        </div>
      )}
    </div>
  )
}
