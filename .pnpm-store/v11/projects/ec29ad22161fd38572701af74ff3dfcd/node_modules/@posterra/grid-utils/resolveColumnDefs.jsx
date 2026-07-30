import { VALUE_FORMATTERS } from './formatters'
import { CELL_RENDERERS } from './renderers.jsx'

// ── Renderers that produce multi-line cell content ──────────────────────────
// These require AG Grid's autoHeight so rows expand to fit their content.
// Without this, multi-line content is clipped at the default ~28px row height.
const MULTI_LINE_RENDERERS = new Set(['composite', 'dualValue'])

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
      // Auto-enable autoHeight for multi-line renderers so AG Grid
      // expands row height to fit composite/dualValue content.
      // This is critical for portal rendering — without it, multi-line
      // cells are clipped at default row height.
      if (MULTI_LINE_RENDERERS.has(resolved.cellRenderer)) {
        resolved.autoHeight = true
        resolved.wrapText = true
      }
      resolved.cellRenderer = CELL_RENDERERS[resolved.cellRenderer]
    }

    // Recursively resolve children (column groups)
    if (resolved.children) {
      resolved.children = resolveColumnDefs(resolved.children)
    }

    return resolved
  })
}
