import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import PageHelpDrawer from './components/PageHelpDrawer'

// Tailwind CSS — imported from the entry point so Tailwind's JIT scans
// the full app module graph (otherwise classes only used in components
// outside MapWidget's graph are purged from the CSS bundle).
import './styles/tailwind.css'

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
        tokenExpiresIn={Number(rootEl.dataset.tokenExpiresIn) || 3600}
      />
    </React.StrictMode>
  )

  // ── Mount PageHelpDrawer at body level (separate React root) ─────
  //
  // The drawer's trigger icon is rendered server-side in QWeb (the
  // page header lives OUTSIDE #app-root), so we can't put the drawer
  // inside the App tree — it'd lose track of the trigger. Instead we
  // mount a second React root on a body-level <div>, and the drawer
  // listens for global clicks on [data-help-content] elements.
  let drawerHost = document.getElementById('pv-page-help-drawer-root')
  if (!drawerHost) {
    drawerHost = document.createElement('div')
    drawerHost.id = 'pv-page-help-drawer-root'
    document.body.appendChild(drawerHost)
  }
  ReactDOM.createRoot(drawerHost).render(
    <React.StrictMode>
      <PageHelpDrawer />
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
