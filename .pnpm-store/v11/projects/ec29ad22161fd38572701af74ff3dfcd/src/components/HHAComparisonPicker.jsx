import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react'
import './HHAComparisonPicker.css'

/**
 * HHAComparisonPicker
 *
 * Chip-based picker for selecting up to 4 HHAs to compare. Used by
 * filters whose ui_type='hha_comparison' (a Selection field on
 * dashboard.page.filter).
 *
 * UX:
 *  • Selected HHAs render as chips (each with ✕ to remove)
 *  • An "+ Add HHA" button reveals an autocomplete input
 *  • Type-ahead matches against ccn_hha + label substrings
 *  • Click a result → adds chip, clears input, refocuses for the next
 *  • Esc / click-outside closes the dropdown
 *  • Backspace on empty input removes last chip
 *  • Hard cap of MAX_CHIPS chips — the "+ Add" button disables at the cap
 *
 * The picker is **renderer-only** — it doesn't trigger Apply or talk
 * to any APIs. The page-level Apply button (in the FilterBar) drives
 * the actual SQL refresh; the picker just keeps the parent's pending
 * filter value in sync via onChange.
 *
 * Props (renderer):
 *  • options:    [{ value, label }] — available HHAs from the page filter
 *  • value:      CSV of currently-selected ccn_hha values
 *  • onChange:   (csv) => void — called when chips change
 *  • placeholder: string for the search input
 */

const MAX_CHIPS = 4

export default function HHAComparisonPicker({
  options = [],
  value = '',
  onChange,
  placeholder = 'Type to search HHAs by CCN or name',
}) {
  // ── Selected values, parsed from CSV ──────────────────────────────
  const selectedValues = useMemo(
    () => (value || '').split(',').map(s => s.trim()).filter(Boolean),
    [value]
  )

  // Map value → option (for chip labels). Falls back to value if option
  // not found (handles cascade-induced stale values gracefully).
  const optionsByValue = useMemo(() => {
    const m = {}
    for (const o of options) m[String(o.value)] = o
    return m
  }, [options])

  const selectedChips = selectedValues.map(v => ({
    value: v,
    label: optionsByValue[v]?.label || v,
  }))

  // ── Autocomplete state ────────────────────────────────────────────
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const inputRef = useRef(null)
  const wrapperRef = useRef(null)

  const atCap = selectedValues.length >= MAX_CHIPS

  // Filter available options:
  //   - exclude already-selected
  //   - if query, match ccn or label (case-insensitive substring)
  //   - cap at 50 results to keep the dropdown manageable
  const filteredResults = useMemo(() => {
    const selectedSet = new Set(selectedValues)
    const q = query.trim().toLowerCase()
    let pool = options.filter(o => !selectedSet.has(String(o.value)))
    if (q) {
      pool = pool.filter(o =>
        String(o.value).toLowerCase().includes(q) ||
        String(o.label || '').toLowerCase().includes(q)
      )
    }
    return pool.slice(0, 50)
  }, [options, query, selectedValues])

  // ── Add / remove chip helpers ─────────────────────────────────────
  const addChip = useCallback((val) => {
    if (!val) return
    if (selectedValues.includes(val)) return
    if (selectedValues.length >= MAX_CHIPS) return
    const next = [...selectedValues, val].join(',')
    if (onChange) onChange(next)
    setQuery('')
    // Keep the dropdown open so the user can add another quickly
    setTimeout(() => inputRef.current?.focus(), 0)
  }, [selectedValues, onChange])

  const removeChip = useCallback((val) => {
    const next = selectedValues.filter(v => v !== val).join(',')
    if (onChange) onChange(next)
  }, [selectedValues, onChange])

  // ── Open/close behaviour ──────────────────────────────────────────
  const openDropdown = useCallback(() => {
    if (atCap) return
    setOpen(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }, [atCap])

  const closeDropdown = useCallback(() => {
    setOpen(false)
    setQuery('')
  }, [])

  // Click-outside closes
  useEffect(() => {
    if (!open) return
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        closeDropdown()
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open, closeDropdown])

  // Keyboard: Esc closes; Enter on first match adds it; Backspace on
  // empty input removes the last chip
  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      closeDropdown()
    } else if (e.key === 'Enter' && filteredResults.length > 0) {
      e.preventDefault()
      addChip(String(filteredResults[0].value))
    } else if (e.key === 'Backspace' && !query && selectedValues.length > 0) {
      e.preventDefault()
      removeChip(selectedValues[selectedValues.length - 1])
    }
  }

  return (
    <div className="hha-cmp-picker" ref={wrapperRef}>
      {/* ── Chip strip + Add button ─────────────────────────────── */}
      <div className="hha-cmp-picker__chips" role="list">
        {selectedChips.map(chip => (
          <span key={chip.value} className="hha-cmp-picker__chip" role="listitem">
            <span className="hha-cmp-picker__chip-label" title={chip.label}>
              {chip.label}
            </span>
            <button
              type="button"
              className="hha-cmp-picker__chip-remove"
              onClick={() => removeChip(chip.value)}
              aria-label={`Remove ${chip.label}`}
              title="Remove"
            >
              ✕
            </button>
          </span>
        ))}

        {/* + Add HHA button — disabled at cap */}
        {!open && (
          <button
            type="button"
            className="hha-cmp-picker__add-btn"
            onClick={openDropdown}
            disabled={atCap}
            title={atCap ? `Maximum ${MAX_CHIPS} HHAs` : 'Add an HHA to compare'}
          >
            <i className="fa fa-plus" aria-hidden="true" />
            <span>{atCap ? `${MAX_CHIPS} of ${MAX_CHIPS}` : 'Add HHA'}</span>
          </button>
        )}

        {/* Inline search input (visible when dropdown is open) */}
        {open && (
          <input
            ref={inputRef}
            type="text"
            className="hha-cmp-picker__search-input"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            aria-label="Search HHAs"
          />
        )}
      </div>

      {/* ── Autocomplete dropdown ───────────────────────────────── */}
      {open && (
        <div className="hha-cmp-picker__dropdown" role="listbox">
          {filteredResults.length === 0 ? (
            <div className="hha-cmp-picker__empty">
              {query
                ? `No HHAs matching "${query}"`
                : 'All available HHAs are already selected'}
            </div>
          ) : (
            filteredResults.map(opt => (
              <button
                key={opt.value}
                type="button"
                className="hha-cmp-picker__option"
                onClick={() => addChip(String(opt.value))}
                role="option"
              >
                <span className="hha-cmp-picker__option-label">{opt.label}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

