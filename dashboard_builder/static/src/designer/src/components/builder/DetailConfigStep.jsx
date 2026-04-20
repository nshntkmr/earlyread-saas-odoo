import React from 'react'
import CustomSqlEditor from './CustomSqlEditor'
import MasterRowLayoutStep from './MasterRowLayoutStep'

/**
 * DetailConfigStep
 *
 * Configures the detail panel for a ranked_detail_list widget.
 *
 * Four sections:
 *   A. Row Key — which master SQL column identifies each row
 *   B. Shared Detail SQL — optional fallback SQL used by any tile or the
 *      sub-list that doesn't have its own SQL.
 *   C. Detail Tiles — up to 3 tiles. Each tile has:
 *        - Tile type (bar/line variants, KPI variants)
 *        - Optional OWN SQL (override — tile runs its own query). When not
 *          set, uses the shared Detail SQL from section B.
 *   D. Sub-List — reuses MasterRowLayoutStep for row layout. Has an
 *      optional OWN SQL (same pattern as tiles). YOU indicator config.
 *
 * Architecture rule: every "data source" picks from its OWN test result
 * when own SQL is configured; otherwise from the shared SQL's test result.
 */
export default function DetailConfigStep({
  detailConfig = {},
  onUpdate,
  masterColumns = [],
  masterSampleRow = null,    // first row of master query test result {col: value, ...}
  apiBase,
  appContext,
}) {
  const cfg = detailConfig || {}

  // Shared SQL + its test result
  const sharedSql = cfg.sql || ''
  const sharedTestResult = cfg._testResult || null
  const sharedColumns = sharedTestResult?.columns || []
  const sharedSampleRow = (sharedTestResult?.rows && sharedTestResult.rows[0])
    ? Object.fromEntries(sharedTestResult.columns.map((c, i) => [c, sharedTestResult.rows[0][i]]))
    : null

  const tiles = cfg.tiles || []
  const sublist = cfg.sublist || {}

  // Helpers
  const updateSublist = (partial) => {
    onUpdate({ sublist: { ...sublist, ...partial } })
  }

  const updateTile = (idx, partial) => {
    const newTiles = [...tiles]
    newTiles[idx] = { ...newTiles[idx], ...partial }
    onUpdate({ tiles: newTiles })
  }

  const addTile = () => {
    if (tiles.length >= 3) return
    onUpdate({
      tiles: [...tiles, {
        title: `Tile ${tiles.length + 1}`,
        type: 'bar',
        xColumn: '',
        yColumn: '',
        color: '#0d9488',
        showLabels: true,
        showLegend: false,
        ownSql: false,
      }],
    })
  }

  const removeTile = (idx) => {
    onUpdate({ tiles: tiles.filter((_, i) => i !== idx) })
  }

  const insertIsYouHelper = () => {
    const snippet = ', CASE WHEN <your_column> = %(selected_hha_ccn)s THEN 1 ELSE 0 END AS is_you'
    onUpdate({ sql: sharedSql.trimEnd() + snippet })
  }

  // Sub-list effective columns/sample — own SQL result if set, else shared
  const sublistOwnSql = !!sublist.ownSql
  const sublistColumns = sublistOwnSql
    ? (sublist._testResult?.columns || [])
    : sharedColumns
  const sublistSampleRow = sublistOwnSql
    ? (sublist._testResult?.rows && sublist._testResult.rows[0]
        ? Object.fromEntries(sublist._testResult.columns.map((c, i) => [c, sublist._testResult.rows[0][i]]))
        : null)
    : sharedSampleRow

  return (
    <div className="wb-detail-config-step">
      <h3 className="wb-step-title">Detail Config</h3>
      <p className="wb-step-hint">
        Configure what appears when a user expands a row: tiles (bar/line/KPI)
        and a nested sub-list. Each tile and the sub-list can use the shared
        Detail SQL below, OR write its own SQL for maximum flexibility.
      </p>

      {/* ── Section A: Row Key ──────────────────────────────── */}
      <div className="wb-section" style={{ marginBottom: 20 }}>
        <h4 className="wb-sub-title">A. Row Key</h4>
        <p className="wb-step-hint" style={{ marginBottom: 8 }}>
          Which column from your master SQL identifies each row? Its value is
          passed to the Detail SQL as <code>%(row_key)s</code>.
        </p>
        <select
          className="wb-select wb-select--sm"
          value={cfg.rowKey || ''}
          onChange={e => onUpdate({ rowKey: e.target.value })}
        >
          <option value="">Pick master column…</option>
          {masterColumns.map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {/* ── Section B: Shared Detail SQL ────────────────────── */}
      <div className="wb-section" style={{ marginBottom: 20 }}>
        <h4 className="wb-sub-title">B. Shared Detail SQL <span style={{ fontSize: 12, fontWeight: 400, color: '#6b7280' }}>(optional — used as fallback)</span></h4>
        <p className="wb-step-hint" style={{ marginBottom: 8 }}>
          This SQL runs once when a row is expanded and is available to any
          tile or the sub-list that doesn't have its own SQL. Use <code>%(row_key)s</code>
          for the clicked row's key.
        </p>
        <div style={{ marginBottom: 8 }}>
          <button
            type="button"
            className="wb-btn wb-btn--sm"
            onClick={insertIsYouHelper}
            title="Appends a CASE expression that marks the user's own row"
          >
            + Insert is_you comparison
          </button>
        </div>
        <CustomSqlEditor
          sql={sharedSql}
          xColumn=""
          yColumns=""
          seriesColumn=""
          testResult={sharedTestResult}
          testParams={cfg._testParams || {}}
          onUpdate={partial => {
            const updates = {}
            if ('sql' in partial) updates.sql = partial.sql
            if ('testResult' in partial) updates._testResult = partial.testResult
            if ('testParams' in partial) updates._testParams = partial.testParams
            if (Object.keys(updates).length) onUpdate(updates)
          }}
          apiBase={apiBase}
          appContext={appContext}
        />
      </div>

      {/* ── Section C: Detail Tiles ─────────────────────────── */}
      <div className="wb-section" style={{ marginBottom: 20 }}>
        <h4 className="wb-sub-title">C. Detail Tiles ({tiles.length}/3)</h4>
        <p className="wb-step-hint" style={{ marginBottom: 8 }}>
          Up to 3 tiles shown at the top of the detail panel. Each tile can
          use the shared SQL above, or write its own.
        </p>

        {tiles.map((tile, idx) => (
          <TileConfig
            key={idx}
            idx={idx}
            tile={tile}
            sharedColumns={sharedColumns}
            masterColumns={masterColumns}
            masterSampleRow={masterSampleRow}
            onChange={partial => updateTile(idx, partial)}
            onRemove={() => removeTile(idx)}
            apiBase={apiBase}
            appContext={appContext}
          />
        ))}

        {tiles.length < 3 && (
          <button type="button" className="wb-btn wb-btn--sm" onClick={addTile}>
            + Add Tile
          </button>
        )}
      </div>

      {/* ── Section D: Sub-List ─────────────────────────────── */}
      <div className="wb-section">
        <h4 className="wb-sub-title">D. Sub-List</h4>
        <div className="wb-field-group" style={{ marginBottom: 12 }}>
          <label style={{ fontWeight: 500, marginBottom: 6, display: 'block' }}>Title</label>
          <input
            type="text"
            className="wb-input wb-input--sm"
            style={{ maxWidth: 400 }}
            placeholder="e.g. Discharging to — Top HHAs"
            value={sublist.title || ''}
            onChange={e => updateSublist({ title: e.target.value })}
          />
        </div>

        {/* Own-SQL toggle */}
        <div style={{ marginBottom: 12, padding: 10, background: '#f8fafc', borderRadius: 6 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500 }}>
            <input
              type="checkbox"
              checked={sublistOwnSql}
              onChange={e => updateSublist({ ownSql: e.target.checked })}
            />
            Use own SQL for sub-list
            <span style={{ fontWeight: 400, color: '#6b7280', fontSize: 12 }}>
              (recommended when the sub-list needs peer-row data different from the tiles)
            </span>
          </label>

          {sublistOwnSql && (
            <div style={{ marginTop: 10, paddingLeft: 22 }}>
              <div style={{ marginBottom: 6 }}>
                <button
                  type="button"
                  className="wb-btn wb-btn--sm"
                  onClick={() => updateSublist({
                    sql: (sublist.sql || '').trimEnd()
                      + ', CASE WHEN <your_column> = %(selected_hha_ccn)s THEN 1 ELSE 0 END AS is_you',
                  })}
                >
                  + Insert is_you comparison
                </button>
              </div>
              <CustomSqlEditor
                sql={sublist.sql || ''}
                xColumn=""
                yColumns=""
                seriesColumn=""
                testResult={sublist._testResult || null}
                testParams={sublist._testParams || {}}
                onUpdate={partial => {
                  const updates = {}
                  if ('sql' in partial) updates.sql = partial.sql
                  if ('testResult' in partial) updates._testResult = partial.testResult
                  if ('testParams' in partial) updates._testParams = partial.testParams
                  if (Object.keys(updates).length) updateSublist(updates)
                }}
                apiBase={apiBase}
                appContext={appContext}
              />
            </div>
          )}
        </div>

        {/* Reuse MasterRowLayoutStep for sub-list row layout */}
        <MasterRowLayoutStep
          config={sublist.layout || {}}
          onChange={partial => updateSublist({ layout: { ...(sublist.layout || {}), ...partial } })}
          columns={sublistColumns}
          sampleRow={sublistSampleRow}
          title="Sub-List Row Layout"
          hideActions
        />

        {/* YOU indicator config */}
        <div style={{ marginTop: 16, padding: 12, background: '#f8fafc', borderRadius: 6 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontWeight: 500 }}>
            <input
              type="checkbox"
              checked={!!sublist.you?.enabled}
              onChange={e => updateSublist({ you: { ...(sublist.you || {}), enabled: e.target.checked } })}
            />
            Enable YOU indicator
          </label>
          {sublist.you?.enabled && (
            <div style={{ paddingLeft: 24, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                YOU column:
                <select
                  className="wb-select wb-select--sm"
                  value={sublist.you?.column || ''}
                  onChange={e => updateSublist({ you: { ...sublist.you, column: e.target.value } })}
                >
                  <option value="">Pick column (e.g. is_you)…</option>
                  {sublistColumns.map(c => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                YOU color:
                <input
                  type="color"
                  value={sublist.you?.youColor || '#10b981'}
                  onChange={e => updateSublist({ you: { ...sublist.you, youColor: e.target.value } })}
                />
                Peer color:
                <input
                  type="color"
                  value={sublist.you?.peerColor || '#f59e0b'}
                  onChange={e => updateSublist({ you: { ...sublist.you, peerColor: e.target.value } })}
                />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={sublist.you?.showProgressBar !== false}
                  onChange={e => updateSublist({ you: { ...sublist.you, showProgressBar: e.target.checked } })}
                />
                Show colored progress bar under each row
              </label>
              <p className="wb-step-hint" style={{ margin: 0 }}>
                Tip: write your sub-list SQL with <code>
                  {'CASE WHEN hha_ccn = %(selected_hha_ccn)s THEN 1 ELSE 0 END AS is_you'}
                </code> to populate this column.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Tile config card (3-way data source: Shared SQL / Own SQL / Master JSON) ──
function TileConfig({
  idx,
  tile,
  sharedColumns,
  masterColumns,
  masterSampleRow,
  onChange,
  onRemove,
  apiBase,
  appContext,
}) {
  const type = tile.type || 'bar'
  const isKpi = type.startsWith('kpi')

  // dataSource: 'shared' | 'sql' | 'master_json'
  // Computed for backward compat: legacy tiles only have ownSql.
  const dataSource = tile.data_source || (tile.ownSql ? 'sql' : 'shared')
  const isMasterJson = dataSource === 'master_json'
  const isOwnSql = dataSource === 'sql'

  // Effective columns for X/Y dropdowns (SQL paths only)
  const effectiveColumns = isOwnSql
    ? (tile._testResult?.columns || [])
    : sharedColumns

  const handleDataSourceChange = (newSource) => {
    if (newSource === dataSource) return

    // Confirm before discarding non-empty SQL (only when leaving 'sql' mode)
    const hasSql = (tile.sql || '').trim().length > 0
    if (isOwnSql && newSource !== 'sql' && hasSql) {
      const ok = window.confirm(
        'Switching data source will clear your Own SQL for this tile. Continue?'
      )
      if (!ok) return
    }

    // Build update payload that ALSO clears legacy/sibling fields so loaded
    // state stays consistent. Discipline rule: write both new + legacy fields
    // so the server-side reader (which checks either) stays correct.
    const updates = { data_source: newSource }
    if (newSource === 'shared') {
      updates.ownSql = false
      updates.sql = ''
      updates._testResult = null
      updates._testParams = {}
      updates.master_json_column = ''
      updates.json_x_key = ''
      updates.json_y_key = ''
    } else if (newSource === 'sql') {
      updates.ownSql = true
      updates.master_json_column = ''
      updates.json_x_key = ''
      updates.json_y_key = ''
    } else if (newSource === 'master_json') {
      updates.ownSql = false
      updates.sql = ''
      updates._testResult = null
      updates._testParams = {}
    }
    onChange(updates)
  }

  const radioName = `tile-ds-${idx}`

  return (
    <div
      style={{
        border: '1px solid #e2e8f0', borderRadius: 6,
        padding: 12, marginBottom: 8, background: '#fafbfc',
      }}
    >
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
        <input
          type="text"
          className="wb-input wb-input--sm"
          style={{ flex: 1 }}
          placeholder="Tile title (e.g. Admits by Year)"
          value={tile.title || ''}
          onChange={e => onChange({ title: e.target.value })}
        />
        <button
          type="button"
          className="wb-btn wb-btn--sm wb-btn--ghost"
          onClick={onRemove}
          title="Remove tile"
        >
          <i className="fa fa-times" />
        </button>
      </div>

      {/* Data source — 3-way radio */}
      <div style={{
        marginBottom: 10, padding: 8, background: '#f8fafc',
        borderRadius: 6, border: '1px solid #e5e7eb',
      }}>
        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
          Data source:
        </div>
        <label style={{ display: 'block', marginBottom: 3, fontSize: 13 }}>
          <input
            type="radio" name={radioName}
            checked={dataSource === 'shared'}
            onChange={() => handleDataSourceChange('shared')}
          />
          {' '}Shared Detail SQL
          <span style={{ color: '#6b7280', fontSize: 11, marginLeft: 6 }}>
            (uses Section B)
          </span>
        </label>
        <label style={{ display: 'block', marginBottom: 3, fontSize: 13 }}>
          <input
            type="radio" name={radioName}
            checked={dataSource === 'sql'}
            onChange={() => handleDataSourceChange('sql')}
          />
          {' '}Own SQL
          <span style={{ color: '#6b7280', fontSize: 11, marginLeft: 6 }}>
            (this tile gets its own query)
          </span>
        </label>
        <label style={{ display: 'block', fontSize: 13 }}>
          <input
            type="radio" name={radioName}
            checked={dataSource === 'master_json'}
            onChange={() => handleDataSourceChange('master_json')}
          />
          {' '}Master JSON column
          <span style={{ color: '#6b7280', fontSize: 11, marginLeft: 6 }}>
            (no extra query — read from master row)
          </span>
        </label>
      </div>

      {/* Own-SQL editor — only when 'sql' mode */}
      {isOwnSql && (
        <div style={{ marginBottom: 10 }}>
          <CustomSqlEditor
            sql={tile.sql || ''}
            xColumn=""
            yColumns=""
            seriesColumn=""
            testResult={tile._testResult || null}
            testParams={tile._testParams || {}}
            onUpdate={partial => {
              const updates = {}
              if ('sql' in partial) updates.sql = partial.sql
              if ('testResult' in partial) updates._testResult = partial.testResult
              if ('testParams' in partial) updates._testParams = partial.testParams
              if (Object.keys(updates).length) onChange(updates)
            }}
            apiBase={apiBase}
            appContext={appContext}
          />
        </div>
      )}

      {/* Master-JSON picker — only when 'master_json' mode */}
      {isMasterJson && (
        <MasterJsonPicker
          tile={tile}
          isKpi={isKpi}
          masterColumns={masterColumns}
          masterSampleRow={masterSampleRow}
          onChange={onChange}
        />
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
          Type:
          <select
            className="wb-select wb-select--sm"
            value={type}
            onChange={e => onChange({ type: e.target.value })}
          >
            <optgroup label="Bar">
              <option value="bar">Bar — Basic</option>
              <option value="bar_stacked">Bar — Stacked</option>
            </optgroup>
            <optgroup label="Line">
              <option value="line">Line — Basic</option>
              <option value="line_area">Line — Area</option>
              <option value="line_stacked_area">Line — Stacked Area</option>
              <option value="combo_bar_line">Combo — Bar + Line</option>
            </optgroup>
            <optgroup label="KPI">
              <option value="kpi_stat">KPI — Stat Card</option>
              <option value="kpi_rag">KPI — RAG Status</option>
              <option value="kpi_strip">KPI — Strip</option>
            </optgroup>
          </select>
        </label>

        {/* X/Y/Color: hide X/Y in master_json mode (MasterJsonPicker handles
            JSON keys); always keep Color picker visible for chart tiles. */}
        {!isKpi && !isMasterJson && (
          <>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              X:
              <select
                className="wb-select wb-select--sm"
                value={tile.xColumn || ''}
                onChange={e => onChange({ xColumn: e.target.value })}
              >
                <option value="">Pick…</option>
                {effectiveColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              Y:
              <select
                className="wb-select wb-select--sm"
                value={tile.yColumn || ''}
                onChange={e => onChange({ yColumn: e.target.value })}
              >
                <option value="">Pick…</option>
                {effectiveColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          </>
        )}
        {!isKpi && (
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            Color:
            <input
              type="color"
              value={tile.color || '#0d9488'}
              onChange={e => onChange({ color: e.target.value })}
            />
          </label>
        )}

        {/* KPI value pickers: only for SQL paths. In master_json mode, the
            value source is master_json_column (and json_y_key for objects). */}
        {!isMasterJson && type === 'kpi_stat' && (
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            Value:
            <select
              className="wb-select wb-select--sm"
              value={tile.valueColumn || ''}
              onChange={e => onChange({ valueColumn: e.target.value })}
            >
              <option value="">Pick…</option>
              {effectiveColumns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        )}

        {type === 'kpi_rag' && (
          <>
            {!isMasterJson && (
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                Value:
                <select
                  className="wb-select wb-select--sm"
                  value={tile.valueColumn || ''}
                  onChange={e => onChange({ valueColumn: e.target.value })}
                >
                  <option value="">Pick…</option>
                  {effectiveColumns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            )}
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              Good ≥:
              <input
                type="number"
                className="wb-input wb-input--xs" style={{ width: 60 }}
                value={tile.goodThreshold ?? 70}
                onChange={e => onChange({ goodThreshold: Number(e.target.value) })}
              />
            </label>
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              Warn ≥:
              <input
                type="number"
                className="wb-input wb-input--xs" style={{ width: 60 }}
                value={tile.warnThreshold ?? 50}
                onChange={e => onChange({ warnThreshold: Number(e.target.value) })}
              />
            </label>
          </>
        )}

        {type === 'kpi_strip' && (
          <div style={{ width: '100%', fontSize: 12, color: '#6b7280' }}>
            KPI Strip items must be configured in JSON (advanced). Default: pick one column per item.
          </div>
        )}
      </div>

      {!isKpi && (
        <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={tile.showLabels !== false}
              onChange={e => onChange({ showLabels: e.target.checked })}
            />
            Show data labels
          </label>
          <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
            <input
              type="checkbox"
              checked={!!tile.showLegend}
              onChange={e => onChange({ showLegend: e.target.checked })}
            />
            Show legend
          </label>
        </div>
      )}
    </div>
  )
}

// ── Master JSON column picker (used by master_json data source) ───────────
// Lets the admin pick a column from the master query that holds JSON data
// (or a scalar for KPI tiles). Detects the shape of the picked column from
// masterSampleRow, shows a sample preview, and renders X/Y/value-key
// dropdowns appropriate to that shape.
function MasterJsonPicker({
  tile,
  isKpi,
  masterColumns,
  masterSampleRow,
  onChange,
}) {
  // No master test result yet
  if (!masterSampleRow) {
    return (
      <div style={{
        marginBottom: 10, padding: 10, background: '#fff7ed',
        border: '1px solid #fed7aa', borderRadius: 6,
        fontSize: 12, color: '#9a3412',
      }}>
        Run the master query test first (Step 2) to populate the column picker.
      </div>
    )
  }

  // Build candidate columns: detect shape per-column from masterSampleRow.
  // For chart tiles: only array-* shapes are useful.
  // For KPI tiles: scalar / object / array-of-objects (admin picks key) all OK.
  const candidates = (masterColumns || []).map(col => ({
    col,
    shape: detectColumnShape(masterSampleRow[col]),
  })).filter(c => isCandidateForTile(c.shape, isKpi))

  if (candidates.length === 0) {
    return (
      <div style={{
        marginBottom: 10, padding: 10, background: '#fff7ed',
        border: '1px solid #fed7aa', borderRadius: 6,
        fontSize: 12, color: '#9a3412',
      }}>
        {isKpi
          ? 'No usable columns found in the master query for a KPI tile.'
          : 'No JSON-array columns found in the master query. '
            + 'Add a json_agg(...) or json_build_array(...) column to your master SQL.'}
      </div>
    )
  }

  const selected = candidates.find(c => c.col === tile.master_json_column)
  const shape = selected?.shape

  return (
    <div style={{
      marginBottom: 10, padding: 10, background: '#f0f9ff',
      border: '1px solid #bae6fd', borderRadius: 6,
    }}>
      <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
        Master column:
        <select
          className="wb-select wb-select--sm"
          value={tile.master_json_column || ''}
          onChange={e => onChange({
            master_json_column: e.target.value,
            json_x_key: '',
            json_y_key: '',
          })}
        >
          <option value="">Pick column…</option>
          {candidates.map(c => (
            <option key={c.col} value={c.col}>
              {c.col} ({c.shape.label})
            </option>
          ))}
        </select>
      </label>

      {selected && (
        <>
          <div style={{ marginTop: 8, fontSize: 11, color: '#0c4a6e' }}>
            <strong>Sample (row 1):</strong>
            <pre style={{
              background: 'white', padding: 6, borderRadius: 4,
              maxHeight: 80, overflow: 'auto',
              margin: '4px 0', fontSize: 11, lineHeight: 1.4,
            }}>
              {prettyTrunc(shape.raw)}
            </pre>
            Detected: {shape.label}
          </div>

          {/* X/Y key pickers — for chart tiles with array-of-objects */}
          {!isKpi && shape.kind === 'array-of-objects' && (
            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
                X key:
                <select
                  className="wb-select wb-select--sm"
                  value={tile.json_x_key || ''}
                  onChange={e => onChange({ json_x_key: e.target.value })}
                >
                  <option value="">Pick…</option>
                  {shape.keys.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
                Y key:
                <select
                  className="wb-select wb-select--sm"
                  value={tile.json_y_key || ''}
                  onChange={e => onChange({ json_y_key: e.target.value })}
                >
                  <option value="">Pick…</option>
                  {shape.keys.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
            </div>
          )}

          {/* Value key picker — for KPI tiles binding to an object column */}
          {isKpi && shape.kind === 'object' && (
            <div style={{ marginTop: 8 }}>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 13 }}>
                Value key:
                <select
                  className="wb-select wb-select--sm"
                  value={tile.json_y_key || ''}
                  onChange={e => onChange({ json_y_key: e.target.value })}
                >
                  <option value="">Pick…</option>
                  {shape.keys.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
            </div>
          )}

          {/* For array-of-scalars + chart: no key picker needed (X = index) */}
          {!isKpi && shape.kind === 'array-of-scalars' && (
            <div style={{ marginTop: 6, fontSize: 11, color: '#6b7280' }}>
              X axis = index (0, 1, 2, …); Y axis = each scalar value.
            </div>
          )}
        </>
      )}

      <div style={{ marginTop: 8, fontSize: 11, color: '#6b7280', borderTop: '1px solid #bae6fd', paddingTop: 6 }}>
        ℹ This data comes from your master query. To control which page filters
        affect it, edit the master SQL's JSON subquery.
      </div>
    </div>
  )
}

// ── Master JSON helpers ───────────────────────────────────────────────────

// Detect what kind of value a master row column holds, returning a
// descriptor shared between MasterJsonPicker (for UI hints) and the
// portal-side parseMasterJson (which renders).
//   kind = 'array-of-objects' | 'array-of-scalars' | 'object' | 'scalar' | 'unknown'
function detectColumnShape(value) {
  if (value == null || value === '') {
    return { kind: 'unknown', label: 'empty', keys: [], raw: value }
  }

  // Try parsing strings as JSON
  let parsed = value
  if (typeof value === 'string') {
    try {
      parsed = JSON.parse(value)
    } catch {
      // CSV of numbers fallback (sparkline-style)
      const parts = value.split(',').map(s => Number(s.trim()))
      if (parts.length >= 2 && parts.every(n => !isNaN(n))) {
        return {
          kind: 'array-of-scalars',
          label: `array of ${parts.length} numbers (csv)`,
          keys: [], raw: value,
        }
      }
      return { kind: 'scalar', label: 'string', keys: [], raw: value }
    }
  }

  if (Array.isArray(parsed)) {
    if (parsed.length === 0) {
      return { kind: 'unknown', label: 'empty array', keys: [], raw: value }
    }
    const allObjects = parsed.every(
      v => v && typeof v === 'object' && !Array.isArray(v))
    if (allObjects) {
      const keys = Object.keys(parsed[0] || {})
      return {
        kind: 'array-of-objects',
        label: `array of ${parsed.length} objects`,
        keys, raw: value,
      }
    }
    return {
      kind: 'array-of-scalars',
      label: `array of ${parsed.length} values`,
      keys: [], raw: value,
    }
  }

  if (typeof parsed === 'object' && parsed !== null) {
    const keys = Object.keys(parsed)
    return {
      kind: 'object',
      label: `object with ${keys.length} keys`,
      keys, raw: value,
    }
  }

  // Number, boolean, etc.
  return { kind: 'scalar', label: typeof parsed, keys: [], raw: value }
}

// Decide if a detected shape is offerable for the tile's mode.
function isCandidateForTile(shape, isKpi) {
  if (shape.kind === 'unknown') return false
  if (isKpi) {
    // KPIs accept scalars, objects, AND array-of-objects (with key picker)
    return shape.kind === 'scalar'
        || shape.kind === 'object'
        || shape.kind === 'array-of-objects'
  }
  // Charts need arrays
  return shape.kind === 'array-of-objects' || shape.kind === 'array-of-scalars'
}

// Pretty-print a sample value, truncating long output.
function prettyTrunc(value) {
  let s
  if (typeof value === 'string') {
    s = value
  } else {
    try { s = JSON.stringify(value, null, 2) } catch { s = String(value) }
  }
  if (s.length > 300) {
    s = s.slice(0, 300) + '…'
  }
  return s
}
