// ── Value formatter registry ────────────────────────────────────────────────
// Keys match the Formatter dropdown in TableColumnSettings.jsx.
// Each receives AG Grid's standard params object: { value, data, colDef, ... }
// and returns a formatted display string.

export const VALUE_FORMATTERS = {
  number: (params) => {
    const v = Number(params.value)
    return isNaN(v) ? params.value : v.toLocaleString('en-US')
  },
  currency: (params) => {
    const v = Number(params.value)
    return isNaN(v)
      ? params.value
      : '$' + v.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  },
  percentage: (params) => {
    const v = Number(params.value)
    if (isNaN(v)) return params.value
    // multiply=true (default): assume 0–1 range → multiply by 100
    // multiply=false: data is already 0–100
    const multiply = params.colDef?.cellRendererParams?.multiply !== false
    const pct = multiply ? v * 100 : v
    return pct.toFixed(1) + '%'
  },
  decimal: (params) => {
    const v = Number(params.value)
    return isNaN(v) ? params.value : v.toFixed(2)
  },
  date: (params) => {
    if (!params.value) return ''
    try { return new Date(params.value).toLocaleDateString() }
    catch { return params.value }
  },
}
