import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
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
 * MultiSelectFilter — virtualized checkbox list with search, select-all,
 * and scrollable container.  Uses @tanstack/react-virtual so that even
 * 11,000+ item lists (e.g., Provider) render instantly with ~30 DOM nodes.
 * Stores value as comma-separated string (matching filter system convention).
 */
function MultiSelectFilter({ options, value, onChange }) {
  const [search, setSearch] = useState('')
  const parentRef = useRef(null)

  const selected = useMemo(
    () => new Set((value || '').split(',').filter(Boolean)),
    [value]
  )

  const filtered = useMemo(() => {
    if (!search) return options
    const q = search.toLowerCase()
    return options.filter(o =>
      (o.label || o.value || '').toLowerCase().includes(q)
    )
  }, [options, search])

  const allSelected = filtered.length > 0 && filtered.every(o => selected.has(o.value))

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 26,
    overscan: 15,
  })

  const toggle = (val) => {
    const next = new Set(selected)
    if (next.has(val)) next.delete(val)
    else next.add(val)
    onChange(Array.from(next).join(','))
  }

  const toggleAll = () => {
    if (allSelected) {
      // Deselect only the filtered items (keep selections outside search)
      const next = new Set(selected)
      filtered.forEach(o => next.delete(o.value))
      onChange(Array.from(next).join(','))
    } else {
      const next = new Set(selected)
      filtered.forEach(o => next.add(o.value))
      onChange(Array.from(next).join(','))
    }
  }

  return (
    <div className="wb-multi-select">
      {options.length > 10 && (
        <input
          type="text"
          className="wb-multi-search"
          placeholder="Search..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      )}
      {filtered.length > 2 && (
        <label className="wb-multi-option wb-multi-option--all">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleAll}
          />
          <span>Select all ({filtered.length})</span>
        </label>
      )}
      <div className="wb-multi-list" ref={parentRef}>
        <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
          {virtualizer.getVirtualItems().map(vItem => {
            const o = filtered[vItem.index]
            return (
              <label
                key={o.value}
                className="wb-multi-option"
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: vItem.size,
                  transform: `translateY(${vItem.start}px)`,
                }}
              >
                <input
                  type="checkbox"
                  checked={selected.has(o.value)}
                  onChange={() => toggle(o.value)}
                />
                <span>{o.label || o.value}</span>
              </label>
            )
          })}
        </div>
      </div>
      {selected.size > 0 && (
        <div className="wb-multi-count">{selected.size} selected</div>
      )}
    </div>
  )
}
