import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import Map, { Source, Layer, Popup, NavigationControl } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import '../../styles/tailwind.css'

// ── Basemap styles ──────────────────────────────────────────────────────────
const MAP_STYLES = {
  light:     { url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',    label: 'Light',     icon: '☀️' },
  streets:   { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',     label: 'Streets',   icon: '🗺️' },
  satellite: { url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',     label: 'Satellite', icon: '🛰️' },
  dark:      { url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json', label: 'Dark',      icon: '🌙' },
}

const BRAND_COLORS = ['#3b82f6','#ef4444','#22c55e','#f97316','#a855f7','#06b6d4','#eab308','#ec4899','#6366f1','#84cc16']
const OTHERS_COLOR = '#94a3b8'
const CHOROPLETH_SEQ = ['#f7fbff','#deebf7','#c6dbef','#9ecae1','#6baed6','#4292c6','#2171b5','#08519c','#08306b']
const CHOROPLETH_DIV = ['#b2182b','#d6604d','#f4a582','#fddbc7','#f7f7f7','#d1e5f0','#92c5de','#4393c3','#2166ac']

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = v => { if(v==null) return '—'; const n=Number(v); if(isNaN(n)) return String(v); if(Math.abs(n)>=1e6) return (n/1e6).toFixed(1)+'M'; if(Math.abs(n)>=1e3) return (n/1e3).toFixed(1)+'K'; return n.toLocaleString() }
const haversine = (lat1,lng1,lat2,lng2) => { const R=3958.8,dLat=(lat2-lat1)*Math.PI/180,dLng=(lng2-lng1)*Math.PI/180; const a=Math.sin(dLat/2)**2+Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2; return R*2*Math.atan2(Math.sqrt(a),Math.sqrt(1-a)) }
const makeCircle = (c,miles) => { const s=64,km=miles*1.60934,r=[]; const dx=km/(111.32*Math.cos(c[1]*Math.PI/180)),dy=km/110.574; for(let i=0;i<=s;i++){const t=i/s*2*Math.PI;r.push([c[0]+dx*Math.cos(t),c[1]+dy*Math.sin(t)])} return{type:'Feature',geometry:{type:'Polygon',coordinates:[r]}} }
const fitFF = (map,ff,opts={}) => { if(!ff.length||!map)return; let a=Infinity,b=Infinity,c=-Infinity,d=-Infinity; ff.forEach(f=>{const[x,y]=f.geometry.coordinates;if(x<a)a=x;if(x>c)c=x;if(y<b)b=y;if(y>d)d=y}); map.fitBounds([[a,b],[c,d]],{padding:60,maxZoom:12,duration:600,...opts}) }
const csv = s => (s||'').split(',').map(x=>x.trim()).filter(Boolean)


// ═════════════════════════════════════════════════════════════════════════════
// MAIN MAP WIDGET
// ═════════════════════════════════════════════════════════════════════════════
export default function MapWidget({ data, height, name }) {
  const mapRef = useRef(null)
  const cfg = data?.map_config || {}

  const [mapStyle, setMapStyle] = useState(cfg.map_style || 'streets')
  const clustering = cfg.clustering !== false
  const markerMode = cfg.marker_mode || 'points'
  const colorCol = cfg.color_column || ''
  const sizeCol = cfg.size_column || ''
  const popupCols = useMemo(() => csv(cfg.popup_columns), [cfg.popup_columns])
  const searchCols = useMemo(() => csv(cfg.search_columns), [cfg.search_columns])
  const summaryCols = useMemo(() => csv(cfg.brand_summary_columns), [cfg.brand_summary_columns])
  const catCol = cfg.brand_category_column || ''
  const panelLabel = cfg.panel_label || 'Brand Layers'
  const radiusMin = cfg.radius_min || 5
  const radiusMax = cfg.radius_max || 200
  const radiusDef = cfg.radius_default || 25

  // Panel visibility
  const [showBrandPanel, setShowBrandPanel] = useState(true)
  const [showRadiusPanel, setShowRadiusPanel] = useState(false)
  const [showAddSearch, setShowAddSearch] = useState(true) // search input visible by default

  // Brand state
  const [brandEntries, setBrandEntries] = useState([])
  const [brandSearch, setBrandSearch] = useState('')
  const [hiddenBrands, setHiddenBrands] = useState(new Set())

  // Radius state
  const [radiusDist, setRadiusDist] = useState(radiusDef)
  const [radiusCenter, setRadiusCenter] = useState(null)
  const [placementMode, setPlacementMode] = useState(false)

  // Popup
  const [popupInfo, setPopupInfo] = useState(null)

  // Data
  const geojson = data?.geojson || { type: 'FeatureCollection', features: [] }
  const allFeatures = geojson.features || []

  // Debug: log data to help diagnose loading issues
  useEffect(() => {
    console.log('[MapWidget] data received:', {
      hasGeojson: !!data?.geojson,
      featureCount: allFeatures.length,
      hasChoropleth: !!data?.choropleth_data,
      mapConfig: cfg,
      sampleFeature: allFeatures[0]?.properties,
    })
  }, [data])

  const effectiveSearchCols = useMemo(() => {
    if (searchCols.length > 0) return searchCols
    if (!allFeatures.length) return []
    return Object.keys(allFeatures[0].properties).filter(k => typeof allFeatures[0].properties[k] === 'string')
  }, [searchCols, allFeatures])

  // All brands from color_column
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

  // Filtered features
  const visibleFeatures = useMemo(() => {
    let ff = allFeatures
    if (hiddenBrands.size > 0 && colorCol) ff = ff.filter(f => !hiddenBrands.has(f.properties[colorCol]))
    if (brandEntries.length > 0) {
      ff = ff.filter(f => brandEntries.some(e => String(f.properties[e.column || colorCol]) === e.name))
    }
    return ff
  }, [allFeatures, hiddenBrands, brandEntries, colorCol])

  const filteredGeoJSON = useMemo(() => ({ type: 'FeatureCollection', features: visibleFeatures }), [visibleFeatures])

  // Radius features
  const featuresInRadius = useMemo(() => {
    if (!radiusCenter || radiusDist <= 0) return []
    return visibleFeatures.filter(f => { const [lng,lat]=f.geometry.coordinates; return haversine(radiusCenter[1],radiusCenter[0],lat,lng)<=radiusDist })
  }, [visibleFeatures, radiusCenter, radiusDist])

  const brandsInRadius = useMemo(() => {
    if (!colorCol || !featuresInRadius.length) return []
    const m = {}; featuresInRadius.forEach(f => { const b=f.properties[colorCol]; if(b) m[b]=(m[b]||0)+1 })
    return Object.entries(m).sort((a,b) => b[1]-a[1])
  }, [featuresInRadius, colorCol])

  // Search results — searches ALL configured searchable columns, not just brands
  const brandSearchResults = useMemo(() => {
    if (!brandSearch || brandSearch.length < 1) return []
    const lower = brandSearch.toLowerCase()
    const inPanel = new Set(brandEntries.map(e => e.name))
    const cols = effectiveSearchCols.length > 0 ? effectiveSearchCols : [colorCol]

    // Collect unique matching values across all searchable columns
    const resultMap = {}
    allFeatures.forEach(f => {
      cols.forEach(col => {
        const val = f.properties[col]
        if (!val) return
        const str = String(val)
        if (!str.toLowerCase().includes(lower)) return
        const key = `${col}:${str}`
        if (!resultMap[key]) {
          resultMap[key] = { name: str, column: col, count: 0, metrics: {}, category: '' }
        }
        resultMap[key].count++
        if (catCol && f.properties[catCol]) resultMap[key].category = f.properties[catCol]
        summaryCols.forEach(c => { resultMap[key].metrics[c] = (resultMap[key].metrics[c]||0) + (Number(f.properties[c])||0) })
      })
    })

    return Object.values(resultMap)
      .filter(r => !inPanel.has(r.name))
      .sort((a,b) => b.count - a.count)
      .slice(0, 12)
  }, [brandSearch, allFeatures, brandEntries, effectiveSearchCols, colorCol, catCol, summaryCols])

  // Fit bounds
  useEffect(() => {
    if (!mapRef.current || !data?.bounds) return
    const [w,s,e,n] = data.bounds
    mapRef.current.fitBounds([[w,s],[e,n]], { padding:60, maxZoom:12, duration:800 })
  }, [data?.bounds])

  // Map click
  const onClick = useCallback((e) => {
    if (placementMode) { setRadiusCenter([e.lngLat.lng, e.lngLat.lat]); setPlacementMode(false); return }
    const f = e.features?.[0]
    if (f?.properties?.cluster) {
      const src = mapRef.current?.getSource('map-points')
      src?.getClusterExpansionZoom?.(f.properties.cluster_id, (err, zoom) => { if(!err) mapRef.current.easeTo({center:f.geometry.coordinates,zoom:Math.min(zoom,15)}) })
      return
    }
    if (f && !f.properties.cluster) { setPopupInfo({ coords: f.geometry.coordinates.slice(), properties: f.properties }); return }
    setPopupInfo(null)
  }, [placementMode])

  const radiusGeoJSON = useMemo(() => radiusCenter ? makeCircle(radiusCenter, radiusDist) : null, [radiusCenter, radiusDist])

  const circleColor = useMemo(() => {
    if (!colorCol || brandEntries.length === 0) return '#3b82f6'
    const expr = ['match', ['get', colorCol]]; brandEntries.forEach(e => expr.push(e.name, e.color)); expr.push(OTHERS_COLOR); return expr
  }, [colorCol, brandEntries])

  const circleRadius = useMemo(() => {
    if (markerMode !== 'bubble' || !sizeCol) return 7
    return ['interpolate',['linear'],['get',sizeCol],0,4,100,8,1000,14,10000,22,100000,32]
  }, [markerMode, sizeCol])

  // Brand/entity actions — column tells us which property to filter by
  const addBrand = (name, column) => {
    if (brandEntries.some(e => e.name === name)) return
    const col = column || colorCol
    setBrandEntries(prev => [...prev, { name, color: BRAND_COLORS[prev.length % BRAND_COLORS.length], visible: true, column: col }])
    setBrandSearch('')
    const ff = allFeatures.filter(f => String(f.properties[col]) === name)
    if (ff.length && mapRef.current) fitFF(mapRef.current, ff)
  }
  const removeBrand = (name) => { setBrandEntries(prev => prev.filter(e => e.name !== name)); setHiddenBrands(prev => { const n = new Set(prev); n.delete(name); return n }) }
  const toggleBrand = (name) => { setHiddenBrands(prev => { const n = new Set(prev); n.has(name) ? n.delete(name) : n.add(name); return n }) }

  // Choropleth shortcut
  if (markerMode === 'choropleth' && data?.choropleth_data) {
    return (
      <div className="flex flex-col w-full rounded-xl overflow-hidden bg-white" style={{ height: height || 500 }}>
        <div className="flex-1 relative">
          <Map ref={mapRef} mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
            initialViewState={{longitude:cfg.default_center_lng||-98.58,latitude:cfg.default_center_lat||39.83,zoom:cfg.default_zoom||3.5}}
            style={{width:'100%',height:'100%'}} interactiveLayerIds={['choropleth-fill']}
            onClick={e=>{const f=e.features?.[0];if(f)setPopupInfo({coords:[e.lngLat.lng,e.lngLat.lat],properties:data.choropleth_popup_data?.[f.properties.STUSPS||f.properties.NAME]||f.properties})}}>
            <NavigationControl position="top-right" />
            <ChoroplethLayers data={data} cfg={cfg} />
            {popupInfo && <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]} onClose={()=>setPopupInfo(null)} closeOnClick={false} className="pv-map-popup" maxWidth="320px">
              <MapPopup properties={popupInfo.properties} columns={popupCols} />
            </Popup>}
          </Map>
          <StyleSwitcher active={mapStyle} onChange={setMapStyle} />
          <ChoroplethLegend data={data} cfg={cfg} />
        </div>
      </div>
    )
  }

  // ══════════════════════════════════════════════════════════════════════════
  // POINT / BUBBLE / HEATMAP
  // ══════════════════════════════════════════════════════════════════════════
  return (
    <div className="flex flex-col w-full rounded-xl overflow-hidden bg-white" style={{ height: height || 500 }}>
      <div className="flex-1 relative" style={{ cursor: placementMode ? 'crosshair' : undefined }}>

        {/* ── Brand Layers Panel (left) ────────────────────────── */}
        {showBrandPanel && colorCol && (
          <div className="absolute top-3 left-3 z-10 w-80 bg-white rounded-xl shadow-lg border border-gray-100 flex flex-col" style={{ maxHeight: 'calc(100% - 70px)' }}>
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <span className="text-lg">🏷️</span>
                <span className="font-bold text-gray-900 text-sm">{panelLabel}</span>
              </div>
              <div className="flex gap-1">
                <button onClick={() => { setShowAddSearch(true); setBrandSearch(''); }} className="w-7 h-7 flex items-center justify-center rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 text-base font-semibold" title="Add brand">+</button>
                <button onClick={() => setShowBrandPanel(false)} className="w-7 h-7 flex items-center justify-center rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 text-base">✕</button>
              </div>
            </div>

            {/* Search (toggleable via + button) */}
            {showAddSearch && (
              <div className="px-4 py-2 relative">
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
                  <input
                    type="text" placeholder="Search brands..."
                    value={brandSearch} onChange={e => setBrandSearch(e.target.value)}
                    className="w-full pl-9 pr-8 py-2.5 text-sm border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition-colors"
                    autoFocus
                  />
                  {brandSearch && <button onClick={() => setBrandSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">✕</button>}
                </div>
                {/* Search dropdown */}
                {brandSearchResults.length > 0 && (
                  <div className="absolute left-4 right-4 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 max-h-60 overflow-y-auto">
                    {brandSearchResults.map(b => (
                      <div key={`${b.column}:${b.name}`} onClick={() => { addBrand(b.name, b.column); setShowAddSearch(false); }}
                        className="px-3 py-2.5 cursor-pointer hover:bg-gray-50 border-b border-gray-50 last:border-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900 text-sm">{b.name}</span>
                          <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{b.column.replace(/^hha_/,'').replace(/_/g,' ')}</span>
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {b.count} matches{summaryCols.slice(0,2).map(c => <span key={c}> · {fmt(b.metrics[c])}</span>)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Summary */}
            <div className="px-4 py-1.5 text-xs text-gray-500 border-b border-gray-50">
              Showing {visibleFeatures.length.toLocaleString()} locations{brandEntries.length > 0 ? ` from ${brandEntries.length} brands` : ''}
            </div>

            {/* Brand cards */}
            <div className="flex-1 overflow-y-auto">
              {brandEntries.map(e => {
                const brand = allBrands.find(b => b.name === e.name)
                const isHidden = hiddenBrands.has(e.name)
                return (
                  <div key={e.name} className={`px-4 py-3 border-b border-gray-50 ${isHidden ? 'opacity-40' : ''}`}>
                    <div className="flex items-center gap-2">
                      <input type="checkbox" checked={!isHidden} onChange={() => toggleBrand(e.name)}
                        className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                      <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: e.color }} />
                      <span className="font-semibold text-gray-900 text-sm flex-1 truncate">{e.name}</span>
                      <button onClick={() => toggleBrand(e.name)} className="text-gray-400 hover:text-gray-600 text-sm">{isHidden ? '👁️‍🗨️' : '👁️'}</button>
                    </div>
                    {brand?.category && <div className="ml-9 text-xs text-gray-500 mt-0.5">{brand.category}</div>}
                    {brand && summaryCols.length > 0 && (
                      <div className="flex gap-6 ml-9 mt-2">
                        {summaryCols.map(c => (
                          <div key={c}>
                            <div className="text-xs text-gray-400 capitalize">{c.replace(/^hha_/,'').replace(/_/g,' ')}</div>
                            <div className="text-sm font-bold text-gray-900">{fmt(brand.metrics[c])}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ── Search Radius Panel (right) ──────────────────────── */}
        {showRadiusPanel && (
          <div className="absolute top-3 right-3 z-10 w-72 bg-white rounded-xl shadow-lg border border-gray-100">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <span className="text-lg">◎</span>
                <span className="font-bold text-gray-900 text-sm">Search Radius</span>
              </div>
              <button onClick={() => setShowRadiusPanel(false)} className="w-7 h-7 flex items-center justify-center rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 text-base">✕</button>
            </div>

            {/* Set center button */}
            <div className="flex gap-2 px-4 py-3">
              <button
                onClick={() => setPlacementMode(!placementMode)}
                className={`flex-1 py-2.5 rounded-lg border-2 text-sm font-semibold transition-all flex items-center justify-center gap-2 ${
                  placementMode
                    ? 'bg-blue-500 text-white border-blue-500 animate-pulse'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-blue-300 hover:bg-blue-50'
                }`}>
                ◎ {placementMode ? 'Click on map...' : 'Set Radius Center'}
              </button>
              {radiusCenter && (
                <button onClick={() => { setRadiusCenter(null); setPlacementMode(false) }}
                  className="w-10 h-10 flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-red-50 hover:border-red-200 hover:text-red-500">🗑️</button>
              )}
            </div>

            {/* Slider */}
            <div className="px-4 pb-3">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs text-gray-500">Radius Distance</span>
                <span className="text-sm font-bold text-blue-600">{radiusDist} miles</span>
              </div>
              <input type="range" min={radiusMin} max={radiusMax} value={radiusDist}
                onChange={e => setRadiusDist(Number(e.target.value))}
                className="w-full h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-blue-500"
                style={{ accentColor: '#3b82f6' }} />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>{radiusMin} mi</span><span>{Math.round((radiusMin+radiusMax)/2)} mi</span><span>{radiusMax} mi</span>
              </div>
            </div>

            {/* Info */}
            {radiusCenter && (
              <div className="px-4 pb-4 space-y-0">
                <div className="flex justify-between py-2 border-t border-gray-100 text-xs text-gray-600">
                  <span>Center Point</span><span className="font-medium">{radiusCenter[1].toFixed(4)}, {radiusCenter[0].toFixed(4)}</span>
                </div>
                <div className="flex justify-between py-2 border-t border-gray-100 text-xs text-gray-600">
                  <span>Locations in Radius</span><span className="font-bold text-gray-900 text-base">{featuresInRadius.length}</span>
                </div>
                <div className="flex justify-between py-2 border-t border-gray-100 text-xs text-gray-600">
                  <span>Approximate Area</span><span className="font-medium">{Math.round(Math.PI * radiusDist * radiusDist).toLocaleString()} sq mi</span>
                </div>
                {brandsInRadius.length > 0 && (
                  <div className="pt-3 border-t border-gray-100">
                    <div className="text-xs font-semibold text-gray-600 mb-2">Brands in Radius</div>
                    <div className="flex flex-wrap gap-1.5">
                      {brandsInRadius.map(([name, count]) => (
                        <span key={name} className="px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                          {name} ({count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── Map ──────────────────────────────────────────────── */}
        <Map ref={mapRef} mapStyle={MAP_STYLES[mapStyle]?.url || MAP_STYLES.streets.url}
          initialViewState={{longitude:cfg.default_center_lng||-98.58,latitude:cfg.default_center_lat||39.83,zoom:cfg.default_zoom||3.5}}
          style={{width:'100%',height:'100%'}}
          interactiveLayerIds={markerMode==='heatmap'?[]:['point-markers','cluster-circles']}
          onClick={onClick}>
          <NavigationControl position="top-right" />
          <Source id="map-points" type="geojson" data={filteredGeoJSON}
            cluster={clustering && markerMode!=='heatmap'} clusterMaxZoom={14} clusterRadius={50}>
            {markerMode==='heatmap' ? (
              <Layer id="heatmap-layer" source="map-points" type="heatmap" paint={{
                'heatmap-weight':cfg.heatmap_weight_column?['interpolate',['linear'],['get',cfg.heatmap_weight_column],0,0,10000,1]:1,
                'heatmap-intensity':['interpolate',['linear'],['zoom'],0,1,12,3],
                'heatmap-radius':['interpolate',['linear'],['zoom'],0,cfg.heatmap_radius||20,12,(cfg.heatmap_radius||20)*2],
                'heatmap-color':['interpolate',['linear'],['heatmap-density'],0,'rgba(0,0,0,0)',0.2,'#4393c3',0.4,'#92c5de',0.6,'#fddbc7',0.8,'#f4a582',1,'#d6604d'],
                'heatmap-opacity':['interpolate',['linear'],['zoom'],7,1,14,0],
              }} />
            ) : (<>
              <Layer id="cluster-circles" source="map-points" type="circle" filter={['has','point_count']} paint={{
                'circle-color':['step',['get','point_count'],'#51bbd6',10,'#f1f075',50,'#f28cb1'],
                'circle-radius':['step',['get','point_count'],18,10,24,50,32],
                'circle-stroke-width':2,'circle-stroke-color':'#fff','circle-opacity':0.9,
              }} />
              <Layer id="cluster-count" source="map-points" type="symbol" filter={['has','point_count']} layout={{
                'text-field':'{point_count_abbreviated}','text-font':['Open Sans Bold'],'text-size':12,
              }} />
              <Layer id="point-markers" source="map-points" type="circle" filter={['!',['has','point_count']]} paint={{
                'circle-color':circleColor,'circle-radius':circleRadius,
                'circle-stroke-width':2,'circle-stroke-color':'#fff','circle-opacity':0.9,
              }} />
            </>)}
          </Source>
          {radiusGeoJSON && (
            <Source id="radius-overlay" type="geojson" data={radiusGeoJSON}>
              <Layer id="radius-fill" source="radius-overlay" type="fill" paint={{'fill-color':'#3b82f6','fill-opacity':0.08}} />
              <Layer id="radius-border" source="radius-overlay" type="line" paint={{'line-color':'#3b82f6','line-width':2,'line-dasharray':[3,2]}} />
            </Source>
          )}
          {popupInfo && <Popup longitude={popupInfo.coords[0]} latitude={popupInfo.coords[1]}
            onClose={()=>setPopupInfo(null)} closeOnClick={false} className="pv-map-popup" maxWidth="320px">
            <MapPopup properties={popupInfo.properties} columns={popupCols}
              color={brandEntries.find(e=>e.name===popupInfo.properties?.[colorCol])?.color} />
          </Popup>}
        </Map>

        {/* ── Style Switcher (bottom-left, vertical) ──────────── */}
        <StyleSwitcher active={mapStyle} onChange={setMapStyle} />

        {/* ── Legend (bottom-right) ────────────────────────────── */}
        {brandEntries.length > 0 && (
          <div className="absolute bottom-3 right-14 z-5 bg-white/95 rounded-lg shadow-md px-3 py-2.5 text-xs backdrop-blur-sm border border-gray-100">
            <div className="flex items-center justify-between mb-1.5">
              <span className="font-semibold text-gray-900">Legend</span>
            </div>
            {brandEntries.map(e => (
              <div key={e.name} className="flex items-center gap-2 py-0.5">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: hiddenBrands.has(e.name) ? '#d1d5db' : e.color }} />
                <span className="text-gray-600">{e.name}</span>
              </div>
            ))}
            {radiusCenter && (
              <div className="flex items-center gap-2 py-0.5">
                <span className="w-2.5 h-2.5 rounded-full border-2 border-dashed border-blue-500 flex-shrink-0" />
                <span className="text-gray-600">Search Radius</span>
              </div>
            )}
          </div>
        )}

        {/* ── Panel toggle buttons (top corners) ────────────── */}
        {colorCol && !showBrandPanel && (
          <button onClick={() => { setShowBrandPanel(true); setShowAddSearch(true); }}
            className="absolute top-3 left-3 z-10 px-4 py-2 rounded-lg bg-white/95 border border-gray-200 text-xs font-medium text-gray-600 shadow-md hover:border-blue-400 hover:text-blue-600 backdrop-blur-sm transition-colors">
            🏷️ Layers
          </button>
        )}
        {!showRadiusPanel && (
          <button onClick={() => setShowRadiusPanel(true)}
            className="absolute top-3 right-3 z-10 px-4 py-2 rounded-lg bg-white/95 border border-gray-200 text-xs font-medium text-gray-600 shadow-md hover:border-blue-400 hover:text-blue-600 backdrop-blur-sm transition-colors">
            ◎ Radius
          </button>
        )}
      </div>

      {/* ── Bottom Summary Bar ──────────────────────────────────── */}
      {brandEntries.length > 0 && (
        <div className="flex items-center gap-6 px-4 py-2 bg-gray-900 text-white overflow-x-auto">
          {brandEntries.map(e => {
            const brand = allBrands.find(b => b.name === e.name)
            if (!brand) return null
            return (
              <div key={e.name} className="flex items-center gap-3 flex-shrink-0 text-xs">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: e.color }} />
                <span className="font-semibold whitespace-nowrap">{e.name}</span>
                <span className="text-gray-400">{brand.count} locations</span>
                {summaryCols.map(c => (
                  <span key={c} className="text-gray-300">{fmt(brand.metrics[c])}</span>
                ))}
              </div>
            )
          })}
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
    <div className="absolute bottom-3 left-3 z-5 flex flex-col bg-white/95 rounded-lg shadow-md overflow-hidden backdrop-blur-sm border border-gray-100">
      {Object.entries(MAP_STYLES).map(([k, { label, icon }]) => (
        <button key={k} onClick={() => onChange(k)}
          className={`flex items-center gap-2 px-3 py-2 text-xs transition-colors text-left ${
            active === k ? 'bg-blue-50 text-blue-700 font-semibold' : 'text-gray-600 hover:bg-gray-50'
          }`}>
          <span className="text-base w-5 text-center">{icon}</span>
          <span>{label}</span>
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
    <div className="text-sm">
      <div className="flex items-center gap-2 px-3 py-2.5 bg-gray-50 border-b border-gray-200">
        {color && <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{backgroundColor:color}} />}
        <span className="font-bold text-gray-900">{properties[titleKey]||'Unknown'}</span>
      </div>
      <div className="px-3 py-2">
        {metricKeys.map(k => { const v=properties[k]; if(v==null) return null; return (
          <div key={k} className="flex justify-between py-1 border-b border-gray-50 last:border-0">
            <span className="text-gray-500 capitalize text-xs">{k.replace(/_/g,' ')}</span>
            <span className="font-semibold text-gray-900">{fmt(v)}</span>
          </div>
        )})}
      </div>
    </div>
  )
}


// ═════════════════════════════════════════════════════════════════════════════
// CHOROPLETH (unchanged logic, Tailwind styling)
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
    <Layer id="choropleth-fill" source="choropleth-boundaries" type="fill" paint={{'fill-color':fillColor,'fill-opacity':0.7}} />
    <Layer id="choropleth-border" source="choropleth-boundaries" type="line" paint={{'line-color':'#fff','line-width':1}} />
  </Source>)
}

function ChoroplethLegend({ data, cfg }) {
  const ranges=(data?.choropleth_ranges||cfg?.choropleth_ranges||'').split(',').map(Number).filter(n=>!isNaN(n)&&n>0)
  if(!ranges.length) return null
  const cs=cfg?.choropleth_color_scale==='diverging'?CHOROPLETH_DIV:CHOROPLETH_SEQ
  const step=Math.floor(cs.length/(ranges.length+1))
  const items=[{label:`< ${fmt(ranges[0])}`,color:cs[0]}]
  ranges.forEach((bp,i)=>{const next=ranges[i+1];items.push({label:next?`${fmt(bp)} – ${fmt(next)}`:`${fmt(bp)}+`,color:cs[Math.min((i+1)*step,cs.length-1)]})})
  return(
    <div className="absolute bottom-3 right-14 z-5 bg-white/95 rounded-lg shadow-md px-3 py-2.5 backdrop-blur-sm border border-gray-100">
      <div className="font-semibold text-gray-900 text-xs mb-1.5">Legend</div>
      {items.map((it,i)=>(<div key={i} className="flex items-center gap-2 py-0.5 text-xs">
        <span className="w-5 h-3 rounded-sm flex-shrink-0" style={{backgroundColor:it.color}} />
        <span className="text-gray-600">{it.label}</span>
      </div>))}
    </div>
  )
}
