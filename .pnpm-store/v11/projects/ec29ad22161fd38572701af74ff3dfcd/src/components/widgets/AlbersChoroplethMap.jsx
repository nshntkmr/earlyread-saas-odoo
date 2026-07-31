import React, { useState, useEffect, useMemo } from 'react'
import { geoAlbersUsa, geoPath } from 'd3-geo'
import { shouldUseAllZeroNoData } from './choroplethDataState'

// ═════════════════════════════════════════════════════════════════════════════
// AlbersChoroplethMap — open-source SVG/D3 choropleth (Image-2 fidelity)
// ═════════════════════════════════════════════════════════════════════════════
// geoAlbersUsa gives the exact US projection WITH Alaska/Hawaii insets, unlike
// MapLibre's WebMercator. Uses committed GeoJSON (no tile/basemap dependency).
// Fixed viewBox + responsive width → no zero-dimension first-render; the SVG
// scales to the card. Hover tooltip is positioned from client/mouse coords (NOT
// projected SVG coords, which live in viewBox space). No MapLibre import here, so
// SVG-only choropleth widgets never pull the MapLibre chunk.
//
// Backend payload contract (from _build_map_choropleth):
//   choropleth_data       { regionKey: number | null }   // null = no data (kept distinct from 0)
//   choropleth_popup_data { regionKey: { col: val, ... } }
//   choropleth_domain     { min, max, mid }               // computed excluding nulls
//   geo_level             'state' | 'county'              // authoritative for geometry
//   join_property         'STUSPS' | 'GEOID'              // feature.properties[join_property]
//   map_config            styling flags
// ═════════════════════════════════════════════════════════════════════════════

const VBW = 960
const VBH = 600
// Default sequential ramp (used when no custom colors configured).
const DEFAULT_STOPS = ['#f7fbff', '#c6dbef', '#6baed6', '#2171b5', '#08306b']
// US territory state-FIPS prefixes (AS, GU, MP, PR, VI) — excluded unless opted in.
const TERRITORY_FIPS = new Set(['60', '66', '69', '72', '78'])

const csv = s => (s || '').split(',').map(x => x.trim()).filter(Boolean)
const fmt = v => {
  if (v == null) return '—'
  const n = Number(v)
  if (isNaN(n)) return String(v)
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toLocaleString()
}
const hexToRgb = h => {
  h = String(h || '').replace('#', '')
  if (h.length === 3) h = h.split('').map(c => c + c).join('')
  if (h.length !== 6) return null
  const n = parseInt(h, 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
const lerp = (a, b, t) => Math.round(a + (b - a) * t)

// Absolute planar area of a ring (shoelace) — used to detect DEGENERATE rings.
function ringArea(r) {
  let a = 0
  for (let i = 0, n = r.length; i < n; i++) { const p = r[i], q = r[(i + 1) % n]; a += p[0] * q[1] - q[0] * p[1] }
  return Math.abs(a / 2)
}
// Some source polygons (e.g. Virginia in us-states.json) carry a DEGENERATE
// sub-polygon: a ring with zero area (collinear / duplicate points). geoAlbersUsa
// renders a zero-area ring as its spherical COMPLEMENT — one giant path that
// fills the ENTIRE map (the "purple blob" bug). Drop zero-area sub-polygons so
// only real land renders. Cheap: only MultiPolygons with a bad part are rebuilt.
function sanitizeFeature(f) {
  const gm = f && f.geometry
  if (!gm || gm.type !== 'MultiPolygon') return f
  const kept = gm.coordinates.filter(poly => poly[0] && ringArea(poly[0]) > 1e-9)
  if (kept.length === gm.coordinates.length) return f
  return { ...f, geometry: { type: 'MultiPolygon', coordinates: kept } }
}

// Build the value→color scale for the active scale mode.
//   linear   — raw value across [min,max] (default; identical to the prior scale).
//   log      — log1p-compressed so a single huge outlier doesn't flatten the rest.
//   quantile — equal-count buckets (color by rank); best for skewed data.
// Returns { scale, breakpoints } — breakpoints is the sorted bucket-boundary
// array for quantile mode (so the legend can show honest ranges), else null.
function buildScale(dom, rawStops, mode, values) {
  const rgbs = rawStops.map(hexToRgb).filter(Boolean)
  const min = dom.min, max = dom.max
  const colorAt = (t) => {
    if (rgbs.length < 2) return rawStops[rawStops.length - 1] || '#2171b5'
    t = Math.max(0, Math.min(1, t))            // clamp to [0,1]
    const seg = t * (rgbs.length - 1)
    const i = Math.min(Math.floor(seg), rgbs.length - 2)
    const f = seg - i
    const a = rgbs[i], b = rgbs[i + 1]
    return `rgb(${lerp(a[0], b[0], f)},${lerp(a[1], b[1], f)},${lerp(a[2], b[2], f)})`
  }
  // Degenerate domain (all equal, or bad bounds) → single flat color.
  if (!(max > min)) {
    const only = rawStops[rawStops.length - 1] || '#2171b5'
    return { scale: () => only, breakpoints: null }
  }

  if (mode === 'log') {
    const denom = Math.log1p(max - min) || 1
    return {
      scale: (v) => {
        if (v == null || !isFinite(v)) return null      // null/NaN → no-data
        return colorAt(Math.log1p(Math.max(0, v - min)) / denom)  // only positive normalized input
      },
      breakpoints: null,
    }
  }

  if (mode === 'quantile') {
    const sorted = (values || [])
      .filter(v => v != null && isFinite(v)).slice().sort((a, b) => a - b)
    // Interpolate across MANY buckets (not just the stop count) so even a 2-stop
    // ramp reads as a smooth low→high gradient rather than a 2-tone blob.
    const nBuckets = Math.max(6, rgbs.length)
    const breakpoints = []
    if (sorted.length) {
      for (let i = 1; i < nBuckets; i++) {
        const idx = Math.floor((i / nBuckets) * (sorted.length - 1))
        breakpoints.push(sorted[Math.max(0, Math.min(sorted.length - 1, idx))])
      }
    }
    const bucketColor = (b) => colorAt(b / Math.max(1, nBuckets - 1))
    return {
      scale: (v) => {
        if (v == null || !isFinite(v)) return null
        let b = 0
        while (b < breakpoints.length && v > breakpoints[b]) b++
        return bucketColor(b)
      },
      breakpoints: breakpoints.length ? breakpoints : null,
    }
  }

  // linear (default)
  return {
    scale: (v) => (v == null || !isFinite(v) ? null : colorAt((v - min) / (max - min))),
    breakpoints: null,
  }
}

// Inverse of the selection scale: a slider position t∈[0,1] → a real value.
// Mirrors buildScale's forward mapping so the interactive-legend handle spreads
// data the SAME way the colors do:
//   linear   — t maps straight across [min,max].
//   log      — de-compress log1p, so low-value regions occupy more of the track.
//   quantile — value at rank t (sorted[t*(n-1)]), so equal drag = equal # regions.
// Labels always print the returned raw value, so the axis stays honest.
function valueAtPos(dom, sorted, scale, t) {
  t = Math.max(0, Math.min(1, t))
  if (!dom || !(dom.max > dom.min)) return dom ? dom.min : 0
  if (scale === 'log') return dom.min + Math.expm1(t * Math.log1p(dom.max - dom.min))
  if (scale === 'quantile' && sorted && sorted.length) {
    const i = Math.round(t * (sorted.length - 1))
    return sorted[Math.max(0, Math.min(sorted.length - 1, i))]
  }
  return dom.min + t * (dom.max - dom.min)   // linear
}

// ── SVG zoom (buttons + wheel/pinch, no pan) ─────────────────────────────────
// Zoom is a <g transform="translate(x y) scale(k)"> around the fixed viewBox.
// k=1 → identity (x=y=0), so an un-zoomed map is byte-identical to before.
const Z_MIN = 1, Z_MAX = 8
// Keep the scaled content covering the whole viewBox — no empty gutters, and at
// k=1 this forces x=y=0 (perfect identity).
function clampZoom(k, x, y) {
  k = Math.max(Z_MIN, Math.min(Z_MAX, k))
  if (k <= 1) return { k: 1, x: 0, y: 0 }
  return {
    k,
    x: Math.min(0, Math.max(VBW * (1 - k), x)),
    y: Math.min(0, Math.max(VBH * (1 - k), y)),
  }
}
// Scale by `factor` while holding the focal point (fx,fy) — in viewBox coords —
// visually fixed. Used by both the +/- buttons (focal = centre) and the wheel
// (focal = cursor), so zooming feels anchored where you act.
function zoomAround(prev, factor, fx, fy) {
  const k2 = Math.max(Z_MIN, Math.min(Z_MAX, prev.k * factor))
  if (k2 === prev.k) return prev
  const x2 = fx - k2 * (fx - prev.x) / prev.k
  const y2 = fy - k2 * (fy - prev.y) / prev.k
  return clampZoom(k2, x2, y2)
}
// Zoom-control button box size by preset (px). Numeric override clamped 28–64.
const ZOOM_SIZES = { compact: 32, small: 38, medium: 44, large: 52 }
function zoomBtnPx(v) {
  if (ZOOM_SIZES[v]) return ZOOM_SIZES[v]
  const n = Number(v)
  return isFinite(n) && n > 0 ? Math.max(28, Math.min(64, n)) : 44
}

// Inline SVG glyphs (currentColor + strokeWidth) — crisp at any button size,
// no icon-font dependency. s = pixel size.
const IcoPlus = ({ s }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
  </svg>
)
const IcoMinus = ({ s }) => (
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path d="M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
  </svg>
)
const IcoMove = ({ s }) => (   // pan tool — 4-way move arrows
  <svg width={s} height={s} viewBox="0 0 24 24" fill="none" aria-hidden="true"
    stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v18M3 12h18" />
    <path d="M12 3 9.5 5.5M12 3l2.5 2.5M12 21l-2.5-2.5M12 21l2.5-2.5M3 12l2.5-2.5M3 12l2.5 2.5M21 12l-2.5-2.5M21 12l2.5 2.5" />
  </svg>
)
const IcoGrip = ({ s }) => (   // drag handle
  <svg width={s} height={s} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <circle cx="9" cy="7" r="1.4" /><circle cx="15" cy="7" r="1.4" />
    <circle cx="9" cy="12" r="1.4" /><circle cx="15" cy="12" r="1.4" />
    <circle cx="9" cy="17" r="1.4" /><circle cx="15" cy="17" r="1.4" />
  </svg>
)

export default function AlbersChoroplethMap({ data, height, name, widgetId = null, onDrill, drillable = false, drilledState = null, onCrossFilter }) {
  const cfg = data?.map_config || {}
  const geoLevel = data?.geo_level || cfg.choropleth_level || 'state'
  const joinProp = data?.join_property || (geoLevel === 'county' ? 'GEOID' : 'STUSPS')
  const regionData = data?.choropleth_data || {}
  const popupData = data?.choropleth_popup_data || {}

  const includeTerr = cfg.choropleth_include_territories === true
  const stops = (cfg.choropleth_color_start && cfg.choropleth_color_end)
    ? [cfg.choropleth_color_start,
       ...(cfg.choropleth_color_mid ? [cfg.choropleth_color_mid] : []),
       cfg.choropleth_color_end]
    : DEFAULT_STOPS
  const noDataColor = cfg.choropleth_no_data_color || '#e9e7ef'
  // Strictly opt-in for backward compatibility. NULL regions always retain
  // their existing no-data behavior; this flag only handles a numeric dataset
  // whose complete finite value set is exactly zero.
  const allZeroAsNoData = cfg.choropleth_all_zero_as_no_data === true
  const borderColor = cfg.choropleth_border_color || '#ffffff'
  const borderWidth = cfg.choropleth_border_width != null ? Number(cfg.choropleth_border_width) : 0.7
  const fillOpacity = cfg.choropleth_fill_opacity != null ? Number(cfg.choropleth_fill_opacity) : 1
  const hoverCols = csv(cfg.choropleth_hover_columns || cfg.popup_columns)
  const hoverEnabled = cfg.choropleth_hover_enabled !== false
  const legendStyle = cfg.choropleth_legend_style || 'steps'
  const legendPos = cfg.choropleth_legend_position || 'bottom'
  const legendTitle = cfg.choropleth_legend_title || ''
  // Human label for the metric shown in the hover tooltip + legend (e.g.
  // "Volume — State", "Penetration per 1k"). Priority: SQL-driven `metric_label`
  // column (per scope tab, surfaced by the backend) > widget Metric Label flag >
  // Legend Title > none. So the tooltip never shows the raw "value" column name,
  // and each scope tab can carry its own label straight from its SQL.
  const metricLabel = data?.metric_label || cfg.choropleth_metric_label || legendTitle || ''
  // Value→color scale: 'linear' (default) | 'log' | 'quantile'. Log/quantile
  // spread skewed data so a single outlier doesn't flatten the palette.
  const scaleMode = cfg.choropleth_scale_mode || 'linear'
  // Region click behavior: 'drill' (default) | 'cross_filter' | 'popup'.
  const clickAction = cfg.choropleth_click_action || 'drill'
  const crossFilterParam = cfg.choropleth_click_filter_param || ''
  const crossFilterCol = cfg.choropleth_click_filter_column || ''
  // County-level clicks can target a DIFFERENT page filter (e.g. FIPS_COUNTY)
  // than state-level clicks — set via the *_county flags. Blank county param →
  // county clicks fall back to the base param/column (pre-existing behavior).
  const crossFilterParamCounty = cfg.choropleth_click_filter_param_county || ''
  const crossFilterColCounty = cfg.choropleth_click_filter_column_county || ''

  // Interactive legend (drag-to-filter). Default OFF → the static legend, so
  // every existing map is byte-identical until an admin opts in. Purely visual:
  // dragging changes region opacity, no data reload.
  const legendInteractive = cfg.choropleth_legend_interactive === true
  const legendMode = cfg.choropleth_legend_mode || 'range'          // 'range' | 'threshold'
  const legendHighlight = cfg.choropleth_legend_highlight || 'dim_others'  // 'dim_others' | 'outline'
  const legendMinLabel = cfg.choropleth_legend_min_label || ''
  const legendMaxLabel = cfg.choropleth_legend_max_label || ''
  // Handle position→value mapping. 'auto' follows the COLOR scale mode so skewed
  // data (quantile/log) spreads evenly across the track instead of bunching all
  // the low-value regions into the first sliver. Labels always show real values.
  const selScaleRaw = cfg.choropleth_legend_selection_scale || 'auto'
  const selScale = selScaleRaw === 'auto' ? scaleMode : selScaleRaw
  // Floating zoom control + wheel/pinch zoom. Default ON. Off = fixed view.
  const zoomControl = cfg.choropleth_zoom_control !== false
  const zoomPosition = cfg.choropleth_zoom_control_position || 'top_right'
  const zoomBtnSize = zoomBtnPx(cfg.choropleth_zoom_control_size || 'medium')
  const zoomGlyph = Math.round(zoomBtnSize * 0.5)
  const zoomDraggable = cfg.choropleth_zoom_draggable !== false   // default on
  const panEnabled = cfg.choropleth_pan_enabled === true          // default off

  const [geo, setGeo] = useState(null)
  const [tip, setTip] = useState(null)
  const svgRef = React.useRef(null)
  const wrapRef = React.useRef(null)   // map viewport (clamps the draggable control)
  const pillRef = React.useRef(null)   // the control itself
  const ctlDrag = React.useRef(null)   // in-flight control-reposition drag
  const panDrag = React.useRef(null)   // in-flight map pan drag
  // Zoom transform for the map <g>. { k:1, x:0, y:0 } = identity (no zoom).
  const [zoom, setZoom] = useState({ k: 1, x: 0, y: 0 })
  const [zoomHover, setZoomHover] = useState(null)   // 'in'|'out'|'pan'|'grip'|null
  const [panMode, setPanMode] = useState(false)      // hand-tool active → drag pans
  // Custom (dragged) control position {left,top} px within the map viewport, or
  // null = use the anchor preset. Seeded from localStorage per widget id.
  const lsKey = widgetId != null ? `pv_choro_zoomctl_${widgetId}` : null
  const [ctlPos, setCtlPos] = useState(() => {
    if (!lsKey) return null
    try { const s = window.localStorage.getItem(lsKey); return s ? JSON.parse(s) : null } catch (_) { return null }
  })
  // Interactive-legend selection as track POSITIONS in [0,1] (lo, hi). Real value
  // cutoffs are derived from these via valueAtPos(selScale), so the labels show
  // raw values even when the handle axis is log/quantile. Full range = no dimming.
  const [hlPos, setHlPos] = useState({ lo: 0, hi: 1 })

  // Lazy-load geometry by level. Each file is its own async chunk, so the
  // 1.7 MB counties GeoJSON only loads when a county view is actually rendered.
  useEffect(() => {
    let cancelled = false
    setGeo(null)
    const src = geoLevel === 'county'
      ? import('../../data/us-counties-10m.json')
      : import('../../data/us-states.json')
    src
      .then(m => { if (!cancelled) setGeo(m.default || m) })
      .catch(() => { if (!cancelled) setGeo({ type: 'FeatureCollection', features: [] }) })
    return () => { cancelled = true }
  }, [geoLevel])

  // Reset the interactive selection to "full" whenever the underlying data
  // changes (tab switch, state drill, filter apply) — the value domain shifts,
  // so a carried-over band would highlight the wrong regions.
  useEffect(() => { setHlPos({ lo: 0, hi: 1 }) }, [
    geoLevel, drilledState, data?.metric_label,
    data?.choropleth_domain?.min, data?.choropleth_domain?.max,
  ])

  // Reset zoom + exit pan mode whenever the geometry changes (level switch or
  // state drill) — the projection refits, so a leftover transform is meaningless.
  useEffect(() => { setZoom({ k: 1, x: 0, y: 0 }); setPanMode(false) }, [geoLevel, drilledState])

  // Keep a dragged control inside the viewport when the widget resizes, so it
  // "cannot disappear" at narrow widths. No-op when using an anchor preset.
  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || !zoomDraggable || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(() => {
      setCtlPos(prev => {
        const pill = pillRef.current
        if (!prev || !pill) return prev
        const wr = wrap.getBoundingClientRect(), pr = pill.getBoundingClientRect()
        const l = Math.max(0, Math.min(Math.max(0, wr.width - pr.width), prev.left))
        const t = Math.max(0, Math.min(Math.max(0, wr.height - pr.height), prev.top))
        return (l === prev.left && t === prev.top) ? prev : { left: l, top: t }
      })
    })
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [zoomDraggable])

  // Wheel / trackpad-pinch zoom on the SVG. Native non-passive listener so we can
  // preventDefault (React's onWheel is passive → can't stop page scroll). Zooms
  // around the cursor. No drag-to-pan — keeps clicks unambiguous for drill.
  useEffect(() => {
    const el = svgRef.current
    if (!el || !zoomControl) return
    const onWheel = (e) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      if (!r.width || !r.height) return
      const fx = ((e.clientX - r.left) / r.width) * VBW
      const fy = ((e.clientY - r.top) / r.height) * VBH
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15
      setZoom(prev => zoomAround(prev, factor, fx, fy))
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [zoomControl, geo])   // geo: rebind once geometry loads and the <svg> mounts

  const view = useMemo(() => {
    if (!geo || !geo.features) return null
    let feats = geo.features
    if (!includeTerr) {
      feats = feats.filter(f => !TERRITORY_FIPS.has(String(f.id).slice(0, 2)))
    }
    // Drill: when a state is selected on the county map, show only its counties
    // (matched by STATEFP, fallback to the first 2 digits of the 5-digit id) and
    // refit the projection to that subset — the state-drill "zoom in".
    if (geoLevel === 'county' && drilledState) {
      const fips = String(drilledState).padStart(2, '0')
      feats = feats.filter(f => (f.properties?.STATEFP || String(f.id).slice(0, 2)) === fips)
    }
    if (!feats.length) return null
    // Drop degenerate (zero-area) sub-polygons that geoAlbersUsa would smear
    // across the whole map (see sanitizeFeature).
    feats = feats.map(sanitizeFeature)

    // Domain from the payload, else derived excluding nulls.
    let dom = data?.choropleth_domain
    if (!dom || dom.min == null || dom.max == null || dom.min === dom.max) {
      const vals = Object.values(regionData)
        .filter(v => v != null && !isNaN(Number(v)))
        .map(Number)
      dom = vals.length
        ? { min: Math.min(...vals), max: Math.max(...vals), mid: (Math.min(...vals) + Math.max(...vals)) / 2 }
        : { min: 0, max: 1, mid: 0.5 }
    }

    const proj = geoAlbersUsa().fitSize([VBW, VBH], { type: 'FeatureCollection', features: feats })
    const pg = geoPath(proj)
    // All numeric region values — needed for quantile bucketing + the
    // interactive-legend quantile handle inverse (value at a given rank).
    const allVals = Object.values(regionData)
      .filter(v => v != null && !isNaN(Number(v))).map(Number)
    const sorted = allVals.slice().sort((a, b) => a - b)
    const allZeroNoData = shouldUseAllZeroNoData(allZeroAsNoData, allVals)
    const { scale, breakpoints } = buildScale(dom, stops, scaleMode, allVals)

    const paths = feats.map(f => {
      const key = f.properties?.[joinProp] ?? f.id
      const raw = regionData[key]
      const v = raw == null || isNaN(Number(raw)) ? null : Number(raw)
      // Drill identity of a STATE feature: 2-letter code + 2-digit FIPS + name.
      const drill = geoLevel === 'state'
        ? {
            code: f.properties?.STUSPS || key,
            fips: String(f.id).padStart(2, '0'),
            name: f.properties?.name || key,
          }
        : null
      return { d: pg(f), key, label: f.properties?.name || key, v, drill }
    })
    return { paths, dom, scale, breakpoints, sorted, allZeroNoData }
  }, [geo, geoLevel, drilledState, includeTerr, joinProp, regionData, data?.choropleth_domain, stops, scaleMode, allZeroAsNoData])

  if (!view) {
    return (
      <div style={{ height: height || 420, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>
        Loading map…
      </div>
    )
  }

  const onMove = (e, p) => {
    if (!hoverEnabled) return
    setTip({ x: e.clientX, y: e.clientY, label: p.label, v: p.v, props: popupData[p.key] || {} })
  }

  // 'drill_cross_filter' = a single click BOTH drills state→county AND applies
  // the page cross-filter (image-4 behaviour). 'drill' / 'cross_filter' keep the
  // single behaviours. Drill still fires only from a STATE view of a drill-capable
  // option; cross-filter fires at any level with a target param.
  const wantsDrill = clickAction === 'drill' || clickAction === 'drill_cross_filter'
  const wantsCross = clickAction === 'cross_filter' || clickAction === 'drill_cross_filter'
  const canDrill = wantsDrill && drillable && geoLevel === 'state' && typeof onDrill === 'function'
  const crossFilterEnabled = wantsCross
    && !!(crossFilterParam || crossFilterParamCounty)
    && typeof onCrossFilter === 'function'

  const handleRegionClick = (p) => {
    setTip(null)
    // Cross-filter AND drill can both fire from one click (drill_cross_filter).
    let crossFired = false
    if (crossFilterEnabled) {
      const props = popupData[p.key] || {}
      // Per-level target: county-level clicks use the *_county param/column
      // when configured (e.g. FIPS_COUNTY, blank column → join key = GEOID),
      // otherwise both levels use the base param/column.
      const useCounty = geoLevel === 'county' && !!crossFilterParamCounty
      const activeParam = useCounty ? crossFilterParamCounty : crossFilterParam
      const activeCol = useCounty ? crossFilterColCounty : crossFilterCol
      // Click value: the configured column when present; the region join key
      // ONLY when no column is configured. A configured-but-absent column
      // (no-data region, or a level whose SQL lacks it) must NO-OP — falling
      // back to the join key would send e.g. a county FIPS into a state param.
      let value = null
      if (activeCol) {
        if (props[activeCol] != null) value = props[activeCol]
      } else {
        value = p.key
      }
      // onCrossFilter returns false when it no-ops (e.g. value already applied).
      if (activeParam && value != null) crossFired = onCrossFilter(activeParam, value) === true
    }
    if (canDrill && p.drill) {
      // Second arg tells WidgetGrid this drill is COUPLED with a cross-filter
      // that ACTUALLY fired (drill_cross_filter). That click changes
      // filterValues, firing the grid's refetch effect, which must PRESERVE
      // this widget's drill rather than snap it back to states. A plain
      // 'drill' — or a skipped/no-opped cross-filter — passes false: only a
      // filterValues change can consume the guard flag, so arming it without
      // one leaves a stale guard that wrongly protects this widget on the
      // next unrelated Apply.
      onDrill(p.drill, crossFired)
    }
  }

  // Interactive-legend value cutoffs (null when off). Handle positions → real
  // values via the selection scale; threshold uses only the low handle (v ≥ lo).
  // At the default full range [0,1] this spans the whole domain → nothing dims.
  const hlCut = legendInteractive ? (() => {
    const a = valueAtPos(view.dom, view.sorted, selScale, hlPos.lo)
    if (legendMode === 'threshold') return { lo: a, hi: Infinity }
    const b = valueAtPos(view.dom, view.sorted, selScale, hlPos.hi)
    return { lo: Math.min(a, b), hi: Math.max(a, b) }
  })() : null
  const isHl = (v) => {
    if (!hlCut) return true       // interactive off → every region renders normally
    if (v == null) return true    // no-data is its own category — never dimmed
    return v >= hlCut.lo && v <= hlCut.hi
  }

  // +/- buttons zoom around the viewBox centre (screen centre stays put).
  const zoomBy = (dir) => () => setZoom(prev => zoomAround(prev, dir > 0 ? 1.5 : 1 / 1.5, VBW / 2, VBH / 2))
  const btnStyle = (which, extra) => {
    const active = which === 'pan' && panMode
    const hot = zoomHover === which || active
    return {
      width: zoomBtnSize, height: zoomBtnSize, border: 0, padding: 0, cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: active ? '#eef2ff' : (zoomHover === which ? '#f8f7ff' : 'transparent'),
      color: hot ? '#4f46e5' : '#334155', ...extra,
    }
  }
  // Anchor preset unless the user has dragged the control (then a custom {left,top}).
  const OFF = 12
  const posStyle = (zoomDraggable && ctlPos)
    ? { left: ctlPos.left, top: ctlPos.top }
    : zoomPosition === 'top_left' ? { top: OFF, left: OFF }
    : zoomPosition === 'bottom_right' ? { bottom: OFF, right: OFF }
    : zoomPosition === 'bottom_left' ? { bottom: OFF, left: OFF }
    : { top: OFF, right: OFF }

  // ── Map pan (only while the hand tool is active) ────────────────────────────
  const startPan = (e) => {
    if (!panMode) return
    const el = svgRef.current; if (!el) return
    const r = el.getBoundingClientRect()
    panDrag.current = { sx: e.clientX, sy: e.clientY, x0: zoom.x, y0: zoom.y, k: zoom.k, rw: r.width, rh: r.height }
    try { el.setPointerCapture(e.pointerId) } catch (_) {}
  }
  const movePan = (e) => {
    const d = panDrag.current; if (!d) return
    const dx = (e.clientX - d.sx) * (VBW / (d.rw || 1))
    const dy = (e.clientY - d.sy) * (VBH / (d.rh || 1))
    setZoom(clampZoom(d.k, d.x0 + dx, d.y0 + dy))   // clamp pins x=y=0 at k=1
  }
  const endPan = () => { panDrag.current = null }

  // ── Control reposition drag (grip handle) ───────────────────────────────────
  // stopPropagation throughout so the map never pans/zooms/clicks while moving it.
  const startCtlDrag = (e) => {
    e.stopPropagation(); e.preventDefault()
    const wrap = wrapRef.current, pill = pillRef.current
    if (!wrap || !pill) return
    const wr = wrap.getBoundingClientRect(), pr = pill.getBoundingClientRect()
    ctlDrag.current = {
      sx: e.clientX, sy: e.clientY, left: pr.left - wr.left, top: pr.top - wr.top,
      maxLeft: Math.max(0, wr.width - pr.width), maxTop: Math.max(0, wr.height - pr.height), last: null,
    }
    try { e.target.setPointerCapture(e.pointerId) } catch (_) {}
    setZoomHover('grip')
  }
  const moveCtlDrag = (e) => {
    const d = ctlDrag.current; if (!d) return
    e.stopPropagation()
    const l = Math.max(0, Math.min(d.maxLeft, d.left + (e.clientX - d.sx)))
    const t = Math.max(0, Math.min(d.maxTop, d.top + (e.clientY - d.sy)))
    d.last = { left: l, top: t }
    setCtlPos(d.last)
  }
  const endCtlDrag = (e) => {
    const d = ctlDrag.current; if (!d) return
    e.stopPropagation()
    if (d.last && lsKey) { try { window.localStorage.setItem(lsKey, JSON.stringify(d.last)) } catch (_) {} }
    ctlDrag.current = null
    setZoomHover(null)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
      <div ref={wrapRef} style={{ position: 'relative', width: '100%' }}>
      <svg ref={svgRef} viewBox={`0 0 ${VBW} ${VBH}`}
        style={{ width: '100%', height: 'auto', display: 'block',
                 cursor: panMode ? 'grab' : 'default', touchAction: panMode ? 'none' : undefined }}
        role="img" aria-label={`${name || 'Choropleth'} map`}
        onPointerDown={panMode ? startPan : undefined}
        onPointerMove={panMode ? movePan : undefined}
        onPointerUp={panMode ? endPan : undefined}
        onPointerCancel={panMode ? endPan : undefined}>
        <g transform={`translate(${zoom.x} ${zoom.y}) scale(${zoom.k})`}>
        {view.paths.map((p, i) => {
          // Interactive legend: fade non-matching regions (dim_others) or bolden
          // the matching ones (outline). No-op when the legend isn't interactive.
          const hl = isHl(p.v)
          const dimmed = legendInteractive && !hl && legendHighlight === 'dim_others'
          const outlined = legendInteractive && hl && legendHighlight === 'outline'
          // Pan mode suppresses region clicks so a pan-drag never drills/cross-filters.
          const clickable = !panMode && (crossFilterEnabled || (canDrill && p.drill))
          return (
          <path key={i} d={p.d}
            fill={(p.v == null || view.allZeroNoData)
              ? noDataColor
              : (view.scale(p.v) || noDataColor)}
            fillOpacity={dimmed ? fillOpacity * 0.2 : fillOpacity}
            stroke={outlined ? '#1f2937' : borderColor}
            strokeWidth={outlined ? Math.max(borderWidth, 1.6) : borderWidth}
            vectorEffect="non-scaling-stroke"
            style={{ transition: 'fill .12s, fill-opacity .12s', cursor: panMode ? 'inherit' : (clickable ? 'pointer' : 'default') }}
            onMouseMove={e => onMove(e, p)}
            onMouseLeave={() => setTip(null)}
            onClick={clickable ? () => handleRegionClick(p) : undefined} />
          )
        })}
        </g>
      </svg>
      {/* Floating zoom control — grip (if draggable) + zoom in/out + optional pan
          toggle. Absolute over the map viewport (no layout height). Inline styles
          so it ships with the JS build alone (no posterra.css regen). */}
      {zoomControl && (
        <div ref={pillRef}
          style={{ position: 'absolute', ...posStyle, display: 'flex', flexDirection: 'column',
                   width: zoomBtnSize, overflow: 'hidden', background: 'rgba(255,255,255,.94)',
                   border: '1px solid #e2e8f0', borderRadius: 12, userSelect: 'none',
                   boxShadow: '0 10px 24px rgba(15,23,42,.16)', zIndex: 5 }}>
          {zoomDraggable && (
            <div title="Drag to move" onPointerDown={startCtlDrag} onPointerMove={moveCtlDrag}
              onPointerUp={endCtlDrag} onPointerCancel={endCtlDrag}
              style={{ height: Math.round(zoomBtnSize * 0.44), display: 'flex', alignItems: 'center',
                       justifyContent: 'center', cursor: 'grab', touchAction: 'none', background: '#faf9ff',
                       color: zoomHover === 'grip' ? '#4f46e5' : '#94a3b8', borderBottom: '1px solid #e2e8f0' }}>
              <IcoGrip s={Math.round(zoomBtnSize * 0.42)} />
            </div>
          )}
          <button type="button" aria-label="Zoom in" onClick={zoomBy(1)}
            onMouseEnter={() => setZoomHover('in')} onMouseLeave={() => setZoomHover(null)}
            style={btnStyle('in')}><IcoPlus s={zoomGlyph} /></button>
          <button type="button" aria-label="Zoom out" onClick={zoomBy(-1)}
            onMouseEnter={() => setZoomHover('out')} onMouseLeave={() => setZoomHover(null)}
            style={btnStyle('out', { borderTop: '1px solid #e2e8f0' })}><IcoMinus s={zoomGlyph} /></button>
          {panEnabled && (
            <button type="button" aria-label={panMode ? 'Exit pan mode' : 'Pan mode'} aria-pressed={panMode}
              onClick={() => setPanMode(m => !m)}
              onMouseEnter={() => setZoomHover('pan')} onMouseLeave={() => setZoomHover(null)}
              style={btnStyle('pan', { borderTop: '1px solid #e2e8f0' })}><IcoMove s={zoomGlyph} /></button>
          )}
        </div>
      )}
      </div>

      {/* Interactive legend shows whenever it's ON, even if the static Legend
          Style is "none" — turning on drag-to-filter IS the intent to show a
          legend. When interactive is off, the old `!== 'none'` gate is unchanged. */}
      {(legendStyle !== 'none' || legendInteractive) && (
        <ChoroplethLegend style={legendStyle} dom={view.dom} stops={stops}
          title={metricLabel} pos={legendPos} noDataColor={noDataColor}
          mode={scaleMode} breakpoints={view.breakpoints}
          interactive={legendInteractive} legendMode={legendMode}
          selScale={selScale} sorted={view.sorted}
          hlPos={hlPos} setHlPos={setHlPos}
          minLabel={legendMinLabel} maxLabel={legendMaxLabel}
          allZeroNoData={view.allZeroNoData} />
      )}

      {tip && (
        <div style={{
          position: 'fixed', left: tip.x + 14, top: tip.y + 14, zIndex: 200,
          background: '#1e1b39', color: '#fff', borderRadius: 8, padding: '8px 11px',
          fontSize: 12, pointerEvents: 'none', boxShadow: '0 8px 24px rgba(0,0,0,.25)', maxWidth: 260,
        }}>
          <b>{tip.label}</b>
          <div style={{ color: '#c4bdf5', fontSize: 11, marginTop: 2 }}>
            {metricLabel ? `${metricLabel}: ` : ''}{fmt(tip.v)}
          </div>
          {hoverCols.map(spec => {
            // "column"        → "column: val"
            // "column:Label"  → "Label: val"
            // "column:"       → "val"  (raw line, e.g. a SQL-formatted detail string)
            const ci = spec.indexOf(':')
            const col = (ci >= 0 ? spec.slice(0, ci) : spec).trim()
            const label = ci >= 0 ? spec.slice(ci + 1).trim() : col
            if (tip.props[col] == null) return null
            return (
              <div key={spec} style={{ fontSize: 11, color: label ? '#fff' : '#c4bdf5' }}>
                {label ? `${label}: ` : ''}{String(tip.props[col])}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Legend: continuous gradient bar OR stepped swatches ──────────────────────
function ChoroplethLegend({ style, dom, stops, title, pos, noDataColor, mode = 'linear', breakpoints = null,
                            interactive = false, legendMode = 'range', selScale = 'linear', sorted = null,
                            hlPos = { lo: 0, hi: 1 }, setHlPos = () => {}, minLabel = '', maxLabel = '',
                            allZeroNoData = false }) {
  const align = (pos === 'top_right' || pos === 'bottom_right') ? 'flex-end' : 'flex-start'
  // An all-zero selection has no meaningful color range. When the widget opts
  // in, replace both static and interactive legends with an honest single-state
  // swatch. Tooltips still receive the underlying numeric zero.
  if (allZeroNoData) {
    return (
      <div style={{ padding: '8px 14px 12px', display: 'flex', flexDirection: 'column', alignItems: align }}>
        {title && (
          <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, marginBottom: 4 }}>{title}</div>
        )}
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#6b7280' }}>
          <i style={{ width: 14, height: 10, background: noDataColor, borderRadius: 2, display: 'inline-block' }} />
          all values 0
        </span>
      </div>
    )
  }
  // Interactive (drag-to-filter) legend replaces the static bar entirely.
  if (interactive) {
    return (
      <InteractiveChoroplethLegend
        dom={dom} stops={stops} sorted={sorted} selScale={selScale} legendMode={legendMode}
        hlPos={hlPos} setHlPos={setHlPos} title={title} mode={mode}
        minLabel={minLabel} maxLabel={maxLabel} align={align} />
    )
  }
  const isQuantile = mode === 'quantile' && Array.isArray(breakpoints) && breakpoints.length > 0
  // Honest heading: a skewed (log/quantile) scale must NOT read as a linear axis.
  const note = mode === 'quantile' ? '· quantile' : mode === 'log' ? '· log scale' : ''
  const headingText = [title, note].filter(Boolean).join(' ')
  const heading = headingText
    ? <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, marginBottom: 4 }}>{headingText}</div>
    : null
  const noDataSwatch = (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <i style={{ width: 14, height: 10, background: noDataColor, borderRadius: 2, display: 'inline-block' }} />no data
    </span>
  )

  // Quantile → rank-based buckets. Numbers would imply a linear axis, so show a
  // smooth low→high gradient bar (matches the graded fills) with plain end labels.
  if (isQuantile) {
    return (
      <div style={{ padding: '8px 14px 12px', display: 'flex', flexDirection: 'column', alignItems: align }}>
        {heading}
        <div style={{ width: '100%', maxWidth: 360 }}>
          <div style={{ height: 10, borderRadius: 5, background: `linear-gradient(to right, ${stops.join(',')})` }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#9ca3af', marginTop: 2 }}>
            <span>low</span><span>high</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '8px 14px 12px', display: 'flex', flexDirection: 'column', alignItems: align }}>
      {heading}
      {style === 'gradient' ? (
        <div style={{ width: '100%', maxWidth: 360 }}>
          <div style={{ height: 10, borderRadius: 5, background: `linear-gradient(to right, ${stops.join(',')})` }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#9ca3af', marginTop: 2 }}>
            <span>{fmt(dom.min)}</span><span>{fmt(dom.mid)}</span><span>{fmt(dom.max)}</span>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 10, color: '#6b7280' }}>
          {stops.map((c, i) => (
            <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <i style={{ width: 14, height: 10, background: c, borderRadius: 2, display: 'inline-block' }} />
              {fmt(dom.min + (dom.max - dom.min) * (i / Math.max(1, stops.length - 1)))}
            </span>
          ))}
          {noDataSwatch}
        </div>
      )}
    </div>
  )
}

// ── Interactive (drag-to-filter) legend ──────────────────────────────────────
// A gradient track with draggable handle(s). Dragging updates POSITIONS in [0,1]
// (owned by the parent so it can dim the map in lock-step). Value labels come
// from the positions via valueAtPos(selScale), so even a log/quantile handle
// axis prints real min / max / selected values. Pure client-side; no data reload.
function InteractiveChoroplethLegend({ dom, stops, sorted, selScale, legendMode, hlPos, setHlPos,
                                       title, mode, minLabel, maxLabel, align }) {
  const trackRef = React.useRef(null)
  const active = React.useRef(null)   // 'lo' | 'hi' | null — handle being dragged

  const posFromX = (clientX) => {
    const el = trackRef.current
    if (!el) return 0
    const r = el.getBoundingClientRect()
    return Math.max(0, Math.min(1, (clientX - r.left) / (r.width || 1)))
  }

  // Global listeners so a drag continues even when the pointer leaves the track.
  // Functional setHlPos + refs avoid stale closures, so the effect binds once.
  useEffect(() => {
    const move = (e) => {
      if (!active.current) return
      const t = Math.max(0, Math.min(1, (e.clientX - (trackRef.current?.getBoundingClientRect().left || 0))
        / (trackRef.current?.getBoundingClientRect().width || 1)))
      setHlPos(prev => ({ ...prev, [active.current]: t }))
    }
    const up = () => { active.current = null }
    document.addEventListener('pointermove', move)
    document.addEventListener('pointerup', up)
    return () => {
      document.removeEventListener('pointermove', move)
      document.removeEventListener('pointerup', up)
    }
  }, [setHlPos])

  const grabHandle = (which) => (e) => { e.stopPropagation(); active.current = which }
  const onTrackDown = (e) => {
    if (active.current) return
    const t = posFromX(e.clientX)
    if (legendMode === 'threshold') { setHlPos({ lo: t, hi: 1 }); active.current = 'lo' }
    else {
      const which = Math.abs(t - hlPos.lo) <= Math.abs(t - hlPos.hi) ? 'lo' : 'hi'
      setHlPos({ ...hlPos, [which]: t }); active.current = which
    }
  }

  // Track band + labels. Threshold: single low handle, band = [lo, 1] (≥ cutoff).
  const loT = legendMode === 'threshold' ? hlPos.lo : Math.min(hlPos.lo, hlPos.hi)
  const hiT = legendMode === 'threshold' ? 1 : Math.max(hlPos.lo, hlPos.hi)
  const loV = valueAtPos(dom, sorted, selScale, hlPos.lo)
  const hiV = valueAtPos(dom, sorted, selScale, hlPos.hi)
  const selText = legendMode === 'threshold'
    ? `≥ ${fmt(loV)}`
    : `${fmt(Math.min(loV, hiV))} – ${fmt(Math.max(loV, hiV))}`
  const note = mode === 'quantile' ? '· quantile' : mode === 'log' ? '· log scale' : ''
  const headingText = [title, note].filter(Boolean).join(' ')

  const handle = (leftT, which) => (
    <div onPointerDown={grabHandle(which)}
      style={{ position: 'absolute', top: '50%', left: `${leftT * 100}%`, width: 16, height: 16,
               borderRadius: '50%', background: '#fff', border: '2px solid #1f2937',
               transform: 'translate(-50%,-50%)', cursor: 'grab', touchAction: 'none', zIndex: 3,
               boxShadow: '0 1px 3px rgba(0,0,0,.25)' }} />
  )

  return (
    <div style={{ padding: '8px 14px 12px', display: 'flex', flexDirection: 'column', alignItems: align }}>
      {headingText &&
        <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, marginBottom: 4 }}>{headingText}</div>}
      <div style={{ width: '100%', maxWidth: 360 }}>
        <div ref={trackRef} onPointerDown={onTrackDown}
          style={{ position: 'relative', height: 14, borderRadius: 7, cursor: 'pointer',
                   background: `linear-gradient(to right, ${stops.join(',')})` }}>
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: `${loT * 100}%`,
                        background: '#fff', opacity: 0.66, borderRadius: '7px 0 0 7px', zIndex: 1 }} />
          <div style={{ position: 'absolute', top: 0, bottom: 0, right: 0, width: `${(1 - hiT) * 100}%`,
                        background: '#fff', opacity: 0.66, borderRadius: '0 7px 7px 0', zIndex: 1 }} />
          {handle(hlPos.lo, 'lo')}
          {legendMode === 'range' && handle(hlPos.hi, 'hi')}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, marginTop: 3 }}>
          <span style={{ color: '#9ca3af' }}>{minLabel || fmt(dom.min)}</span>
          <span style={{ color: '#4f46e5', fontWeight: 600 }}>{selText}</span>
          <span style={{ color: '#9ca3af' }}>{maxLabel || fmt(dom.max)}</span>
        </div>
      </div>
    </div>
  )
}
