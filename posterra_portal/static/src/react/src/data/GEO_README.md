# Bundled US geometry (choropleth maps)

These GeoJSON files back the SVG/D3 `geoAlbersUsa` choropleth renderer
(`components/widgets/AlbersChoroplethMap.jsx`). They are committed so the map has
**no runtime tile/basemap dependency** and never calls out to a CDN.

## Files

| File | Level | Features | Size (raw / gzip) | Join key |
|------|-------|----------|-------------------|----------|
| `us-states.json`       | State  | 52 (50 + DC + PR) | 88 KB / ~29 KB | `properties.STUSPS` (2-letter) — fallback `id` (2-digit FIPS) |
| `us-counties-10m.json` | County | 3231              | 1.69 MB / ~0.46 MB | `properties.GEOID` (5-digit FIPS) — fallback `id` |

Both are lazy-`import()`-ed only when their level is rendered, so the states file
loads for the default state view and the (larger) counties file loads only when a
county tab is active or a user drills into a state.

### Feature properties

- **states**: `{ name, density, STUSPS }`, `id` = 2-digit state FIPS (`"06"` = CA).
- **counties**: `{ name, GEOID, STATEFP }`, `id` = 5-digit county FIPS (`"06037"` = LA County).
  `STATEFP` = first 2 digits of `GEOID`; used to filter a state's counties on drill
  (`feature.properties.STATEFP === <2-digit state fips>`).

## Source & license

- Source: **[us-atlas](https://github.com/topojson/us-atlas)** `@3` — `counties-10m.json`
  (TopoJSON), derived from the US Census Bureau cartographic boundary files.
- License: **ISC** (us-atlas) / US Census data is **public domain**.
- `us-states.json` was produced earlier from the same `states` object.

## Regenerating `us-counties-10m.json`

Requires the `topojson-client` devDependency (already in `package.json`).

```bash
# 1. Fetch the source TopoJSON (842 KB)
curl -o counties-10m.json https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json

# 2. Convert TopoJSON -> GeoJSON, inject GEOID + STATEFP, round coords to 4 decimals
node src/data/convert-counties.cjs counties-10m.json src/data/us-counties-10m.json 4
```

`convert-counties.cjs` (committed alongside) uses `topojson-client`'s `feature()` to
decode arcs into a `FeatureCollection`, sets `properties.GEOID`/`properties.STATEFP`
from the 5-digit id, and rounds coordinates to 4 decimals (~11 m — imperceptible on a
national/state choropleth) which cuts the raw payload from 3.0 MB to 1.7 MB. Pass `-1`
as the last arg to keep full precision.

**Size gate:** at 0.46 MB gzipped the single national file is well under the ~2-3 MB
gzip budget, so no per-state chunk split is needed. If a future higher-resolution
source pushes it over budget, split into `data/us-counties/{STATEFP}.json` and load by
FIPS with a **Vite-safe** `import.meta.glob('./data/us-counties/*.json')` map (NOT a
variable `import()` path, which Vite cannot statically analyze).
