import React, { useState, useEffect } from 'react'
import { designerFetch } from '../api/client'
import { appsUrl, appPagesUrl } from '../api/endpoints'

/**
 * AppContextBar — Optional horizontal bar at top of designer.
 * Lets admin scope work to a specific App → Page → Tab.
 *
 * Props:
 *   apiBase    — designer API base URL
 *   appContext — { app, page, tab } | null
 *   onChange   — (newContext) => void
 */
export default function AppContextBar({ apiBase, appContext, onChange }) {
  const [apps, setApps] = useState([])
  const [pages, setPages] = useState([])
  const [loadingPages, setLoadingPages] = useState(false)

  // Load apps on mount
  useEffect(() => {
    designerFetch(appsUrl(apiBase))
      .then(setApps)
      .catch(() => setApps([]))
  }, [apiBase])

  // Load pages when app changes
  useEffect(() => {
    if (!appContext?.app) {
      setPages([])
      return
    }
    setLoadingPages(true)
    designerFetch(appPagesUrl(apiBase, appContext.app.id))
      .then(setPages)
      .catch(() => setPages([]))
      .finally(() => setLoadingPages(false))
  }, [apiBase, appContext?.app?.id])

  const handleAppChange = (e) => {
    const appId = parseInt(e.target.value, 10)
    if (!appId) {
      onChange(null)
      return
    }
    const app = apps.find(a => a.id === appId)
    onChange({ app, page: null, tab: null })
  }

  const handlePageChange = (e) => {
    const pageId = parseInt(e.target.value, 10)
    if (!pageId) {
      onChange({ ...appContext, page: null, tab: null })
      return
    }
    const page = pages.find(p => p.id === pageId)
    onChange({ ...appContext, page, tab: null })
  }

  const handleTabChange = (e) => {
    const tabId = parseInt(e.target.value, 10)
    if (!tabId) {
      onChange({ ...appContext, tab: null })
      return
    }
    const tab = appContext.page.tabs.find(t => t.id === tabId)
    onChange({ ...appContext, tab })
  }

  const handleClear = () => onChange(null)

  const tabs = appContext?.page?.tabs || []

  return (
    <div className="dd-context-bar">
      <div className="dd-context-bar-inner">
        <span className="dd-context-label">
          <i className="fa fa-crosshairs me-1" />
          Context
        </span>

        {/* App dropdown */}
        <select
          className="dd-context-select"
          value={appContext?.app?.id || ''}
          onChange={handleAppChange}
        >
          <option value="">All Apps</option>
          {apps.map(a => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>

        {/* Page dropdown */}
        {appContext?.app && (
          <>
            <i className="fa fa-chevron-right dd-context-sep" />
            <select
              className="dd-context-select"
              value={appContext?.page?.id || ''}
              onChange={handlePageChange}
              disabled={loadingPages}
            >
              <option value="">
                {loadingPages ? 'Loading...' : 'Select Page'}
              </option>
              {pages.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </>
        )}

        {/* Tab dropdown */}
        {appContext?.page && tabs.length > 0 && (
          <>
            <i className="fa fa-chevron-right dd-context-sep" />
            <select
              className="dd-context-select"
              value={appContext?.tab?.id || ''}
              onChange={handleTabChange}
            >
              <option value="">Page level</option>
              {tabs.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </>
        )}

        {/* Clear button */}
        {appContext?.app && (
          <button
            type="button"
            className="dd-context-clear"
            onClick={handleClear}
            title="Clear context"
          >
            <i className="fa fa-times" />
          </button>
        )}
      </div>
    </div>
  )
}
