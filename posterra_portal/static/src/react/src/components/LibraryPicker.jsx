import React, { useState, useEffect } from 'react'
import { apiFetch } from '../api/client'
import { libraryUrl, placeUrl } from '../api/builder_endpoints'

const CHART_ICONS = {
  bar: 'fa-bar-chart', line: 'fa-line-chart', pie: 'fa-pie-chart',
  donut: 'fa-circle-o-notch', gauge: 'fa-tachometer', radar: 'fa-bullseye',
  kpi: 'fa-hashtag', status_kpi: 'fa-arrow-up', table: 'fa-table',
  scatter: 'fa-braille', heatmap: 'fa-th', battle_card: 'fa-columns',
  insight_panel: 'fa-lightbulb-o', gauge_kpi: 'fa-dashboard',
}

/**
 * LibraryPicker — Lightweight modal for adding widgets from the library.
 *
 * Shows widget definitions from GET /api/v1/builder/library.
 * On selection, calls POST /api/v1/builder/library/<id>/place to place
 * the definition on the current page/tab.
 *
 * Props:
 *   isOpen       — boolean
 *   onClose      — () => void
 *   onPlaced     — () => void — called after successful placement
 *   pageKey      — string (current page key)
 *   tabKey       — string (current tab key)
 *   apiBase      — string
 *   accessToken  — string
 */
export default function LibraryPicker({
  isOpen, onClose, onPlaced,
  pageKey, tabKey, apiBase, accessToken, refreshToken,
}) {
  const [definitions, setDefinitions] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [placing, setPlacing] = useState(null) // id being placed
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!isOpen) return
    loadLibrary()
  }, [isOpen, apiBase, accessToken])

  const loadLibrary = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch(libraryUrl(apiBase), accessToken, {}, refreshToken)
      setDefinitions(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePlace = async (def) => {
    setPlacing(def.id)
    setError(null)
    try {
      await apiFetch(placeUrl(apiBase, def.id), accessToken, {
        method: 'POST',
        body: JSON.stringify({
          page_key: pageKey,
          tab_key: tabKey,
        }),
      }, refreshToken)
      onPlaced?.()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setPlacing(null)
    }
  }

  if (!isOpen) return null

  const filtered = search
    ? definitions.filter(d => d.name.toLowerCase().includes(search.toLowerCase()))
    : definitions

  return (
    <div className="wb-modal-overlay" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="wb-modal wb-modal--builder">
        {/* Header */}
        <div className="wb-modal-header">
          <h3 className="wb-modal-title">
            <i className="fa fa-th-large me-2" />
            Add from Library
          </h3>
          <button type="button" className="wb-btn-close" onClick={onClose}>
            <i className="fa fa-times" />
          </button>
        </div>

        {/* Search bar */}
        <div style={{ padding: '12px 24px', borderBottom: '1px solid #e5e7eb' }}>
          <input
            type="text"
            className="wb-input"
            placeholder="Search widgets..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoFocus
          />
        </div>

        {/* Body */}
        <div className="wb-modal-body">
          {error && (
            <div className="wb-preview-error mb-3">
              <i className="fa fa-exclamation-triangle me-1" />
              {error}
            </div>
          )}

          {loading ? (
            <div className="wb-loading">
              <span className="spinner-border spinner-border-sm me-2" />
              Loading library...
            </div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af' }}>
              <i className="fa fa-inbox" style={{ fontSize: '32px', display: 'block', marginBottom: '12px' }} />
              {search ? 'No widgets match your search.' : 'No widget definitions in the library yet.'}
              <br />
              <small>Create widgets in the Dashboard Designer first.</small>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filtered.map(def => (
                <div
                  key={def.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px 16px',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    background: '#ffffff',
                    cursor: 'pointer',
                    transition: 'box-shadow 0.15s',
                  }}
                  onClick={() => handlePlace(def)}
                  onMouseOver={e => e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)'}
                  onMouseOut={e => e.currentTarget.style.boxShadow = 'none'}
                >
                  <div style={{
                    width: '40px', height: '40px', borderRadius: '8px',
                    background: '#eff6ff', display: 'flex', alignItems: 'center',
                    justifyContent: 'center', flexShrink: 0,
                  }}>
                    <i className={`fa ${CHART_ICONS[def.chart_type] || 'fa-cube'}`}
                       style={{ fontSize: '18px', color: '#2563eb' }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: '#1f2937' }}>
                      {def.name}
                    </div>
                    <div style={{ fontSize: '12px', color: '#6b7280' }}>
                      {def.description || `${def.chart_type} widget`}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                    <span style={{
                      padding: '2px 8px', fontSize: '11px', fontWeight: 600,
                      borderRadius: '10px', background: '#dbeafe', color: '#1d4ed8',
                    }}>
                      {def.chart_type}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="wb-btn wb-btn--primary wb-btn--sm"
                    onClick={e => { e.stopPropagation(); handlePlace(def) }}
                    disabled={placing === def.id}
                  >
                    {placing === def.id ? (
                      <span className="spinner-border spinner-border-sm" />
                    ) : (
                      <><i className="fa fa-plus me-1" /> Add</>
                    )}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="wb-modal-footer">
          <button type="button" className="wb-btn wb-btn--outline" onClick={onClose}>
            Cancel
          </button>
          <div style={{ fontSize: '12px', color: '#9ca3af' }}>
            {filtered.length} widget{filtered.length !== 1 ? 's' : ''} available
          </div>
        </div>
      </div>
    </div>
  )
}
