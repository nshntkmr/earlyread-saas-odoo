import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

const rootEl = document.getElementById('app-root')
if (rootEl) {
  // Parse JSON data attributes embedded by portal.py
  let pageConfig = {}
  let initialWidgets = {}
  try { pageConfig    = JSON.parse(rootEl.dataset.pageConfig    || '{}') } catch (e) { console.error('pageConfig parse error', e) }
  try { initialWidgets = JSON.parse(rootEl.dataset.initialWidgets || '{}') } catch (e) { console.error('initialWidgets parse error', e) }

  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <App
        pageConfig={pageConfig}
        initialWidgets={initialWidgets}
        apiBase={rootEl.dataset.apiBase || '/api/v1'}
        accessToken={rootEl.dataset.accessToken || ''}
      />
    </React.StrictMode>
  )
}
