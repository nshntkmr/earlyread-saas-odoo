import React from 'react'
import { TokenProvider } from './state/TokenManager'
import { FilterProvider } from './state/FilterContext'
import FilterBar from './components/FilterBar'
import SectionHost from './components/SectionHost'
import TabBar from './components/TabBar'
import WidgetGrid from './components/WidgetGrid'

/**
 * Root component.
 *
 * Props come from main.jsx (parsed from data-* attributes on #app-root):
 *   pageConfig      — { app, page, tabs, filters, filter_dep_map, current_tab_key }
 *   initialWidgets  — { "<widgetId>": { id, chart_type, tab_key, col_span, height, name, data } }
 *   apiBase         — "/api/v1"
 *   accessToken     — JWT access token for API calls
 */
export default function App({ pageConfig, initialWidgets, apiBase, accessToken }) {
  const appKey = pageConfig?.app?.key || ''

  return (
    <TokenProvider initialToken={accessToken} appKey={appKey} apiBase={apiBase}>
      <FilterProvider
        pageConfig={pageConfig}
        apiBase={apiBase}
      >
        <FilterBar />
        <SectionHost placement="page-level" />
        <TabBar />
        <SectionHost placement="tab-level" />
        <WidgetGrid initialWidgets={initialWidgets} />
      </FilterProvider>
    </TokenProvider>
  )
}
