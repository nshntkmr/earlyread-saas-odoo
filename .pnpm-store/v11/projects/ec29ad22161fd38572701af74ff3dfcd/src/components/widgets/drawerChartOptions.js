const COMPACT_FORMATTER = new Intl.NumberFormat('en-US', {
  notation: 'compact',
  maximumSignificantDigits: 3,
})
const NUMBER_FORMATTER = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 2,
})

export function formatDrawerChartValue(value, mode = 'compact') {
  const number = Number(value)
  if (!Number.isFinite(number)) return value == null ? '' : String(value)
  if (mode === 'raw') return String(value)
  if (mode === 'number') return NUMBER_FORMATTER.format(number)
  return COMPACT_FORMATTER.format(number)
}

function themePrimaryColor() {
  if (typeof document === 'undefined' || typeof getComputedStyle === 'undefined') {
    return '#0066cc'
  }
  return getComputedStyle(document.documentElement)
    .getPropertyValue('--pv-primary')
    .trim() || '#0066cc'
}

/**
 * Build the standard Detail Drawer bar-chart option.
 *
 * This intentionally exposes a small config surface instead of arbitrary
 * ECharts overrides. Every application therefore gets the same axes, grid,
 * typography, tooltip, bar radius, and animation. Applications may select the
 * data columns, orientation, value format, height, series label, and accent
 * color without forking the visual design.
 */
export function buildDrawerChartOption(section, rows) {
  const xColumn = section.x_column
  const yColumn = section.y_column
  const numberFormat = section.number_format || 'compact'
  const horizontal = section.orientation === 'horizontal'
  const showValues = section.show_values !== false
  const color = section.color || themePrimaryColor()
  const categories = rows.map(row => {
    const value = row?.[xColumn]
    return value == null ? '' : String(value)
  })
  const values = rows.map(row => {
    const value = Number(row?.[yColumn])
    return Number.isFinite(value) ? value : null
  })
  const valueFormatter = value => formatDrawerChartValue(value, numberFormat)
  const categoryAxis = {
    type: 'category',
    data: categories,
    axisLine: { lineStyle: { color: '#d1d5db' } },
    axisTick: { show: false },
    axisLabel: { color: '#6b7280', fontSize: 11 },
  }
  const valueAxis = {
    type: 'value',
    min: 0,
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: '#6b7280', fontSize: 11, formatter: valueFormatter },
    splitLine: { lineStyle: { color: '#e5e7eb' } },
  }

  return {
    animationDuration: 450,
    grid: horizontal
      ? { top: 8, right: 54, bottom: 16, left: 8, containLabel: true }
      : { top: 22, right: 12, bottom: 12, left: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter,
    },
    xAxis: horizontal ? valueAxis : categoryAxis,
    yAxis: horizontal ? categoryAxis : valueAxis,
    series: [{
      name: section.series_name || yColumn,
      type: 'bar',
      data: values,
      barMaxWidth: 34,
      itemStyle: {
        color,
        borderRadius: horizontal ? [0, 5, 5, 0] : [5, 5, 0, 0],
      },
      emphasis: { focus: 'series' },
      label: {
        show: showValues,
        position: horizontal ? 'right' : 'top',
        color: '#374151',
        fontSize: 11,
        formatter: params => valueFormatter(params.value),
      },
    }],
  }
}

export function drawerChartHeight(section) {
  const requested = Number(section.height)
  if (!Number.isFinite(requested)) return 220
  return Math.max(160, Math.min(420, requested))
}
