// @posterra/grid-utils — shared AG Grid utilities for portal + designer
//
// Single source of truth for formatters, renderers, column types, and
// resolveColumnDefs(). Both React apps import from here instead of
// maintaining duplicate registries.

export { VALUE_FORMATTERS } from './formatters'
export { CUSTOM_COLUMN_TYPES, TYPE_DEFAULTS } from './columnTypes'
export { CELL_RENDERERS, ComplianceStrip } from './renderers.jsx'
export { resolveColumnDefs } from './resolveColumnDefs.jsx'

// Smart Table cell recipes (chart_type='smart_table' — independent of AG Grid)
export { CELL_RECIPES, CellHost, VARIANT_STYLES } from './cellRecipes.jsx'
export { default as SmartTable } from './SmartTable.jsx'

// v5 widgets — attribute_grid + metric_list. Components are BODY-ONLY (host
// owns card chrome) and ship their own stylesheet (widgetCards.css) so the
// designer preview matches the portal without portal CSS.
export { default as AttributeGrid } from './AttributeGrid.jsx'
export { default as MetricList } from './MetricList.jsx'
export { normalizeAttributeGrid, normalizeMetricList } from './configNormalizer'
export { effectiveColumns, resolvePlacement } from './placement'
export {
  ATTRIBUTE_GRID_DEFAULTS, METRIC_LIST_DEFAULTS, FIELD_ITEM_DEFAULTS,
  STATUS_RULE_DEFAULTS, METRIC_SETTING_DEFAULTS, DIRECTIONS, LEGEND_MODES,
  ATTR_FORMAT_TYPES, METRIC_FORMAT_TYPES, LINK_TYPES, DATA_SHAPES,
} from './configDefaults'
