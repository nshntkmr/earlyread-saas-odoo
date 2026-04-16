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
            tile={tile}
            sharedColumns={sharedColumns}
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

// ── Tile config card (with own-SQL toggle) ──────────────────────────────
function TileConfig({ tile, sharedColumns, onChange, onRemove, apiBase, appContext }) {
  const type = tile.type || 'bar'
  const isKpi = type.startsWith('kpi')
  const ownSql = !!tile.ownSql

  // Effective columns — from own SQL test result if set, else shared
  const effectiveColumns = ownSql
    ? (tile._testResult?.columns || [])
    : sharedColumns

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

      {/* Own SQL toggle */}
      <div style={{ marginBottom: 10 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={ownSql}
            onChange={e => onChange({ ownSql: e.target.checked })}
          />
          Use own SQL for this tile
          <span style={{ color: '#6b7280', fontSize: 11 }}>
            (otherwise uses the Shared Detail SQL)
          </span>
        </label>
        {ownSql && (
          <div style={{ marginTop: 8, paddingLeft: 22 }}>
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
      </div>

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

        {!isKpi && (
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
            <label style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              Color:
              <input
                type="color"
                value={tile.color || '#0d9488'}
                onChange={e => onChange({ color: e.target.value })}
              />
            </label>
          </>
        )}

        {type === 'kpi_stat' && (
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
