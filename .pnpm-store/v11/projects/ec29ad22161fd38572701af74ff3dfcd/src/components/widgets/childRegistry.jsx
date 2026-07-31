// Child-safe renderers ONLY. Excludes BattleCard, InsightPanel,
// RankedDetailList, MapWidget, CompositeWidget — those are handled directly
// in WidgetGrid.resolveTopWidget. Imports flow one direction:
// childRegistry → concrete widget components. Nothing imports back into this
// file, so no cycles can form.

import EChartWidget from './EChartWidget'
import KpiRouter from './KpiRouter'
import GaugeRouter from './GaugeRouter'
import GaugeKPI from './GaugeKPI'
import DataTable from './DataTable'
import LegendList from './LegendList'
import TextNote from './TextNote'
// Shared package — same component standalone (WidgetGrid) and as a child;
// the composite child payload is byte-identical to the standalone payload
// (both come from dashboard.widget._build_smart_table_data).
import { SmartTable } from '@posterra/grid-utils'

export function resolveChildWidget(chartType) {
  switch (chartType) {
    case 'bar':
    case 'line':
    case 'pie':
    case 'donut':
    case 'radar':
    case 'scatter':
    case 'heatmap':
    case 'sankey':        return EChartWidget
    case 'gauge':         return GaugeRouter
    case 'gauge_kpi':     return GaugeKPI
    case 'kpi':
    case 'status_kpi':
    case 'kpi_strip':     return KpiRouter
    case 'table':         return DataTable
    case 'smart_table':   return SmartTable
    case 'legend_list':   return LegendList
    case 'text_note':     return TextNote
    // v2 follow-ups (NOT supported as composite children):
    //   'ranked_detail_list' — needs widgetId for /detail endpoint
    //   'map' — lazy-loaded; needs per-child Suspense
    //   'battle_card', 'insight_panel' — complex per-widget config; defer
    default:              return null  // signals UnsupportedChild placeholder in CompositeWidget
  }
}
