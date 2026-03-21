/**
 * Designer API client — uses Odoo session cookies (no JWT).
 */

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Fetch JSON from the Designer API.
 * Relies on Odoo session cookie for auth (same-origin request).
 */
export async function designerFetch(url, opts = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  }

  const res = await fetch(url, { ...opts, headers, credentials: 'same-origin' })

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
