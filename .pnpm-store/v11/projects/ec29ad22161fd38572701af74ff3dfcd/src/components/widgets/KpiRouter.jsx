import React from 'react'
import KPICard from './KPICard'
import StatusKPI from './StatusKPI'
import KPIStrip from './KPIStrip'
import KpiCardGeneric from './KpiCardGeneric'

/**
 * KpiRouter — dispatches KPI widgets to the appropriate variant component.
 *
 * Mirrors GaugeRouter pattern: switches on data.kpi_variant from visual_config.
 * Backward compat: widgets without kpi_variant fall back to StatusKPI or KPICard
 * based on data.type.
 */
export default function KpiRouter({ data = {}, name }) {
  const variant = data.kpi_variant

  switch (variant) {
    case 'sparkline':
    case 'progress':
    case 'mini_gauge':
    case 'comparison':
    case 'rag_status':
      return <KpiCardGeneric data={data} name={name} />
    case 'strip':
      return <KPIStrip data={data} name={name} />
    case 'stat_card':
      return <StatusKPI data={data} name={name} />
    default:
      // Backward compat for existing widgets without kpi_variant
      if (data.type === 'status_kpi') return <StatusKPI data={data} name={name} />
      if (data.type === 'kpi_strip')  return <KPIStrip data={data} name={name} />
      return <KPICard data={data} name={name} />
  }
}
