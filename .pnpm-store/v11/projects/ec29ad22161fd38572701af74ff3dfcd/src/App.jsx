import React from 'react'
import { TokenProvider } from './state/TokenManager'
import { FilterProvider } from './state/FilterContext'
import BadgeBar from './components/BadgeBar'
import BelowHeaderStart from './components/BelowHeaderStart'
import FilterBar from './components/FilterBar'
import IdleWarningModal from './components/IdleWarningModal'
import SectionGrid from './components/SectionGrid'
import TabBar from './components/TabBar'
import WidgetGrid from './components/WidgetGrid'

/**
 * Root component.
 *
 * Props come from main.jsx (parsed from data-* attributes on #app-root):
 *   pageConfig      — { app, page, tabs, filters, filter_dep_map, current_tab_key }
 *   initialWidgets  — { "<widgetId>": { id, chart_type, tab_key, col_span, height, name, data } }
 *   initialSections — { "<sectionId>": { id, name, section_type, scope, data, ... } }
 *   initialBadges   — [ { id, icon, value, font_size, text_color, icon_color, is_link } ]
 *   apiBase         — "/api/v1"
 *   accessToken     — JWT access token for API calls
 */
export default function App({ pageConfig, initialWidgets, initialSections, initialBadges, apiBase, accessToken, tokenExpiresIn }) {
  const appKey = pageConfig?.app?.key || ''

  // ── Page annotation placement (additive; opt-in) ──────────────────────
  // Existing badges carry no placement → they are all `below_header_end`, so
  // `legacyBadges` === the full set and BadgeBar renders exactly as before.
  const bySeq = (a, b) => (a.sequence || 0) - (b.sequence || 0)
  const allBadges = initialBadges || []
  const legacyBadges = allBadges
    .filter(b => !b.placement || b.placement === 'below_header_end')
    .slice().sort(bySeq)
  const belowStartBadges = allBadges
    .filter(b => b.placement === 'below_header_start')
    .slice().sort(bySeq)
  const headerBadges = allBadges
    .filter(b => b.placement === 'page_header_start' || b.placement === 'page_header_end')

  // ── Page-level widget placement (render_region) ───────────────────────
  // Existing widgets carry no render_region → all resolve to tab_content, so
  // the tab-content grid gets the full set and renders exactly as before.
  const widgetEntries = Object.entries(initialWidgets || {})
  const isPageSummaryWidget = ([, w]) => (w.render_region || 'tab_content') === 'page_summary'
  const pageSummaryWidgets = Object.fromEntries(widgetEntries.filter(isPageSummaryWidget))
  const tabContentWidgets = Object.fromEntries(widgetEntries.filter(e => !isPageSummaryWidget(e)))

  return (
    <TokenProvider
      initialToken={accessToken}
      appKey={appKey}
      apiBase={apiBase}
      initialExpiresIn={tokenExpiresIn}
      idleTimeoutMins={pageConfig?.app?.idle_timeout_mins || 0}
      userId={pageConfig?.user_id || 0}
    >
      <FilterProvider
        pageConfig={pageConfig}
        apiBase={apiBase}
      >
        {belowStartBadges.length > 0 ? (
          <div className="pv-below-header-split">
            <BelowHeaderStart badges={belowStartBadges} />
            <BadgeBar initialBadges={legacyBadges} />
          </div>
        ) : (
          <BadgeBar initialBadges={legacyBadges} />
        )}
        {/* FilterBar owns the unified page-header renderer (badges + header
            filters, sorted). The old standalone <HeaderActions> is gone so
            header badges don't double-render. */}
        <FilterBar headerBadges={headerBadges} />
        <SectionGrid placement="page-level" initialSections={initialSections} apiBase={apiBase} />
        {Object.keys(pageSummaryWidgets).length > 0 && (
          <WidgetGrid placement="page-summary" initialWidgets={pageSummaryWidgets} />
        )}
        <TabBar />
        <SectionGrid placement="tab-level" initialSections={initialSections} apiBase={apiBase} />
        <WidgetGrid placement="tab-content" initialWidgets={tabContentWidgets} />
        <IdleWarningModal primaryColor={pageConfig?.app?.primary_color || '#0066cc'} />
      </FilterProvider>
    </TokenProvider>
  )
}
