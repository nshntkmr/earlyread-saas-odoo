import { VALUE_FORMATTERS } from './formatters'
import { CELL_RENDERERS } from './renderers.jsx'

// ── Resolve string formatter/renderer keys to actual functions ──────────────
// AG Grid expects functions for valueFormatter and cellRenderer, but our
// column config stores them as strings (e.g., "number", "starRating").
// This function walks the columnDefs tree and resolves string keys to
// their registered implementations.

export function resolveColumnDefs(columnDefs) {
  if (!columnDefs) return []
  return columnDefs.map(col => {
    const resolved = { ...col }

    // Resolve string valueFormatter → function
    if (typeof resolved.valueFormatter === 'string' && VALUE_FORMATTERS[resolved.valueFormatter]) {
      resolved.valueFormatter = VALUE_FORMATTERS[resolved.valueFormatter]
    }

    // Resolve string cellRenderer → React component
    if (typeof resolved.cellRenderer === 'string' && CELL_RENDERERS[resolved.cellRenderer]) {
      resolved.cellRenderer = CELL_RENDERERS[resolved.cellRenderer]
    }

    // Recursively resolve children (column groups)
    if (resolved.children) {
      resolved.children = resolveColumnDefs(resolved.children)
    }

    return resolved
  })
}
