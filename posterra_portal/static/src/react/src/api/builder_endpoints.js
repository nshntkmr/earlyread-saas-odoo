/**
 * URL builders for the Dashboard Builder API (/api/v1/builder/*).
 */

// ── Schema endpoints ──────────────────────────────────────────────────────────

export function sourcesUrl(apiBase) {
  return `${apiBase}/builder/sources`
}

export function sourceDetailUrl(apiBase, sourceId) {
  return `${apiBase}/builder/sources/${sourceId}`
}

export function sourceRelationsUrl(apiBase, sourceId) {
  return `${apiBase}/builder/sources/${sourceId}/relations`
}

// ── Builder endpoints ─────────────────────────────────────────────────────────

export function previewUrl(apiBase) {
  return `${apiBase}/builder/preview`
}

export function createUrl(apiBase) {
  return `${apiBase}/builder/create`
}

export function updateUrl(apiBase, widgetId) {
  return `${apiBase}/builder/widget/${widgetId}`
}

export function drillUrl(apiBase, widgetId) {
  return `${apiBase}/builder/widget/${widgetId}/drill`
}

// ── Navigation endpoints ──────────────────────────────────────────────────────

export function pagesUrl(apiBase) {
  return `${apiBase}/builder/pages`
}

// ── Library endpoints ─────────────────────────────────────────────────────────

export function libraryUrl(apiBase, params = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v))
  ).toString()
  return `${apiBase}/builder/library${qs ? '?' + qs : ''}`
}

export function libraryDetailUrl(apiBase, defId) {
  return `${apiBase}/builder/library/${defId}`
}

export function placeUrl(apiBase, defId) {
  return `${apiBase}/builder/library/${defId}/place`
}

// ── Reorder endpoint ──────────────────────────────────────────────────────────

export function reorderUrl(apiBase) {
  return `${apiBase}/builder/reorder`
}

// ── Template endpoints ────────────────────────────────────────────────────────

export function templatesUrl(apiBase) {
  return `${apiBase}/builder/templates`
}

export function useTemplateUrl(apiBase, tplId) {
  return `${apiBase}/builder/templates/${tplId}/use`
}
