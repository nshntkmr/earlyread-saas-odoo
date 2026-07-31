import React from 'react'

// ═════════════════════════════════════════════════════════════════════════════
// MAP WIDGET — thin renderer shell
// ═════════════════════════════════════════════════════════════════════════════
// This shell owns ZERO MapLibre imports so that choropleth maps rendered with the
// SVG/D3 Albers renderer never pull the ~1 MB MapLibre chunk. It lazy-routes to:
//   • AlbersChoroplethMap  — SVG/D3 geoAlbersUsa choropleth (Image-2 fidelity)
//   • MapLibreMap          — point / bubble / heatmap / maplibre-choropleth
// The choice is driven by the widget's map_config (marker_mode + choropleth_renderer).
// Each renderer loads under a LOCAL <Suspense> so a nested lazy chunk never blanks
// the whole widget grid (the grid's outer Suspense is fallback={null}).
// ═════════════════════════════════════════════════════════════════════════════

const MapLibreMap = React.lazy(() => import('./MapLibreMap'))
const AlbersChoroplethMap = React.lazy(() => import('./AlbersChoroplethMap'))

export default function MapWidget({ data, height, name, widgetId = null, onMapDrill, mapDrillState, drillable = false, onCrossFilter }) {
  const cfg = data?.map_config || {}
  const isChoropleth = !!data?.choropleth_data || cfg.marker_mode === 'choropleth'
  // Default renderer = MapLibre (back-compat with existing choropleth widgets).
  const renderer = cfg.choropleth_renderer || 'maplibre_webmercator'
  const useSvgAlbers = isChoropleth && renderer === 'svg_albers_usa'

  // Only the SVG/Albers renderer supports state→county drill. Translate the
  // grid's drill state into the concrete drilled FIPS the renderer filters by.
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
      {useSvgAlbers
        ? <AlbersChoroplethMap data={data} height={height} name={name} widgetId={widgetId}
            onDrill={onMapDrill} drillable={drillable} drilledState={drilledState}
            onCrossFilter={onCrossFilter} />
        : <MapLibreMap data={data} height={height} name={name}
            onCrossFilter={onCrossFilter} />}
    </React.Suspense>
  )
}
