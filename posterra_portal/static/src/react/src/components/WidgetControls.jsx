import React from 'react'

/**
 * WidgetControls — renders toggle buttons, dropdown, and/or search bar
 * inside a widget's card header.
 *
 * Only renders when the widget has scope controls or search enabled.
 * Widgets with scope_mode='none' and search_enabled=false render nothing.
 */
export default function WidgetControls({
  scope,           // { mode, ui, query_mode, label, options, param_name, default_value, ... }
  search,          // { placeholder } or null/undefined
  scopeValue,      // current scope selection (string)
  onScopeChange,   // (newValue: string, optionId?: number) => void
  searchText,      // current search text (string)
  onSearchChange,  // (newText: string) => void
}) {
  const hasScope = scope && scope.mode !== 'none'
  const hasSearch = !!search

  if (!hasScope && !hasSearch) return null

  return (
    <div className="pv-widget-controls">
      {/* Toggle Buttons */}
      {hasScope && scope.ui === 'toggle' && scope.options?.length > 0 && (
        <div className="pv-widget-toggle-group" role="group">
          {scope.options.map(opt => {
            const optValue = opt.value ?? ''
            const isActive = scopeValue === optValue
            return (
              <button
                key={optValue || opt.id || opt.label}
                className={`pv-widget-toggle-btn${isActive ? ' active' : ''}`}
                onClick={() => onScopeChange(optValue, opt.id)}
                title={opt.label}
                type="button"
              >
                {opt.icon && <i className={`fa ${opt.icon}`} />}
                <span>{opt.label}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Dropdown */}
      {hasScope && scope.ui === 'dropdown' && (
        <select
          className="pv-widget-scope-select"
          value={scopeValue}
          onChange={e => {
            const selected = scope.options?.find(o => (o.value ?? '') === e.target.value)
            onScopeChange(e.target.value, selected?.id)
          }}
        >
          <option value="">{scope.label || 'All'}</option>
          {(scope.options || []).map(opt => (
            <option key={opt.value ?? opt.id ?? opt.label} value={opt.value ?? ''}>
              {opt.label}
            </option>
          ))}
        </select>
      )}

      {/* Search Bar */}
      {hasSearch && (
        <div className="pv-widget-search-wrap">
          <i className="fa fa-search pv-widget-search-icon" />
          <input
            type="text"
            className="pv-widget-search"
            placeholder={search.placeholder}
            value={searchText}
            onChange={e => onSearchChange(e.target.value)}
          />
        </div>
      )}
    </div>
  )
}
