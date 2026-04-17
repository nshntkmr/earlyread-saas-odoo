// @posterra/grid-utils — shared AG Grid utilities for portal + designer
//
// Single source of truth for formatters, renderers, column types, and
// resolveColumnDefs(). Both React apps import from here instead of
// maintaining duplicate registries.

export { VALUE_FORMATTERS } from './formatters'
export { CUSTOM_COLUMN_TYPES, TYPE_DEFAULTS } from './columnTypes'
export { CELL_RENDERERS } from './renderers.jsx'
export { resolveColumnDefs } from './resolveColumnDefs.jsx'

// TanStack Table adapters (for UniversalTable / ranked_detail_list)
export { TANSTACK_RENDERERS, TANSTACK_FORMATTERS, adaptRenderer, adaptFormatter } from './tanstackAdapters.jsx'
export { resolveTanStackColumns, buildRankColumn, buildExpandColumn, buildNavigateColumn } from './resolveTanStackColumns.jsx'
