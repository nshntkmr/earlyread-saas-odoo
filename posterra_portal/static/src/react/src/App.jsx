import React from 'react'
import { TokenProvider } from './state/TokenManager'
import { FilterProvider } from './state/FilterContext'
import FilterBar from './components/FilterBar'
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
 *   apiBase         — "/api/v1"
 *   accessToken     — JWT access token for API calls
 */
export default function App({ pageConfig, initialWidgets, initialSections, apiBase, accessToken }) {
  const appKey = pageConfig?.app?.key || ''

  return (
    <TokenProvider initialToken={accessToken} appKey={appKey} apiBase={apiBase}>
      <FilterProvider
        pageConfig={pageConfig}
        apiBase={apiBase}
      >
        <FilterBar />
        <SectionGrid placement="page-level" initialSections={initialSections} apiBase={apiBase} />
        <TabBar />
        <SectionGrid placement="tab-level" initialSections={initialSections} apiBase={apiBase} />
        <WidgetGrid initialWidgets={initialWidgets} />
      </FilterProvider>
    </TokenProvider>
  )
}
