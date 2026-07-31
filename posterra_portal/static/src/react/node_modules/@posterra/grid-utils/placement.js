// Shared deterministic grid placement for attribute_grid — the ONE
// implementation both the portal and the Designer preview use, so the two
// surfaces can never disagree about where a field lands.
//
// The Python formatter only validates/normalizes each item's requested
// row_order / column_start / column_span into safe metadata (it cannot know
// the browser container width). This function resolves final positions:
//   1. invalid/absent column_start → automatic placement (next free cell)
//   2. span clamped to the effective column count (min 1)
//   3. requested position occupied → next available position
//   4. nothing available → append in SQL order
//   5. recomputed at every responsive step — no overlap, ever
//   6. SQL ordering is the final tie-breaker (stable sort)

// Container-width steps (px) → effective column ceiling. Wide keeps the
// configured count; medium ≤ 4; narrow ≤ 2; small = 1.
export function effectiveColumns(containerWidth, configuredColumns) {
  const cfg = Math.max(1, Math.min(configuredColumns || 1, 8))
  if (!containerWidth || containerWidth >= 900) return cfg
  if (containerWidth >= 560) return Math.min(cfg, 4)
  if (containerWidth >= 360) return Math.min(cfg, 2)
  return 1
}

// items: [{ placement: {row_order, column_start, column_span}, ... }]
// Returns a new array (original order preserved) where each item gains
// resolved {col, row, span} under `resolved`.
export function resolvePlacement(items, columns) {
  const cols = Math.max(1, columns | 0)
  // Stable order: row_order (nulls last) then original index.
  const indexed = items.map((item, i) => ({ item, i }))
  indexed.sort((a, b) => {
    const ra = a.item?.placement?.row_order
    const rb = b.item?.placement?.row_order
    const na = (ra === null || ra === undefined) ? Infinity : ra
    const nb = (rb === null || rb === undefined) ? Infinity : rb
    return na === nb ? a.i - b.i : na - nb
  })

  const occupied = new Set()          // 'row:col'
  const isFree = (row, col, span) => {
    for (let c = col; c < col + span; c++) {
      if (c > cols || occupied.has(`${row}:${c}`)) return false
    }
    return true
  }
  const claim = (row, col, span) => {
    for (let c = col; c < col + span; c++) occupied.add(`${row}:${c}`)
  }
  // First free slot scanning row-major from row 1.
  const findFree = (span, startRow) => {
    for (let row = startRow; ; row++) {
      for (let col = 1; col + span - 1 <= cols; col++) {
        if (isFree(row, col, span)) return { row, col }
      }
    }
  }

  let cursorRow = 1
  const resolvedByIndex = new Array(items.length)
  for (const { item, i } of indexed) {
    const p = item?.placement || {}
    const span = Math.max(1, Math.min(p.column_span || 1, cols))
    let placed = null
    const start = p.column_start
    if (Number.isInteger(start) && start >= 1 && start + span - 1 <= cols) {
      // Requested column: try from the current cursor row downwards.
      for (let row = cursorRow; row < cursorRow + items.length + 1; row++) {
        if (isFree(row, start, span)) { placed = { row, col: start }; break }
      }
    }
    if (!placed) placed = findFree(span, 1)
    claim(placed.row, placed.col, span)
    cursorRow = Math.max(cursorRow, placed.row)
    resolvedByIndex[i] = { row: placed.row, col: placed.col, span }
  }
  return items.map((item, i) => ({ ...item, resolved: resolvedByIndex[i] }))
}
