import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { ModuleRegistry, AllCommunityModule, themeQuartz } from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import { CUSTOM_COLUMN_TYPES, TYPE_DEFAULTS, VALUE_FORMATTERS, CELL_RENDERERS, resolveColumnDefs } from '@posterra/grid-utils'

// Register all AG Grid Community modules (required for v35+)
ModuleRegistry.registerModules([AllCommunityModule])

import { designerFetch } from '../../api/client'
import { previewUrl, libraryPlaceUrl } from '../../api/endpoints'
import { buildPreviewPayload } from './LivePreview'
import PageFilterPanel from './PageFilterPanel'
import TableColumnSettings from './TableColumnSettings'

function getTypeDefaults(dataType) {
  const dt = (dataType || 'text').toLowerCase()
  if (dt.includes('int') || dt.includes('numeric') || dt.includes('serial')) return TYPE_DEFAULTS.numeric
  if (dt.includes('float') || dt.includes('double') || dt.includes('decimal') || dt.includes('real')) return TYPE_DEFAULTS.float
  if (dt.includes('date') || dt.includes('timestamp')) return TYPE_DEFAULTS.date
  if (dt.includes('bool')) return TYPE_DEFAULTS.boolean
  return TYPE_DEFAULTS.text
}

/**
 * TableConfigurator — Split-pane component for table widget configuration.
 *
 * Left panel:  column list (drag-to-reorder) + expandable settings + WHERE filters
 * Right panel: live AG Grid preview + page filters + save buttons
 */
export default function TableConfigurator({
  sources, joins, dataMode, customSql, filters, visualFlags, appearance,
  tableColumnConfig, builderState, onUpdate, onSave, saving,
  apiBase, appContext = null,
}) {
  // ── Stable column ID counter ────────────────────────────────────────────────
  const colIdRef = useRef(0)
  const assignId = (col) => {
    if (!col._id) col._id = `col_${++colIdRef.current}`
    return col
  }

  // ── State ──────────────────────────────────────────────────────────────────
  const [columns, setColumns] = useState(() =>
    (tableColumnConfig?.length ? tableColumnConfig : []).map(assignId)
  )
  const [selectedIdx, setSelectedIdx] = useState(null)
  const [previewData, setPreviewData] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewError, setPreviewError] = useState(null)
  const [filterValues, setFilterValues] = useState({})
  const [placing, setPlacing] = useState(false)
  const [placeSuccess, setPlaceSuccess] = useState(false)
  const [widgetTitle, setWidgetTitle] = useState(appearance?.title || '')

  const hasPageContext = !!appContext?.page?.id

  // ── Sync from parent prop when tableColumnConfig changes externally ────────
  // (e.g., LOAD_DEFINITION restores a saved config)
  useEffect(() => {
    if (tableColumnConfig?.length && columns.length === 0) {
      setColumns(tableColumnConfig.map(assignId))
    }
  }, [tableColumnConfig])

  // ── Available columns from data sources ────────────────────────────────────
  const availableColumns = useMemo(() => {
    if (dataMode === 'custom_sql' && customSql?.testResult?.columns) {
      return customSql.testResult.columns.map(c => ({
        column_name: c,
        display_name: c,
        data_type: 'text',
        source_id: null,
      }))
    }
    return (sources || []).flatMap(src =>
      (src.columns || []).map(c => ({
        ...c,
        source_id: src.id,
        source_name: src.name,
      }))
    )
  }, [sources, dataMode, customSql])

  // ── Add column ─────────────────────────────────────────────────────────────
  const addColumn = useCallback((colMeta) => {
    const defaults = getTypeDefaults(colMeta.data_type)
    const newCol = {
      _id: `col_${++colIdRef.current}`,  // stable key for React rendering
      // Source metadata
      source_id: colMeta.source_id || null,
      column: colMeta.column_name,
      alias: colMeta.column_name,
      data_type: colMeta.data_type || 'text',
      // AG Grid properties
      field: colMeta.column_name,
      headerName: colMeta.display_name || colMeta.column_name,
      width: defaults.width,
      minWidth: 60,
      flex: null,
      pinned: null,
      sortable: true,
      sort: null,
      sortIndex: null,
      filter: defaults.filter,
      resizable: true,
      cellRenderer: null,
      cellRendererParams: {},
      valueFormatter: defaults.formatter,
      cellStyle: defaults.align !== 'left' ? { textAlign: defaults.align } : null,
      cellClassRules: {},
      headerClass: null,
      hide: false,
      tooltipField: null,
      wrapText: false,
      type: defaults.type,
      // Click action
      clickAction: 'none',
      actionPageKey: '',
      actionTabKey: '',
      actionFilterParam: '',
      actionUrlTemplate: '',
    }
    const updated = [...columns, newCol]
    setColumns(updated)
    syncToParent(updated)
    setSelectedIdx(updated.length - 1)
  }, [columns])

  // ── Update column ──────────────────────────────────────────────────────────
  const updateColumn = useCallback((idx, changes) => {
    const updated = columns.map((col, i) =>
      i === idx ? { ...col, ...changes } : col
    )
    setColumns(updated)
    syncToParent(updated)
  }, [columns])

  // ── Remove column ──────────────────────────────────────────────────────────
  const removeColumn = useCallback((idx) => {
    const updated = columns.filter((_, i) => i !== idx)
    setColumns(updated)
    syncToParent(updated)
    if (selectedIdx === idx) setSelectedIdx(null)
    else if (selectedIdx > idx) setSelectedIdx(selectedIdx - 1)
  }, [columns, selectedIdx])

  // ── Move column ────────────────────────────────────────────────────────────
  const moveColumn = useCallback((fromIdx, toIdx) => {
    if (toIdx < 0 || toIdx >= columns.length) return
    const updated = [...columns]
    const [moved] = updated.splice(fromIdx, 1)
    updated.splice(toIdx, 0, moved)
    setColumns(updated)
    syncToParent(updated)
    setSelectedIdx(toIdx)
  }, [columns])

  // ── Sync column config to parent state ─────────────────────────────────────
  // Strip internal _id keys before persisting — they're React rendering keys only
  const syncToParent = useCallback((cols) => {
    const clean = cols.map(({ _id, ...rest }) => rest)
    onUpdate({ type: 'SET_TABLE_COLUMN_CONFIG', value: clean })
  }, [onUpdate])

  // ── Run preview ────────────────────────────────────────────────────────────
  // Uses the SAME buildPreviewPayload as LivePreview (shared across all widget
  // types: bar, line, pie, table, kpi, etc.) so filter handling is consistent.
  const runPreview = useCallback(async () => {
    setPreviewLoading(true)
    setPreviewError(null)
    try {
      // Build a snapshot of builderState with the latest local columns
      // (local state may be ahead of parent due to async dispatch)
      const clean = columns.map(({ _id, ...rest }) => rest)
      const stateSnapshot = { ...builderState, tableColumnConfig: clean }

      const body = buildPreviewPayload(
        stateSnapshot,
        hasPageContext ? filterValues : null
      )
      if (hasPageContext && appContext?.page?.id) {
        body.page_id = appContext.page.id
      }
      const result = await designerFetch(previewUrl(apiBase), {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setPreviewData(result)
    } catch (err) {
      setPreviewError(err.message || 'Preview failed')
    } finally {
      setPreviewLoading(false)
    }
  }, [builderState, columns, filterValues, hasPageContext, apiBase, appContext])

  // ── Save handlers ──────────────────────────────────────────────────────────
  // Dispatch title update, then wait one tick for React to process the reducer
  // before calling onSave() — otherwise buildCreatePayload reads stale state.
  const flushTitle = useCallback(() => new Promise(resolve => {
    onUpdate({ type: 'SET_APPEARANCE', value: { ...appearance, title: widgetTitle } })
    // requestAnimationFrame ensures React has processed the dispatch
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  }), [onUpdate, appearance, widgetTitle])

  const handleSave = useCallback(async () => {
    await flushTitle()
    const result = await onSave()
    return result
  }, [onSave, flushTitle])

  const handleSaveAndPlace = useCallback(async () => {
    await flushTitle()
    const result = await onSave()
    if (!result?.id || !appContext?.page?.id) return
    setPlacing(true)
    try {
      await designerFetch(libraryPlaceUrl(apiBase, result.id), {
        method: 'POST',
        body: JSON.stringify({
          page_id: appContext.page.id,
          tab_id: appContext.tab?.id || null,
        }),
      })
      setPlaceSuccess(true)
    } catch { /* ignore */ }
    finally { setPlacing(false) }
  }, [onSave, onUpdate, appearance, widgetTitle, apiBase, appContext])

  // ── Columns not yet added ──────────────────────────────────────────────────
  const unusedColumns = useMemo(() => {
    const usedFields = new Set(columns.map(c => c.column))
    return availableColumns.filter(c => !usedFields.has(c.column_name))
  }, [availableColumns, columns])

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="tc-split-pane">
      {/* ═══ LEFT PANEL: Column Config ═══ */}
      <div className="tc-left-panel">
        {/* Widget title */}
        <div className="wb-field-group">
          <label className="wb-label">Widget Name</label>
          <input
            type="text"
            className="wb-input"
            value={widgetTitle}
            onChange={e => setWidgetTitle(e.target.value)}
            placeholder="e.g. Peer Profile Table"
          />
        </div>

        {/* Add column dropdown */}
        <div className="wb-field-group">
          <label className="wb-label">Columns ({columns.length})</label>
          {unusedColumns.length > 0 && (
            <select
              className="wb-select wb-select--sm"
              value=""
              onChange={e => {
                const col = availableColumns.find(c => c.column_name === e.target.value)
                if (col) addColumn(col)
              }}
            >
              <option value="">+ Add column...</option>
              {unusedColumns.map(c => (
                <option key={c.column_name} value={c.column_name}>
                  {c.display_name || c.column_name} ({c.data_type})
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Column list */}
        <div className="tc-column-list">
          {columns.length === 0 && (
            <div className="tc-empty-hint">
              <i className="fa fa-info-circle me-1" />
              Add columns from the dropdown above to start configuring your table.
            </div>
          )}
          {columns.map((col, idx) => (
            <div key={col._id || idx} className={`tc-column-item ${selectedIdx === idx ? 'tc-column-item--selected' : ''}`}>
              <div className="tc-column-header" onClick={() => setSelectedIdx(selectedIdx === idx ? null : idx)}>
                <div className="tc-column-drag">
                  <button
                    type="button" className="tc-move-btn"
                    disabled={idx === 0}
                    onClick={e => { e.stopPropagation(); moveColumn(idx, idx - 1) }}
                  ><i className="fa fa-chevron-up" /></button>
                  <button
                    type="button" className="tc-move-btn"
                    disabled={idx === columns.length - 1}
                    onClick={e => { e.stopPropagation(); moveColumn(idx, idx + 1) }}
                  ><i className="fa fa-chevron-down" /></button>
                </div>
                <span className="tc-column-num">{idx + 1}.</span>
                <span className="tc-column-name">{col.headerName || col.field}</span>
                <div className="tc-column-badges">
                  {col.pinned && <span className="tc-badge tc-badge--pin">{col.pinned}</span>}
                  {col.sort && <span className="tc-badge tc-badge--sort">{col.sort}</span>}
                  {col.cellRenderer && <span className="tc-badge tc-badge--renderer">{col.cellRenderer}</span>}
                  {col.hide && <span className="tc-badge tc-badge--hidden">hidden</span>}
                </div>
                <button
                  type="button" className="tc-remove-btn"
                  onClick={e => { e.stopPropagation(); removeColumn(idx) }}
                ><i className="fa fa-times" /></button>
              </div>

              {/* Expandable settings */}
              {selectedIdx === idx && (
                <TableColumnSettings
                  column={col}
                  allColumns={availableColumns}
                  onChange={changes => updateColumn(idx, changes)}
                />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* ═══ RIGHT PANEL: Preview ═══ */}
      <div className="tc-right-panel">
        {/* Page filters */}
        {hasPageContext && (
          <div className="tc-preview-filters">
            <PageFilterPanel
              apiBase={apiBase}
              pageId={appContext.page.id}
              values={filterValues}
              onChange={setFilterValues}
            />
          </div>
        )}

        {/* Preview actions */}
        <div className="tc-preview-actions">
          <button
            type="button"
            className="wb-btn wb-btn--primary wb-btn--sm"
            onClick={runPreview}
            disabled={previewLoading || columns.length === 0}
          >
            {previewLoading ? (
              <><span className="spinner-border spinner-border-sm me-1" /> Running...</>
            ) : (
              <><i className="fa fa-play me-1" /> Run Preview</>
            )}
          </button>
        </div>

        {/* Preview result */}
        <div className="tc-preview-area">
          {previewError && (
            <div className="wb-preview-error">
              <i className="fa fa-exclamation-triangle me-1" />{previewError}
            </div>
          )}
          {previewData && !previewError && (
            <PreviewGrid
              previewData={previewData}
              columns={columns}
            />
          )}
          {!previewData && !previewError && !previewLoading && (
            <div className="tc-preview-placeholder">
              <i className="fa fa-table me-2" />
              Add columns and click <strong>Run Preview</strong> to see your table.
            </div>
          )}
        </div>

        {/* Save buttons */}
        <div className="tc-save-bar">
          {placeSuccess && (
            <span className="text-success me-2">
              <i className="fa fa-check me-1" /> Placed on page!
            </span>
          )}
          <button
            type="button"
            className="wb-btn wb-btn--outline"
            onClick={handleSave}
            disabled={saving || columns.length === 0}
          >
            {saving ? 'Saving...' : 'Save to Library'}
          </button>
          {hasPageContext && (
            <button
              type="button"
              className="wb-btn wb-btn--primary ms-2"
              onClick={handleSaveAndPlace}
              disabled={saving || placing || columns.length === 0}
            >
              {placing ? 'Placing...' : 'Save & Place on Page'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * PreviewGrid — AG Grid instance that renders preview data using the admin's
 * configured columnDefs. Gives true WYSIWYG: alignment, formatters, pinning,
 * sorting, conditional formatting all visible in the preview.
 */
function PreviewGrid({ previewData, columns }) {
  const prevCols = previewData.columns || []
  const prevRows = previewData.rows || []

  // Convert row arrays to row dicts for AG Grid: [{col1: val, col2: val}, ...]
  const rowData = useMemo(() =>
    prevRows.map(row => {
      const obj = {}
      prevCols.forEach((colName, i) => { obj[colName] = row[i] ?? '' })
      return obj
    }),
    [prevCols, prevRows]
  )

  // Build AG Grid columnDefs from admin's configured columns.
  // Only include columns that exist in the preview data.
  const prevColSet = useMemo(() => new Set(prevCols), [prevCols])
  const colMap = useMemo(() => {
    const m = {}
    for (const c of columns) m[c.column || c.field] = c
    return m
  }, [columns])

  const columnDefs = useMemo(() => {
    return prevCols.map(colName => {
      const cfg = colMap[colName]
      if (!cfg) {
        // Column in SQL but not configured — show raw with defaults
        return { field: colName, headerName: colName }
      }
      // Build columnDef from admin config
      const def = { field: colName }
      if (cfg.headerName)       def.headerName = cfg.headerName
      if (cfg.width)            def.width = cfg.width
      if (cfg.minWidth)         def.minWidth = cfg.minWidth
      if (cfg.flex)             def.flex = cfg.flex
      if (cfg.pinned)           def.pinned = cfg.pinned
      if (cfg.sortable != null) def.sortable = cfg.sortable
      if (cfg.sort)             def.sort = cfg.sort
      if (cfg.filter)           def.filter = cfg.filter
      if (cfg.resizable != null) def.resizable = cfg.resizable
      if (cfg.cellStyle)        def.cellStyle = cfg.cellStyle
      if (cfg.hide)             def.hide = cfg.hide
      if (cfg.tooltipField)     def.tooltipField = cfg.tooltipField
      if (cfg.wrapText)         { def.wrapText = true; def.autoHeight = true }
      if (cfg.type)             def.type = cfg.type
      // Pass valueFormatter and cellRenderer strings through — resolveColumnDefs()
      // will convert them to actual functions/components at line 464
      if (cfg.valueFormatter)       def.valueFormatter = cfg.valueFormatter
      if (cfg.cellRenderer)         def.cellRenderer = cfg.cellRenderer
      if (cfg.cellRendererParams)   def.cellRendererParams = cfg.cellRendererParams
      // cellClassRules (conditional formatting)
      if (cfg.cellClassRules && Object.keys(cfg.cellClassRules).length) {
        def.cellClassRules = cfg.cellClassRules
      }
      // headerClass
      if (cfg.headerClass) def.headerClass = cfg.headerClass
      return def
    })
  }, [prevCols, colMap])

  const resolvedColDefs = useMemo(() => resolveColumnDefs(columnDefs), [columnDefs])

  const defaultColDef = useMemo(() => ({
    resizable: true,
    sortable: true,
    suppressMovable: true,
  }), [])

  if (!prevCols.length) {
    return <div className="text-muted p-3">No data returned.</div>
  }

  return (
    <div className="tc-preview-grid">
      <div style={{ width: '100%' }}>
        <AgGridReact
          theme={themeQuartz}
          columnDefs={resolvedColDefs}
          rowData={rowData}
          defaultColDef={defaultColDef}
          columnTypes={CUSTOM_COLUMN_TYPES}
          domLayout="autoHeight"
          suppressCellFocus={true}
          enableCellTextSelection={true}
          animateRows={false}
        />
      </div>
      <div className="text-muted small mt-1">
        Showing {Math.min(prevRows.length, rowData.length)} of {prevRows.length} rows
      </div>
    </div>
  )
}
