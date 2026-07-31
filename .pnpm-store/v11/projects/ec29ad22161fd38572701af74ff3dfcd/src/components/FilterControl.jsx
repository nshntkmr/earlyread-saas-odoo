import React from 'react'
import MultiSelectDropdown from './MultiSelectDropdown'
import SearchableSelect from './SearchableSelect'
import HHAComparisonPicker from './HHAComparisonPicker'
import PillTabs from './PillTabs'
import RemoteAutocomplete from './RemoteAutocomplete'

/**
 * FilterControl — the presentational renderer for ONE filter, dispatched by
 * `filter.ui_type`. Extracted verbatim from FilterBar so the identical control
 * can render in the filter bar AND the page header (D1 placement). The label,
 * wrapper, and cascade wiring stay with the caller; this component only paints
 * the input and calls `onChange(value)`.
 *
 * ui_type dispatch (unchanged for every existing type):
 *   'pills' | 'segmented'  → PillTabs
 *   'hha_comparison'       → HHAComparisonPicker
 *   'remote_autocomplete'  → RemoteAutocomplete (server search, no preload)
 *   else                   → multi-select / searchable / plain <select>
 *
 * Props:
 *   filter   — filter config dict
 *   options  — [{value, label}] (from dynamicOptions ?? filter.options)
 *   value    — current (pending) value
 *   onChange — (value) => void
 */
export default function FilterControl({ filter, options = [], value = '', onChange }) {
  const paramKey = filter.param_name || filter.field_name
  // hide_all_option suppresses the synthetic "All"/empty choice — single-select
  // only (mirrors the backend _prepend_all_option gate).
  const hideAll = filter.hide_all_option && !filter.is_multiselect

  if (filter.ui_type === 'remote_autocomplete') {
    return <RemoteAutocomplete filter={filter} value={value} onChange={onChange} />
  }
  if (filter.ui_type === 'pills' || filter.ui_type === 'segmented') {
    return (
      <PillTabs
        options={options}
        value={value}
        onChange={onChange}
        isMultiselect={filter.is_multiselect}
        includeAllOption={!filter.include_all_option && !hideAll}
        segmented={filter.ui_type === 'segmented'}
      />
    )
  }
  if (filter.ui_type === 'hha_comparison') {
    return (
      <HHAComparisonPicker
        options={options}
        value={value}
        onChange={onChange}
        placeholder={filter.placeholder || 'Type to search HHAs by CCN or name'}
      />
    )
  }
  if (filter.is_multiselect) {
    return (
      <MultiSelectDropdown
        options={options}
        value={value}
        onChange={onChange}
        searchable={filter.is_searchable}
        placeholder={filter.placeholder || 'All'}
      />
    )
  }
  if (filter.is_searchable) {
    return (
      <SearchableSelect
        options={options}
        value={value}
        onChange={onChange}
        placeholder={filter.placeholder || 'All'}
        includeAllOption={!filter.include_all_option && !hideAll}
      />
    )
  }
  return (
    <select
      id={`ctx-${paramKey}-select`}
      className="pv-ctx-select"
      data-filter-id={filter.id}
      data-field-name={paramKey}
      value={value}
      onChange={e => onChange(e.target.value)}
    >
      {!filter.include_all_option && !hideAll && (
        <option value="">All</option>
      )}
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}
