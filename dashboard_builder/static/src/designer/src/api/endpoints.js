/**
 * URL builders for the Designer API (/dashboard/designer/api/*).
 */

// ── Schema ────────────────────────────────────────────────────────────────────
export const sourcesUrl     = (base) => `${base}/sources`
export const sourceDetailUrl = (base, id) => `${base}/sources/${id}`
export const sourceRelationsUrl = (base, id) => `${base}/sources/${id}/relations`

// ── Preview ───────────────────────────────────────────────────────────────────
export const previewUrl = (base) => `${base}/preview`

// ── Library ───────────────────────────────────────────────────────────────────
export const libraryUrl = (base, params = {}) => {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v))
  ).toString()
  return `${base}/library${qs ? '?' + qs : ''}`
}
export const libraryDetailUrl = (base, id) => `${base}/library/${id}`
export const libraryCreateUrl = (base) => `${base}/library/create`
export const libraryPlaceUrl  = (base, id) => `${base}/library/${id}/place`

// ── Templates ─────────────────────────────────────────────────────────────────
export const templatesUrl    = (base) => `${base}/templates`
export const templateUseUrl  = (base, id) => `${base}/templates/${id}/use`

// ── Apps & Pages ──────────────────────────────────────────────────────────────
export const appsUrl       = (base) => `${base}/apps`
export const appPagesUrl   = (base, appId) => `${base}/apps/${appId}/pages`
export const pageFiltersUrl = (base, pageId) => `${base}/pages/${pageId}/filters`
