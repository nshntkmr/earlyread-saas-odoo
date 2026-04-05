import React, { useState, useEffect } from 'react'
import { designerFetch } from '../api/client'
import { libraryUrl, libraryDetailUrl } from '../api/endpoints'

const CHART_ICONS = {
  bar: 'fa-bar-chart', line: 'fa-line-chart', pie: 'fa-pie-chart',
  donut: 'fa-circle-o-notch', gauge: 'fa-tachometer', radar: 'fa-bullseye',
  kpi: 'fa-hashtag', status_kpi: 'fa-arrow-up', table: 'fa-table',
  scatter: 'fa-braille', heatmap: 'fa-th', battle_card: 'fa-columns',
  insight_panel: 'fa-lightbulb-o', gauge_kpi: 'fa-dashboard',
}

const CHART_TYPES = [
  { key: '',              label: 'All',           icon: null },
  { key: 'bar',           label: 'Bar',           icon: 'fa-bar-chart' },
  { key: 'line',          label: 'Line',          icon: 'fa-line-chart' },
  { key: 'pie',           label: 'Pie',           icon: 'fa-pie-chart' },
  { key: 'donut',         label: 'Donut',         icon: 'fa-circle-o-notch' },
  { key: 'gauge',         label: 'Gauge',         icon: 'fa-tachometer' },
  { key: 'radar',         label: 'Radar',         icon: 'fa-bullseye' },
  { key: 'kpi',           label: 'KPI',           icon: 'fa-hashtag' },
  { key: 'table',         label: 'Table',         icon: 'fa-table' },
  { key: 'scatter',       label: 'Scatter',       icon: 'fa-braille' },
  { key: 'heatmap',       label: 'Heatmap',       icon: 'fa-th' },
  { key: 'battle_card',   label: 'Battle Card',   icon: 'fa-columns' },
  { key: 'insight_panel', label: 'Insight',        icon: 'fa-lightbulb-o' },
  { key: 'gauge_kpi',     label: 'Gauge+KPI',     icon: 'fa-dashboard' },
]

/**
 * WidgetLibrary — Browsable grid of widget definitions.
 */
export default function WidgetLibrary({ apiBase, appContext, onCreate, onEdit }) {
  const [definitions, setDefinitions] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [chartType, setChartType] = useState('')
  const [deleting, setDeleting] = useState(null)

  useEffect(() => {
    loadLibrary()
  }, [chartType, apiBase, appContext?.app?.id, appContext?.page?.id, appContext?.tab?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const loadLibrary = async () => {
    setLoading(true)
    try {
      const params = {}
      if (chartType) params.chart_type = chartType
      if (search) params.search = search
      if (appContext?.app?.id) params.app_id = appContext.app.id
      if (appContext?.page?.id) params.page_id = appContext.page.id
      if (appContext?.tab?.id) params.tab_id = appContext.tab.id
      const data = await designerFetch(libraryUrl(apiBase, params))
      setDefinitions(data)
    } catch (err) {
      console.error('Failed to load library:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e) => {
    e.preventDefault()
    loadLibrary()
  }

  const handleDelete = async (def) => {
    if (!window.confirm(`Delete "${def.name}"? This cannot be undone.`)) return
    setDeleting(def.id)
    try {
      await designerFetch(libraryDetailUrl(apiBase, def.id), { method: 'DELETE' })
      setDefinitions(prev => prev.filter(d => d.id !== def.id))
    } catch (err) {
      alert(err.message || 'Delete failed')
    } finally {
      setDeleting(null)
    }
  }

  const filtered = search
    ? definitions.filter(d => d.name.toLowerCase().includes(search.toLowerCase()))
    : definitions

  return (
    <div className="dd-page">
      <div className="dd-page-header">
        <h1 className="dd-page-title">Widget Library</h1>
        <button
          type="button"
          className="wb-btn wb-btn--primary"
          onClick={onCreate}
        >
          <i className="fa fa-plus me-1" /> Create New Widget
        </button>
      </div>

      {/* Filters bar */}
      <div className="dd-filters-bar">
        <div className="dd-category-tabs">
          {CHART_TYPES.map(ct => (
            <button
              key={ct.key}
              type="button"
              className={`dd-cat-tab ${chartType === ct.key ? 'dd-cat-tab--active' : ''}`}
              onClick={() => setChartType(ct.key)}
              title={ct.label}
            >
              {ct.icon && <i className={`fa ${ct.icon} me-1`} />}
              {ct.label}
            </button>
          ))}
        </div>
        <form className="dd-search-form" onSubmit={handleSearch}>
          <input
            type="text"
            className="wb-input wb-input--sm"
            placeholder="Search widgets..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </form>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="dd-loading-state">
          <span className="spinner-border spinner-border-sm me-2" />
          Loading library...
        </div>
      ) : filtered.length === 0 ? (
        <div className="dd-empty-state">
          <i className="fa fa-inbox dd-empty-icon" />
          <p>No widget definitions found.</p>
          <button type="button" className="wb-btn wb-btn--primary" onClick={onCreate}>
            Create your first widget
          </button>
        </div>
      ) : (
        <div className="dd-def-grid">
          {filtered.map(def => (
            <div key={def.id} className="dd-def-card">
              <div className="dd-def-card-icon">
                <i className={`fa ${CHART_ICONS[def.chart_type] || 'fa-cube'}`} />
              </div>
              <div className="dd-def-card-body">
                <h3 className="dd-def-name">{def.name}</h3>
                <p className="dd-def-desc">{def.description || `${def.chart_type} widget`}</p>
                <div className="dd-def-meta">
                  <span className="dd-badge dd-badge--type">{def.chart_type}</span>
                  <span className="dd-badge dd-badge--cat">{def.category}</span>
                  {def.app_names && def.app_names.length > 0 ? (
                    def.app_names.map(name => (
                      <span key={name} className="dd-badge dd-badge--app">{name}</span>
                    ))
                  ) : (
                    <span className="dd-badge dd-badge--app-global">All Apps</span>
                  )}
                  {def.instance_count > 0 && (
                    <span className="dd-badge dd-badge--count">
                      {def.instance_count} instance{def.instance_count !== 1 ? 's' : ''}
                    </span>
                  )}
                </div>
              </div>
              <div className="dd-def-card-actions">
                <button
                  type="button"
                  className="wb-btn wb-btn--outline wb-btn--sm"
                  onClick={(e) => { e.stopPropagation(); onEdit?.(def) }}
                  title="Edit"
                >
                  <i className="fa fa-pencil" />
                </button>
                <button
                  type="button"
                  className="wb-btn wb-btn--danger wb-btn--sm"
                  onClick={(e) => { e.stopPropagation(); handleDelete(def) }}
                  disabled={deleting === def.id || def.instance_count > 0}
                  title={def.instance_count > 0 ? 'Cannot delete: has instances' : 'Delete'}
                >
                  {deleting === def.id
                    ? <span className="spinner-border spinner-border-sm" />
                    : <i className="fa fa-trash" />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
