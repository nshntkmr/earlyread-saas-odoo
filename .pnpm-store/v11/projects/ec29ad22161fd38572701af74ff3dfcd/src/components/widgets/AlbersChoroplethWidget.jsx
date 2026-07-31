import React from 'react'

// ═════════════════════════════════════════════════════════════════════════════
// US CHOROPLETH WIDGET — thin shell for the standalone `albers_choropleth` type
// ═════════════════════════════════════════════════════════════════════════════
// This is the SVG-Albers-only half of MapWidget, with ZERO MapLibre imports, so
// the `albers_choropleth` chart type never pulls the ~1 MB MapLibre chunk.
//
// Why a wrapper (not resolving straight to AlbersChoroplethMap): WidgetGrid passes
// map-grid prop names (`onMapDrill` / `mapDrillState`), but AlbersChoroplethMap
// expects `onDrill` / `drilledState`. MapWidget adapts them for the `map` type;
// this wrapper does the same adaptation for the standalone choropleth type.
// ═════════════════════════════════════════════════════════════════════════════

const AlbersChoroplethMap = React.lazy(() => import('./AlbersChoroplethMap'))

export default function AlbersChoroplethWidget({
  data, height, name, widgetId = null, onMapDrill, mapDrillState, drillable = false, onCrossFilter,
}) {
  // Only the county level is a drilled view; translate the grid's drill state
  // into the concrete drilled FIPS the renderer filters by (same as MapWidget).
  const drilledState = (mapDrillState && mapDrillState.mapLevel === 'county')
    ? (mapDrillState.drillStateFips || null)
    : null

  const fallback = (
    <div style={{
      height: height || 420, display: 'flex', alignItems: 'center',
      justifyContent: 'center', color: '#9ca3af', fontSize: 13,
    }}>Loading map…</div>
  )

  return (
    <React.Suspense fallback={fallback}>
      <AlbersChoroplethMap
        data={data} height={height} name={name} widgetId={widgetId}
        onDrill={onMapDrill} drillable={drillable} drilledState={drilledState}
        onCrossFilter={onCrossFilter} />
    </React.Suspense>
  )
}
