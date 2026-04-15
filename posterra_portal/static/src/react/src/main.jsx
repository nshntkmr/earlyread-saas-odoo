import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

function mount() {
  const rootEl = document.getElementById('app-root')
  if (!rootEl) return  // Not on a dashboard page — silently skip

  // Parse JSON data attributes embedded by portal.py
  let pageConfig = {}
  let initialWidgets = {}
  let initialSections = {}
  let initialBadges = []
  try { pageConfig    = JSON.parse(rootEl.dataset.pageConfig    || '{}') } catch (e) { console.error('pageConfig parse error', e) }
  try { initialWidgets = JSON.parse(rootEl.dataset.initialWidgets || '{}') } catch (e) { console.error('initialWidgets parse error', e) }
  try { initialSections = JSON.parse(rootEl.dataset.initialSections || '{}') } catch (e) { console.error('initialSections parse error', e) }
  try { initialBadges  = JSON.parse(rootEl.dataset.initialBadges  || '[]') } catch (e) { console.error('initialBadges parse error', e) }

  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <App
        pageConfig={pageConfig}
        initialWidgets={initialWidgets}
        initialSections={initialSections}
        initialBadges={initialBadges}
        apiBase={rootEl.dataset.apiBase || '/api/v1'}
        accessToken={rootEl.dataset.accessToken || ''}
      />
    </React.StrictMode>
  )
}

// Mount after DOM is ready — script may load before #app-root exists
// (portal.js is loaded via <script defer> outside Odoo's asset system)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount)
} else {
  mount()  // DOM already parsed (e.g., script has defer or is at bottom)
}
