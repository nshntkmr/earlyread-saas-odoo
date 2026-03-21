import React, { useState, useEffect } from 'react'
import { designerFetch } from '../api/client'
import { appsUrl, appPagesUrl, libraryPlaceUrl } from '../api/endpoints'

/**
 * AppPagePicker — Tree picker: App → Page → Tab for widget placement.
 *
 * Props:
 *  - definition: the widget definition to place
 *  - apiBase: designer API base URL
 *  - initialApps: apps passed from server-rendered data-apps (fallback if API unavailable)
 *  - onDone: called after successful placement
 *  - onBack: navigate back
 */
export default function AppPagePicker({ definition, apiBase, initialApps, onDone, onBack }) {
  const [apps, setApps] = useState(initialApps || [])
  const [selectedApp, setSelectedApp] = useState(null)
  const [pages, setPages] = useState([])
  const [selectedPage, setSelectedPage] = useState(null)
  const [selectedTab, setSelectedTab] = useState(null)
  const [loadingPages, setLoadingPages] = useState(false)
  const [placing, setPlacing] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (!initialApps || initialApps.length === 0) {
      loadApps()
    }
  }, [apiBase])

  const loadApps = async () => {
    try {
      const data = await designerFetch(appsUrl(apiBase))
      setApps(data)
    } catch (err) {
      console.error('Failed to load apps:', err)
    }
  }

  const handleSelectApp = async (app) => {
    setSelectedApp(app)
    setSelectedPage(null)
    setSelectedTab(null)
    setLoadingPages(true)
    setError(null)
    try {
      const data = await designerFetch(appPagesUrl(apiBase, app.id))
      setPages(data)
    } catch (err) {
      console.error('Failed to load pages:', err)
      setPages([])
    } finally {
      setLoadingPages(false)
    }
  }

  const handleSelectPage = (page) => {
    setSelectedPage(page)
    setSelectedTab(null)
    setError(null)
  }

  const handlePlace = async () => {
    if (!selectedApp || !selectedPage) return
    setPlacing(true)
    setError(null)
    try {
      await designerFetch(libraryPlaceUrl(apiBase, definition.id), {
        method: 'POST',
        body: JSON.stringify({
          app_id: selectedApp.id,
          page_id: selectedPage.id,
          tab_id: selectedTab?.id || null,
        }),
      })
      setSuccess(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setPlacing(false)
    }
  }

  if (success) {
    return (
      <div className="dd-page">
        <div className="dd-success-state">
          <i className="fa fa-check-circle dd-success-icon" />
          <h2>Widget Placed!</h2>
          <p>
            <strong>{definition.name}</strong> has been placed on{' '}
            <strong>{selectedPage.name}</strong>
            {selectedTab && <> (tab: <strong>{selectedTab.name}</strong>)</>}
            {' '}in <strong>{selectedApp.name}</strong>.
          </p>
          <div className="dd-success-actions">
            <button type="button" className="wb-btn wb-btn--primary" onClick={onDone}>
              <i className="fa fa-th-large me-1" /> Back to Library
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="dd-page">
      <div className="dd-page-header">
        <h1 className="dd-page-title">Place Widget</h1>
        <button type="button" className="wb-btn wb-btn--ghost" onClick={onBack}>
          <i className="fa fa-arrow-left me-1" /> Back
        </button>
      </div>

      <div className="dd-place-summary">
        <span className="dd-place-label">Placing:</span>
        <span className="dd-place-def-name">{definition.name}</span>
        <span className="dd-badge dd-badge--type">{definition.chart_type}</span>
      </div>

      {error && (
        <div className="dd-result-banner dd-result-banner--error">
          <i className="fa fa-exclamation-triangle me-1" />
          {error}
        </div>
      )}

      {apps.length === 0 ? (
        <div className="dd-empty-state">
          <i className="fa fa-desktop dd-empty-icon" />
          <p>No apps available. Install an app module (e.g. posterra_portal) to place widgets.</p>
          <button type="button" className="wb-btn wb-btn--ghost" onClick={onBack}>
            Back to Library
          </button>
        </div>
      ) : (
        <div className="dd-place-tree">
          {/* Step 1: Select App */}
          <div className="dd-place-step">
            <h3 className="dd-place-step-title">
              <span className="dd-step-num">1</span> Select App
            </h3>
            <div className="dd-place-options">
              {apps.map(app => (
                <button
                  key={app.id}
                  type="button"
                  className={`dd-place-option ${selectedApp?.id === app.id ? 'dd-place-option--active' : ''}`}
                  onClick={() => handleSelectApp(app)}
                >
                  <i className="fa fa-desktop me-2" />
                  {app.name}
                </button>
              ))}
            </div>
          </div>

          {/* Step 2: Select Page */}
          {selectedApp && (
            <div className="dd-place-step">
              <h3 className="dd-place-step-title">
                <span className="dd-step-num">2</span> Select Page
              </h3>
              {loadingPages ? (
                <div className="dd-loading-state">
                  <span className="spinner-border spinner-border-sm me-2" />
                  Loading pages...
                </div>
              ) : pages.length === 0 ? (
                <p className="text-muted">No pages found for this app.</p>
              ) : (
                <div className="dd-place-options">
                  {pages.map(page => (
                    <button
                      key={page.id}
                      type="button"
                      className={`dd-place-option ${selectedPage?.id === page.id ? 'dd-place-option--active' : ''}`}
                      onClick={() => handleSelectPage(page)}
                    >
                      <i className="fa fa-file-o me-2" />
                      {page.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 3: Select Tab (optional) */}
          {selectedPage && selectedPage.tabs && selectedPage.tabs.length > 0 && (
            <div className="dd-place-step">
              <h3 className="dd-place-step-title">
                <span className="dd-step-num">3</span> Select Tab <span className="text-muted">(optional)</span>
              </h3>
              <div className="dd-place-options">
                <button
                  type="button"
                  className={`dd-place-option ${selectedTab === null ? 'dd-place-option--active' : ''}`}
                  onClick={() => setSelectedTab(null)}
                >
                  <i className="fa fa-columns me-2" />
                  No specific tab (page level)
                </button>
                {selectedPage.tabs.map(tab => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`dd-place-option ${selectedTab?.id === tab.id ? 'dd-place-option--active' : ''}`}
                    onClick={() => setSelectedTab(tab)}
                  >
                    <i className="fa fa-bookmark-o me-2" />
                    {tab.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Place button */}
          {selectedApp && selectedPage && (
            <div className="dd-place-confirm">
              <button
                type="button"
                className="wb-btn wb-btn--primary wb-btn--lg"
                onClick={handlePlace}
                disabled={placing}
              >
                {placing ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-1" />
                    Placing...
                  </>
                ) : (
                  <>
                    <i className="fa fa-external-link me-1" />
                    Place on {selectedPage.name}
                    {selectedTab && ` → ${selectedTab.name}`}
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
