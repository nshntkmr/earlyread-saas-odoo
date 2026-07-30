import React, { useState, useRef, useEffect, useMemo } from 'react'

/**
 * SearchableSelect
 *
 * A zero-dependency single-select dropdown with type-to-filter search.
 * Useful for filters with many options (50+ states, counties, providers).
 *
 * Props:
 *   options        — [{value, label}, ...]
 *   value          — selected value string (single)
 *   onChange(val)  — callback with new value
 *   placeholder    — text when nothing selected (default: "All")
 *   includeAllOption — whether to show "All" option at top
 */
export default function SearchableSelect({
  options = [],
  value = '',
  onChange,
  placeholder = 'All',
  includeAllOption = true,
}) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const containerRef = useRef(null)
  const searchRef = useRef(null)

  // Filter options by search term
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
    if (isOpen && searchRef.current) {
      searchRef.current.focus()
    }
  }, [isOpen])

  // Select an option and close
  const handleSelect = (optValue) => {
    onChange(optValue)
    setIsOpen(false)
    setSearchTerm('')
  }

  // Current display text
  const displayText = useMemo(() => {
    if (!value) return placeholder
    const opt = options.find(o => o.value === value)
    return opt ? opt.label : value
  }, [value, options, placeholder])

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
          <input
            ref={searchRef}
            type="text"
            className="pv-multiselect-search"
            placeholder="Type to search..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />

          {/* Options list */}
          <ul className="pv-multiselect-options">
            {/* "All" option */}
            {includeAllOption && !searchTerm && (
              <li>
                <button
                  type="button"
                  className={`pv-searchselect-option ${!value ? 'pv-searchselect-active' : ''}`}
                  onClick={() => handleSelect('')}
                >
                  {placeholder}
                </button>
              </li>
            )}

            {filteredOptions.length === 0 && (
              <li className="pv-multiselect-empty">No matches</li>
            )}
            {filteredOptions.map(opt => (
              <li key={opt.value}>
                <button
                  type="button"
                  className={`pv-searchselect-option ${opt.value === value ? 'pv-searchselect-active' : ''}`}
                  onClick={() => handleSelect(opt.value)}
                >
                  {opt.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
