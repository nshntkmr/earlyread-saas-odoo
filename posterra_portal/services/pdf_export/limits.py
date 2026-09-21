# -*- coding: utf-8 -*-
"""PDF export limits and settings (single source of truth).

Secrets and endpoints follow the platform's env-first pattern
(``POSTERRA_JWT_SECRET`` precedent): environment variable first, then
``ir.config_parameter`` for dev / single-pod installs. Values are never
logged.
"""

import os

# ── Hard limits (decision V4) ─────────────────────────────────────────────
PDF_ROW_LIMIT_DEFAULT = 500
PDF_ROW_LIMIT_MAX = 5000
PDF_COLUMN_LIMIT_DEFAULT = 16
PDF_COLUMN_LIMIT_MAX = 24
KEYNOTE_MAX_CHARS = 2000
MAX_HTML_BYTES = 10 * 1024 * 1024          # checked before posting to the renderer
MAX_REQUEST_BYTES = 256 * 1024              # JSON body from the browser
MAX_WIDGET_PARAM_ENTRIES = 400              # scope/widget-filter entries per request

# ── Time budget (decision V6: 25 s total under the 30 s gateway) ─────────
TOTAL_BUDGET_S_DEFAULT = 25.0
RENDER_RESERVE_S = 8.0          # Gotenberg --api-timeout is set to this
AUDIT_RESERVE_S = 2.0           # terminal audit write + response
WIDGET_TIMEOUT_MAX_S = 12.0     # per-statement cap inside the collect budget
MIN_STEP_S = 1.0                # skip a step when less than this remains
CONNECT_TIMEOUT_S = 3.0         # TCP connect to the render service

# ── Advisory-lock keys (decision V3: one export cluster-wide + per user) ──
LOCK_NAMESPACE = 'posterra_pdf_export'

# ── Settings resolution ───────────────────────────────────────────────────
ENV_RENDER_URL = 'POSTERRA_PDF_RENDER_URL'
ENV_RENDER_USER = 'POSTERRA_PDF_RENDER_USER'
ENV_RENDER_PASSWORD = 'POSTERRA_PDF_RENDER_PASSWORD'
ENV_FINGERPRINT_KEY = 'POSTERRA_PDF_FINGERPRINT_KEY'
ENV_FINGERPRINT_KEY_VERSION = 'POSTERRA_PDF_FINGERPRINT_KEY_VERSION'

ICP_RENDER_URL = 'posterra_portal.pdf_render_url'
ICP_RENDER_USER = 'posterra_portal.pdf_render_user'
ICP_RENDER_PASSWORD = 'posterra_portal.pdf_render_password'
ICP_FINGERPRINT_KEY = 'posterra_portal.pdf_fingerprint_key'
ICP_TOTAL_BUDGET = 'posterra_portal.pdf_total_budget_seconds'
ICP_LOG_RETENTION_DAYS = 'posterra_portal.pdf_export_log_retention_days'
LOG_RETENTION_DAYS_DEFAULT = 400

DEFAULT_RENDER_URL = 'http://localhost:3000'


def _icp(env):
    return env['ir.config_parameter'].sudo()


def render_settings(env):
    """``(url, (user, password) | None)`` for the render service."""
    icp = _icp(env)
    url = os.environ.get(ENV_RENDER_URL) or icp.get_param(ICP_RENDER_URL) or DEFAULT_RENDER_URL
    user = os.environ.get(ENV_RENDER_USER) or icp.get_param(ICP_RENDER_USER) or ''
    password = os.environ.get(ENV_RENDER_PASSWORD) or icp.get_param(ICP_RENDER_PASSWORD) or ''
    auth = (user, password) if user and password else None
    return url.rstrip('/'), auth


def fingerprint_key(env):
    """``(key_bytes, key_version)`` for the input fingerprint HMAC.

    Production: dedicated ``POSTERRA_PDF_FINGERPRINT_KEY`` (+ optional
    ``..._VERSION``, default ``env-1``). Dev fallback: an ICP value generated
    on first use (version ``icp-1``), same pattern as the JWT secret.
    """
    env_key = os.environ.get(ENV_FINGERPRINT_KEY)
    if env_key:
        return env_key.encode(), os.environ.get(ENV_FINGERPRINT_KEY_VERSION) or 'env-1'
    key = _icp(env).get_param(ICP_FINGERPRINT_KEY)
    if not key:
        # The export route runs on a READ-ONLY cursor: generate the dev key
        # on an autonomous cursor (never a write on the request cursor).
        import base64
        from odoo import SUPERUSER_ID, api
        with env.registry.cursor() as cr:
            aenv = api.Environment(cr, SUPERUSER_ID, {})
            icp = aenv['ir.config_parameter']
            key = icp.get_param(ICP_FINGERPRINT_KEY)
            if not key:
                key = base64.urlsafe_b64encode(os.urandom(32)).decode()
                icp.set_param(ICP_FINGERPRINT_KEY, key)
                cr.commit()
    return key.encode(), 'icp-1'


def total_budget_s(env):
    try:
        val = float(_icp(env).get_param(ICP_TOTAL_BUDGET) or TOTAL_BUDGET_S_DEFAULT)
    except (TypeError, ValueError):
        val = TOTAL_BUDGET_S_DEFAULT
    # Never below what render + audit need, never above the gateway ceiling.
    return max(RENDER_RESERVE_S + AUDIT_RESERVE_S + 3.0, min(val, 28.0))


def clamp_row_limit(value):
    try:
        v = int(value or PDF_ROW_LIMIT_DEFAULT)
    except (TypeError, ValueError):
        v = PDF_ROW_LIMIT_DEFAULT
    return max(1, min(v, PDF_ROW_LIMIT_MAX))


def clamp_column_limit(value):
    try:
        v = int(value or PDF_COLUMN_LIMIT_DEFAULT)
    except (TypeError, ValueError):
        v = PDF_COLUMN_LIMIT_DEFAULT
    return max(1, min(v, PDF_COLUMN_LIMIT_MAX))
