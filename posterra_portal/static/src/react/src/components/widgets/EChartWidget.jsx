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
 *   onChartClick — ({ name, value, clickValue, seriesName, dataIndex }) => void
 *
 * `clickValue` is a server-attached custom field on each data point
 * (set in dashboard_widget._build_echart_option for scatter when the
 * admin configures a "Click Value Column" flag). It carries a clean
 * drilldown key (e.g. an HHA's CCN) so go_to_page navigation can pass
 * a usable filter value instead of the multi-line tooltip text.
 */
export default function EChartWidget({ data, height = 350, clickAction, onChartClick, fill = false }) {
  const containerRef = useRef(null)
  const chartRef     = useRef(null)

  // ── Click handler ───────────────────────────────────────────────────────
  const handleClick = useCallback((params) => {
    if (!clickAction || clickAction === 'none' || !onChartClick) return
    onChartClick({
      name: params.name,
      value: params.value,
      // Optional clean drilldown value — see jsdoc above. Older
      // widgets without this field flow through as `undefined`,
      // and WidgetGrid falls back to its existing logic.
      clickValue: params.data?.clickValue,
      seriesName: params.seriesName,
      dataIndex: params.dataIndex,
    })
  }, [clickAction, onChartClick])

  // ── Initialise ECharts instance once ─────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current) return
    chartRef.current = echarts.init(containerRef.current, null, { renderer: 'canvas' })

    // Responsive resize — window for viewport changes, ResizeObserver for the
    // container itself (needed in fill mode: the flex height resolves after the
    // initial layout, and the card can change size, e.g. filter-panel toggle).
    const onResize = () => chartRef.current?.resize()
    window.addEventListener('resize', onResize)
    let ro = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(() => chartRef.current?.resize())
      ro.observe(containerRef.current)
    }

    return () => {
      window.removeEventListener('resize', onResize)
      ro?.disconnect()
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

  // fill mode (standalone in a flex card) → fill the card body via the
  // .pv-widget-echart--fill class (flex:1; min-height:0). Composite/other callers
  // (fill omitted) keep the fixed-pixel height so the alignment wrapper still works.
  return (
    <div
      ref={containerRef}
      className={fill ? 'pv-widget-echart pv-widget-echart--fill' : undefined}
      style={{
        ...(fill ? {} : { height: `${height}px` }),
        width: '100%',
        cursor: (clickAction && clickAction !== 'none') ? 'pointer' : 'default',
      }}
      aria-hidden="true"
    />
  )
}
