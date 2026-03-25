import React, { useState, useEffect } from 'react'
import { designerFetch } from '../../api/client'
import { pageFiltersUrl } from '../../api/endpoints'

/**
 * PageFilterPanel — Renders real page filter dropdowns for designer preview.
 *
 * When an admin selects a page in the AppContextBar, this component
 * fetches the page's actual filter definitions (with options) and renders
 * dropdowns so preview can use real filter values.
 *
 * Props:
 *   pageId   — selected page ID
 *   apiBase  — designer API base URL
 *   values   — { param_name: value } current filter values
 *   onChange — (newValues) => void — called when a filter changes
 */
export default function PageFilterPanel({ pageId, apiBase, values = {}, onChange }) {
  const [filters, setFilters] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!pageId) {
      setFilters([])
      return
    }
    setLoading(true)
    setError(null)
    designerFetch(pageFiltersUrl(apiBase, pageId))
      .then(data => {
        setFilters(data)
        // Auto-set defaults for filters that have default_value
        const defaults = {}
        for (const f of data) {
          if (f.default_value && !values[f.param_name]) {
            defaults[f.param_name] = f.default_value
          }
        }
        if (Object.keys(defaults).length > 0) {
          onChange({ ...values, ...defaults })
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [pageId, apiBase]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!pageId) return null

  if (loading) {
    return (
      <div className="wb-filter-panel">
        <span className="spinner-border spinner-border-sm me-2" />
        Loading page filters...
      </div>
    )
  }

  if (error) {
    return (
      <div className="wb-filter-panel wb-filter-panel--error">
        <i className="fa fa-exclamation-triangle me-1" />
        {error}
      </div>
    )
  }

  const visibleFilters = filters.filter(f => f.is_visible)
  if (visibleFilters.length === 0) return null

  const handleChange = (paramName, newValue) => {
    onChange({ ...values, [paramName]: newValue })
  }

  return (
    <div className="wb-filter-panel">
      <label className="wb-label">
        <i className="fa fa-filter me-1" />
        Page Filters (from {visibleFilters.length} filter{visibleFilters.length !== 1 ? 's' : ''})
      </label>
      <div className="wb-filter-grid">
        {visibleFilters.map(f => (
          <div key={f.id} className="wb-filter-item">
            <label className="wb-label-sm">
              {f.label || f.param_name}
              {f.is_multiselect && <span className="wb-multi-badge">multi</span>}
            </label>
            {f.is_multiselect ? (
              <MultiSelectFilter
                options={f.options || []}
                value={values[f.param_name] || ''}
                onChange={val => handleChange(f.param_name, val)}
              />
            ) : (
              <select
                className="wb-input wb-input--sm"
                value={values[f.param_name] || ''}
                onChange={e => handleChange(f.param_name, e.target.value)}
              >
                {f.include_all_option && <option value="">All</option>}
                {!f.include_all_option && <option value="">-- select --</option>}
                {(f.options || []).map(o => (
                  <option key={o.value} value={o.value}>
                    {o.label || o.value}
                  </option>
                ))}
              </select>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * MultiSelectFilter — checkbox list with select-all and scrollable container.
 * Stores value as comma-separated string (matching filter system convention).
 */
function MultiSelectFilter({ options, value, onChange }) {
  const selected = new Set((value || '').split(',').filter(Boolean))
  const allSelected = options.length > 0 && options.every(o => selected.has(o.value))

  const toggle = (val) => {
    const next = new Set(selected)
    if (next.has(val)) next.delete(val)
    else next.add(val)
    onChange(Array.from(next).join(','))
  }

  const toggleAll = () => {
    if (allSelected) {
      onChange('')
    } else {
      onChange(options.map(o => o.value).join(','))
    }
  }

  return (
    <div className="wb-multi-select">
      {options.length > 2 && (
        <label className="wb-multi-option wb-multi-option--all">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleAll}
          />
          <span>Select all ({options.length})</span>
        </label>
      )}
      <div className="wb-multi-list">
        {options.map(o => (
          <label key={o.value} className="wb-multi-option">
            <input
              type="checkbox"
              checked={selected.has(o.value)}
              onChange={() => toggle(o.value)}
            />
            <span>{o.label || o.value}</span>
          </label>
        ))}
      </div>
      {selected.size > 0 && (
        <div className="wb-multi-count">{selected.size} selected</div>
      )}
    </div>
  )
}
