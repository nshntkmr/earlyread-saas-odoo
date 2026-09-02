import React from 'react'
import FilterControl from './FilterControl'

// Text color that stays readable on a given hex background (WCAG-ish luma).
function readableOn(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '')
  if (!m) return '#fff'
  const n = parseInt(m[1], 16)
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255
  const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
  return luma > 150 ? '#1e1b39' : '#fff'
}

/**
 * WidgetControls — renders the widget-scoped controls in the card header:
 *   - Toggle buttons (scope_ui = 'toggle')
 *   - Dropdown (scope_ui = 'dropdown')
 *   - Search bar (search_enabled)
 *   - Widget-level filters (N independent controls, `widget_filters` payload)
 *
 * Only renders when the widget has scope controls, search, or widget filters.
 * Widgets with none of them render nothing.
 *
 * Widget-level filters reuse the page-filter renderer (`FilterControl`) so a
 * widget's own dropdown / multi-select / toggle looks and behaves exactly like
 * the filter bar's. Values are held by WidgetGrid and sent as `_wf_<param>`
 * on every fetch of THAT widget only.
 */
export default function WidgetControls({
  scope,           // { mode, ui, query_mode, label, options, param_name, default_value, ... }
  search,          // { placeholder } or null/undefined
  scopeValue,      // current scope selection (string)
  onScopeChange,   // (newValue: string, optionId?: number) => void
  searchText,      // current search text (string)
  onSearchChange,  // (newText: string) => void
  placement = 'header', // 'header' (default) | 'body' (in-map toolbar styling, left-aligned tabs)
  widgetFilters = [],        // [{ id, label, param_name, mode, ui_type, is_multiselect, is_searchable,
                             //    include_all_option, default_value, filter_param, options }]
  widgetFilterValues = {},   // { param_name: value } for THIS widget
  onWidgetFilterChange = () => {}, // (param_name, newValue) => void
  pageFilters = [],          // pageConfig.filters — options source for mirror-mode filters
}) {
  const hasScope = scope && scope.mode !== 'none'
  const hasSearch = !!search
  const hasWidgetFilters = Array.isArray(widgetFilters) && widgetFilters.length > 0

  if (!hasScope && !hasSearch && !hasWidgetFilters) return null

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

      {/* Widget-level filters — one control per configured filter */}
      {hasWidgetFilters && widgetFilters.map(wf => {
        const isMirror = wf.mode === 'mirror' && !!wf.filter_param
        const pf = isMirror
          ? (pageFilters || []).find(f => (f.param_name || f.field_name) === wf.filter_param)
          : null
        // Mirror: borrow the page filter's options, minus any server-prepended
        // "All N …" entry (blank value) — the control adds its own All.
        const options = isMirror
          ? (pf?.options || []).filter(o => (o.value ?? '') !== '')
          : (wf.options || [])
        // Synthetic page-filter config so FilterControl renders identically.
        // include_all_option=false makes the control draw its own blank "All";
        // hide_all_option suppresses it when the admin turned Include All off.
        const synthetic = {
          id: `wf-${wf.id}`,
          // Unique DOM id/data-attr per widget filter: a mirror shares the page
          // filter's param, so the raw param would collide with the filter bar's
          // own `ctx-<param>-select` element. Only FilterControl reads this key.
          param_name: `wf${wf.id}_${wf.param_name}`,
          ui_type: wf.ui_type === 'toggle' ? 'pills' : 'default',
          is_multiselect: !!wf.is_multiselect,
          is_searchable: !!wf.is_searchable,
          include_all_option: false,
          hide_all_option: !wf.include_all_option,
          placeholder: 'All',
        }
        const value = widgetFilterValues[wf.param_name] ?? wf.default_value ?? ''
        return (
          <div
            key={wf.id}
            className="pv-widget-filter"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            title={isMirror ? 'Overrides the page filter for this widget only; All = page value' : undefined}
          >
            {wf.label && (
              <span
                className="pv-widget-filter-label"
                style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', whiteSpace: 'nowrap' }}
              >
                {wf.label}
              </span>
            )}
            <FilterControl
              filter={synthetic}
              options={options}
              value={value}
              onChange={v => onWidgetFilterChange(wf.param_name, v)}
            />
          </div>
        )
      })}

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
