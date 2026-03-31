import React from 'react'
import EChartWidget from './EChartWidget'
import BulletGauge from './BulletGauge'
import TrafficLightGauge from './TrafficLightGauge'
import PercentileGauge from './PercentileGauge'

/**
 * GaugeRouter
 *
 * Routes gauge widget data to the appropriate renderer based on `gauge_variant`.
 * - ECharts variants (standard, half_arc, three_quarter, multi_ring) return echart_option
 *   and are rendered by EChartWidget.
 * - Non-ECharts variants (bullet, traffic_light_rag, percentile_rank) return plain dicts
 *   and are rendered by dedicated React components.
 */
export default function GaugeRouter({ data = {}, height, ...rest }) {
  const variant = data?.gauge_variant

  switch (variant) {
    case 'bullet':
      return <BulletGauge data={data} height={height} {...rest} />
    case 'traffic_light_rag':
      return <TrafficLightGauge data={data} height={height} {...rest} />
    case 'percentile_rank':
      return <PercentileGauge data={data} height={height} {...rest} />
    default:
      // ECharts-based variants (standard, half_arc, three_quarter, multi_ring)
      // or any unrecognized variant — fall through to EChartWidget
      return <EChartWidget data={data} height={height} {...rest} />
  }
}
