import React from 'react'

/**
 * PillTabs
 *
 * Renders a page filter's options as an inline row of pill / segmented buttons
 * instead of a <select> dropdown. Driven entirely by the filter's `ui_type`
 * ('pills' | 'segmented') — no hardcoding. Honours multi-select.
 *
 * Contract matches the dropdown path exactly: `onChange(newValue)` receives a
 * value string (single-select) or a comma-separated CSV (multi-select), so the
 * parent's `handleFilterChange(filter, value)` / cascade / Apply / URL-sync all
 * behave identically to the dropdown.
 */
export default function PillTabs({
  options = [],
  value = '',
  onChange,
  isMultiselect = false,
  includeAllOption = true,
  segmented = false,
}) {
  const v = value == null ? '' : String(value)
  const selected = isMultiselect
    ? new Set(v.split(',').map(s => s.trim()).filter(Boolean))
    : null

  const isActive = (optVal) =>
    isMultiselect ? selected.has(String(optVal)) : v === String(optVal)

  const handleClick = (optVal) => {
    const ov = String(optVal)
    if (isMultiselect) {
      if (ov === '') { onChange(''); return }     // "All" clears the multi-select
      const next = new Set(selected)
      next.has(ov) ? next.delete(ov) : next.add(ov)
      onChange(Array.from(next).join(','))
    } else {
      onChange(ov)
    }
  }

  // Single-select gets a synthetic "All" pill (empty value) unless suppressed.
  const allPill = (!isMultiselect && includeAllOption) ? [{ value: '', label: 'All' }] : []
  const pills = [...allPill, ...options]

  return (
    <div
      className={`pv-pill-tabs${segmented ? ' pv-pill-tabs--segmented' : ''}`}
      role="group"
      style={{ display: 'inline-flex', flexWrap: 'wrap', gap: segmented ? 0 : 5, alignItems: 'center' }}
    >
      {pills.map((opt, i) => {
        const active = isActive(opt.value)
        const style = {
          fontFamily: 'inherit',
          fontSize: 12.5,
          fontWeight: 600,
          lineHeight: 1.2,
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          padding: '6px 14px',
          border: '1.5px solid',
          borderColor: active ? 'var(--pv-primary, #0066cc)' : '#e5e7eb',
          background: active ? 'var(--pv-primary, #0066cc)' : '#fff',
          color: active ? '#fff' : '#374151',
          transition: 'all .12s',
          ...(segmented
            ? { borderRadius: 0, marginLeft: i === 0 ? 0 : -1, position: 'relative', zIndex: active ? 1 : 0 }
            : { borderRadius: 18 }),
        }
        return (
          <button
            type="button"
            key={String(opt.value)}
            onClick={() => handleClick(opt.value)}
            aria-pressed={active}
            style={style}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
