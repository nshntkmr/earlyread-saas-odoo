import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'

// ── Basemap styles (free CARTO) ─────────────────────────────────────────────
const MAP_STYLES = {
  light:     { url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',    label: 'Light',     icon: '☀' },
  streets:   { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',     label: 'Streets',   icon: '🗺' },
  satellite: { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',     label: 'Satellite', icon: '🛰' },
  dark:      { url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', label: 'Dark',      icon: '🌙' },
}

const BRAND_COLORS = [
  '#3b82f6','#ef4444','#22c55e','#f97316','#a855f7',
  '#06b6d4','#eab308','#ec4899','#6366f1','#84cc16',
]
const OTHERS_COLOR = '#94a3b8'

const CHOROPLETH_SEQ = ['#f7fbff','#deebf7','#c6dbef','#9ecae1','#6baed6','#4292c6','#2171b5','#08519c','#08306b']
const CHOROPLETH_DIV = ['#b2182b','#d6604d','#f4a582','#fddbc7','#f7f7f7','#d1e5f0','#92c5de','#4393c3','#2166ac']

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = v => {
  if (v == null) return '—'
  const n = Number(v); if (isNaN(n)) return String(v)
  if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(1)+'M'
  if (Math.abs(n) >= 1e3) return (n/1e3).toFixed(1)+'K'
  return n.toLocaleString()
}

const haversine = (lat1,lng1,lat2,lng2) => {
  const R=3958.8, dLat=(lat2-lat1)*Math.PI/180, dLng=(lng2-lng1)*Math.PI/180
  const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2
  return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a))
}

const makeCircle = (c, miles) => {
  const s=64, km=miles*1.60934, r=[]
  const dx=km/(111.32*Math.cos(c[1]*Math.PI/180)), dy=km/110.574
  for(let i=0;i<=s;i++){const t=i/s*2*Math.PI;r.push([c[0]+dx*Math.cos(t),c[1]+dy*Math.sin(t)])}
  return {type:'Feature',geometry:{type:'Polygon',coordinates:[r]}}
}

const fitFeatures = (map, ff, opts={}) => {
  if(!ff.length||!map) return
  let mnX=Infinity,mnY=Infinity,mxX=-Infinity,mxY=-Infinity
  ff.forEach(f=>{const[x,y]=f.geometry.coordinates;if(x<mnX)mnX=x;if(x>mxX)mxX=x;if(y<mnY)mnY=y;if(y>mxY)mxY=y})
  map.fitBounds([[mnX,mnY],[mxX,mxY]],{padding:60,maxZoom:12,duration:600,...opts})
}

const csvToArr = s => (s||'').split(',').map(x=>x.trim()).filter(Boolean)


// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═════════════════════════════════════════════════════════════════════════════
export default function MapWidget({ data, height, name }) {
  const mapRef = useRef(null)
  const cfg = data?.map_config || {}

  // Config
  const [mapStyle, setMapStyle] = useState(cfg.map_style || 'streets')
  const clustering = cfg.clustering !== false
  const markerMode = cfg.marker_mode || 'points'
  const colorCol = cfg.color_column || ''
  const sizeCol = cfg.size_column || ''
  const popupCols = useMemo(() => csvToArr(cfg.popup_columns), [cfg.popup_columns])
  const searchCols = useMemo(() => csvToArr(cfg.search_columns), [cfg.search_columns])
  const summaryCols = useMemo(() => csvToArr(cfg.brand_summary_columns), [cfg.brand_summary_columns])
  const catCol = cfg.brand_category_column || ''
  const radiusMin = cfg.radius_min || 5
  const radiusMax = cfg.radius_max || 200
  const radiusDef = cfg.radius_default || 25

  // State: panels
  const [showBrandPanel, setShowBrandPanel] = useState(true)
  const [showRadiusPanel, setShowRadiusPanel] = useState(false)

  // State: brands
  const [brandEntries, setBrandEntries] = useState([]) // [{name, color, visible}]
  const [brandSearch, setBrandSearch] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [hiddenBrands, setHiddenBrands] = useState(new Set())

  // State: radius
  const [radiusDist, setRadiusDist] = useState(radiusDef)
  const [radiusCenter, setRadiusCenter] = useState(null) // [lng, lat]
  const [placementMode, setPlacementMode] = useState(false)

  // State: popup
  const [popupInfo, setPopupInfo] = useState(null)

  // ── Data ────────────────────────────────────────────────────────────────
  const geojson = data?.geojson || { type: 'FeatureCollection', features: [] }
  const allFeatures = geojson.features || []

  // All searchable columns (fallback to all string props if search_columns not set)
  const effectiveSearchCols = useMemo(() => {
    if (searchCols.length > 0) return searchCols
    if (!allFeatures.length) return []
    const sample = allFeatures[0].properties
    return Object.keys(sample).filter(k => typeof sample[k] === 'string' || !isNaN(Number(sample[k])))
  }, [searchCols, allFeatures])

  // All unique brands from color_column
  const allBrands = useMemo(() => {
    if (!colorCol) return []
    const m = {}
    allFeatures.forEach(f => {
      const b = f.properties[colorCol]; if (!b) return
      if (!m[b]) m[b] = { name: b, count: 0, metrics: {}, category: '' }
      m[b].count++
      if (catCol && f.properties[catCol]) m[b].category = f.properties[catCol]
      summaryCols.forEach(c => { m[b].metrics[c] = (m[b].metrics[c]||0) + (Number(f.properties[c])||0) })
    })
    return Object.values(m).sort((a,b) => b.count - a.count)
  }, [allFeatures, colorCol, catCol, summaryCols])

  // All unique states for filter dropdown
  const allStates = useMemo(() => {
    const s = new Set()
    allFeatures.forEach(f => {
      const v = f.properties.hha_state || f.properties.state; if (v) s.add(v)
    })
    return [...s].sort()
  }, [allFeatures])

  // ── Filtered features ──────────────────────────────────────────────────
  const visibleFeatures = useMemo(() => {
    let ff = allFeatures

    // State filter
    if (stateFilter) {
      ff = ff.filter(f => (f.properties.hha_state || f.properties.state) === stateFilter)
    }

    // Brand visibility
    if (hiddenBrands.size > 0 && colorCol) {
      ff = ff.filter(f => !hiddenBrands.has(f.properties[colorCol]))
    }

    // Only show brands in brandEntries (if any are added)
    if (brandEntries.length > 0 && colorCol) {
      const activeNames = new Set(brandEntries.map(e => e.name))
      ff = ff.filter(f => activeNames.has(f.properties[colorCol]))
    }

    return ff
  }, [allFeatures, stateFilter, hiddenBrands, brandEntries, colorCol])

  const filteredGeoJSON = useMemo(() => ({
    type: 'FeatureCollection', features: visibleFeatures,
  }), [visibleFeatures])

  // Features within radius
  const featuresInRadius = useMemo(() => {
    if (!radiusCenter || radiusDist <= 0) return []
    return visibleFeatures.filter(f => {
      const [lng,lat] = f.geometry.coordinates
      return haversine(radiusCenter[1], radiusCenter[0], lat, lng) <= radiusDist
    })
  }, [visibleFeatures, radiusCenter, radiusDist])

  // Brands in radius
  const brandsInRadius = useMemo(() => {
    if (!colorCol || !featuresInRadius.length) return []
    const m = {}
    featuresInRadius.forEach(f => {
      const b = f.properties[colorCol]; if (!b) return
      m[b] = (m[b]||0) + 1
    })
    return Object.entries(m).sort((a,b) => b[1]-a[1])
  }, [featuresInRadius, colorCol])

  // ── Brand panel search results ─────────────────────────────────────────
  const brandSearchResults = useMemo(() => {
    if (!brandSearch || brandSearch.length < 1) return []
    const lower = brandSearch.toLowerCase()
    const inPanel = new Set(brandEntries.map(e => e.name))
    return allBrands
      .filter(b => !inPanel.has(b.name) && b.name.toLowerCase().includes(lower))
      .slice(0, 8)
  }, [brandSearch, allBrands, brandEntries])

  // ── Fit bounds on load ─────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !data?.bounds) return
    const [w,s,e,n] = data.bounds
    mapRef.current.fitBounds([[w,s],[e,n]], { padding:60, maxZoom:12, duration:800 })
  }, [data?.bounds])

  // ── Map click ──────────────────────────────────────────────────────────
  const onClick = useCallback((e) => {
    // Placement mode: set radius center
    if (placementMode) {
      setRadiusCenter([e.lngLat.lng, e.lngLat.lat])
      setPlacementMode(false)
      return
    }

    const f = e.features?.[0]
    if (f?.properties?.cluster) {
      const src = mapRef.current?.getSource('map-points')
      src?.getClusterExpansionZoom?.(f.properties.cluster_id, (err, zoom) => {
        if (!err) mapRef.current.easeTo({ center: f.geometry.coordinates, zoom: Math.min(zoom, 15) })
      })
      return
    }
    if (f && !f.properties.cluster) {
      setPopupInfo({ coords: f.geometry.coordinates.slice(), properties: f.properties })
      return
    }
    setPopupInfo(null)
  }, [placementMode])

  // ── Radius GeoJSON ─────────────────────────────────────────────────────
  const radiusGeoJSON = useMemo(() => {
    if (!radiusCenter) return null
    return makeCircle(radiusCenter, radiusDist)
  }, [radiusCenter, radiusDist])

  // ── Circle paint expressions ───────────────────────────────────────────
  const circleColor = useMemo(() => {
    if (!colorCol || brandEntries.length === 0) return '#3b82f6'
    const expr = ['match', ['get', colorCol]]
    brandEntries.forEach(e => { expr.push(e.name, e.color) })
    expr.push(OTHERS_COLOR)
    return expr
  }, [colorCol, brandEntries])

  const circleRadius = useMemo(() => {
    if (markerMode !== 'bubble' || !sizeCol) return 7
    return ['interpolate',['linear'],['get',sizeCol],0,4,100,8,1000,14,10000,22,100000,32]
  }, [markerMode, sizeCol])

  // ── Brand panel actions ────────────────────────────────────────────────
  const addBrand = (name) => {
    if (brandEntries.some(e => e.name === name)) return
    const color = BRAND_COLORS[brandEntries.length % BRAND_COLORS.length]
    setBrandEntries(prev => [...prev, { name, color, visible: true }])
    setBrandSearch('')
    // Fit to brand locations
    const ff = allFeatures.filter(f => f.properties[colorCol] === name)
    if (ff.length && mapRef.current) fitFeatures(mapRef.current, ff)
  }

  const removeBrand = (name) => {
    setBrandEntries(prev => prev.filter(e => e.name !== name))
    setHiddenBrands(prev => { const n = new Set(prev); n.delete(name); return n })
  }

  const toggleBrandVis = (name) => {
    setHiddenBrands(prev => {
      const n = new Set(prev); n.has(name) ? n.delete(name) : n.add(name); return n
    })
  }

  // ── Choropleth shortcut ────────────────────────────────────────────────
  if (markerMode === 'choropleth' && data?.choropleth_data) {
    return (
      <div className="pv-map-widget" style={{ height: height || 500 }}>
        <div className="pv-map-canvas">
          <Map ref={mapRef} mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
            initialViewState={{ longitude: cfg.default_center_lng||-98.58, latitude: cfg.default_center_lat||39.83, zoom: cfg.default_zoom||3.5 }}
            style={{ width:'100%', height:'100%' }} interactiveLayerIds={['choropleth-fill']}
            onClick={e => { const f=e.features?.[0]; if(f) setPopupInfo({ coords:[e.lngLat.lng,e.lngLat.lat], properties: data.choropleth_popup_data?.[f.properties.STUSPS||f.properties.NAME]||f.properties }) }}>
            <NavigationControl position="top-right" />
            <ChoroplethLayers data={data} cfg={cfg} />
            {popupInfo && <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]} onClose={()=>setPopupInfo(null)} closeOnClick={false} className="pv-map-popup" maxWidth="320px">
              <MapPopup properties={popupInfo.properties} columns={popupCols} />
            </Popup>}
          </Map>
          <StyleSwitcher active={mapStyle} onChange={setMapStyle} />
          <ChoroplethLegend data={data} cfg={cfg} />
        </div>
        <StatusBar total={Object.keys(data.choropleth_data).length} label="regions" />
      </div>
    )
  }

  // ══════════════════════════════════════════════════════════════════════════
  // POINT / BUBBLE / HEATMAP MODE
  // ══════════════════════════════════════════════════════════════════════════
  return (
    <div className="pv-map-widget" style={{ height: height || 500 }}>
      <div className="pv-map-canvas" style={{ cursor: placementMode ? 'crosshair' : undefined }}>

        {/* Brand Layers Panel (left) */}
        {showBrandPanel && colorCol && (
          <BrandLayersPanel
            allBrands={allBrands}
            entries={brandEntries}
            hidden={hiddenBrands}
            search={brandSearch}
            setSearch={setBrandSearch}
            results={brandSearchResults}
            onAdd={addBrand}
            onRemove={removeBrand}
            onToggle={toggleBrandVis}
            states={allStates}
            stateFilter={stateFilter}
            setStateFilter={setStateFilter}
            summaryCols={summaryCols}
            catCol={catCol}
            visibleCount={visibleFeatures.length}
            onClose={() => setShowBrandPanel(false)}
          />
        )}

        {/* Search Radius Panel (right) */}
        {showRadiusPanel && (
          <SearchRadiusPanel
            distance={radiusDist}
            setDistance={setRadiusDist}
            center={radiusCenter}
            setCenter={setRadiusCenter}
            min={radiusMin}
            max={radiusMax}
            placementMode={placementMode}
            setPlacementMode={setPlacementMode}
            locationsInRadius={featuresInRadius.length}
            brandsInRadius={brandsInRadius}
            onClose={() => setShowRadiusPanel(false)}
            onClear={() => { setRadiusCenter(null); setPlacementMode(false) }}
          />
        )}

        {/* Map */}
        <Map ref={mapRef} mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
          initialViewState={{ longitude: cfg.default_center_lng||-98.58, latitude: cfg.default_center_lat||39.83, zoom: cfg.default_zoom||3.5 }}
          style={{ width:'100%', height:'100%' }}
          interactiveLayerIds={markerMode==='heatmap'?[]:['point-markers','cluster-circles']}
          onClick={onClick}>

          <NavigationControl position="top-right" />

          <Source id="map-points" type="geojson" data={filteredGeoJSON}
            cluster={clustering && markerMode!=='heatmap'} clusterMaxZoom={14} clusterRadius={50}>
            {markerMode==='heatmap' ? (
              <Layer id="heatmap-layer" type="heatmap" paint={{
                'heatmap-weight':cfg.heatmap_weight_column?['interpolate',['linear'],['get',cfg.heatmap_weight_column],0,0,10000,1]:1,
                'heatmap-intensity':['interpolate',['linear'],['zoom'],0,1,12,3],
                'heatmap-radius':['interpolate',['linear'],['zoom'],0,cfg.heatmap_radius||20,12,(cfg.heatmap_radius||20)*2],
                'heatmap-color':['interpolate',['linear'],['heatmap-density'],0,'rgba(0,0,0,0)',0.2,'#4393c3',0.4,'#92c5de',0.6,'#fddbc7',0.8,'#f4a582',1,'#d6604d'],
                'heatmap-opacity':['interpolate',['linear'],['zoom'],7,1,14,0],
              }} />
            ) : (<>
              <Layer id="cluster-circles" type="circle" filter={['has','point_count']} paint={{
                'circle-color':['step',['get','point_count'],'#51bbd6',10,'#f1f075',50,'#f28cb1'],
                'circle-radius':['step',['get','point_count'],18,10,24,50,32],
                'circle-stroke-width':2,'circle-stroke-color':'#fff','circle-opacity':0.9,
              }} />
              <Layer id="cluster-count" type="symbol" filter={['has','point_count']} layout={{
                'text-field':'{point_count_abbreviated}','text-font':['Open Sans Bold'],'text-size':12,
              }} />
              <Layer id="point-markers" type="circle" filter={['!',['has','point_count']]} paint={{
                'circle-color':circleColor,'circle-radius':circleRadius,
                'circle-stroke-width':2,'circle-stroke-color':'#fff','circle-opacity':0.9,
              }} />
            </>)}
          </Source>

          {radiusGeoJSON && (
            <Source id="radius-overlay" type="geojson" data={radiusGeoJSON}>
              <Layer id="radius-fill" type="fill" paint={{'fill-color':'#3b82f6','fill-opacity':0.08}} />
              <Layer id="radius-border" type="line" paint={{'line-color':'#3b82f6','line-width':2,'line-dasharray':[3,2]}} />
            </Source>
          )}

          {popupInfo && <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]}
            onClose={()=>setPopupInfo(null)} closeOnClick={false} className="pv-map-popup" maxWidth="320px">
            <MapPopup properties={popupInfo.properties} columns={popupCols}
              color={brandEntries.find(e=>e.name===popupInfo.properties?.[colorCol])?.color} />
          </Popup>}
        </Map>

        {/* Style switcher (vertical, bottom-left) */}
        <StyleSwitcher active={mapStyle} onChange={setMapStyle} />

        {/* Panel toggle buttons (bottom center) */}
        <div className="pv-map-panel-toggles">
          {colorCol && !showBrandPanel && (
            <button className="pv-map-toggle-btn" onClick={() => setShowBrandPanel(true)}>🏷 Layers</button>
          )}
          {!showRadiusPanel && (
            <button className="pv-map-toggle-btn" onClick={() => setShowRadiusPanel(true)}>◎ Radius</button>
          )}
        </div>
      </div>

      <StatusBar total={visibleFeatures.length} allTotal={allFeatures.length} label="agencies"
        stateFilter={stateFilter} radiusCenter={radiusCenter} radiusDist={radiusDist}
        radiusCount={featuresInRadius.length} brandCount={brandEntries.length} />
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════════
// BRAND LAYERS PANEL (left floating)
// ═════════════════════════════════════════════════════════════════════════════
function BrandLayersPanel({
  allBrands, entries, hidden, search, setSearch, results,
  onAdd, onRemove, onToggle, states, stateFilter, setStateFilter,
  summaryCols, catCol, visibleCount, onClose,
}) {
  const [showSearch, setShowSearch] = useState(false)
  const brandCount = entries.length
  const locCount = visibleCount

  return (
    <div className="pv-map-float-panel pv-map-brand-panel">
      {/* Header */}
      <div className="pv-map-panel-header">
        <span className="pv-map-panel-title">🏷 Brand Layers</span>
        <div className="pv-map-panel-actions">
          <button className="pv-map-panel-btn" onClick={() => setShowSearch(!showSearch)} title="Add brand">+</button>
          <button className="pv-map-panel-btn" onClick={onClose} title="Close">✕</button>
        </div>
      </div>

      {/* State filter */}
      {states.length > 0 && (
        <div className="pv-map-panel-filter">
          <select value={stateFilter} onChange={e => setStateFilter(e.target.value)} className="pv-map-panel-select">
            <option value="">All States</option>
            {states.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      )}

      {/* Search / Add */}
      {(showSearch || entries.length === 0) && (
        <div className="pv-map-panel-search">
          <input
            type="text"
            placeholder="Search brands..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pv-map-panel-input"
            autoFocus
          />
          {search && <button className="pv-map-panel-input-clear" onClick={() => setSearch('')}>✕</button>}
          {results.length > 0 && (
            <div className="pv-map-panel-dropdown">
              {results.map(b => (
                <div key={b.name} className="pv-map-panel-dropdown-item" onClick={() => onAdd(b.name)}>
                  <div className="pv-map-panel-dropdown-name">{b.name}</div>
                  <div className="pv-map-panel-dropdown-meta">
                    {b.count} locations
                    {summaryCols.slice(0,2).map(c => <span key={c}> · {fmt(b.metrics[c])}</span>)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Summary */}
      <div className="pv-map-panel-summary">
        Showing {locCount.toLocaleString()} locations{brandCount > 0 ? ` from ${brandCount} brands` : ''}
      </div>

      {/* Brand cards */}
      <div className="pv-map-panel-list">
        {entries.map(e => {
          const brand = allBrands.find(b => b.name === e.name)
          const isHidden = hidden.has(e.name)
          return (
            <div key={e.name} className={`pv-map-brand-card ${isHidden ? 'pv-map-brand-card--hidden' : ''}`}>
              <div className="pv-map-brand-card-top">
                <input type="checkbox" checked={!isHidden} onChange={() => onToggle(e.name)} className="pv-map-brand-check" />
                <span className="pv-map-brand-dot" style={{ backgroundColor: e.color }} />
                <span className="pv-map-brand-name">{e.name}</span>
                <button className="pv-map-brand-eye" onClick={() => onToggle(e.name)} title={isHidden ? 'Show' : 'Hide'}>
                  {isHidden ? '👁‍🗨' : '👁'}
                </button>
              </div>
              {brand?.category && <div className="pv-map-brand-category">{brand.category}</div>}
              {brand && summaryCols.length > 0 && (
                <div className="pv-map-brand-metrics">
                  {summaryCols.map(c => (
                    <div key={c} className="pv-map-brand-metric">
                      <span className="pv-map-brand-metric-label">{c.replace(/^hha_/,'').replace(/_/g,' ')}</span>
                      <span className="pv-map-brand-metric-value">{fmt(brand.metrics[c])}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════════
// SEARCH RADIUS PANEL (right floating)
// ═════════════════════════════════════════════════════════════════════════════
function SearchRadiusPanel({
  distance, setDistance, center, setCenter, min, max,
  placementMode, setPlacementMode, locationsInRadius, brandsInRadius,
  onClose, onClear,
}) {
  const area = center ? Math.round(Math.PI * distance * distance) : 0

  return (
    <div className="pv-map-float-panel pv-map-radius-panel">
      {/* Header */}
      <div className="pv-map-panel-header">
        <span className="pv-map-panel-title">◎ Search Radius</span>
        <button className="pv-map-panel-btn" onClick={onClose} title="Close">✕</button>
      </div>

      {/* Place / Clear buttons */}
      <div className="pv-map-radius-actions">
        <button
          className={`pv-map-radius-place ${placementMode ? 'pv-map-radius-place--active' : ''}`}
          onClick={() => setPlacementMode(!placementMode)}
        >
          ◎ {placementMode ? 'Click on map...' : 'Click map to place'}
        </button>
        {center && (
          <button className="pv-map-radius-clear" onClick={onClear} title="Clear radius">🗑</button>
        )}
      </div>

      {/* Slider */}
      <div className="pv-map-radius-slider-section">
        <div className="pv-map-radius-slider-header">
          <span>Radius Distance</span>
          <span className="pv-map-radius-slider-value">{distance} miles</span>
        </div>
        <input
          type="range"
          min={min}
          max={max}
          value={distance}
          onChange={e => setDistance(Number(e.target.value))}
          className="pv-map-radius-slider"
        />
        <div className="pv-map-radius-slider-labels">
          <span>{min} mi</span>
          <span>{Math.round((min+max)/2)} mi</span>
          <span>{max} mi</span>
        </div>
      </div>

      {/* Info */}
      {center && (
        <div className="pv-map-radius-info">
          <div className="pv-map-radius-info-row">
            <span>Center Point</span>
            <span>{center[1].toFixed(4)}, {center[0].toFixed(4)}</span>
          </div>
          <div className="pv-map-radius-info-row">
            <span>Locations in Radius</span>
            <span className="pv-map-radius-info-bold">{locationsInRadius}</span>
          </div>
          <div className="pv-map-radius-info-row">
            <span>Approximate Area</span>
            <span>{area.toLocaleString()} sq mi</span>
          </div>

          {brandsInRadius.length > 0 && (
            <div className="pv-map-radius-brands">
              <div className="pv-map-radius-brands-label">Brands in Radius</div>
              <div className="pv-map-radius-brands-chips">
                {brandsInRadius.map(([name, count]) => (
                  <span key={name} className="pv-map-radius-chip">{name} ({count})</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════════
// STYLE SWITCHER (vertical, bottom-left)
// ═════════════════════════════════════════════════════════════════════════════
function StyleSwitcher({ active, onChange }) {
  return (
    <div className="pv-map-style-vert">
      {Object.entries(MAP_STYLES).map(([k, { label, icon }]) => (
        <button key={k}
          className={`pv-map-style-vert-btn ${active===k ? 'pv-map-style-vert-btn--active' : ''}`}
          onClick={() => onChange(k)}>
          <span className="pv-map-style-vert-icon">{icon}</span>
          <span className="pv-map-style-vert-label">{label}</span>
        </button>
      ))}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════════
// POPUP
// ═════════════════════════════════════════════════════════════════════════════
function MapPopup({ properties, columns, color }) {
  if (!properties) return null
  const keys = columns.length > 0 ? columns : Object.keys(properties)
  const titleKey = keys[0], metricKeys = keys.slice(1)
  return (
    <div className="pv-map-popup-card">
      <div className="pv-map-popup-header">
        {color && <span className="pv-map-popup-dot" style={{backgroundColor:color}} />}
        <span className="pv-map-popup-title">{properties[titleKey]||'Unknown'}</span>
      </div>
      <div className="pv-map-popup-metrics">
        {metricKeys.map(k => {
          const v = properties[k]; if(v==null) return null
          return (<div key={k} className="pv-map-popup-metric">
            <span className="pv-map-popup-metric-label">{k.replace(/_/g,' ')}</span>
            <span className="pv-map-popup-metric-value">{fmt(v)}</span>
          </div>)
        })}
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════════
// STATUS BAR
// ═════════════════════════════════════════════════════════════════════════════
function StatusBar({ total, allTotal, label, stateFilter, radiusCenter, radiusDist, radiusCount, brandCount }) {
  return (
    <div className="pv-map-status">
      <span>Showing <strong>{total.toLocaleString()}</strong>{allTotal && total<allTotal ? ` of ${allTotal.toLocaleString()}` : ''} {label}</span>
      {stateFilter && <span className="pv-map-status-tag">📍 {stateFilter}</span>}
      {brandCount > 0 && <span className="pv-map-status-tag">🏷 {brandCount} brands</span>}
      {radiusCenter && <span className="pv-map-status-tag">◎ {radiusDist} mi · {radiusCount} in radius</span>}
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════════
// CHOROPLETH (unchanged)
// ═════════════════════════════════════════════════════════════════════════════
function ChoroplethLayers({ data, cfg }) {
  const [boundaries, setBoundaries] = useState(null)
  useEffect(() => { import('../../data/us-states.json').then(m=>setBoundaries(m.default||m)).catch(()=>{}) }, [])
  const enriched = useMemo(() => {
    if(!boundaries||!data?.choropleth_data) return null
    const md=data.choropleth_data
    return{...boundaries,features:boundaries.features.map(f=>({...f,properties:{...f.properties,_metric:md[f.properties.STUSPS||f.properties.NAME]??null}}))}
  },[boundaries,data?.choropleth_data])
  if(!enriched) return null
  const ranges=(data.choropleth_ranges||cfg.choropleth_ranges||'').split(',').map(Number).filter(n=>!isNaN(n)&&n>0)
  const cs=cfg.choropleth_color_scale==='diverging'?CHOROPLETH_DIV:CHOROPLETH_SEQ
  let fillColor=OTHERS_COLOR
  if(ranges.length){const expr=['step',['coalesce',['get','_metric'],0],cs[0]];const step=Math.floor(cs.length/(ranges.length+1));ranges.forEach((bp,i)=>{expr.push(bp,cs[Math.min((i+1)*step,cs.length-1)])});fillColor=expr}
  return(<Source id="choropleth-boundaries" type="geojson" data={enriched}>
    <Layer id="choropleth-fill" type="fill" paint={{'fill-color':fillColor,'fill-opacity':0.7}} />
    <Layer id="choropleth-border" type="line" paint={{'line-color':'#fff','line-width':1}} />
  </Source>)
}

function ChoroplethLegend({ data, cfg }) {
  const ranges=(data?.choropleth_ranges||cfg?.choropleth_ranges||'').split(',').map(Number).filter(n=>!isNaN(n)&&n>0)
  if(!ranges.length) return null
  const cs=cfg?.choropleth_color_scale==='diverging'?CHOROPLETH_DIV:CHOROPLETH_SEQ
  const step=Math.floor(cs.length/(ranges.length+1))
  const items=[{label:`< ${fmt(ranges[0])}`,color:cs[0]}]
  ranges.forEach((bp,i)=>{const next=ranges[i+1];items.push({label:next?`${fmt(bp)} – ${fmt(next)}`:`${fmt(bp)}+`,color:cs[Math.min((i+1)*step,cs.length-1)]})})
  return(<div className="pv-map-float-panel pv-map-choropleth-legend">
    <div className="pv-map-panel-header"><span className="pv-map-panel-title">Legend</span></div>
    {items.map((it,i)=>(<div key={i} className="pv-map-choropleth-item"><span className="pv-map-choropleth-swatch" style={{backgroundColor:it.color}} /><span>{it.label}</span></div>))}
  </div>)
}
