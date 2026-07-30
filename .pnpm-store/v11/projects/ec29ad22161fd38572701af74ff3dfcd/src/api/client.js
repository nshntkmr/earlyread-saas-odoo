/**
 * API client — thin fetch wrapper that attaches the Bearer JWT.
 *
 * Includes a 401 retry: if the server returns "Token has expired",
 * the client calls refreshFn() to get a fresh token and retries once.
 */

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Fetch JSON from the Posterra API.
 *
 * @param {string}   url       — full URL (built by endpoints.js helpers)
 * @param {string}   token     — JWT access token
 * @param {object}   opts      — additional fetch options
 * @param {Function} refreshFn — optional async function that returns a fresh token
 * @returns {Promise<any>} — parsed JSON response body
 * @throws {ApiError}      — on HTTP errors (status != 2xx)
 */
export async function apiFetch(url, token, opts = {}, refreshFn = null) {
  const doFetch = async (tok) => {
    const headers = {
      'Content-Type': 'application/json',
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
      ...(opts.headers || {}),
    }
    return fetch(url, { ...opts, headers })
  }

  let res = await doFetch(token)

  // 401 retry: refresh the token once and retry
  if (res.status === 401 && refreshFn) {
    const newToken = await refreshFn()
    if (newToken) {
      res = await doFetch(newToken)
    }
  }

  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      message = body.error || message
    } catch (_) { /* ignore */ }
    throw new ApiError(message, res.status)
  }
  return res.json()
}

/**
 * Fetch a binary file from the Posterra API (widget data downloads).
 *
 * Same auth + 401-refresh-retry contract as apiFetch, but resolves with the
 * response Blob plus the server-provided filename instead of parsed JSON.
 * No default Content-Type header — GET downloads send none, and POST callers
 * set application/json themselves via opts.headers.
 *
 * @param {string}   url       — full URL (built by endpoints.js helpers)
 * @param {string}   token     — JWT access token
 * @param {object}   opts      — additional fetch options (method, body, headers)
 * @param {Function} refreshFn — optional async function that returns a fresh token
 * @returns {Promise<{blob: Blob, filename: string|null, truncated: boolean}>}
 * @throws {ApiError}          — on HTTP errors (status != 2xx)
 */
export async function apiFetchBlob(url, token, opts = {}, refreshFn = null) {
  const doFetch = async (tok) => {
    const headers = {
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
      ...(opts.headers || {}),
    }
    return fetch(url, { ...opts, headers })
  }

  let res = await doFetch(token)

  // 401 retry: refresh the token once and retry
  if (res.status === 401 && refreshFn) {
    const newToken = await refreshFn()
    if (newToken) {
      res = await doFetch(newToken)
    }
  }

  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      message = body.error || message
    } catch (_) { /* ignore */ }
    throw new ApiError(message, res.status)
  }

  return {
    blob: await res.blob(),
    filename: parseContentDispositionFilename(res.headers.get('Content-Disposition')),
    truncated: res.headers.get('X-Download-Truncated') === '1',
  }
}

/**
 * Extract a filename from a Content-Disposition header. Handles both the
 * plain `filename="x.csv"` form and RFC 5987 `filename*=UTF-8''x.csv`
 * (Odoo's content_disposition emits both). Returns null when absent.
 */
function parseContentDispositionFilename(header) {
  if (!header) return null
  const star = header.match(/filename\*=(?:UTF-8'')?([^;]+)/i)
  if (star) {
    try {
      return decodeURIComponent(star[1].trim().replace(/^"|"$/g, ''))
    } catch (_) { /* fall through to plain form */ }
  }
  const plain = header.match(/filename="?([^";]+)"?/i)
  return plain ? plain[1].trim() : null
}
