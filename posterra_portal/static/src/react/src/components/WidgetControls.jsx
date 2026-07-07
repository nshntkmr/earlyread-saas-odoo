import React from 'react'

// Pick a readable text/icon color (near-black or white) for a given hex
// background, so an admin-chosen option accent stays legible whatever its
// luminance — a light accent gets dark text, not unreadable white.
function readableOn(hex) {
  const h = String(hex || '').replace('#', '')
  const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h
  if (full.length !== 6) return '#ffffff'
  const n = parseInt(full, 16)
  if (Number.isNaN(n)) return '#ffffff'
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255
  const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return lum > 0.6 ? '#0f172a' : '#ffffff'
}

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
  placement = 'header', // 'header' (default) | 'body' (in-map toolbar styling, left-aligned tabs)
}) {
  const hasScope = scope && scope.mode !== 'none'
  const hasSearch = !!search

  if (!hasScope && !hasSearch) return null

  return (
    <div className={`pv-widget-controls${placement === 'body' ? ' pv-widget-controls--body' : ''}`}>
      {/* Toggle Buttons */}
      {hasScope && scope.ui === 'toggle' && scope.options?.length > 0 && (
        <div className="pv-widget-toggle-group" role="group">
          {scope.options.map(opt => {
            const optValue = opt.value ?? ''
            const isActive = scopeValue === optValue
            const color = opt.color || ''
            const iconColor = opt.icon_color || color || ''
            // Active + a configured color → colored pill with contrast-safe text.
            // Inactive stays the default muted style (only the icon gets a tint).
            const btnStyle = (color && isActive)
              ? { background: color, color: readableOn(color), boxShadow: 'none' }
              : undefined
            const iconStyle = (color && isActive)
              ? { color: readableOn(color) }
              : (iconColor ? { color: iconColor } : undefined)
            return (
              <button
                key={optValue || opt.id || opt.label}
                className={`pv-widget-toggle-btn${isActive ? ' active' : ''}`}
                style={btnStyle}
                onClick={() => onScopeChange(optValue, opt.id)}
                title={opt.label}
                type="button"
              >
                {opt.icon && <i className={`fa ${opt.icon}`} style={iconStyle} />}
                <span>{opt.label}</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Dropdown — native <select> can't reliably color per-option rows or show
          FA icons cross-browser, so we only ACCENT the control with the selected
          option's color (border + left bar). Blank color = default styling. */}
      {hasScope && scope.ui === 'dropdown' && (() => {
        const selColor =
          (scope.options || []).find(o => (o.value ?? '') === scopeValue)?.color || ''
        return (
          <select
            className="pv-widget-scope-select"
            style={selColor ? { borderColor: selColor, boxShadow: `inset 3px 0 0 ${selColor}` } : undefined}
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
        )
      })()}

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
