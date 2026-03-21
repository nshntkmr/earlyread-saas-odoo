import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react'

/**
 * MultiSelectDropdown
 *
 * A zero-dependency multi-select dropdown with checkboxes and optional search.
 * Value is a comma-separated string (e.g. "Arkansas,Ohio") for URL compatibility.
 *
 * Props:
 *   options       — [{value, label}, ...]
 *   value         — comma-separated string or '' (empty = nothing selected = "All")
 *   onChange(csv) — callback with new comma-separated value
 *   searchable    — boolean: show search input
 *   placeholder   — text when nothing selected (default: "All")
 *   allLabel      — label for the "All" display (e.g. "All 50 States")
 */
export default function MultiSelectDropdown({
  options = [],
  value = '',
  onChange,
  searchable = false,
  placeholder = 'All',
  allLabel,
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const containerRef = useRef(null)
  const searchRef = useRef(null)

  // Parse CSV value into a Set for O(1) lookups
  const selectedSet = useMemo(() => {
    if (!value) return new Set()
    return new Set(value.split(',').map(v => v.trim()).filter(Boolean))
  }, [value])

  // Filter options by search term (client-side)
  const filteredOptions = useMemo(() => {
    if (!searchTerm) return options
    const term = searchTerm.toLowerCase()
    return options.filter(opt => opt.label.toLowerCase().includes(term))
  }, [options, searchTerm])

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false)
        setSearchTerm('')
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Auto-focus search when dropdown opens
  useEffect(() => {
    if (isOpen && searchable && searchRef.current) {
      searchRef.current.focus()
    }
  }, [isOpen, searchable])

  // Toggle a single option
  const toggleOption = useCallback((optValue) => {
    const next = new Set(selectedSet)
    if (next.has(optValue)) {
      next.delete(optValue)
    } else {
      next.add(optValue)
    }
    onChange(Array.from(next).join(','))
  }, [selectedSet, onChange])

  // Select all visible (filtered) options
  const selectAll = useCallback(() => {
    const next = new Set(selectedSet)
    for (const opt of filteredOptions) {
      next.add(opt.value)
    }
    onChange(Array.from(next).join(','))
  }, [selectedSet, filteredOptions, onChange])

  // Deselect all
  const deselectAll = useCallback(() => {
    if (searchTerm) {
      // When searching: only deselect the visible (filtered) options
      const next = new Set(selectedSet)
      for (const opt of filteredOptions) {
        next.delete(opt.value)
      }
      onChange(Array.from(next).join(','))
    } else {
      onChange('')
    }
  }, [selectedSet, filteredOptions, searchTerm, onChange])

  // Display text for the trigger button
  const displayText = useMemo(() => {
    const count = selectedSet.size
    if (count === 0) return allLabel || placeholder
    if (count === 1) {
      const val = Array.from(selectedSet)[0]
      const opt = options.find(o => o.value === val)
      return opt ? opt.label : val
    }
    return `${count} selected`
  }, [selectedSet, options, allLabel, placeholder])

  return (
    <div className="pv-multiselect" ref={containerRef}>
      {/* Trigger button */}
      <button
        type="button"
        className={`pv-multiselect-trigger ${isOpen ? 'pv-multiselect-open' : ''}`}
        onClick={() => { setIsOpen(!isOpen); setSearchTerm('') }}
      >
        <span className="pv-multiselect-display">{displayText}</span>
        <span className="pv-multiselect-arrow">{isOpen ? '▴' : '▾'}</span>
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div className="pv-multiselect-dropdown">
          {/* Search input */}
          {searchable && (
            <input
              ref={searchRef}
              type="text"
              className="pv-multiselect-search"
              placeholder="Search..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
            />
          )}

          {/* Actions bar */}
          <div className="pv-multiselect-actions">
            <button type="button" onClick={selectAll}>Select All</button>
            <span className="pv-multiselect-divider">|</span>
            <button type="button" onClick={deselectAll}>Clear</button>
            {selectedSet.size > 0 && (
              <span className="pv-multiselect-count">{selectedSet.size} selected</span>
            )}
          </div>

          {/* Options list */}
          <ul className="pv-multiselect-options">
            {filteredOptions.length === 0 && (
              <li className="pv-multiselect-empty">No matches</li>
            )}
            {filteredOptions.map(opt => (
              <li key={opt.value}>
                <label className="pv-multiselect-option">
                  <input
                    type="checkbox"
                    checked={selectedSet.has(opt.value)}
                    onChange={() => toggleOption(opt.value)}
                  />
                  <span>{opt.label}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
