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
import TableConfigurator  from './TableConfigurator'
import AiSqlEditor        from './AiSqlEditor'
import WidgetControlsStep from './WidgetControlsStep'
import OptionTabBar        from './OptionTabBar'

function getSteps(chartType, scopeMode) {
  const steps = [
    { key: 'chart_type', label: 'Chart Type' },
    { key: 'controls',   label: 'Widget Controls' },
  ]
  steps.push({ key: 'data_source', label: 'Data Source' })
  if (chartType !== 'table') {
    steps.push({ key: 'columns', label: 'Columns' })
  }
  steps.push({ key: 'filters', label: 'Filters & Actions' })
  steps.push(chartType === 'table'
    ? { key: 'configure', label: 'Configure Table' }
    : { key: 'preview', label: 'Preview & Save' }
  )
  return steps
}

// Keep legacy constants for backward compat
const CHART_STEPS = getSteps('bar', 'none')
const TABLE_STEPS = getSteps('table', 'none')
const STEPS = CHART_STEPS

/**
 * getActiveConfig — returns the config object for the currently active scope option.
 * When scopeMode = 'none', returns the top-level state (backward compatible).
 * When scopeMode = 'independent', returns optionConfigs[activeScopeIdx].
 */
function getActiveConfig(state) {
  if (state.scopeMode !== 'none' && state.optionConfigs?.length > 0) {
    return state.optionConfigs[state.activeScopeIdx || 0] || state
  }
  return state
}

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

  // Widget Controls (optional, collapsed by default)
  scopeMode: 'none',
  scopeUi: 'toggle',
  scopeQueryMode: 'query',
  scopeParamName: '',
  scopeLabel: '',
  scopeDefaultValue: '',
  scopeOptions: [],          // [{label, value, icon}] — option identity
  optionConfigs: [],         // per-option full config (dataMode, sources, customSql, etc.)
  activeScopeIdx: 0,         // which option tab is active in steps 2-5
  searchEnabled: false,
  searchPlaceholder: 'Search...',

  // Visual config flags (chart-specific, from flag schema)
  visualFlags: {},

  // Step 5
  appearance: {
    title: '',
    colorPalette: 'default',
    colSpan: 50,
    rowSpan: 1,
    chartHeight: 350,
    showLegend: true,
    showAxisLabels: true,
    showDataLabels: false,
    barStack: false,
  },

  // Step 6
  generatedSql: '',

  // Table column config (AG Grid columnDefs — only for chart_type 'table')
  tableColumnConfig: [],

  // AI Assistant state
  aiState: {
    prompt: '',
    generatedSql: '',
    xColumn: '',
    yColumns: '',
    explanation: '',
    warnings: [],
  },
}

// Helper: route a state update to optionConfigs[activeScopeIdx] when scope is active
function _routeToOption(state, updates) {
  if (state.scopeMode !== 'none' && state.optionConfigs?.length > 0) {
    const idx = state.activeScopeIdx || 0
    const configs = [...state.optionConfigs]
    configs[idx] = { ...configs[idx], ...updates }
    return { ...state, optionConfigs: configs }
  }
  return { ...state, ...updates }
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_STEP':
      return { ...state, step: action.step }
    case 'NEXT': {
      const maxStep = getSteps(state.chartType, state.scopeMode).length - 1
      return { ...state, step: Math.min(state.step + 1, maxStep) }
    }
    case 'PREV':
      return { ...state, step: Math.max(state.step - 1, 0) }
    case 'SET_CHART_TYPE':
      return { ...state, chartType: action.value }
    case 'SET_ACTIVE_SCOPE_IDX':
      return { ...state, activeScopeIdx: action.value }
    // Per-option config actions — routed via _routeToOption
    case 'SET_DATA_MODE':
      return _routeToOption(state, { dataMode: action.value })
    case 'SET_SOURCES':
      return _routeToOption(state, { sources: action.value })
    case 'SET_JOINS':
      return _routeToOption(state, { joins: action.value })
    case 'UPDATE_CUSTOM_SQL': {
      const cfg = getActiveConfig(state)
      return _routeToOption(state, { customSql: { ...(cfg.customSql || {}), ...action.value } })
    }
    case 'SET_AI_PROMPT': {
      const cfg = getActiveConfig(state)
      return _routeToOption(state, { aiState: { ...(cfg.aiState || {}), prompt: action.value } })
    }
    case 'SET_AI_RESULT': {
      const cfg = getActiveConfig(state)
      return _routeToOption(state, { aiState: { ...(cfg.aiState || {}), ...action.value } })
    }
    case 'CLEAR_AI_STATE':
      return _routeToOption(state, { aiState: { prompt: '', generatedSql: '', xColumn: '', yColumns: '', explanation: '', warnings: [] } })
    case 'SET_X_COLUMN':
      return _routeToOption(state, { xColumn: action.value })
    case 'SET_COLUMNS':
      return _routeToOption(state, { columns: action.value })
    case 'SET_SERIES_COLUMN':
      return _routeToOption(state, { seriesColumn: action.value })
    case 'SET_ORDER_BY':
      return _routeToOption(state, { orderBy: action.value })
    case 'SET_LIMIT':
      return _routeToOption(state, { limit: action.value })
    case 'UPDATE_COLUMN_MAPPER':
      return _routeToOption(state, action.value)
    case 'UPDATE_FILTERS': {
      // Filter/action updates and scope config updates both come through here
      // Scope-level fields (scopeMode, scopeOptions, etc.) go to top-level state
      // Per-option fields (filters, clickAction, etc.) go to active option
      const scopeKeys = new Set([
        'scopeMode', 'scopeUi', 'scopeQueryMode', 'scopeParamName',
        'scopeLabel', 'scopeDefaultValue', 'scopeOptions', 'optionConfigs',
        'activeScopeIdx', 'searchEnabled', 'searchPlaceholder',
      ])
      const topLevel = {}
      const optionLevel = {}
      for (const [k, v] of Object.entries(action.value)) {
        if (scopeKeys.has(k)) topLevel[k] = v
        else optionLevel[k] = v
      }
      let newState = Object.keys(topLevel).length
        ? { ...state, ...topLevel }
        : state
      if (Object.keys(optionLevel).length) {
        newState = _routeToOption(newState, optionLevel)
      }
      return newState
    }
    case 'SET_VISUAL_FLAG':
      return { ...state, visualFlags: { ...state.visualFlags, [action.flag]: action.value } }
    case 'SET_VISUAL_FLAGS':
      return { ...state, visualFlags: action.value }
    case 'SET_APPEARANCE':
      return { ...state, appearance: action.value }
    case 'SET_GENERATED_SQL':
      return _routeToOption(state, { generatedSql: action.value })
    case 'SET_TABLE_COLUMN_CONFIG':
      return _routeToOption(state, { tableColumnConfig: action.value })
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
        y: bcColumns.filter(c => c.axis === 'y').map(c => ({
          ...c,
          weightColumn: c.weight_column || c.weightColumn || '',
        })),
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
          rowSpan: d.default_row_span || 1,
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
        tableColumnConfig: (() => {
          try {
            return d.table_column_config
              ? (typeof d.table_column_config === 'string'
                  ? JSON.parse(d.table_column_config)
                  : d.table_column_config)
              : []
          } catch { return [] }
        })(),
        // Widget-Scoped Controls
        scopeMode: d.scope_mode || 'none',
        scopeUi: d.scope_ui || 'toggle',
        scopeQueryMode: d.scope_query_mode || 'parameter',
        scopeParamName: d.scope_param_name || '',
        scopeLabel: d.scope_label || '',
        scopeDefaultValue: d.scope_default_value || '',
        searchEnabled: d.search_enabled || false,
        searchPlaceholder: d.search_placeholder || 'Search...',
        activeScopeIdx: 0,
        // Restore scope options + per-option configs
        scopeOptions: (d.scope_options || []).map(o => ({
          label: o.label || '',
          value: o.value || '',
          icon: o.icon || '',
        })),
        optionConfigs: (d.scope_options || []).map(o => ({
          dataMode: o.query_sql ? 'custom_sql' : 'custom_sql',
          sources: [],
          joins: [],
          customSql: {
            sql: o.query_sql || '',
            xColumn: o.x_column || '',
            yColumns: o.y_columns || '',
            seriesColumn: o.series_column || '',
            testResult: null,
            testParams: {},
          },
          xColumn: o.x_column || '',
          columns: [],
          seriesColumn: o.series_column || '',
          orderBy: '',
          limit: '',
          filters: [],
          clickAction: o.click_action || 'none',
          actionPageKey: o.action_page_key || '',
          actionTabKey: o.action_tab_key || '',
          actionPassValueAs: o.action_pass_value_as || '',
          drillDetailColumns: o.drill_detail_columns || '',
          actionUrlTemplate: o.action_url_template || '',
          tableColumnConfig: (() => {
            try {
              return o.table_column_config
                ? (typeof o.table_column_config === 'string'
                    ? JSON.parse(o.table_column_config)
                    : o.table_column_config)
                : []
            } catch { return [] }
          })(),
          generatedSql: '',
          aiState: { prompt: '', generatedSql: '', xColumn: '', yColumns: '', explanation: '', warnings: [] },
        })),
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

  const handleSave = useCallback(async (overrides = {}) => {
    setSaving(true)
    setSaveError(null)
    try {
      const payload = { ...buildCreatePayload(state), ...overrides }
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

  const activeSteps = getSteps(state.chartType, state.scopeMode)
  const currentStep = activeSteps[state.step] || activeSteps[0]
  const currentStepKey = currentStep?.key || ''
  const canNext = state.step < activeSteps.length - 1
  const canPrev = state.step > 0
  const isEditing = !!editId
  const isTableConfigStep = currentStepKey === 'configure'
  const hasScope = state.scopeMode !== 'none' && state.scopeOptions?.length > 0
  const ac = getActiveConfig(state)  // active option config (or top-level state)

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
                Step {state.step + 1} of {activeSteps.length} &mdash; {currentStep.label}
              </p>
            </div>
          </div>
          <button type="button" className="wb-btn wb-btn--ghost" onClick={onClose}>
            <i className="fa fa-ellipsis-h" />
          </button>
        </div>

        {/* Step tabs */}
        <div className="dd-wizard-tabs">
          {activeSteps.map((s, i) => (
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
          {currentStepKey === 'chart_type' && 'Choose how this widget displays data.'}
          {currentStepKey === 'controls' && 'Add toggle buttons, dropdown filters, or search bar (optional).'}
          {currentStepKey === 'data_source' && 'Select your data source — visual table builder or custom SQL.'}
          {currentStepKey === 'columns' && 'Map columns to axes and configure aggregation.'}
          {currentStepKey === 'filters' && 'Add WHERE filters and configure click actions.'}
          {currentStepKey === 'configure' && 'Configure table columns and preview with real data.'}
          {currentStepKey === 'preview' && 'Preview your widget and save it to the library.'}
        </div>

        {/* Body */}
        <div className="dd-wizard-body">
          {saveError && (
            <div className="wb-preview-error mb-3">
              <i className="fa fa-exclamation-triangle me-1" />
              {saveError}
            </div>
          )}

          {/* Step 0: Chart Type */}
          {currentStepKey === 'chart_type' && (
            <ChartTypePicker
              selected={state.chartType}
              onSelect={v => {
                dispatch({ type: 'SET_CHART_TYPE', value: v })
                // Set sensible defaults for chart types that require visual flags.
                // KPI defaults to stat_card style — without this, the kpi_style
                // flag is missing from visual_config and the widget renders
                // without the trend arrow variant.
                const defaults = v === 'kpi' ? { kpi_style: 'stat_card' } : {}
                dispatch({ type: 'SET_VISUAL_FLAGS', value: defaults })
              }}
              visualFlags={state.visualFlags}
              onFlagChange={(flag, value) => dispatch({ type: 'SET_VISUAL_FLAG', flag, value })}
              barStack={state.appearance.barStack}
              onBarStack={v => dispatch({ type: 'SET_APPEARANCE', value: { ...state.appearance, barStack: v } })}
            />
          )}

          {/* Step 1: Widget Controls */}
          {currentStepKey === 'controls' && (
            <WidgetControlsStep
              scopeMode={state.scopeMode}
              scopeUi={state.scopeUi}
              scopeQueryMode={state.scopeQueryMode}
              scopeParamName={state.scopeParamName}
              scopeLabel={state.scopeLabel}
              searchEnabled={state.searchEnabled}
              searchPlaceholder={state.searchPlaceholder}
              scopeOptions={state.scopeOptions}
              optionConfigs={state.optionConfigs}
              onUpdate={v => dispatch({ type: 'UPDATE_FILTERS', value: v })}
            />
          )}

          {/* Step 2: Data Source */}
          {currentStepKey === 'data_source' && (
            <div>
              {hasScope && (
                <OptionTabBar
                  options={state.scopeOptions}
                  activeIdx={state.activeScopeIdx}
                  onSelect={idx => dispatch({ type: 'SET_ACTIVE_SCOPE_IDX', value: idx })}
                />
              )}
              <h3 className="wb-step-title">Data Source</h3>
              <div className="wb-field-group">
                <div className="wb-mode-toggle">
                  <button
                    type="button"
                    className={`wb-btn ${(ac.dataMode === 'visual' || ac.dataMode === 'visual_builder') ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                    onClick={() => dispatch({ type: 'SET_DATA_MODE', value: 'visual' })}
                  >
                    <i className="fa fa-mouse-pointer me-1" /> Visual Builder
                  </button>
                  <button
                    type="button"
                    className={`wb-btn ${ac.dataMode === 'custom_sql' ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                    onClick={() => dispatch({ type: 'SET_DATA_MODE', value: 'custom_sql' })}
                  >
                    <i className="fa fa-code me-1" /> Custom SQL
                  </button>
                  <button
                    type="button"
                    className={`wb-btn ${ac.dataMode === 'ai' ? 'wb-btn--primary' : 'wb-btn--outline'}`}
                    onClick={() => dispatch({ type: 'SET_DATA_MODE', value: 'ai' })}
                    style={ac.dataMode === 'ai' ? { background: '#7c3aed', borderColor: '#7c3aed' } : {}}
                  >
                    <i className="fa fa-magic me-1" /> AI Assistant
                  </button>
                </div>
              </div>

              {ac.dataMode === 'ai' ? (
                <AiSqlEditor
                  sources={ac.sources || []}
                  aiState={ac.aiState || {}}
                  chartType={state.chartType}
                  gaugeStyle={state.visualFlags?.gauge_style}
                  lineStyle={state.visualFlags?.line_style}
                  donutStyle={state.visualFlags?.donut_style}
                  ragLayout={state.visualFlags?.rag_layout}
                  kpiStyle={state.visualFlags?.kpi_style}
                  valueDisplay={state.visualFlags?.value_display}
                  appContext={appContext}
                  apiBase={apiBase}
                  onSourcesChange={s => dispatch({ type: 'SET_SOURCES', value: s })}
                  onUpdate={v => dispatch({ type: 'SET_AI_RESULT', value: v })}
                  onPromptChange={v => dispatch({ type: 'SET_AI_PROMPT', value: v })}
                  onSwitchToCustomSql={(sql, xCol, yCols, seriesCol) => {
                    dispatch({ type: 'SET_DATA_MODE', value: 'custom_sql' })
                    dispatch({ type: 'UPDATE_CUSTOM_SQL', value: { sql, xColumn: xCol, yColumns: yCols, seriesColumn: seriesCol || '' } })
                  }}
                />
              ) : (ac.dataMode === 'visual' || ac.dataMode === 'visual_builder') ? (
                <TableJoinBuilder
                  sources={ac.sources || []}
                  joins={ac.joins || []}
                  onUpdate={({ sources, joins }) => {
                    if (sources !== undefined) dispatch({ type: 'SET_SOURCES', value: sources })
                    if (joins !== undefined) dispatch({ type: 'SET_JOINS', value: joins })
                  }}
                  apiBase={apiBase}
                />
              ) : (
                <CustomSqlEditor
                  sql={(ac.customSql || {}).sql || ''}
                  xColumn={(ac.customSql || {}).xColumn || ''}
                  yColumns={(ac.customSql || {}).yColumns || ''}
                  seriesColumn={(ac.customSql || {}).seriesColumn || ''}
                  testResult={(ac.customSql || {}).testResult}
                  testParams={(ac.customSql || {}).testParams || {}}
                  onUpdate={v => dispatch({ type: 'UPDATE_CUSTOM_SQL', value: v })}
                  apiBase={apiBase}
                  appContext={appContext}
                  chartType={state.chartType}
                  donutStyle={state.visualFlags?.donut_style || 'standard'}
                  lineStyle={state.visualFlags?.line_style || 'basic'}
                  gaugeStyle={state.visualFlags?.gauge_style || 'standard'}
                />
              )}
            </div>
          )}

          {/* Columns step (chart types — visual mode) */}
          {currentStepKey === 'columns' && (
            <>
              {hasScope && (
                <OptionTabBar
                  options={state.scopeOptions}
                  activeIdx={state.activeScopeIdx}
                  onSelect={idx => dispatch({ type: 'SET_ACTIVE_SCOPE_IDX', value: idx })}
                />
              )}
              {(ac.dataMode === 'visual' || ac.dataMode === 'visual_builder') ? (
                <ColumnMapper
                  sources={ac.sources || []}
                  columns={ac.columns || []}
                  xColumn={ac.xColumn || ''}
                  seriesColumn={ac.seriesColumn || ''}
                  orderBy={ac.orderBy || ''}
                  limit={ac.limit || ''}
                  chartType={state.chartType}
                  visualFlags={state.visualFlags}
                  onUpdate={v => dispatch({ type: 'UPDATE_COLUMN_MAPPER', value: v })}
                />
              ) : (
                <div className="wb-step-skip">
                  <i className="fa fa-info-circle me-2" />
                  Column mapping is configured in the Custom SQL step. Click <strong>Next</strong> to continue.
                </div>
              )}
            </>
          )}

          {/* Filters & Actions step */}
          {currentStepKey === 'filters' && (
            <>
            {hasScope && (
              <OptionTabBar
                options={state.scopeOptions}
                activeIdx={state.activeScopeIdx}
                onSelect={idx => dispatch({ type: 'SET_ACTIVE_SCOPE_IDX', value: idx })}
              />
            )}
            <FilterActionConfig
              dataSourceMode={ac.dataMode || 'custom_sql'}
              sources={ac.sources || []}
              filters={ac.filters || []}
              clickAction={ac.clickAction || 'none'}
              actionPageKey={ac.actionPageKey || ''}
              actionTabKey={ac.actionTabKey || ''}
              actionPassValueAs={ac.actionPassValueAs || ''}
              drillDetailColumns={ac.drillDetailColumns || ''}
              actionUrlTemplate={ac.actionUrlTemplate || ''}
              chartType={state.chartType}
              onUpdate={v => dispatch({ type: 'UPDATE_FILTERS', value: v })}
              apiBase={apiBase}
            />
            </>
          )}

          {/* Table Configurator step */}
          {currentStepKey === 'configure' && (
            <>
            {hasScope && (
              <OptionTabBar
                options={state.scopeOptions}
                activeIdx={state.activeScopeIdx}
                onSelect={idx => dispatch({ type: 'SET_ACTIVE_SCOPE_IDX', value: idx })}
              />
            )}
            <TableConfigurator
              sources={ac.sources || []}
              joins={ac.joins || []}
              dataMode={ac.dataMode || 'custom_sql'}
              customSql={ac.customSql || {}}
              filters={ac.filters || []}
              visualFlags={state.visualFlags}
              appearance={state.appearance}
              tableColumnConfig={ac.tableColumnConfig || []}
              builderState={state}
              onUpdate={dispatch}
              onSave={handleSave}
              saving={saving}
              apiBase={apiBase}
              appContext={appContext}
              editId={editId}
            />
            </>
          )}

          {/* Preview & Save step (charts) */}
          {currentStepKey === 'preview' && (
            <>
              {hasScope && (
                <OptionTabBar
                  options={state.scopeOptions}
                  activeIdx={state.activeScopeIdx}
                  onSelect={idx => dispatch({ type: 'SET_ACTIVE_SCOPE_IDX', value: idx })}
                />
              )}
              <LivePreview
                builderState={state}
                generatedSql={ac.generatedSql || ''}
                onSqlGenerated={sql => dispatch({ type: 'SET_GENERATED_SQL', value: sql })}
                onSave={handleSave}
                saving={saving}
                apiBase={apiBase}
                appContext={appContext}
                onAppearanceChange={v => dispatch({ type: 'SET_APPEARANCE', value: v })}
                editId={editId}
              />
            </>
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
            {activeSteps.map((_, i) => (
              <span
                key={i}
                className={`dd-wizard-dot ${i === state.step ? 'dd-wizard-dot--active' : ''} ${i < state.step ? 'dd-wizard-dot--done' : ''}`}
              />
            ))}
          </div>
          {canNext && !isTableConfigStep ? (
            <button
              type="button"
              className="dd-wizard-btn dd-wizard-btn--primary"
              onClick={() => dispatch({ type: 'NEXT' })}
            >
              Next &mdash; {activeSteps[state.step + 1]?.label} <i className="fa fa-arrow-right ms-1" />
            </button>
          ) : (
            <div /> // placeholder — save is in LivePreview or TableConfigurator
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
  // DEBUG: log scope state at save time
  console.log('[buildCreatePayload] scopeMode:', state.scopeMode,
    'scopeOptions:', state.scopeOptions?.length,
    'optionConfigs:', state.optionConfigs?.length,
    'option0 sql:', state.optionConfigs?.[0]?.customSql?.sql?.substring(0, 50))
  const base = {
    chart_type: state.chartType,
    data_mode: state.dataMode,
    name: state.appearance.title || `New ${state.chartType} widget`,
    col_span: [25,33,50,67,100].includes(Number(state.appearance.colSpan))
      ? {25:'3',33:'4',50:'6',67:'8',100:'12'}[Number(state.appearance.colSpan)]
      : '6',
    width_pct: Number(state.appearance.colSpan) || 50,
    chart_height: state.appearance.chartHeight || 350,
    row_span: state.appearance.rowSpan || 1,
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
    // Table column config (AG Grid columnDefs) — only meaningful for table type
    table_column_config: state.chartType === 'table' && state.tableColumnConfig?.length
      ? JSON.stringify(state.tableColumnConfig)
      : '',
    // Widget-Scoped Controls (only include if configured)
    ...(state.scopeMode !== 'none' ? {
      scope_mode: state.scopeMode,
      scope_ui: state.scopeUi,
      scope_query_mode: (state.optionConfigs || []).some(cfg => {
        const sql = cfg.dataMode === 'ai'
          ? cfg.aiState?.generatedSql
          : cfg.customSql?.sql
        return sql && sql.trim()
      }) ? 'query' : (state.scopeQueryMode || 'parameter'),
      scope_param_name: state.scopeParamName || '',
      scope_label: state.scopeLabel || '',
      scope_default_value: state.scopeDefaultValue || '',
      scope_options: (state.scopeOptions || []).map((opt, idx) => {
        // Merge identity (from scopeOptions) + config (from optionConfigs)
        const cfg = (state.optionConfigs || [])[idx] || {}
        const cs = cfg.customSql || {}
        const ai = cfg.aiState || {}
        const optSql = cfg.dataMode === 'ai'
          ? (ai.generatedSql || '')
          : (cs.sql || '')
        return {
          label: opt.label || '',
          value: opt.value || '',
          icon: opt.icon || '',
          sequence: (idx + 1) * 10,
          query_sql: optSql,
          table_column_config: cfg.tableColumnConfig?.length
            ? JSON.stringify(cfg.tableColumnConfig) : '',
          x_column: cs.xColumn || cfg.xColumn || '',
          y_columns: cs.yColumns || cfg.yColumns || '',
          series_column: cs.seriesColumn || cfg.seriesColumn || '',
          click_action: cfg.clickAction || 'none',
          action_page_key: cfg.actionPageKey || '',
          action_tab_key: cfg.actionTabKey || '',
          action_pass_value_as: cfg.actionPassValueAs || '',
          drill_detail_columns: cfg.drillDetailColumns || '',
          action_url_template: cfg.actionUrlTemplate || '',
        }
      }),
    } : {}),
    ...(state.searchEnabled ? {
      search_enabled: true,
      search_placeholder: state.searchPlaceholder || 'Search...',
    } : {}),
  }

  // When scope is configured, use first option's config as the main widget SQL
  // (so the widget has a valid SQL even without toggle interaction)
  const effectiveConfig = (state.scopeMode !== 'none' && state.optionConfigs?.length)
    ? state.optionConfigs[0]
    : state
  const effectiveDataMode = effectiveConfig.dataMode || state.dataMode

  if (effectiveDataMode === 'custom_sql') {
    const cs = effectiveConfig.customSql || state.customSql || {}
    return {
      ...base,
      data_mode: 'custom_sql',
      query_sql: cs.sql || '',
      x_column: cs.xColumn || '',
      y_columns: cs.yColumns || '',
      series_column: cs.seriesColumn || '',
    }
  }

  // AI mode: save as custom_sql — the generated SQL is the artifact
  if (effectiveDataMode === 'ai') {
    const ai = effectiveConfig.aiState || state.aiState || {}
    return {
      ...base,
      data_mode: 'custom_sql',  // stored as custom_sql for portal execution
      query_sql: ai.generatedSql || '',
      x_column: ai.xColumn || '',
      y_columns: ai.yColumns || '',
      series_column: ai.seriesColumn || '',
      builder_config: JSON.stringify({
        ai_prompt: ai.prompt || '',
        ai_generated: true,
      }),
    }
  }

  // ── Table type (visual mode): build columns from tableColumnConfig ──────────
  if (state.chartType === 'table' && state.tableColumnConfig?.length) {
    const tcc = state.tableColumnConfig
    const sources = (state.sources || []).map(s => ({ id: s.id, alias: s.alias || null }))
    const defaultSourceId = sources[0]?.id ?? null
    // Build flatColumns from tableColumnConfig for QueryBuilder compatibility
    const flatColumns = tcc.map(col => ({
      source_id: col.source_id || defaultSourceId,
      column: col.column || col.field,
      agg: null,
      alias: col.alias || col.field,
      axis: 'y',
    }))
    // Collect fields referenced by renderers (composite lines, dualValue secondary)
    // that aren't already in flatColumns — they must be in the SQL SELECT
    const existingFields = new Set(flatColumns.map(c => c.column))
    for (const col of tcc) {
      const params = col.cellRendererParams || {}
      // CompositeRenderer: lines[].fields[]
      if (Array.isArray(params.lines)) {
        for (const line of params.lines) {
          for (const f of (line.fields || [])) {
            if (!existingFields.has(f)) {
              flatColumns.push({ source_id: defaultSourceId, column: f, agg: null, alias: f, axis: 'y' })
              existingFields.add(f)
            }
          }
        }
      }
      // DualValueRenderer: secondaryField
      if (params.secondaryField && !existingFields.has(params.secondaryField)) {
        flatColumns.push({ source_id: defaultSourceId, column: params.secondaryField, agg: null, alias: params.secondaryField, axis: 'y' })
        existingFields.add(params.secondaryField)
      }
    }
    return {
      ...base,
      sources,
      joins: state.joins || [],
      columns: flatColumns,
      x_column: flatColumns[0]?.alias || '',
      y_columns: flatColumns.map(c => c.alias).join(','),
      series_column: '',
      filters: state.filters || [],
      order_by: '',
      limit: null,
      generated_sql: '',
      builder_config: {
        sources,
        source_ids: sources.map(s => s.id),
        columns: flatColumns,
        filters: state.filters || [],
        group_by: [],
        order_by: '',
        limit: null,
      },
    }
  }

  // ── Chart types (visual mode): build columns from ColumnMapper ────────────
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
      const entry = {
        source_id: yc.source_id,
        column: yc.column,
        agg: yc.agg || 'sum',
        alias: yc.alias || yc.column,
        axis: 'y',
      }
      if (yc.weightColumn) entry.weight_column = yc.weightColumn
      flatColumns.push(entry)
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
    builder_config: (() => {
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
