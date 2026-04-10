import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

// ── Map style URLs (free, no API key for light/streets/dark) ────────────────
const MAP_STYLES = {
  light:     'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  streets:   'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
  dark:      'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
  satellite: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json', // fallback until Maptiler key
}

// ── Color palettes for category coloring ────────────────────────────────────
const CATEGORY_COLORS = [
  '#0ea5e9', '#f97316', '#22c55e', '#ef4444', '#a855f7',
  '#eab308', '#14b8a6', '#ec4899', '#6366f1', '#84cc16',
]

const CHOROPLETH_SEQUENTIAL = [
  '#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6',
  '#4292c6', '#2171b5', '#08519c', '#08306b',
]

const CHOROPLETH_DIVERGING = [
  '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7',
  '#d1e5f0', '#92c5de', '#4393c3', '#2166ac',
]

// ── Helper: build circle radius for hovered marker ──────────────────────────
function milesToMeters(miles) {
  return miles * 1609.344
}

function createRadiusGeoJSON(center, radiusMiles) {
  const steps = 64
  const km = radiusMiles * 1.60934
  const ret = []
  const distanceX = km / (111.32 * Math.cos((center[1] * Math.PI) / 180))
  const distanceY = km / 110.574
  for (let i = 0; i < steps; i++) {
    const theta = (i / steps) * (2 * Math.PI)
    ret.push([
      center[0] + distanceX * Math.cos(theta),
      center[1] + distanceY * Math.sin(theta),
    ])
  }
  ret.push(ret[0])
  return {
    type: 'Feature',
    geometry: { type: 'Polygon', coordinates: [ret] },
  }
}

// ── Main MapWidget Component ────────────────────────────────────────────────
export default function MapWidget({ data, height, name }) {
  const mapRef = useRef(null)
  const [popupInfo, setPopupInfo] = useState(null)
  const [hoveredRegion, setHoveredRegion] = useState(null)

  // Map config from visual_config flags (admin defaults)
  const cfg = data?.map_config || {}

  // Runtime overrides (session-only, end-user toolbar)
  const [mapStyle, setMapStyle] = useState(cfg.map_style || 'light')
  const [markerMode, setMarkerMode] = useState(cfg.marker_mode || 'points')
  const [clustering, setClustering] = useState(cfg.clustering !== false)
  const [showRadius, setShowRadius] = useState(cfg.show_radius || false)
  const [radiusMiles, setRadiusMiles] = useState(cfg.radius_miles || 25)

  const popupColumns = useMemo(() => {
    const raw = cfg.popup_columns || ''
    return raw.split(',').map(s => s.trim()).filter(Boolean)
  }, [cfg.popup_columns])

  const colorColumn = cfg.color_column || ''
  const sizeColumn = cfg.size_column || ''

  // ── Build category → color mapping ──────────────────────────────────────
  const categoryColors = useMemo(() => {
    if (!colorColumn || !data?.geojson?.features) return {}
    const unique = [...new Set(
      data.geojson.features
        .map(f => f.properties[colorColumn])
        .filter(Boolean)
    )]
    const map = {}
    unique.forEach((cat, i) => {
      map[cat] = CATEGORY_COLORS[i % CATEGORY_COLORS.length]
    })
    return map
  }, [colorColumn, data?.geojson])

  // ── Fit bounds on data load ─────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current) return
    const map = mapRef.current
    if (data?.bounds) {
      const [w, s, e, n] = data.bounds
      map.fitBounds([[w, s], [e, n]], { padding: 50, maxZoom: 12, duration: 500 })
    }
  }, [data?.bounds])

  // ── Marker click handler ────────────────────────────────────────────────
  const onMarkerClick = useCallback((e) => {
    const feature = e.features?.[0]
    if (!feature) return

    // Cluster click: zoom in
    if (feature.properties.cluster) {
      const map = mapRef.current
      if (!map) return
      const source = map.getSource('map-points')
      if (source?.getClusterExpansionZoom) {
        source.getClusterExpansionZoom(feature.properties.cluster_id, (err, zoom) => {
          if (!err) {
            map.easeTo({
              center: feature.geometry.coordinates,
              zoom: Math.min(zoom, 15),
            })
          }
        })
      }
      return
    }

    // Single marker click: show popup
    const coords = feature.geometry.coordinates.slice()
    setPopupInfo({ coords, properties: feature.properties })
  }, [])

  // ── Choropleth hover/click ──────────────────────────────────────────────
  const onChoroplethHover = useCallback((e) => {
    const feature = e.features?.[0]
    if (feature) {
      setHoveredRegion(feature.properties)
    } else {
      setHoveredRegion(null)
    }
  }, [])

  // ── Radius overlay GeoJSON ──────────────────────────────────────────────
  const radiusGeoJSON = useMemo(() => {
    if (!showRadius || !popupInfo) return null
    return createRadiusGeoJSON(popupInfo.coords, radiusMiles)
  }, [showRadius, popupInfo, radiusMiles])

  // ── Build circle-color paint expression ─────────────────────────────────
  const circleColor = useMemo(() => {
    if (!colorColumn || Object.keys(categoryColors).length === 0) return '#0ea5e9'
    const expr = ['match', ['get', colorColumn]]
    Object.entries(categoryColors).forEach(([cat, color]) => {
      expr.push(cat, color)
    })
    expr.push('#94a3b8') // fallback color
    return expr
  }, [colorColumn, categoryColors])

  // ── Build circle-radius expression ──────────────────────────────────────
  const circleRadius = useMemo(() => {
    if (markerMode !== 'bubble' || !sizeColumn) return 6
    return [
      'interpolate', ['linear'],
      ['get', sizeColumn],
      0, 4,
      100, 8,
      1000, 14,
      10000, 22,
      100000, 32,
    ]
  }, [markerMode, sizeColumn])

  // ── Choropleth rendering ────────────────────────────────────────────────
  if (markerMode === 'choropleth' && data?.choropleth_data) {
    return (
      <div style={{ width: '100%', height: height || 400, position: 'relative' }}>
        <MapToolbar
          mapStyle={mapStyle} setMapStyle={setMapStyle}
          markerMode={markerMode} setMarkerMode={setMarkerMode}
          clustering={clustering} setClustering={setClustering}
          showRadius={showRadius} setShowRadius={setShowRadius}
        />
        <Map
          ref={mapRef}
          mapStyle={MAP_STYLES[mapStyle] || MAP_STYLES.light}
          initialViewState={{
            longitude: cfg.default_center_lng || -98.58,
            latitude: cfg.default_center_lat || 39.83,
            zoom: cfg.default_zoom || 4,
          }}
          style={{ width: '100%', height: '100%' }}
          interactiveLayerIds={['choropleth-fill']}
          onMouseMove={onChoroplethHover}
          onClick={(e) => {
            const feature = e.features?.[0]
            if (feature) {
              setPopupInfo({
                coords: [e.lngLat.lng, e.lngLat.lat],
                properties: data.choropleth_popup_data?.[
                  feature.properties.STUSPS || feature.properties.NAME
                ] || feature.properties,
              })
            }
          }}
        >
          <NavigationControl position="bottom-right" />
          <ChoroplethLayers
            data={data}
            cfg={cfg}
          />
          {popupInfo && (
            <Popup
              longitude={popupInfo.coords[0]}
              latitude={popupInfo.coords[1]}
              onClose={() => setPopupInfo(null)}
              closeOnClick={false}
              className="pv-map-popup"
            >
              <PopupContent properties={popupInfo.properties} columns={popupColumns} />
            </Popup>
          )}
        </Map>
        <ChoroplethLegend data={data} cfg={cfg} />
      </div>
    )
  }

  // ── Point / Bubble / Heatmap rendering ──────────────────────────────────
  const geojson = data?.geojson || { type: 'FeatureCollection', features: [] }

  return (
    <div style={{ width: '100%', height: height || 400, position: 'relative' }}>
      <MapToolbar
        mapStyle={mapStyle} setMapStyle={setMapStyle}
        markerMode={markerMode} setMarkerMode={setMarkerMode}
        clustering={clustering} setClustering={setClustering}
        showRadius={showRadius} setShowRadius={setShowRadius}
      />
      <Map
        ref={mapRef}
        mapStyle={MAP_STYLES[mapStyle] || MAP_STYLES.light}
        initialViewState={{
          longitude: cfg.default_center_lng || -98.58,
          latitude: cfg.default_center_lat || 39.83,
          zoom: cfg.default_zoom || 4,
        }}
        style={{ width: '100%', height: '100%' }}
        interactiveLayerIds={
          markerMode === 'heatmap' ? [] : ['point-markers', 'cluster-circles']
        }
        onClick={onMarkerClick}
      >
        <NavigationControl position="bottom-right" />

        <Source
          id="map-points"
          type="geojson"
          data={geojson}
          cluster={clustering && markerMode !== 'heatmap'}
          clusterMaxZoom={14}
          clusterRadius={50}
        >
          {markerMode === 'heatmap' ? (
            <Layer
              id="heatmap-layer"
              type="heatmap"
              paint={{
                'heatmap-weight': cfg.heatmap_weight_column
                  ? ['interpolate', ['linear'], ['get', cfg.heatmap_weight_column], 0, 0, 10000, 1]
                  : 1,
                'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 12, 3],
                'heatmap-radius': ['interpolate', ['linear'], ['zoom'],
                  0, cfg.heatmap_radius || 20,
                  12, (cfg.heatmap_radius || 20) * 2,
                ],
                'heatmap-color': [
                  'interpolate', ['linear'], ['heatmap-density'],
                  0, 'rgba(0,0,0,0)',
                  0.2, 'rgb(103,169,207)',
                  0.4, 'rgb(209,229,240)',
                  0.6, 'rgb(253,219,199)',
                  0.8, 'rgb(239,138,98)',
                  1, 'rgb(178,24,43)',
                ],
                'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 7, 1, 14, 0],
              }}
            />
          ) : (
            <>
              {/* Cluster circles */}
              <Layer
                id="cluster-circles"
                type="circle"
                filter={['has', 'point_count']}
                paint={{
                  'circle-color': [
                    'step', ['get', 'point_count'],
                    '#51bbd6', 10,
                    '#f1f075', 50,
                    '#f28cb1',
                  ],
                  'circle-radius': [
                    'step', ['get', 'point_count'],
                    16, 10,
                    22, 50,
                    30,
                  ],
                  'circle-stroke-width': 2,
                  'circle-stroke-color': '#fff',
                }}
              />
              {/* Cluster count label */}
              <Layer
                id="cluster-count"
                type="symbol"
                filter={['has', 'point_count']}
                layout={{
                  'text-field': '{point_count_abbreviated}',
                  'text-font': ['Open Sans Bold'],
                  'text-size': 12,
                }}
              />
              {/* Individual point markers */}
              <Layer
                id="point-markers"
                type="circle"
                filter={['!', ['has', 'point_count']]}
                paint={{
                  'circle-color': circleColor,
                  'circle-radius': circleRadius,
                  'circle-stroke-width': 1.5,
                  'circle-stroke-color': '#fff',
                  'circle-opacity': 0.85,
                }}
              />
            </>
          )}
        </Source>

        {/* Radius overlay */}
        {radiusGeoJSON && (
          <Source id="radius-overlay" type="geojson" data={radiusGeoJSON}>
            <Layer
              id="radius-fill"
              type="fill"
              paint={{
                'fill-color': '#0ea5e9',
                'fill-opacity': 0.1,
              }}
            />
            <Layer
              id="radius-border"
              type="line"
              paint={{
                'line-color': '#0ea5e9',
                'line-width': 2,
                'line-dasharray': [2, 2],
              }}
            />
          </Source>
        )}

        {/* Popup */}
        {popupInfo && (
          <Popup
            longitude={popupInfo.coords[0]}
            latitude={popupInfo.coords[1]}
            onClose={() => setPopupInfo(null)}
            closeOnClick={false}
            className="pv-map-popup"
          >
            <PopupContent properties={popupInfo.properties} columns={popupColumns} />
          </Popup>
        )}
      </Map>

      {/* Legend for category colors */}
      {colorColumn && Object.keys(categoryColors).length > 0 && (
        <div className="pv-map-legend">
          {Object.entries(categoryColors).map(([cat, color]) => (
            <div key={cat} className="pv-map-legend-item">
              <span className="pv-map-legend-dot" style={{ backgroundColor: color }} />
              <span className="pv-map-legend-label">{cat}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


// ── Sub-components ──────────────────────────────────────────────────────────

function MapToolbar({
  mapStyle, setMapStyle,
  markerMode, setMarkerMode,
  clustering, setClustering,
  showRadius, setShowRadius,
}) {
  return (
    <div className="pv-map-toolbar">
      <select
        className="pv-map-toolbar-select"
        value={markerMode}
        onChange={e => setMarkerMode(e.target.value)}
        title="Visualization mode"
      >
        <option value="points">Points</option>
        <option value="bubble">Bubble</option>
        <option value="choropleth">Choropleth</option>
        <option value="heatmap">Heatmap</option>
      </select>

      {(markerMode === 'points' || markerMode === 'bubble') && (
        <label className="pv-map-toolbar-toggle" title="Cluster nearby markers">
          <input
            type="checkbox"
            checked={clustering}
            onChange={e => setClustering(e.target.checked)}
          />
          <span>Cluster</span>
        </label>
      )}

      <select
        className="pv-map-toolbar-select"
        value={mapStyle}
        onChange={e => setMapStyle(e.target.value)}
        title="Map style"
      >
        <option value="light">Light</option>
        <option value="streets">Streets</option>
        <option value="dark">Dark</option>
        <option value="satellite">Satellite</option>
      </select>

      <label className="pv-map-toolbar-toggle" title="Show radius overlay">
        <input
          type="checkbox"
          checked={showRadius}
          onChange={e => setShowRadius(e.target.checked)}
        />
        <span>Radius</span>
      </label>
    </div>
  )
}


function PopupContent({ properties, columns }) {
  if (!properties) return null
  const keys = columns.length > 0 ? columns : Object.keys(properties)
  return (
    <div className="pv-map-popup-content">
      {keys.map(key => {
        const val = properties[key]
        if (val === null || val === undefined) return null
        return (
          <div key={key} className="pv-map-popup-row">
            <span className="pv-map-popup-label">{key}:</span>
            <span className="pv-map-popup-value">{val}</span>
          </div>
        )
      })}
    </div>
  )
}


function ChoroplethLayers({ data, cfg }) {
  // This loads a static US states GeoJSON and joins metric data client-side.
  // For Phase 1, we use a simple approach: inject metric values into feature properties.
  const [boundaries, setBoundaries] = useState(null)

  useEffect(() => {
    // Lazy-load US state boundaries
    import('../../data/us-states.json')
      .then(mod => setBoundaries(mod.default || mod))
      .catch(() => {
        console.warn('MapWidget: us-states.json not found. Choropleth needs boundary data.')
      })
  }, [])

  const enrichedGeoJSON = useMemo(() => {
    if (!boundaries || !data?.choropleth_data) return null

    const joinCol = cfg.choropleth_join_column || ''
    const metricData = data.choropleth_data

    // Clone and inject metric values into feature properties
    const features = boundaries.features.map(f => {
      const regionKey = f.properties.STUSPS || f.properties.NAME || ''
      const metric = metricData[regionKey]
      return {
        ...f,
        properties: {
          ...f.properties,
          _metric: metric !== undefined ? metric : null,
        },
      }
    })

    return { ...boundaries, features }
  }, [boundaries, data?.choropleth_data, cfg.choropleth_join_column])

  if (!enrichedGeoJSON) return null

  // Build color steps from ranges
  const ranges = (data.choropleth_ranges || cfg.choropleth_ranges || '')
    .split(',').map(Number).filter(n => !isNaN(n) && n > 0)

  const colorScale = cfg.choropleth_color_scale === 'diverging'
    ? CHOROPLETH_DIVERGING : CHOROPLETH_SEQUENTIAL

  // Build step expression: ['step', ['get', '_metric'], color0, break1, color1, ...]
  let fillColor
  if (ranges.length > 0) {
    const expr = ['step', ['coalesce', ['get', '_metric'], 0]]
    const step = Math.floor(colorScale.length / (ranges.length + 1))
    expr.push(colorScale[0]) // default color for values below first range
    ranges.forEach((breakpoint, i) => {
      expr.push(breakpoint)
      expr.push(colorScale[Math.min((i + 1) * step, colorScale.length - 1)])
    })
    fillColor = expr
  } else {
    fillColor = '#94a3b8'
  }

  return (
    <Source id="choropleth-boundaries" type="geojson" data={enrichedGeoJSON}>
      <Layer
        id="choropleth-fill"
        type="fill"
        paint={{
          'fill-color': fillColor,
          'fill-opacity': 0.7,
        }}
      />
      <Layer
        id="choropleth-border"
        type="line"
        paint={{
          'line-color': '#ffffff',
          'line-width': 1,
        }}
      />
    </Source>
  )
}


function ChoroplethLegend({ data, cfg }) {
  const ranges = (data?.choropleth_ranges || cfg?.choropleth_ranges || '')
    .split(',').map(Number).filter(n => !isNaN(n) && n > 0)

  if (ranges.length === 0) return null

  const colorScale = cfg?.choropleth_color_scale === 'diverging'
    ? CHOROPLETH_DIVERGING : CHOROPLETH_SEQUENTIAL
  const step = Math.floor(colorScale.length / (ranges.length + 1))

  const items = [{ label: `< ${ranges[0]}`, color: colorScale[0] }]
  ranges.forEach((bp, i) => {
    const next = ranges[i + 1]
    const label = next ? `${bp} – ${next}` : `${bp}+`
    items.push({
      label,
      color: colorScale[Math.min((i + 1) * step, colorScale.length - 1)],
    })
  })

  return (
    <div className="pv-map-legend pv-map-legend--choropleth">
      {items.map((item, i) => (
        <div key={i} className="pv-map-legend-item">
          <span
            className="pv-map-legend-swatch"
            style={{ backgroundColor: item.color }}
          />
          <span className="pv-map-legend-label">{item.label}</span>
        </div>
      ))}
    </div>
  )
}
