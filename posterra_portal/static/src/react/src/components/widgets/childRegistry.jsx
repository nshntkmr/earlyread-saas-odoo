// Child-safe renderers ONLY (v1 subset). Excludes BattleCard, InsightPanel,
// SmartTable, RankedDetailList, MapWidget, CompositeWidget — those are
// handled directly in WidgetGrid.resolveTopWidget. Imports flow one direction:
// childRegistry → concrete widget components. Nothing imports back into this
// file, so no cycles can form.

import EChartWidget from './EChartWidget'
import KpiRouter from './KpiRouter'
import GaugeRouter from './GaugeRouter'
import GaugeKPI from './GaugeKPI'
import DataTable from './DataTable'
import LegendList from './LegendList'
import TextNote from './TextNote'

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
    case 'legend_list':   return LegendList
    case 'text_note':     return TextNote
    // v2 follow-ups (NOT supported as composite children in v1):
    //   'ranked_detail_list' — needs widgetId for /detail endpoint
    //   'map' — lazy-loaded; needs per-child Suspense
    //   'smart_table' — no v1 demand as child
    //   'battle_card', 'insight_panel' — complex per-widget config; defer
    default:              return null  // signals UnsupportedChild placeholder in CompositeWidget
  }
}
