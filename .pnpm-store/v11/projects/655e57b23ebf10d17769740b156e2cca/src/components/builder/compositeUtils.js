/**
 * compositeUtils — shared helpers for the Composite chart type.
 *
 * ONE serialization everywhere: `serializeCompositeChildren` is the single
 * source of truth for the `composite_children` payload shape, used by BOTH
 * the save path (WidgetBuilder.buildCreatePayload) and the preview path
 * (LivePreview.buildPreviewPayload). Do not fork the shape.
 */

// v1 child chart_types — keep aligned with the backend child set in
// posterra_portal/models/dashboard_widget_composite_item.py (_CHILD_CHART_TYPES)
// and childRegistry.jsx on the portal React side.
export const COMPOSITE_CHILD_TYPES = [
  { key: 'donut',       label: 'Donut',       icon: 'fa-circle-o-notch' },
  { key: 'pie',         label: 'Pie',         icon: 'fa-pie-chart' },
  { key: 'bar',         label: 'Bar',         icon: 'fa-bar-chart' },
  { key: 'line',        label: 'Line',        icon: 'fa-line-chart' },
  { key: 'kpi',         label: 'KPI',         icon: 'fa-hashtag' },
  { key: 'status_kpi',  label: 'Status KPI',  icon: 'fa-flag' },
  { key: 'kpi_strip',   label: 'KPI Strip',   icon: 'fa-ellipsis-h' },
  { key: 'table',       label: 'Table',       icon: 'fa-table' },
  { key: 'smart_table', label: 'Smart Table', icon: 'fa-th-list' },
  { key: 'gauge',       label: 'Gauge',       icon: 'fa-tachometer' },
  { key: 'gauge_kpi',   label: 'Gauge + KPI', icon: 'fa-dashboard' },
  { key: 'sankey',      label: 'Sankey',      icon: 'fa-random' },
  { key: 'legend_list', label: 'Legend List', icon: 'fa-list-ul' },
  { key: 'text_note',   label: 'Text Note',   icon: 'fa-sticky-note-o' },
]

export const COMPOSITE_CHILD_TYPE_KEYS = COMPOSITE_CHILD_TYPES.map(t => t.key)

// Column-field validity per child type — used when switching a child's type
// (kept columns are revalidated; incompatible ones are dropped).
const STATUS_COLUMN_TYPES = ['kpi', 'status_kpi', 'kpi_strip']
const SERIES_COLUMN_TYPES = ['bar', 'line']

let _childUid = 1

/**
 * Factory for a new composite child block.
 * `strategy` ('shared' | 'own') sets the initial data_mode;
 * `index` drives simple side-by-side auto-placement (even → cols 1-6,
 * odd → cols 7-12) — the admin adjusts with the layout steppers.
 */
export function createCompositeChild(chartType, strategy, index = 0) {
  return {
    _uid: `cc${_childUid++}`,          // builder-only key (stripped on save)
    name: '',
    chart_type: chartType,
    is_active: true,
    data_mode: strategy === 'own' ? 'own_sql' : 'inherit_parent',
    dataModeOverridden: false,          // builder-only: survives strategy re-defaults
    query_sql: '',
    schema_source_id: null,
    where_clause_exclude: '',
    x_column: '',
    y_columns: '',
    series_column: '',
    status_column: '',
    col_start: index % 2 === 0 ? 1 : 7,
    col_span: 6,
    row_start: 0,                       // 0 = auto-flow
    row_span: 1,
    min_height_px: 240,
    content_vertical_align: 'stretch',   // stretch = original fill behavior
    content_horizontal_align: 'stretch',
    visual_config: {},                  // object in state; JSON string on save
    table_column_config: [],            // array in state; JSON string on save
    smart_table_config: { columns: [], table: {} },  // object in state; JSON string on save
    color_custom_json: '',
    text_note_body: '',
    kpi_format: 'number',
    kpi_prefix: '',
    kpi_suffix: '',
    metric_direction: '',
    bar_stack: false,
  }
}

/**
 * Type-switch reset rules (strict — agreed in plan):
 *   KEEP:  name/title, layout (incl. content_vertical_align /
 *          content_horizontal_align — alignment is layout config),
 *          data_mode (+overridden flag), query_sql, schema_source_id,
 *          where_clause_exclude, color_custom_json
 *          (generic ECharts palette — valid for any type)
 *   KEEP*: x/y/series/status column names revalidated against the new type
 *   CLEAR: visual_config, table_column_config, kpi/gauge specifics,
 *          text_note_body, bar_stack
 */
export function applyChildTypeSwitch(child, newType) {
  return {
    ...child,
    chart_type: newType,
    // Revalidate kept columns against the new type
    x_column: newType === 'text_note' ? '' : child.x_column,
    y_columns: newType === 'text_note' ? '' : child.y_columns,
    series_column: SERIES_COLUMN_TYPES.includes(newType) ? child.series_column : '',
    status_column: STATUS_COLUMN_TYPES.includes(newType) ? child.status_column : '',
    // Clear type-specific configs
    visual_config: {},
    table_column_config: [],
    smart_table_config: { columns: [], table: {} },
    text_note_body: '',
    bar_stack: false,
    kpi_format: 'number',
    kpi_prefix: '',
    kpi_suffix: '',
    metric_direction: '',
  }
}

/**
 * THE composite_children serialization — used verbatim by save AND preview.
 * Children are emitted in array order with stable sequence = (idx+1)*10.
 */
export function serializeCompositeChildren(children) {
  return (children || []).map((c, idx) => ({
    sequence: (idx + 1) * 10,
    name: c.name || '',
    chart_type: c.chart_type,
    is_active: c.is_active !== false,
    data_mode: c.data_mode || 'inherit_parent',
    query_sql: c.data_mode === 'own_sql' ? (c.query_sql || '') : '',
    schema_source_id: c.schema_source_id || null,
    where_clause_exclude: c.where_clause_exclude || '',
    x_column: c.x_column || '',
    y_columns: c.y_columns || '',
    series_column: c.series_column || '',
    status_column: c.status_column || '',
    col_start: Number(c.col_start) || 1,
    col_span: Number(c.col_span) || 6,
    row_start: Number(c.row_start) || 0,
    row_span: Number(c.row_span) || 1,
    min_height_px: Number(c.min_height_px) || 240,
    content_vertical_align: c.content_vertical_align || 'stretch',
    content_horizontal_align: c.content_horizontal_align || 'stretch',
    visual_config: c.visual_config && Object.keys(c.visual_config).length
      ? JSON.stringify(c.visual_config) : '',
    table_column_config: Array.isArray(c.table_column_config) && c.table_column_config.length
      ? JSON.stringify(c.table_column_config) : '',
    smart_table_config: c.smart_table_config && (c.smart_table_config.columns || []).length
      ? JSON.stringify(c.smart_table_config) : '',
    color_custom_json: c.color_custom_json || '',
    text_note_body: c.text_note_body || '',
    kpi_format: c.kpi_format || 'number',
    kpi_prefix: c.kpi_prefix || '',
    kpi_suffix: c.kpi_suffix || '',
    metric_direction: c.metric_direction || '',
    bar_stack: !!c.bar_stack,
  }))
}

/**
 * Inverse of serializeCompositeChildren — hydrate builder state from a
 * library_detail `composite_children` array (JSON strings → objects).
 * `strategyDefault` marks dataModeOverridden for children that deviate.
 */
export function hydrateCompositeChildren(rawChildren, strategyDefault) {
  const defMode = strategyDefault === 'own' ? 'own_sql' : 'inherit_parent'
  return (rawChildren || []).map(c => ({
    _uid: `cc${_childUid++}`,
    name: c.name || '',
    chart_type: c.chart_type || 'kpi',
    is_active: c.is_active !== false,
    data_mode: c.data_mode || 'inherit_parent',
    dataModeOverridden: (c.data_mode || 'inherit_parent') !== defMode,
    query_sql: c.query_sql || '',
    schema_source_id: c.schema_source_id || null,
    where_clause_exclude: c.where_clause_exclude || '',
    x_column: c.x_column || '',
    y_columns: c.y_columns || '',
    series_column: c.series_column || '',
    status_column: c.status_column || '',
    col_start: Number(c.col_start) || 1,
    col_span: Number(c.col_span) || 6,
    row_start: Number(c.row_start) || 0,
    row_span: Number(c.row_span) || 1,
    min_height_px: Number(c.min_height_px) || 240,
    content_vertical_align: c.content_vertical_align || 'stretch',
    content_horizontal_align: c.content_horizontal_align || 'stretch',
    visual_config: (() => {
      try {
        const v = c.visual_config
        if (!v) return {}
        return typeof v === 'string' ? (JSON.parse(v) || {}) : v
      } catch { return {} }
    })(),
    table_column_config: (() => {
      try {
        const v = c.table_column_config
        if (!v) return []
        return typeof v === 'string' ? (JSON.parse(v) || []) : v
      } catch { return [] }
    })(),
    smart_table_config: (() => {
      const empty = { columns: [], table: {} }
      try {
        const v = c.smart_table_config
        if (!v) return empty
        const parsed = typeof v === 'string' ? JSON.parse(v) : v
        return (parsed && typeof parsed === 'object')
          ? { columns: parsed.columns || [], table: parsed.table || {} }
          : empty
      } catch { return empty }
    })(),
    color_custom_json: c.color_custom_json || '',
    text_note_body: c.text_note_body || '',
    kpi_format: c.kpi_format || 'number',
    kpi_prefix: c.kpi_prefix || '',
    kpi_suffix: c.kpi_suffix || '',
    metric_direction: c.metric_direction || '',
    bar_stack: !!c.bar_stack,
  }))
}

/** Derive the data strategy from hydrated children (edit mode). */
export function deriveStrategy(rawChildren) {
  const kids = rawChildren || []
  if (!kids.length) return 'shared'
  return kids.every(c => c.data_mode === 'own_sql') ? 'own' : 'shared'
}

/** True when at least one active non-text_note child inherits the parent SQL. */
export function anyChildInherits(children) {
  return (children || []).some(c =>
    c.is_active !== false
    && c.chart_type !== 'text_note'
    && (c.data_mode || 'inherit_parent') === 'inherit_parent'
  )
}
