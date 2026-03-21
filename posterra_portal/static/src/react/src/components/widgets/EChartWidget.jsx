import React, { useEffect, useRef, useCallback } from 'react'
import * as echarts from 'echarts'

/**
 * EChartWidget
 *
 * Generic wrapper for all Apache ECharts 5 chart types:
 *   bar, line, pie, donut, gauge, radar, scatter, heatmap
 *
 * The widget API returns `echart_option` (a parsed dict) when the portal.py
 * JSON builder normalises `echart_json` string → `echart_option` dict.
 *
 * Props:
 *   data        — { echart_option: {...} }  (from widget_data / API)
 *   height      — number (pixels), default 350
 *   clickAction — string (none|filter_page|go_to_page|show_details|open_url)
 *   onChartClick — ({ name, value, seriesName, dataIndex }) => void
 */
export default function EChartWidget({ data, height = 350, clickAction, onChartClick }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)

  // ── Click handler ───────────────────────────────────────────────────────
  const handleClick = useCallback((params) => {
    if (!clickAction || clickAction === 'none' || !onChartClick) return
    onChartClick({
      name: params.name,
      value: params.value,
      seriesName: params.seriesName,
      dataIndex: params.dataIndex,
    })
  }, [clickAction, onChartClick])

  // ── Initialise ECharts instance once ─────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return
    chartRef.current = echarts.init(containerRef.current, null, { renderer: 'canvas' })

    // Responsive resize
    const onResize = () => chartRef.current?.resize()
    window.addEventListener('resize', onResize)

    return () => {
      window.removeEventListener('resize', onResize)
      chartRef.current?.dispose()
      chartRef.current = null
    }
  }, [])

  // ── Attach / re-attach click listener ──────────────────────────────────
  useEffect(() => {
    if (!chartRef.current) return
    chartRef.current.off('click')
    if (clickAction && clickAction !== 'none') {
      chartRef.current.on('click', handleClick)
    }
  }, [clickAction, handleClick])

  // ── Update chart option whenever data changes ─────────────────────────────
  useEffect(() => {
    if (!chartRef.current) return
    const option = data?.echart_option
    if (!option || typeof option !== 'object') return
    chartRef.current.setOption(option, { notMerge: true, lazyUpdate: false })
  }, [data])

  return (
    <div
      ref={containerRef}
      style={{
        height: `${height}px`,
        width: '100%',
        cursor: (clickAction && clickAction !== 'none') ? 'pointer' : 'default',
      }}
      aria-hidden="true"
    />
  )
}
