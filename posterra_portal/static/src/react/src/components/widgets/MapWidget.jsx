import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

// ── Map style URLs (free CARTO basemaps) ────────────────────────────────────
const MAP_STYLES = {
  light:     { url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',      label: 'Light' },
  streets:   { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',       label: 'Streets' },
  dark:      { url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',   label: 'Dark' },
  satellite: { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',       label: 'Satellite' },
}

// ── Color palettes ──────────────────────────────────────────────────────────
const LEGEND_COLORS = [
  '#3b82f6', '#ef4444', '#22c55e', '#f97316', '#a855f7',
  '#06b6d4', '#eab308', '#ec4899', '#6366f1', '#84cc16',
]
const OTHERS_COLOR = '#94a3b8'

const CHOROPLETH_SEQ = ['#f7fbff','#deebf7','#c6dbef','#9ecae1','#6baed6','#4292c6','#2171b5','#08519c','#08306b']
const CHOROPLETH_DIV = ['#b2182b','#d6604d','#f4a582','#fddbc7','#f7f7f7','#d1e5f0','#92c5de','#4393c3','#2166ac']

// ── Helpers ─────────────────────────────────────────────────────────────────
function fmtNum(v) {
  if (v == null) return '—'
  const n = Number(v)
  if (isNaN(n)) return String(v)
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toLocaleString()
}

function createRadiusGeoJSON(center, miles) {
  const steps = 64, km = miles * 1.60934, ret = []
  const dx = km / (111.32 * Math.cos((center[1] * Math.PI) / 180))
  const dy = km / 110.574
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * 2 * Math.PI
    ret.push([center[0] + dx * Math.cos(t), center[1] + dy * Math.sin(t)])
  }
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ret] } }
}

function haversine(lat1, lng1, lat2, lng2) {
  const R = 3958.8 // Earth radius in miles
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLng = (lng2 - lng1) * Math.PI / 180
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLng/2)**2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
}

function getBoundsForFeatures(features) {
  let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity
  features.forEach(f => {
    const [lng, lat] = f.geometry.coordinates
    if (lng < minLng) minLng = lng
    if (lng > maxLng) maxLng = lng
    if (lat < minLat) minLat = lat
    if (lat > maxLat) maxLat = lat
  })
  return features.length > 0 ? [[minLng, minLat], [maxLng, maxLat]] : null
}


// ═══════════════════════════════════════════════════════════════════════════════
// MAIN MAP WIDGET
// ═══════════════════════════════════════════════════════════════════════════════
export default function MapWidget({ data, height, name }) {
  const mapRef = useRef(null)
  const cfg = data?.map_config || {}

  // ── Config from visual flags ───────────────────────────────────────────────
  const [mapStyle, setMapStyle] = useState(cfg.map_style || 'streets')
  const [clustering, setClustering] = useState(cfg.clustering !== false)
  const markerMode = cfg.marker_mode || 'points'
  const colorCol = cfg.color_column || ''
  const sizeCol = cfg.size_column || ''
  const metricCol = cfg.legend_metric_column || ''
  const showSearch = cfg.show_search !== false
  const showRadiusSel = cfg.show_radius_selector !== false
  const showStatusBar = cfg.show_status_bar !== false
  const radiusOpts = useMemo(() =>
    (cfg.radius_options || '10,25,50,100').split(',').map(Number).filter(n => !isNaN(n)),
  [cfg.radius_options])
  const searchCols = useMemo(() =>
    (cfg.search_columns || '').split(',').map(s => s.trim()).filter(Boolean),
  [cfg.search_columns])
  const popupCols = useMemo(() =>
    (cfg.popup_columns || '').split(',').map(s => s.trim()).filter(Boolean),
  [cfg.popup_columns])

  // ── State ──────────────────────────────────────────────────────────────────
  const [popupInfo, setPopupInfo] = useState(null)
  const [searchText, setSearchText] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [showDropdown, setShowDropdown] = useState(false)
  const [activeSearchFilter, setActiveSearchFilter] = useState(null) // {type, value, label}
  const [activeRadius, setActiveRadius] = useState(0) // 0 = off
  const [radiusCenter, setRadiusCenter] = useState(null) // [lng, lat]
  const [legendEntries, setLegendEntries] = useState([]) // [{name, color, visible}]
  const [legendAddSearch, setLegendAddSearch] = useState('')
  const [showLegendAdd, setShowLegendAdd] = useState(false)
  const [hiddenLegend, setHiddenLegend] = useState(new Set())

  // ── GeoJSON features ───────────────────────────────────────────────────────
  const geojson = data?.geojson || { type: 'FeatureCollection', features: [] }
  const allFeatures = geojson.features || []

  // ── Build category info from color_column ──────────────────────────────────
  const categories = useMemo(() => {
    if (!colorCol) return []
    const map = {}
    allFeatures.forEach(f => {
      const cat = f.properties[colorCol]
      if (!cat) return
      if (!map[cat]) map[cat] = { name: cat, count: 0, metric: 0 }
      map[cat].count += 1
      if (metricCol) map[cat].metric += Number(f.properties[metricCol]) || 0
    })
    return Object.values(map).sort((a, b) => b.count - a.count)
  }, [allFeatures, colorCol, metricCol])

  // Initialize legend entries from categories
  useEffect(() => {
    if (categories.length > 0 && legendEntries.length === 0) {
      setLegendEntries(categories.slice(0, 5).map((c, i) => ({
        name: c.name, color: LEGEND_COLORS[i % LEGEND_COLORS.length], visible: true,
      })))
    }
  }, [categories])

  // ── Filter features based on search + radius + legend ──────────────────────
  const visibleFeatures = useMemo(() => {
    let ff = allFeatures

    // Search filter
    if (activeSearchFilter) {
      const { type, value } = activeSearchFilter
      if (type === 'location') {
        ff = ff.filter(f => {
          // Match any property that contains the value
          return searchCols.some(col => {
            const v = f.properties[col]
            return v && String(v).toLowerCase() === value.toLowerCase()
          })
        })
      } else if (type === 'entity') {
        ff = ff.filter(f => {
          return searchCols.some(col => {
            const v = f.properties[col]
            return v && String(v).toLowerCase().includes(value.toLowerCase())
          })
        })
      }
    }

    // Radius filter
    if (activeRadius > 0 && radiusCenter) {
      ff = ff.filter(f => {
        const [lng, lat] = f.geometry.coordinates
        return haversine(radiusCenter[1], radiusCenter[0], lat, lng) <= activeRadius
      })
    }

    // Legend visibility
    if (legendEntries.length > 0 && colorCol && hiddenLegend.size > 0) {
      ff = ff.filter(f => !hiddenLegend.has(f.properties[colorCol]))
    }

    return ff
  }, [allFeatures, activeSearchFilter, activeRadius, radiusCenter, legendEntries, hiddenLegend, colorCol, searchCols])

  const filteredGeoJSON = useMemo(() => ({
    type: 'FeatureCollection', features: visibleFeatures,
  }), [visibleFeatures])

  // ── Fit bounds ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !data?.bounds) return
    const [w, s, e, n] = data.bounds
    mapRef.current.fitBounds([[w, s], [e, n]], { padding: 60, maxZoom: 12, duration: 800 })
  }, [data?.bounds])

  // Fit to filtered features when search/radius changes
  useEffect(() => {
    if (!mapRef.current || !activeSearchFilter) return
    const bounds = getBoundsForFeatures(visibleFeatures)
    if (bounds) mapRef.current.fitBounds(bounds, { padding: 60, maxZoom: 12, duration: 600 })
  }, [activeSearchFilter, visibleFeatures.length])

  // ── Search logic ───────────────────────────────────────────────────────────
  const doSearch = useCallback((text) => {
    setSearchText(text)
    if (text.length < 2) { setSearchResults([]); setShowDropdown(false); return }

    const lower = text.toLowerCase()
    const resultMap = {} // dedupe by value

    allFeatures.forEach(f => {
      searchCols.forEach(col => {
        const val = f.properties[col]
        if (!val) return
        const str = String(val)
        if (str.toLowerCase().includes(lower)) {
          const key = `${col}:${str}`
          if (!resultMap[key]) {
            resultMap[key] = {
              column: col,
              value: str,
              count: 0,
              type: ['hha_state', 'hha_county', 'hha_city', 'state', 'county', 'city'].includes(col)
                ? 'location' : 'entity',
            }
          }
          resultMap[key].count += 1
        }
      })
    })

    const results = Object.values(resultMap)
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)

    setSearchResults(results)
    setShowDropdown(results.length > 0)
  }, [allFeatures, searchCols])

  const selectSearchResult = useCallback((result) => {
    setActiveSearchFilter({ type: result.type, value: result.value, label: `${result.value} (${result.count})` })
    setSearchText(result.value)
    setShowDropdown(false)
    // Clear radius when searching
    setRadiusCenter(null)
  }, [])

  const clearSearch = useCallback(() => {
    setSearchText('')
    setActiveSearchFilter(null)
    setSearchResults([])
    setShowDropdown(false)
    setRadiusCenter(null)
    // Fit back to all data
    if (mapRef.current && data?.bounds) {
      const [w, s, e, n] = data.bounds
      mapRef.current.fitBounds([[w, s], [e, n]], { padding: 60, maxZoom: 12, duration: 600 })
    }
  }, [data?.bounds])

  // ── Map click handler ──────────────────────────────────────────────────────
  const onClick = useCallback((e) => {
    const f = e.features?.[0]

    // Cluster click → zoom in
    if (f?.properties?.cluster) {
      const src = mapRef.current?.getSource('map-points')
      src?.getClusterExpansionZoom?.(f.properties.cluster_id, (err, zoom) => {
        if (!err) mapRef.current.easeTo({ center: f.geometry.coordinates, zoom: Math.min(zoom, 15) })
      })
      return
    }

    // Single marker click
    if (f && !f.properties.cluster) {
      const coords = f.geometry.coordinates.slice()
      setPopupInfo({ coords, properties: f.properties })

      // If radius is active, set center to clicked marker
      if (activeRadius > 0) {
        setRadiusCenter(coords)
      }
      return
    }

    // Click on empty map with radius active → set radius center there
    if (activeRadius > 0) {
      setRadiusCenter([e.lngLat.lng, e.lngLat.lat])
      setPopupInfo(null)
    }
  }, [activeRadius])

  // ── Radius GeoJSON ─────────────────────────────────────────────────────────
  const radiusGeoJSON = useMemo(() => {
    if (activeRadius <= 0 || !radiusCenter) return null
    return createRadiusGeoJSON(radiusCenter, activeRadius)
  }, [activeRadius, radiusCenter])

  // ── Circle color expression ────────────────────────────────────────────────
  const circleColor = useMemo(() => {
    if (!colorCol || legendEntries.length === 0) return '#3b82f6'
    const expr = ['match', ['get', colorCol]]
    legendEntries.forEach(e => { expr.push(e.name, e.color) })
    expr.push(OTHERS_COLOR)
    return expr
  }, [colorCol, legendEntries])

  const circleRadius = useMemo(() => {
    if (markerMode !== 'bubble' || !sizeCol) return 7
    return ['interpolate', ['linear'], ['get', sizeCol], 0, 4, 100, 8, 1000, 14, 10000, 22, 100000, 32]
  }, [markerMode, sizeCol])

  // ── Legend toggle ──────────────────────────────────────────────────────────
  const toggleLegend = (name) => {
    setHiddenLegend(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }

  const removeLegend = (name) => {
    setLegendEntries(prev => prev.filter(e => e.name !== name))
    setHiddenLegend(prev => { const n = new Set(prev); n.delete(name); return n })
  }

  const addToLegend = (name) => {
    if (legendEntries.some(e => e.name === name)) return
    const color = LEGEND_COLORS[legendEntries.length % LEGEND_COLORS.length]
    setLegendEntries(prev => [...prev, { name, color, visible: true }])
    setShowLegendAdd(false)
    setLegendAddSearch('')
  }

  // Available categories not yet in legend (for "+" add flow)
  const addableCats = useMemo(() => {
    const inLegend = new Set(legendEntries.map(e => e.name))
    return categories
      .filter(c => !inLegend.has(c.name))
      .filter(c => !legendAddSearch || c.name.toLowerCase().includes(legendAddSearch.toLowerCase()))
  }, [categories, legendEntries, legendAddSearch])

  // Count visible features per legend entry
  const legendCounts = useMemo(() => {
    const counts = {}
    visibleFeatures.forEach(f => {
      const cat = f.properties[colorCol]
      if (cat) counts[cat] = (counts[cat] || 0) + 1
    })
    return counts
  }, [visibleFeatures, colorCol])

  // ── Choropleth mode ────────────────────────────────────────────────────────
  if (markerMode === 'choropleth' && data?.choropleth_data) {
    return (
      <div className="pv-map-widget" style={{ height: height || 500 }}>
        {showSearch && <MapSearchBar text={searchText} onChange={doSearch} results={searchResults}
          showDropdown={showDropdown} onSelect={selectSearchResult} onClear={clearSearch}
          activeFilter={activeSearchFilter} />}
        <div className="pv-map-canvas">
          <Map ref={mapRef}
            mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
            initialViewState={{ longitude: cfg.default_center_lng || -98.58, latitude: cfg.default_center_lat || 39.83, zoom: cfg.default_zoom || 3.5 }}
            style={{ width: '100%', height: '100%' }}
            interactiveLayerIds={['choropleth-fill']}
            onClick={(e) => {
              const f = e.features?.[0]
              if (f) setPopupInfo({
                coords: [e.lngLat.lng, e.lngLat.lat],
                properties: data.choropleth_popup_data?.[f.properties.STUSPS || f.properties.NAME] || f.properties,
              })
            }}>
            <NavigationControl position="top-right" />
            <ChoroplethLayers data={data} cfg={cfg} />
            {popupInfo && <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]}
              onClose={() => setPopupInfo(null)} closeOnClick={false} className="pv-map-popup" maxWidth="320px">
              <MapPopup properties={popupInfo.properties} columns={popupCols} />
            </Popup>}
          </Map>
          <MapStyleSwitcher active={mapStyle} onChange={setMapStyle} />
          <ChoroplethLegend data={data} cfg={cfg} />
        </div>
        {showStatusBar && <MapStatusBar total={Object.keys(data.choropleth_data).length}
          label="regions" filter={activeSearchFilter} radius={0} />}
      </div>
    )
  }

  // ── Point / Bubble / Heatmap mode ──────────────────────────────────────────
  return (
    <div className="pv-map-widget" style={{ height: height || 500 }}>
      {/* Search bar + radius selector */}
      {(showSearch || showRadiusSel) && (
        <div className="pv-map-topbar">
          {showSearch && <MapSearchBar text={searchText} onChange={doSearch} results={searchResults}
            showDropdown={showDropdown} onSelect={selectSearchResult} onClear={clearSearch}
            activeFilter={activeSearchFilter} />}
          {showRadiusSel && <RadiusSelector options={radiusOpts} active={activeRadius}
            onChange={(r) => { setActiveRadius(r); if (r === 0) setRadiusCenter(null) }} />}
        </div>
      )}

      {/* Map canvas */}
      <div className="pv-map-canvas">
        <Map ref={mapRef}
          mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
          initialViewState={{ longitude: cfg.default_center_lng || -98.58, latitude: cfg.default_center_lat || 39.83, zoom: cfg.default_zoom || 3.5 }}
          style={{ width: '100%', height: '100%' }}
          interactiveLayerIds={markerMode === 'heatmap' ? [] : ['point-markers', 'cluster-circles']}
          onClick={onClick}>

          <NavigationControl position="top-right" />

          <Source id="map-points" type="geojson" data={filteredGeoJSON}
            cluster={clustering && markerMode !== 'heatmap'} clusterMaxZoom={14} clusterRadius={50}>
            {markerMode === 'heatmap' ? (
              <Layer id="heatmap-layer" type="heatmap" paint={{
                'heatmap-weight': cfg.heatmap_weight_column ? ['interpolate',['linear'],['get',cfg.heatmap_weight_column],0,0,10000,1] : 1,
                'heatmap-intensity': ['interpolate',['linear'],['zoom'],0,1,12,3],
                'heatmap-radius': ['interpolate',['linear'],['zoom'],0,cfg.heatmap_radius||20,12,(cfg.heatmap_radius||20)*2],
                'heatmap-color': ['interpolate',['linear'],['heatmap-density'],0,'rgba(0,0,0,0)',0.2,'#4393c3',0.4,'#92c5de',0.6,'#fddbc7',0.8,'#f4a582',1,'#d6604d'],
                'heatmap-opacity': ['interpolate',['linear'],['zoom'],7,1,14,0],
              }} />
            ) : (
              <>
                <Layer id="cluster-circles" type="circle" filter={['has','point_count']} paint={{
                  'circle-color': ['step',['get','point_count'],'#51bbd6',10,'#f1f075',50,'#f28cb1'],
                  'circle-radius': ['step',['get','point_count'],18,10,24,50,32],
                  'circle-stroke-width': 2, 'circle-stroke-color': '#fff', 'circle-opacity': 0.9,
                }} />
                <Layer id="cluster-count" type="symbol" filter={['has','point_count']} layout={{
                  'text-field': '{point_count_abbreviated}', 'text-font': ['Open Sans Bold'], 'text-size': 12,
                }} />
                <Layer id="point-markers" type="circle" filter={['!',['has','point_count']]} paint={{
                  'circle-color': circleColor, 'circle-radius': circleRadius,
                  'circle-stroke-width': 2, 'circle-stroke-color': '#fff', 'circle-opacity': 0.9,
                }} />
              </>
            )}
          </Source>

          {/* Radius overlay */}
          {radiusGeoJSON && (
            <Source id="radius-overlay" type="geojson" data={radiusGeoJSON}>
              <Layer id="radius-fill" type="fill" paint={{ 'fill-color': '#3b82f6', 'fill-opacity': 0.08 }} />
              <Layer id="radius-border" type="line" paint={{ 'line-color': '#3b82f6', 'line-width': 2, 'line-dasharray': [3,2] }} />
            </Source>
          )}

          {/* Popup */}
          {popupInfo && <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]}
            onClose={() => setPopupInfo(null)} closeOnClick={false} className="pv-map-popup" maxWidth="320px">
            <MapPopup properties={popupInfo.properties} columns={popupCols}
              color={legendEntries.find(e => e.name === popupInfo.properties?.[colorCol])?.color} />
          </Popup>}
        </Map>

        <MapStyleSwitcher active={mapStyle} onChange={setMapStyle} />

        {/* Interactive Legend */}
        {colorCol && categories.length > 0 && (
          <MapLegend
            entries={legendEntries}
            hidden={hiddenLegend}
            counts={legendCounts}
            metricCol={metricCol}
            categories={categories}
            onToggle={toggleLegend}
            onRemove={removeLegend}
            onAdd={addToLegend}
            addableCats={addableCats}
            showAdd={showLegendAdd}
            setShowAdd={setShowLegendAdd}
            addSearch={legendAddSearch}
            setAddSearch={setLegendAddSearch}
            radiusActive={activeRadius > 0}
            radiusMiles={activeRadius}
            othersCount={visibleFeatures.filter(f => !legendEntries.some(e => e.name === f.properties[colorCol])).length}
          />
        )}
      </div>

      {/* Status bar */}
      {showStatusBar && <MapStatusBar
        total={visibleFeatures.length}
        allTotal={allFeatures.length}
        label="agencies"
        filter={activeSearchFilter}
        radius={activeRadius}
        radiusCount={activeRadius > 0 && radiusCenter ? visibleFeatures.length : 0}
      />}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// SEARCH BAR — single input with typeahead
// ═══════════════════════════════════════════════════════════════════════════════
function MapSearchBar({ text, onChange, results, showDropdown, onSelect, onClear, activeFilter }) {
  const inputRef = useRef(null)
  return (
    <div className="pv-map-search">
      <span className="pv-map-search-icon">🔍</span>
      <input ref={inputRef}
        type="text"
        className="pv-map-search-input"
        placeholder="Search city, county, state, or name..."
        value={text}
        onChange={e => onChange(e.target.value)}
        onFocus={() => { if (results.length) setShowDropdown?.(true) }}
      />
      {(text || activeFilter) && (
        <button className="pv-map-search-clear" onClick={onClear}>✕</button>
      )}
      {showDropdown && results.length > 0 && (
        <div className="pv-map-search-dropdown">
          {results.map((r, i) => (
            <div key={i} className="pv-map-search-result" onClick={() => onSelect(r)}>
              <span className="pv-map-search-result-icon">{r.type === 'location' ? '📍' : '🏢'}</span>
              <span className="pv-map-search-result-text">{r.value}</span>
              <span className="pv-map-search-result-meta">{r.count} {r.count === 1 ? 'match' : 'matches'} · {r.column.replace(/_/g, ' ')}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// RADIUS SELECTOR — pill buttons
// ═══════════════════════════════════════════════════════════════════════════════
function RadiusSelector({ options, active, onChange }) {
  return (
    <div className="pv-map-radius">
      <span className="pv-map-radius-label">Radius:</span>
      <button className={`pv-map-radius-btn ${active === 0 ? 'pv-map-radius-btn--active' : ''}`}
        onClick={() => onChange(0)}>Off</button>
      {options.map(r => (
        <button key={r}
          className={`pv-map-radius-btn ${active === r ? 'pv-map-radius-btn--active' : ''}`}
          onClick={() => onChange(r)}>{r} mi</button>
      ))}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// INTERACTIVE LEGEND — toggle, add, remove layers
// ═══════════════════════════════════════════════════════════════════════════════
function MapLegend({
  entries, hidden, counts, metricCol, categories,
  onToggle, onRemove, onAdd,
  addableCats, showAdd, setShowAdd, addSearch, setAddSearch,
  radiusActive, radiusMiles, othersCount,
}) {
  return (
    <div className="pv-map-legend">
      <div className="pv-map-legend-title">Legend</div>

      {entries.map(e => (
        <div key={e.name}
          className={`pv-map-legend-entry ${hidden.has(e.name) ? 'pv-map-legend-entry--hidden' : ''}`}
          onClick={() => onToggle(e.name)}>
          <span className="pv-map-legend-dot" style={{ backgroundColor: hidden.has(e.name) ? '#d1d5db' : e.color }} />
          <span className="pv-map-legend-name">{e.name}</span>
          <span className="pv-map-legend-count">{counts[e.name] || 0}</span>
          <button className="pv-map-legend-remove" onClick={ev => { ev.stopPropagation(); onRemove(e.name) }}>✕</button>
        </div>
      ))}

      {othersCount > 0 && (
        <div className="pv-map-legend-entry pv-map-legend-entry--others">
          <span className="pv-map-legend-dot" style={{ backgroundColor: OTHERS_COLOR }} />
          <span className="pv-map-legend-name">Others</span>
          <span className="pv-map-legend-count">{othersCount}</span>
        </div>
      )}

      {radiusActive && (
        <div className="pv-map-legend-entry pv-map-legend-entry--radius">
          <span className="pv-map-legend-dot pv-map-legend-dot--radius" />
          <span className="pv-map-legend-name">Search Radius ({radiusMiles} mi)</span>
        </div>
      )}

      {/* Add to legend */}
      {addableCats.length > 0 && (
        <div className="pv-map-legend-add">
          {showAdd ? (
            <div className="pv-map-legend-add-panel">
              <input
                type="text"
                className="pv-map-legend-add-input"
                placeholder="Search to add..."
                value={addSearch}
                onChange={e => setAddSearch(e.target.value)}
                autoFocus
              />
              <div className="pv-map-legend-add-list">
                {addableCats.slice(0, 8).map(c => (
                  <div key={c.name} className="pv-map-legend-add-item" onClick={() => onAdd(c.name)}>
                    <span>{c.name}</span>
                    <span className="pv-map-legend-add-count">{c.count}</span>
                  </div>
                ))}
              </div>
              <button className="pv-map-legend-add-close" onClick={() => { setShowAdd(false); setAddSearch('') }}>Cancel</button>
            </div>
          ) : (
            <button className="pv-map-legend-add-btn" onClick={() => setShowAdd(true)}>+ Add to legend</button>
          )}
        </div>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// MAP STYLE SWITCHER — pill buttons (bottom-left)
// ═══════════════════════════════════════════════════════════════════════════════
function MapStyleSwitcher({ active, onChange }) {
  return (
    <div className="pv-map-style-switcher">
      {Object.entries(MAP_STYLES).map(([k, { label }]) => (
        <button key={k}
          className={`pv-map-style-btn ${active === k ? 'pv-map-style-btn--active' : ''}`}
          onClick={() => onChange(k)}>{label}</button>
      ))}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// MAP POPUP — card layout
// ═══════════════════════════════════════════════════════════════════════════════
function MapPopup({ properties, columns, color }) {
  if (!properties) return null
  const keys = columns.length > 0 ? columns : Object.keys(properties)
  const titleKey = keys[0]
  const metricKeys = keys.slice(1)
  return (
    <div className="pv-map-popup-card">
      <div className="pv-map-popup-header">
        {color && <span className="pv-map-popup-dot" style={{ backgroundColor: color }} />}
        <span className="pv-map-popup-title">{properties[titleKey] || 'Unknown'}</span>
      </div>
      <div className="pv-map-popup-metrics">
        {metricKeys.map(k => {
          const v = properties[k]
          if (v == null) return null
          return (
            <div key={k} className="pv-map-popup-metric">
              <span className="pv-map-popup-metric-label">{k.replace(/_/g, ' ')}</span>
              <span className="pv-map-popup-metric-value">{fmtNum(v)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// STATUS BAR
// ═══════════════════════════════════════════════════════════════════════════════
function MapStatusBar({ total, allTotal, label, filter, radius, radiusCount }) {
  return (
    <div className="pv-map-status">
      <span>
        Showing <strong>{total.toLocaleString()}</strong>
        {allTotal && total < allTotal ? ` of ${allTotal.toLocaleString()}` : ''} {label}
      </span>
      {filter && <span className="pv-map-status-tag">📍 {filter.label}</span>}
      {radius > 0 && <span className="pv-map-status-tag">◎ {radius} mi radius</span>}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════════════════
// CHOROPLETH LAYERS + LEGEND (unchanged from Phase 1A)
// ═══════════════════════════════════════════════════════════════════════════════
function ChoroplethLayers({ data, cfg }) {
  const [boundaries, setBoundaries] = useState(null)
  useEffect(() => {
    import('../../data/us-states.json').then(m => setBoundaries(m.default || m)).catch(() => {})
  }, [])
  const enriched = useMemo(() => {
    if (!boundaries || !data?.choropleth_data) return null
    const md = data.choropleth_data
    return { ...boundaries, features: boundaries.features.map(f => ({
      ...f, properties: { ...f.properties, _metric: md[f.properties.STUSPS || f.properties.NAME] ?? null },
    }))}
  }, [boundaries, data?.choropleth_data])
  if (!enriched) return null
  const ranges = (data.choropleth_ranges || cfg.choropleth_ranges || '').split(',').map(Number).filter(n => !isNaN(n) && n > 0)
  const cs = cfg.choropleth_color_scale === 'diverging' ? CHOROPLETH_DIV : CHOROPLETH_SEQ
  let fillColor = OTHERS_COLOR
  if (ranges.length) {
    const expr = ['step', ['coalesce', ['get', '_metric'], 0], cs[0]]
    const step = Math.floor(cs.length / (ranges.length + 1))
    ranges.forEach((bp, i) => { expr.push(bp, cs[Math.min((i+1)*step, cs.length-1)]) })
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
  const ranges = (data?.choropleth_ranges || cfg?.choropleth_ranges || '').split(',').map(Number).filter(n => !isNaN(n) && n > 0)
  if (!ranges.length) return null
  const cs = cfg?.choropleth_color_scale === 'diverging' ? CHOROPLETH_DIV : CHOROPLETH_SEQ
  const step = Math.floor(cs.length / (ranges.length + 1))
  const items = [{ label: `< ${fmtNum(ranges[0])}`, color: cs[0] }]
  ranges.forEach((bp, i) => {
    const next = ranges[i+1]
    items.push({ label: next ? `${fmtNum(bp)} – ${fmtNum(next)}` : `${fmtNum(bp)}+`, color: cs[Math.min((i+1)*step, cs.length-1)] })
  })
  return (
    <div className="pv-map-legend pv-map-legend--choropleth">
      <div className="pv-map-legend-title">Legend</div>
      {items.map((it, i) => (
        <div key={i} className="pv-map-legend-entry">
          <span className="pv-map-legend-swatch" style={{ backgroundColor: it.color }} />
          <span className="pv-map-legend-name">{it.label}</span>
        </div>
      ))}
    </div>
  )
}
