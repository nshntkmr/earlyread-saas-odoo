import React, { useReducer, useState, useCallback, useEffect } from 'react'
import { designerFetch } from '../../api/client'
import { libraryCreateUrl, libraryDetailUrl, sourceDetailUrl } from '../../api/endpoints'

// Step components
import ChartTypePicker    from './ChartTypePicker'
import TableJoinBuilder   from './TableJoinBuilder'
import CustomSqlEditor    from './CustomSqlEditor'
import ColumnMapper       from './ColumnMapper'
import FilterActionConfig from './FilterActionConfig'
import LivePreview        from './LivePreview'

const STEPS = [
  { key: 'chart_type',   label: 'Chart Type' },
  { key: 'data_source',  label: 'Data Source' },
  { key: 'columns',      label: 'Columns' },
  { key: 'filters',      label: 'Filters & Actions' },
  { key: 'preview',      label: 'Preview & Save' },
]

// ── State ────────────────────────────────────────────────────────────────────

const initialState = {
  step: 0,

  // Step 1
  chartType: 'bar',

  // Step 2
  dataMode: 'visual',           // 'visual' | 'custom_sql'
  sources: [],                  // selected sources with columns
  joins: [],                    // [{left_source_id, right_source_id, left_column, right_column}]
  customSql: {
    sql: '',
    xColumn: '',
    yColumns: '',
    seriesColumn: '',
    testResult: null,
    testParams: {},
  },

  // Step 3 (visual mode)
  xColumn: '',
  columns: [],                  // [{source_id, column, agg, alias, axis}]
  seriesColumn: '',
  orderBy: '',
  limit: '',

  // Step 4
  filters: [],
  clickAction: 'none',
  actionPageKey: '',
  actionTabKey: '',
  actionPassValueAs: '',
  drillDetailColumns: '',
  actionUrlTemplate: '',

  // Visual config flags (chart-specific, from flag schema)
  visualFlags: {},

  // Step 5
  appearance: {
    title: '',
    colorPalette: 'default',
    colSpan: 50,
    chartHeight: 350,
    showLegend: true,
    showAxisLabels: true,
    showDataLabels: false,
    barStack: false,
  },

  // Step 6
  generatedSql: '',
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.step }
    case 'NEXT':
      return { ...state, step: Math.min(state.step + 1, STEPS.length - 1) }
    case 'PREV':
      return { ...state, step: Math.max(state.step - 1, 0) }
    case 'SET_CHART_TYPE':
      return { ...state, chartType: action.value }
    case 'SET_DATA_MODE':
      return { ...state, dataMode: action.value }
    case 'SET_SOURCES':
      return { ...state, sources: action.value }
    case 'SET_JOINS':
      return { ...state, joins: action.value }
    case 'UPDATE_CUSTOM_SQL':
      return { ...state, customSql: { ...state.customSql, ...action.value } }
    case 'SET_X_COLUMN':
      return { ...state, xColumn: action.value }
    case 'SET_COLUMNS':
      return { ...state, columns: action.value }
    case 'SET_SERIES_COLUMN':
      return { ...state, seriesColumn: action.value }
    case 'SET_ORDER_BY':
      return { ...state, orderBy: action.value }
    case 'SET_LIMIT':
      return { ...state, limit: action.value }
    case 'UPDATE_COLUMN_MAPPER':
      return { ...state, ...action.value }
    case 'UPDATE_FILTERS':
      return { ...state, ...action.value }
    case 'SET_VISUAL_FLAG':
      return { ...state, visualFlags: { ...state.visualFlags, [action.flag]: action.value } }
    case 'SET_VISUAL_FLAGS':
      return { ...state, visualFlags: action.value }
    case 'SET_APPEARANCE':
      return { ...state, appearance: action.value }
    case 'SET_GENERATED_SQL':
      return { ...state, generatedSql: action.value }
    case 'LOAD_DEFINITION': {
      const d = action.value
      // Parse builder_config to restore visual builder state (sources, columns, filters, etc.)
      let bc = {}
      try {
        bc = d.builder_config ? (typeof d.builder_config === 'string' ? JSON.parse(d.builder_config) : d.builder_config) : {}
      } catch { bc = {} }

      // Restore column mappings from builder_config
      const bcColumns = bc.columns || []
      const restoredColumns = {
        x: bcColumns.find(c => c.axis === 'x') || null,
        y: bcColumns.filter(c => c.axis === 'y') || [],
        series: bcColumns.find(c => c.axis === 'series') || null,
      }

      return {
        ...initialState,
        step: 0,
        chartType: d.chart_type || 'bar',
        dataMode: (d.data_mode === 'visual' || d.data_mode === 'visual_builder' || bc.sources?.length) ? 'visual_builder' : (d.data_mode || 'custom_sql'),
        customSql: {
          sql: d.query_sql || '',
          xColumn: d.x_column || '',
          yColumns: d.y_columns || '',
          seriesColumn: d.series_column || '',
          testResult: null,
        },
        // Visual builder state from builder_config
        sources: bc.sources || [],
        columns: (d.data_mode === 'visual' || d.data_mode === 'visual_builder' || bc.sources?.length) ? restoredColumns : {},
        xColumn: d.x_column || '',
        seriesColumn: d.series_column || '',
        filters: bc.filters || [],
        orderBy: bc.order_by || '',
        limit: bc.limit || null,
        clickAction: d.click_action || 'none',
        actionPageKey: d.action_page_key || '',
        actionTabKey: d.action_tab_key || '',
        actionPassValueAs: d.action_pass_value_as || '',
        drillDetailColumns: d.drill_detail_columns || '',
        actionUrlTemplate: d.action_url_template || '',
        appearance: {
          title: d.name || '',
          colorPalette: d.color_palette || 'default',
          colSpan: d.default_width_pct || {'3':25,'4':33,'6':50,'8':67,'12':100}[d.default_col_span] || 50,
          chartHeight: d.chart_height || 350,
          showLegend: true,
          showAxisLabels: true,
          showDataLabels: false,
          barStack: d.bar_stack || false,
        },
        visualFlags: (() => {
          try { return d.visual_config ? JSON.parse(d.visual_config) : {} }
          catch { return {} }
        })(),
        generatedSql: d.generated_sql || '',
      }
    }
    case 'RESET':
      return { ...initialState }
    default:
      return state
  }
}

// ── Component ────────────────────────────────────────────────────────────────

/**
 * WidgetBuilder — 6-step wizard for creating/editing widget definitions.
 *
 * Props:
 *   isOpen           — boolean
 *   onClose          — () => void
 *   onWidgetCreated  — (definition) => void  — called after successful save
 *   apiBase          — string
 *   editId           — number|null — if set, loads this definition for editing
 */
export default function WidgetBuilder({
  isOpen, onClose, onWidgetCreated, apiBase, editId = null, appContext = null,
}) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [loadingEdit, setLoadingEdit] = useState(false)

  // Load existing definition for editing
  useEffect(() => {
    if (!editId || !isOpen) return
    setLoadingEdit(true)
    designerFetch(libraryDetailUrl(apiBase, editId))
      .then(def => {
        dispatch({ type: 'LOAD_DEFINITION', value: def })
      })
      .catch(err => setSaveError(`Failed to load: ${err.message}`))
      .finally(() => setLoadingEdit(false))
  }, [editId, isOpen, apiBase])

  // Auto-fetch column metadata for sources restored from builder_config.
  // builder_config stores only {id, alias} — no columns array.
  // ColumnMapper needs the full column list to render dropdown options.
  useEffect(() => {
    if (!state.sources || state.sources.length === 0) return
    const needsFetch = state.sources.some(s => !s.columns || s.columns.length === 0)
    if (!needsFetch) return

    Promise.all(
      state.sources.map(async (src) => {
        if (src.columns && src.columns.length > 0) return src
        try {
          const detail = await designerFetch(sourceDetailUrl(apiBase, src.id))
          return { ...src, columns: detail.columns || [], name: detail.name || src.name }
        } catch (err) {
          console.error(`Failed to fetch columns for source ${src.id}:`, err)
          return src
        }
      })
    ).then(enrichedSources => {
      dispatch({ type: 'SET_SOURCES', value: enrichedSources })
    })
  }, [state.sources.length, apiBase])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaveError(null)
    try {
      const payload = buildCreatePayload(state)
      let result
      if (editId) {
        result = await designerFetch(libraryDetailUrl(apiBase, editId), {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
      } else {
        result = await designerFetch(libraryCreateUrl(apiBase), {
          method: 'POST',
          body: JSON.stringify(payload),
        })
      }
      onWidgetCreated?.(result)
      dispatch({ type: 'RESET' })
      return result
    } catch (err) {
      setSaveError(err.message || 'Save failed')
      return null
    } finally {
      setSaving(false)
    }
  }, [state, apiBase, editId, onWidgetCreated])

  if (!isOpen) return null

  if (loadingEdit) {
    return (
      <div className="dd-page">
        <div className="dd-wizard" style={{ padding: '48px', textAlign: 'center' }}>
          <span className="spinner-border spinner-border-sm me-2" />
          Loading widget definition...
        </div>
      </div>
    )
  }

  const currentStep = STEPS[state.step]
  const canNext = state.step < STEPS.length - 1
  const canPrev = state.step > 0
  const isEditing = !!editId

  return (
    <div className="dd-page">
      <div className="dd-wizard">
        {/* Header */}
        <div className="dd-wizard-header">
          <div className="dd-wizard-header-left">
            <div className="dd-wizard-icon">
              <i className={`fa ${isEditing ? 'fa-pencil' : 'fa-th-large'}`} />
            </div>
            <div>
              <h2 className="dd-wizard-title">{isEditing ? 'Edit widget' : 'Create widget'}</h2>
              <p className="dd-wizard-subtitle">
                Step {state.step + 1} of {STEPS.length} &mdash; {currentStep.label}
              </p>
            </div>
          </div>
          <button type="button" className="wb-btn wb-btn--ghost" onClick={onClose}>
            <i className="fa fa-ellipsis-h" />
          </button>
        </div>

        {/* Step tabs */}
        <div className="dd-wizard-tabs">
          {STEPS.map((s, i) => (
            <button
              key={s.key}
              type="button"
              className={`dd-wizard-tab ${i === state.step ? 'dd-wizard-tab--active' : ''} ${i < state.step ? 'dd-wizard-tab--done' : ''}`}
              onClick={() => dispatch({ type: 'SET_STEP', step: i })}
            >
              {s.label}
            </button>
          ))}
        </div>

        {/* Instruction text */}
        <div className="dd-wizard-instruction">
          {state.step === 0 && 'Choose how this widget displays data.'}
          {state.step === 1 && 'Select your data source — visual table builder or custom SQL.'}
          {state.step === 2 && 'Map columns to axes and configure aggregation.'}
          {state.step === 3 && 'Add filters and configure click actions.'}
          {state.step === 4 && 'Preview your widget and save it to the library.'}
        </div>

        {/* Body */}
        <div className="dd-wizard-body">
          {saveError && (
            <div className="wb-preview-error mb-3">
              <i className="fa fa-exclamation-triangle me-1" />
              {saveError}
            </div>
          )}

          {/* Step 1: Chart Type */}
          {state.step === 0 && (
            <ChartTypePicker
              selected={state.chartType}
              onSelect={v => {
                dispatch({ type: 'SET_CHART_TYPE', value: v })
                dispatch({ type: 'SET_VISUAL_FLAGS', value: {} })
              }}
              visualFlags={state.visualFlags}
              onFlagChange={(flag, value) => dispatch({ type: 'SET_VISUAL_FLAG', flag, value })}
              barStack={state.appearance.barStack}
              onBarStack={v => dispatch({ type: 'SET_APPEARANCE', value: { ...state.appearance, barStack: v } })}
            />
          )}

          {/* Step 2: Data Source */}
          {state.step === 1 && (
            <div>
              <h3 className="wb-step-title">Data Source</h3>
              <div className="wb-field-group">
                <div className="wb-mode-toggle">
                  <button
                    type="button"
                    className={`wb-btn ${(state.dataMode === 'visual' || state.dataMode === 'visual_builder') ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                    onClick={() => dispatch({ type: 'SET_DATA_MODE', value: 'visual' })}
                  >
                    <i className="fa fa-mouse-pointer me-1" /> Visual Builder
                  </button>
                  <button
                    type="button"
                    className={`wb-btn ${state.dataMode === 'custom_sql' ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                    onClick={() => dispatch({ type: 'SET_DATA_MODE', value: 'custom_sql' })}
                  >
                    <i className="fa fa-code me-1" /> Custom SQL
                  </button>
                </div>
              </div>

              {(state.dataMode === 'visual' || state.dataMode === 'visual_builder') ? (
                <TableJoinBuilder
                  sources={state.sources}
                  joins={state.joins}
                  onUpdate={({ sources, joins }) => {
                    if (sources !== undefined) dispatch({ type: 'SET_SOURCES', value: sources })
                    if (joins !== undefined) dispatch({ type: 'SET_JOINS', value: joins })
                  }}
                  apiBase={apiBase}
                />
              ) : (
                <CustomSqlEditor
                  sql={state.customSql.sql}
                  xColumn={state.customSql.xColumn}
                  yColumns={state.customSql.yColumns}
                  seriesColumn={state.customSql.seriesColumn}
                  testResult={state.customSql.testResult}
                  testParams={state.customSql.testParams}
                  onUpdate={v => dispatch({ type: 'UPDATE_CUSTOM_SQL', value: v })}
                  apiBase={apiBase}
                  appContext={appContext}
                />
              )}
            </div>
          )}

          {/* Step 3: Columns (visual mode) */}
          {state.step === 2 && (
            (state.dataMode === 'visual' || state.dataMode === 'visual_builder') ? (
              <ColumnMapper
                sources={state.sources}
                columns={state.columns}
                xColumn={state.xColumn}
                seriesColumn={state.seriesColumn}
                orderBy={state.orderBy}
                limit={state.limit}
                chartType={state.chartType}
                onUpdate={v => dispatch({ type: 'UPDATE_COLUMN_MAPPER', value: v })}
              />
            ) : (
              <div className="wb-step-skip">
                <i className="fa fa-info-circle me-2" />
                Column mapping is configured in the Custom SQL step. Click <strong>Next</strong> to continue.
              </div>
            )
          )}

          {/* Step 4: Filters & Actions */}
          {state.step === 3 && (
            <FilterActionConfig
              dataSourceMode={state.dataMode}
              sources={state.sources}
              filters={state.filters}
              clickAction={state.clickAction}
              actionPageKey={state.actionPageKey}
              actionTabKey={state.actionTabKey}
              actionPassValueAs={state.actionPassValueAs}
              drillDetailColumns={state.drillDetailColumns}
              actionUrlTemplate={state.actionUrlTemplate}
              onUpdate={v => dispatch({ type: 'UPDATE_FILTERS', value: v })}
              apiBase={apiBase}
            />
          )}

          {/* Step 5: Preview & Save */}
          {state.step === 4 && (
            <LivePreview
              builderState={state}
              generatedSql={state.generatedSql}
              onSqlGenerated={sql => dispatch({ type: 'SET_GENERATED_SQL', value: sql })}
              onSave={handleSave}
              saving={saving}
              apiBase={apiBase}
              appContext={appContext}
              onAppearanceChange={v => dispatch({ type: 'SET_APPEARANCE', value: v })}
            />
          )}
        </div>

        {/* Footer navigation */}
        <div className="dd-wizard-footer">
          <button
            type="button"
            className="dd-wizard-btn dd-wizard-btn--outline"
            onClick={() => dispatch({ type: 'PREV' })}
            disabled={!canPrev}
          >
            <i className="fa fa-arrow-left me-1" /> Back
          </button>
          <div className="dd-wizard-step-dots">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`dd-wizard-dot ${i === state.step ? 'dd-wizard-dot--active' : ''} ${i < state.step ? 'dd-wizard-dot--done' : ''}`}
              />
            ))}
          </div>
          {canNext ? (
            <button
              type="button"
              className="dd-wizard-btn dd-wizard-btn--primary"
              onClick={() => dispatch({ type: 'NEXT' })}
            >
              Next &mdash; {STEPS[state.step + 1].label} <i className="fa fa-arrow-right ms-1" />
            </button>
          ) : (
            <div /> // placeholder — save is in LivePreview
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Build the POST payload for /dashboard/designer/api/library/create.
 * Creates a widget DEFINITION in the library (not an instance on a page).
 */
function buildCreatePayload(state) {
  const base = {
    chart_type: state.chartType,
    data_mode: state.dataMode,
    name: state.appearance.title || `New ${state.chartType} widget`,
    col_span: [25,33,50,67,100].includes(Number(state.appearance.colSpan))
      ? {25:'3',33:'4',50:'6',67:'8',100:'12'}[Number(state.appearance.colSpan)]
      : '6',
    width_pct: Number(state.appearance.colSpan) || 50,
    chart_height: state.appearance.chartHeight || 350,
    color_palette: state.appearance.colorPalette || 'default',
    show_legend: state.appearance.showLegend !== false,
    show_axis_labels: state.appearance.showAxisLabels !== false,
    show_data_labels: state.appearance.showDataLabels === true,
    bar_stack: state.chartType === 'bar' && (state.visualFlags.stack ?? state.appearance.barStack) === true,
    visual_config: Object.keys(state.visualFlags || {}).length > 0
      ? JSON.stringify(state.visualFlags)
      : '',
    click_action: state.clickAction || 'none',
    action_page_key: state.actionPageKey || '',
    action_tab_key: state.actionTabKey || '',
    action_pass_value_as: state.actionPassValueAs || '',
    drill_detail_columns: state.drillDetailColumns || '',
    action_url_template: state.actionUrlTemplate || '',
  }

  if (state.dataMode === 'custom_sql') {
    return {
      ...base,
      query_sql: state.customSql.sql || '',
      x_column: state.customSql.xColumn || '',
      y_columns: state.customSql.yColumns || '',
      series_column: state.customSql.seriesColumn || '',
    }
  }

  // Visual mode — build columns from ColumnMapper's {x, y, series} structure
  const colState = state.columns || {}
  const flatColumns = []

  if (colState.x && colState.x.column) {
    flatColumns.push({
      source_id: colState.x.source_id,
      column: colState.x.column,
      agg: null,
      alias: colState.x.alias || colState.x.column,
      axis: 'x',
    })
  }
  for (const yc of (colState.y || [])) {
    if (yc.column) {
      flatColumns.push({
        source_id: yc.source_id,
        column: yc.column,
        agg: yc.agg || 'sum',
        alias: yc.alias || yc.column,
        axis: 'y',
      })
    }
  }
  const seriesCol = colState.series
  if (seriesCol && seriesCol.column) {
    flatColumns.push({
      source_id: seriesCol.source_id,
      column: seriesCol.column,
      agg: null,
      alias: seriesCol.alias || seriesCol.column,
      axis: 'series',
    })
  }

  const sources = (state.sources || []).map(s => ({
    id: s.id,
    alias: s.alias || null,
  }))
  const filters = state.filters || []
  const orderBy = state.orderBy || ''
  const limit = state.limit || null

  return {
    ...base,
    sources,
    joins: state.joins || [],
    columns: flatColumns,
    x_column: colState.x?.alias || colState.x?.column || '',
    y_columns: (colState.y || []).map(c => c.alias || c.column).filter(Boolean).join(','),
    series_column: seriesCol?.alias || seriesCol?.column || '',
    filters,
    order_by: orderBy,
    limit,
    generated_sql: state.generatedSql || '',
    // Bundle visual builder state for edit/reload later
    // source_ids is what QueryBuilder needs; sources is what the React builder needs to restore
    builder_config: (() => {
      // Build group_by from x_column + series_column (same logic as preview)
      const groupBy = []
      if (colState.x && colState.x.column) {
        groupBy.push({ source_id: colState.x.source_id, column: colState.x.column })
      }
      if (seriesCol && seriesCol.column) {
        groupBy.push({ source_id: seriesCol.source_id, column: seriesCol.column })
      }
      return {
        sources,
        source_ids: sources.map(s => s.id),
        columns: flatColumns,
        filters,
        group_by: groupBy,
        order_by: orderBy,
        limit,
      }
    })(),
  }
}
