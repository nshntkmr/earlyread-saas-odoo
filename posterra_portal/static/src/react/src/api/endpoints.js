/**
 * URL builders for the Posterra JSON API (/api/v1/*).
 *
 * The apiBase is read from data-api-base on #app-root (default: "/api/v1").
 */

/**
 * Build the URL for fetching a single widget's data.
 *
 * @param {string} apiBase    — e.g. "/api/v1"
 * @param {number} widgetId   — dashboard.widget ID
 * @param {object} params     — filter values dict (field_name → value)
 * @returns {string}
 */
export function widgetDataUrl(apiBase, widgetId, params = {}) {
  const filtered = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)
  )
  const qs = new URLSearchParams(filtered).toString()
  return `${apiBase}/widget/${widgetId}/data${qs ? '?' + qs : ''}`
}

/**
 * Build the URL for fetching cascading filter options.
 *
 * @param {string} apiBase      — e.g. "/api/v1"
 * @param {number} filterId     — dashboard.page.filter ID
 * @param {string} parentValue  — current value of the parent filter
 * @returns {string}
 */
export function cascadeUrl(apiBase, filterId, parentValue) {
  return `${apiBase}/filters/cascade?filter_id=${filterId}&parent_value=${encodeURIComponent(parentValue || '')}`
}

/**
 * Build the URL for fetching cascading filter options with multiple constraints.
 *
 * @param {string} apiBase       — e.g. "/api/v1"
 * @param {number} filterId      — target dashboard.page.filter ID
 * @param {object} constraints   — {sourceFilterId: value, ...}
 * @returns {string}
 */
export function cascadeMultiUrl(apiBase, filterId, constraints = {}, allValues = null) {
  const params = {
    filter_id: filterId,
    constraints: JSON.stringify(constraints),
  }
  if (allValues) {
    params.all_values = JSON.stringify(allValues)
  }
  const qs = new URLSearchParams(params).toString()
  return `${apiBase}/filters/cascade/multi?${qs}`
}
