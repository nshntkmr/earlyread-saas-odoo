import React, { useMemo } from 'react'
import EChartWidget from './EChartWidget'
import { buildDrawerChartOption, drawerChartHeight } from './drawerChartOptions'

/** Opt-in chart section for DetailDrawer; legacy section renderers never enter here. */
export default function DrawerChartSection({ section, rows }) {
  const option = useMemo(
    () => buildDrawerChartOption(section, rows),
    [section, rows],
  )

  if (!rows.length) {
    return <div style={{ fontSize: 12, color: '#9ca3af' }}>No records.</div>
  }

  return (
    <EChartWidget
      data={{ echart_option: option }}
      height={drawerChartHeight(section)}
    />
  )
}
