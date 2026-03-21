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
