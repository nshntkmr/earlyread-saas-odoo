import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

const rootEl = document.getElementById('designer-root')
if (rootEl) {
  let apps = []
  try { apps = JSON.parse(rootEl.dataset.apps || '[]') } catch (e) { console.error('apps parse error', e) }

  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <App
        apiBase={rootEl.dataset.apiBase || '/dashboard/designer/api'}
        userName={rootEl.dataset.userName || 'Admin'}
        initialApps={apps}
      />
    </React.StrictMode>
  )
}
