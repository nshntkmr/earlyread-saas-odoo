import React from 'react'
import CustomSqlEditor from './CustomSqlEditor'
import MasterRowLayoutStep from './MasterRowLayoutStep'

/**
 * DetailConfigStep
 *
 * Configures the detail panel for a ranked_detail_list widget.
 * Four sections:
 *   A. Row Key — which master SQL column identifies each row
 *   B. Detail SQL — SQL with %(row_key)s placeholder (+ "insert is_you" helper)
 *   C. Detail Tiles — up to 3 tiles (bar/line/KPI variants)
 *   D. Sub-List — reuses MasterRowLayoutStep + YOU indicator config
 *
 * Props:
 *   detailConfig          — current v2 detail config
 *   onUpdate              — (partial) => void (shallow merge)
 *   masterColumns         — columns from master SQL test (for Row Key dropdown)
 *   apiBase, appContext   — passed to CustomSqlEditor
 */
export default function DetailConfigStep({
  detailConfig = {},
  onUpdate,
  masterColumns = [],
  apiBase,
  appContext,
}) {
  const cfg = detailConfig || {}
  const detailSql = cfg.sql || ''
  const detailTestResult = cfg._testResult || null
  const detailColumns = detailTestResult?.columns || []
  const detailSampleRow = (detailTestResult?.rows && detailTestResult.rows[0])
    ? Object.fromEntries(detailTestResult.columns.map((c, i) => [c, detailTestResult.rows[0][i]]))
    : null

  const tiles = cfg.tiles || []
  const sublist = cfg.sublist || {}

  // Helper to update sublist config
  const updateSublist = (partial) => {
    onUpdate({ sublist: { ...sublist, ...partial } })
  }

  // Helper to update tile at index
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
      }],
    })
  }

  const removeTile = (idx) => {
    onUpdate({ tiles: tiles.filter((_, i) => i !== idx) })
  }

  const insertIsYouHelper = () => {
    const snippet = ', CASE WHEN <your_column> = %(selected_hha_ccn)s THEN 1 ELSE 0 END AS is_you'
    onUpdate({
      sql: detailSql.trimEnd() + snippet,
    })
  }

  return (
    <div className="wb-detail-config-step">
      <h3 className="wb-step-title">Detail Config</h3>
      <p className="wb-step-hint">
        Configure what appears when a user expands a row: tiles (bar/line/KPI)
        and a nested sub-list. Only shown for widgets with the expand chevron
        enabled.
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

      {/* ── Section B: Detail SQL ───────────────────────────── */}
      <div className="wb-section" style={{ marginBottom: 20 }}>
        <h4 className="wb-sub-title">B. Detail SQL</h4>
        <p className="wb-step-hint" style={{ marginBottom: 8 }}>
          SQL that runs when a row is expanded. Use <code>%(row_key)s</code> for the
          clicked row's key, and any page filter params (e.g. <code>%(year)s</code>).
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
          sql={detailSql}
          xColumn=""
          yColumns=""
          seriesColumn=""
          testResult={detailTestResult}
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
          Up to 3 tiles shown at the top of the detail panel.
        </p>

        {tiles.map((tile, idx) => (
          <TileConfig
            key={idx}
            tile={tile}
            detailColumns={detailColumns}
            onChange={partial => updateTile(idx, partial)}
            onRemove={() => removeTile(idx)}
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

        {/* Reuse MasterRowLayoutStep for sub-list row layout */}
        <MasterRowLayoutStep
          config={sublist.layout || {}}
          onChange={partial => updateSublist({ layout: { ...(sublist.layout || {}), ...partial } })}
          columns={detailColumns}
          sampleRow={detailSampleRow}
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
                  {detailColumns.map(c => (
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
                Tip: write your detail SQL with <code>
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

// ── Tile config card (used inside DetailConfigStep) ──────────────────
function TileConfig({ tile, detailColumns, onChange, onRemove }) {
  const type = tile.type || 'bar'
  const isKpi = type.startsWith('kpi')

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
                {detailColumns.map(c => <option key={c} value={c}>{c}</option>)}
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
                {detailColumns.map(c => <option key={c} value={c}>{c}</option>)}
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
              {detailColumns.map(c => <option key={c} value={c}>{c}</option>)}
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
                {detailColumns.map(c => <option key={c} value={c}>{c}</option>)}
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
