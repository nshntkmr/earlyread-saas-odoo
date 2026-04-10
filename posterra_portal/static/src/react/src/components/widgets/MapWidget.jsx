import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

// ── Map style URLs (free, no API key for light/streets/dark) ────────────────
const MAP_STYLES = {
  light:     { url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json', label: 'Light' },
  streets:   { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json', label: 'Streets' },
  dark:      { url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', label: 'Dark' },
  satellite: { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json', label: 'Satellite' },
}

// ── Color palettes ──────────────────────────────────────────────────────────
const LAYER_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f97316', '#a855f7',
  '#06b6d4', '#eab308', '#ec4899', '#6366f1', '#84cc16',
  '#14b8a6', '#f43f5e', '#8b5cf6', '#0ea5e9', '#d946ef',
]

const CHOROPLETH_SEQUENTIAL = [
  '#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6',
  '#4292c6', '#2171b5', '#08519c', '#08306b',
]

const CHOROPLETH_DIVERGING = [
  '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7',
  '#d1e5f0', '#92c5de', '#4393c3', '#2166ac',
]

// ── Radius helper ───────────────────────────────────────────────────────────
function createRadiusGeoJSON(center, radiusMiles) {
  const steps = 64
  const km = radiusMiles * 1.60934
  const ret = []
  const distX = km / (111.32 * Math.cos((center[1] * Math.PI) / 180))
  const distY = km / 110.574
  for (let i = 0; i < steps; i++) {
    const t = (i / steps) * (2 * Math.PI)
    ret.push([center[0] + distX * Math.cos(t), center[1] + distY * Math.sin(t)])
  }
  ret.push(ret[0])
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ret] } }
}

// ── Format numbers ──────────────────────────────────────────────────────────
function fmtNum(v) {
  if (v == null) return '—'
  const n = Number(v)
  if (isNaN(n)) return String(v)
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toLocaleString()
}


// ═══════════════════════════════════════════════════════════════════════════════
// MAIN MAP WIDGET
// ═══════════════════════════════════════════════════════════════════════════════
export default function MapWidget({ data, height, name }) {
  const mapRef = useRef(null)
  const cfg = data?.map_config || {}

  // ── State ──────────────────────────────────────────────────────────────────
  const [mapStyle, setMapStyle] = useState(cfg.map_style || 'streets')
  const [markerMode, setMarkerMode] = useState(cfg.marker_mode || 'points')
  const [clustering, setClustering] = useState(cfg.clustering !== false)
  const [popupInfo, setPopupInfo] = useState(null)
  const [radiusMiles, setRadiusMiles] = useState(cfg.radius_miles || 25)

  // Layer panel state
  const layerCol = cfg.layer_column || cfg.brand_column || cfg.color_column || ''
  const [activeLayers, setActiveLayers] = useState(new Set())
  const [layerFilter, setLayerFilter] = useState('')
  const [layerSearch, setLayerSearch] = useState('')

  const showLayerPanel = cfg.show_layer_panel !== false && !!layerCol
  const show3D = cfg.show_3d_globe !== false
  const pitch = show3D ? (cfg.default_pitch || 45) : 0

  const popupCols = useMemo(() =>
    (cfg.popup_columns || '').split(',').map(s => s.trim()).filter(Boolean),
  [cfg.popup_columns])

  const summaryColNames = useMemo(() =>
    (cfg.layer_summary_columns || '').split(',').map(s => s.trim()).filter(Boolean),
  [cfg.layer_summary_columns])

  const filterCol = cfg.layer_filter_column || ''

  // ── GeoJSON & layer data ───────────────────────────────────────────────────
  const geojson = data?.geojson || { type: 'FeatureCollection', features: [] }
  const features = geojson.features || []

  // Build layer info: group features by layerCol
  const layerInfo = useMemo(() => {
    if (!layerCol) return []
    const map = {}
    features.forEach(f => {
      const key = f.properties[layerCol]
      if (!key) return
      if (!map[key]) map[key] = { name: key, count: 0, metrics: {} }
      map[key].count += 1
      // Aggregate summary columns
      summaryColNames.forEach(col => {
        const val = Number(f.properties[col])
        if (!isNaN(val)) map[key].metrics[col] = (map[key].metrics[col] || 0) + val
      })
    })
    return Object.values(map).sort((a, b) => b.count - a.count)
  }, [features, layerCol, summaryColNames])

  // Assign colors to layers
  const layerColors = useMemo(() => {
    const m = {}
    layerInfo.forEach((l, i) => { m[l.name] = LAYER_COLORS[i % LAYER_COLORS.length] })
    return m
  }, [layerInfo])

  // Distinct values for filter dropdown
  const filterValues = useMemo(() => {
    if (!filterCol) return []
    const set = new Set()
    features.forEach(f => { const v = f.properties[filterCol]; if (v) set.add(v) })
    return [...set].sort()
  }, [features, filterCol])

  // Filtered GeoJSON for the map
  const filteredGeoJSON = useMemo(() => {
    let ff = features
    if (activeLayers.size > 0) {
      ff = ff.filter(f => activeLayers.has(f.properties[layerCol]))
    }
    if (layerFilter) {
      ff = ff.filter(f => f.properties[filterCol] === layerFilter)
    }
    return { type: 'FeatureCollection', features: ff }
  }, [features, activeLayers, layerCol, layerFilter, filterCol])

  // ── Fit bounds ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !data?.bounds) return
    const [w, s, e, n] = data.bounds
    mapRef.current.fitBounds([[w, s], [e, n]], { padding: 60, maxZoom: 12, duration: 800 })
  }, [data?.bounds])

  // ── Click handler ──────────────────────────────────────────────────────────
  const onClick = useCallback((e) => {
    const f = e.features?.[0]
    if (!f) return
    if (f.properties.cluster) {
      const src = mapRef.current?.getSource('map-points')
      src?.getClusterExpansionZoom?.(f.properties.cluster_id, (err, zoom) => {
        if (!err) mapRef.current.easeTo({ center: f.geometry.coordinates, zoom: Math.min(zoom, 15) })
      })
      return
    }
    setPopupInfo({ coords: f.geometry.coordinates.slice(), properties: f.properties })
  }, [])

  // ── Radius GeoJSON ─────────────────────────────────────────────────────────
  const radiusGeoJSON = useMemo(() => {
    if (!popupInfo) return null
    return createRadiusGeoJSON(popupInfo.coords, radiusMiles)
  }, [popupInfo, radiusMiles])

  // ── Circle color expression ────────────────────────────────────────────────
  const circleColor = useMemo(() => {
    if (!layerCol || Object.keys(layerColors).length === 0) return '#3b82f6'
    const expr = ['match', ['get', layerCol]]
    Object.entries(layerColors).forEach(([k, c]) => { expr.push(k, c) })
    expr.push('#94a3b8')
    return expr
  }, [layerCol, layerColors])

  const circleRadius = useMemo(() => {
    const sizeCol = cfg.size_column || ''
    if (markerMode !== 'bubble' || !sizeCol) return 7
    return ['interpolate', ['linear'], ['get', sizeCol], 0, 4, 100, 8, 1000, 14, 10000, 22, 100000, 32]
  }, [markerMode, cfg.size_column])

  // ── Choropleth mode ────────────────────────────────────────────────────────
  if (markerMode === 'choropleth' && data?.choropleth_data) {
    return (
      <div className="pv-map-container" style={{ height: height || 500 }}>
        <div className="pv-map-canvas">
          <Map
            ref={mapRef}
            mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
            projection={show3D ? 'globe' : 'mercator'}
            initialViewState={{
              longitude: cfg.default_center_lng || -98.58,
              latitude: cfg.default_center_lat || 39.83,
              zoom: cfg.default_zoom || 3.5,
              pitch, bearing: -10,
            }}
            style={{ width: '100%', height: '100%' }}
            interactiveLayerIds={['choropleth-fill']}
            onClick={(e) => {
              const f = e.features?.[0]
              if (f) setPopupInfo({
                coords: [e.lngLat.lng, e.lngLat.lat],
                properties: data.choropleth_popup_data?.[f.properties.STUSPS || f.properties.NAME] || f.properties,
              })
            }}
          >
            <NavigationControl position="top-right" />
            <ChoroplethLayers data={data} cfg={cfg} />
            {popupInfo && (
              <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]}
                onClose={() => setPopupInfo(null)} closeOnClick={false} className="pv-map-popup">
                <MapPopup properties={popupInfo.properties} columns={popupCols} />
              </Popup>
            )}
          </Map>
          <MapStyleSwitcher active={mapStyle} onChange={setMapStyle} />
          <ChoroplethLegend data={data} cfg={cfg} />
        </div>
      </div>
    )
  }

  // ── Point / Bubble / Heatmap mode ──────────────────────────────────────────
  return (
    <div className="pv-map-container" style={{ height: height || 500 }}>
      {showLayerPanel && (
        <LayerPanel
          layers={layerInfo}
          colors={layerColors}
          activeLayers={activeLayers}
          setActiveLayers={setActiveLayers}
          filterValues={filterValues}
          layerFilter={layerFilter}
          setLayerFilter={setLayerFilter}
          search={layerSearch}
          setSearch={setLayerSearch}
          summaryColNames={summaryColNames}
          label={cfg.layer_label || 'Layers'}
        />
      )}
      <div className="pv-map-canvas">
        <Map
          ref={mapRef}
          mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
          projection={show3D ? 'globe' : 'mercator'}
          initialViewState={{
            longitude: cfg.default_center_lng || -98.58,
            latitude: cfg.default_center_lat || 39.83,
            zoom: cfg.default_zoom || 3.5,
            pitch, bearing: -10,
          }}
          style={{ width: '100%', height: '100%' }}
          interactiveLayerIds={markerMode === 'heatmap' ? [] : ['point-markers', 'cluster-circles']}
          onClick={onClick}
        >
          <NavigationControl position="top-right" />

          <Source
            id="map-points"
            type="geojson"
            data={filteredGeoJSON}
            cluster={clustering && markerMode !== 'heatmap'}
            clusterMaxZoom={14}
            clusterRadius={50}
          >
            {markerMode === 'heatmap' ? (
              <Layer id="heatmap-layer" type="heatmap" paint={{
                'heatmap-weight': cfg.heatmap_weight_column
                  ? ['interpolate', ['linear'], ['get', cfg.heatmap_weight_column], 0, 0, 10000, 1] : 1,
                'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 1, 12, 3],
                'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, cfg.heatmap_radius || 20, 12, (cfg.heatmap_radius || 20) * 2],
                'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'],
                  0, 'rgba(0,0,0,0)', 0.2, '#4393c3', 0.4, '#92c5de', 0.6, '#fddbc7', 0.8, '#f4a582', 1, '#d6604d'],
                'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], 7, 1, 14, 0],
              }} />
            ) : (
              <>
                {/* Cluster circles */}
                <Layer id="cluster-circles" type="circle" filter={['has', 'point_count']} paint={{
                  'circle-color': ['step', ['get', 'point_count'], '#51bbd6', 10, '#f1f075', 50, '#f28cb1'],
                  'circle-radius': ['step', ['get', 'point_count'], 18, 10, 24, 50, 32],
                  'circle-stroke-width': 2, 'circle-stroke-color': '#fff',
                  'circle-opacity': 0.9,
                }} />
                <Layer id="cluster-count" type="symbol" filter={['has', 'point_count']} layout={{
                  'text-field': '{point_count_abbreviated}', 'text-font': ['Open Sans Bold'], 'text-size': 12,
                }} />
                {/* Individual markers */}
                <Layer id="point-markers" type="circle" filter={['!', ['has', 'point_count']]} paint={{
                  'circle-color': circleColor,
                  'circle-radius': circleRadius,
                  'circle-stroke-width': 2, 'circle-stroke-color': '#fff',
                  'circle-opacity': 0.9,
                }} />
              </>
            )}
          </Source>

          {/* Radius overlay */}
          {radiusGeoJSON && (
            <Source id="radius-overlay" type="geojson" data={radiusGeoJSON}>
              <Layer id="radius-fill" type="fill" paint={{ 'fill-color': '#3b82f6', 'fill-opacity': 0.08 }} />
              <Layer id="radius-border" type="line" paint={{
                'line-color': '#3b82f6', 'line-width': 2, 'line-dasharray': [3, 2],
              }} />
            </Source>
          )}

          {/* Popup */}
          {popupInfo && (
            <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]}
              onClose={() => setPopupInfo(null)} closeOnClick={false} className="pv-map-popup" maxWidth="320px">
              <MapPopup properties={popupInfo.properties} columns={popupCols} layerCol={layerCol}
                color={layerColors[popupInfo.properties?.[layerCol]]} />
            </Popup>
          )}
        </Map>

        {/* Controls overlay */}
        <MapStyleSwitcher active={mapStyle} onChange={setMapStyle} />

        {/* Legend */}
        {layerCol && Object.keys(layerColors).length > 0 && (
          <div className="pv-map-legend">
            <div className="pv-map-legend-title">Legend</div>
            {Object.entries(layerColors).map(([name, color]) => (
              <div key={name} className="pv-map-legend-item">
                <span className="pv-map-legend-dot" style={{ backgroundColor: color }} />
                <span className="pv-map-legend-label">{name}</span>
              </div>
            ))}
            {popupInfo && (
              <div className="pv-map-legend-item">
                <span className="pv-map-legend-dot pv-map-legend-dot--radius" />
                <span className="pv-map-legend-label">Search Radius</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// LAYER PANEL SIDEBAR (Generic — works for any entity)
// ═══════════════════════════════════════════════════════════════════════════════
function LayerPanel({
  layers, colors, activeLayers, setActiveLayers,
  filterValues, layerFilter, setLayerFilter,
  search, setSearch, summaryColNames, label,
}) {
  const filtered = layers.filter(l =>
    (!search || l.name.toLowerCase().includes(search.toLowerCase()))
  )

  const toggleLayer = (name) => {
    setActiveLayers(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const removeLayer = (name) => {
    setActiveLayers(prev => {
      const next = new Set(prev)
      next.delete(name)
      return next
    })
  }

  return (
    <div className="pv-map-sidebar">
      {/* Header */}
      <div className="pv-map-sidebar-header">
        <span className="pv-map-sidebar-title">
          🏷 {label} <span className="pv-map-sidebar-badge">{layers.length}</span>
        </span>
      </div>

      {/* Filter dropdown */}
      {filterValues.length > 0 && (
        <div className="pv-map-sidebar-filter">
          <select value={layerFilter} onChange={e => setLayerFilter(e.target.value)}
            className="pv-map-sidebar-select">
            <option value="">All Regions</option>
            {filterValues.map(v => <option key={v} value={v}>{v}</option>)}
          </select>
        </div>
      )}

      {/* Search */}
      <div className="pv-map-sidebar-search">
        <span className="pv-map-sidebar-search-icon">🔍</span>
        <input
          type="text"
          placeholder={`Search ${label.toLowerCase()}...`}
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="pv-map-sidebar-input"
        />
        {search && (
          <button className="pv-map-sidebar-clear" onClick={() => setSearch('')}>×</button>
        )}
      </div>

      {/* Layer cards */}
      <div className="pv-map-sidebar-list">
        {filtered.length === 0 && (
          <div className="pv-map-sidebar-empty">
            {search ? `No matches for "${search}"` : 'Type 3+ characters to search'}
          </div>
        )}
        {filtered.map(layer => {
          const isActive = activeLayers.size === 0 || activeLayers.has(layer.name)
          return (
            <div
              key={layer.name}
              className={`pv-map-layer-card ${isActive ? '' : 'pv-map-layer-card--dimmed'}`}
              onClick={() => toggleLayer(layer.name)}
            >
              <div className="pv-map-layer-card-header">
                <span className="pv-map-layer-dot" style={{ backgroundColor: colors[layer.name] }} />
                <span className="pv-map-layer-name">{layer.name}</span>
                {activeLayers.has(layer.name) && (
                  <button className="pv-map-layer-remove" onClick={e => { e.stopPropagation(); removeLayer(layer.name) }}>×</button>
                )}
              </div>
              <div className="pv-map-layer-meta">
                <span>{layer.count} locations</span>
                {summaryColNames.slice(0, 2).map(col => (
                  <span key={col}> · {fmtNum(layer.metrics[col])}</span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// MAP STYLE SWITCHER (pill buttons, bottom-left)
// ═══════════════════════════════════════════════════════════════════════════════
function MapStyleSwitcher({ active, onChange }) {
  return (
    <div className="pv-map-style-switcher">
      {Object.entries(MAP_STYLES).map(([key, { label }]) => (
        <button
          key={key}
          className={`pv-map-style-btn ${active === key ? 'pv-map-style-btn--active' : ''}`}
          onClick={() => onChange(key)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// MAP POPUP (redesigned with card layout)
// ═══════════════════════════════════════════════════════════════════════════════
function MapPopup({ properties, columns, layerCol, color }) {
  if (!properties) return null

  // First column as title, rest as metrics
  const keys = columns.length > 0 ? columns : Object.keys(properties)
  const titleKey = keys[0]
  const metricKeys = keys.slice(1)

  return (
    <div className="pv-map-popup-card">
      <div className="pv-map-popup-header">
        {color && <span className="pv-map-popup-dot" style={{ backgroundColor: color }} />}
        <span className="pv-map-popup-title">{properties[titleKey] || 'Unknown'}</span>
      </div>
      {layerCol && properties[layerCol] && titleKey !== layerCol && (
        <div className="pv-map-popup-subtitle">{properties[layerCol]}</div>
      )}
      <div className="pv-map-popup-metrics">
        {metricKeys.map(key => {
          const val = properties[key]
          if (val == null) return null
          return (
            <div key={key} className="pv-map-popup-metric">
              <span className="pv-map-popup-metric-label">{key.replace(/_/g, ' ')}</span>
              <span className="pv-map-popup-metric-value">{fmtNum(val)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// CHOROPLETH LAYERS + LEGEND
// ═══════════════════════════════════════════════════════════════════════════════
function ChoroplethLayers({ data, cfg }) {
  const [boundaries, setBoundaries] = useState(null)
  useEffect(() => {
    import('../../data/us-states.json')
      .then(mod => setBoundaries(mod.default || mod))
      .catch(() => console.warn('MapWidget: us-states.json not found.'))
  }, [])

  const enriched = useMemo(() => {
    if (!boundaries || !data?.choropleth_data) return null
    const md = data.choropleth_data
    return {
      ...boundaries,
      features: boundaries.features.map(f => ({
        ...f,
        properties: { ...f.properties, _metric: md[f.properties.STUSPS || f.properties.NAME] ?? null },
      })),
    }
  }, [boundaries, data?.choropleth_data])

  if (!enriched) return null

  const ranges = (data.choropleth_ranges || cfg.choropleth_ranges || '')
    .split(',').map(Number).filter(n => !isNaN(n) && n > 0)
  const cs = cfg.choropleth_color_scale === 'diverging' ? CHOROPLETH_DIVERGING : CHOROPLETH_SEQUENTIAL

  let fillColor = '#94a3b8'
  if (ranges.length > 0) {
    const expr = ['step', ['coalesce', ['get', '_metric'], 0], cs[0]]
    const step = Math.floor(cs.length / (ranges.length + 1))
    ranges.forEach((bp, i) => {
      expr.push(bp, cs[Math.min((i + 1) * step, cs.length - 1)])
    })
    fillColor = expr
  }

  return (
    <Source id="choropleth-boundaries" type="geojson" data={enriched}>
      <Layer id="choropleth-fill" type="fill" paint={{ 'fill-color': fillColor, 'fill-opacity': 0.7 }} />
      <Layer id="choropleth-border" type="line" paint={{ 'line-color': '#fff', 'line-width': 1 }} />
    </Source>
  )
}

function ChoroplethLegend({ data, cfg }) {
  const ranges = (data?.choropleth_ranges || cfg?.choropleth_ranges || '')
    .split(',').map(Number).filter(n => !isNaN(n) && n > 0)
  if (!ranges.length) return null
  const cs = cfg?.choropleth_color_scale === 'diverging' ? CHOROPLETH_DIVERGING : CHOROPLETH_SEQUENTIAL
  const step = Math.floor(cs.length / (ranges.length + 1))
  const items = [{ label: `< ${fmtNum(ranges[0])}`, color: cs[0] }]
  ranges.forEach((bp, i) => {
    const next = ranges[i + 1]
    items.push({ label: next ? `${fmtNum(bp)} – ${fmtNum(next)}` : `${fmtNum(bp)}+`, color: cs[Math.min((i + 1) * step, cs.length - 1)] })
  })
  return (
    <div className="pv-map-legend pv-map-legend--choropleth">
      <div className="pv-map-legend-title">Legend</div>
      {items.map((it, i) => (
        <div key={i} className="pv-map-legend-item">
          <span className="pv-map-legend-swatch" style={{ backgroundColor: it.color }} />
          <span className="pv-map-legend-label">{it.label}</span>
        </div>
      ))}
    </div>
  )
}
