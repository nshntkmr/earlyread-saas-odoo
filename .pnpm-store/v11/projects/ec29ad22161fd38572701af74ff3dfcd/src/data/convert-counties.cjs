// Offline conversion: us-atlas counties-10m TopoJSON -> GeoJSON FeatureCollection
// with per-feature GEOID (5-digit county FIPS) + STATEFP (2-digit state FIPS).
// Coordinates rounded to 4 decimals (~11 m) — ample for a national choropleth,
// meaningfully smaller payload. Run from the react app root so Node resolves
// topojson-client from node_modules:
//   node src/data/convert-counties.cjs counties-10m.json src/data/us-counties-10m.json 4
const fs = require('fs')
const { feature } = require('topojson-client')

const [, , inPath, outPath, precArg] = process.argv
const PREC = precArg != null ? parseInt(precArg, 10) : 4
const topo = JSON.parse(fs.readFileSync(inPath, 'utf8'))
const fc = feature(topo, topo.objects.counties)

const factor = Math.pow(10, PREC)
const round = n => Math.round(n * factor) / factor
function roundCoords(c) {
  if (typeof c[0] === 'number') return [round(c[0]), round(c[1])]
  return c.map(roundCoords)
}

let kept = 0
for (const f of fc.features) {
  const id = String(f.id).padStart(5, '0')
  f.id = id
  f.properties = {
    name: (f.properties && f.properties.name) ? f.properties.name : '',
    GEOID: id,
    STATEFP: id.slice(0, 2),
  }
  if (PREC >= 0 && f.geometry && f.geometry.coordinates) {
    f.geometry.coordinates = roundCoords(f.geometry.coordinates)
  }
  kept++
}

fs.writeFileSync(outPath, JSON.stringify(fc))
console.error(`wrote ${kept} counties -> ${outPath} (precision=${PREC})`)
