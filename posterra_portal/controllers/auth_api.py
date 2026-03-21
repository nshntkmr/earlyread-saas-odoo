# -*- coding: utf-8 -*-
"""
Phase 6 — JWT Authentication API
=================================
Provides stateless JWT-based auth for the Posterra JSON API.

Endpoints:
    POST /api/v1/auth/login   — exchange credentials for access + refresh tokens
    POST /api/v1/auth/refresh — exchange refresh token for new access token

JWT implementation uses standard-library only (base64, hmac, hashlib, json, os, time).
No external PyJWT dependency required.

The signing secret is auto-generated on first use and stored in
ir.config_parameter under the key 'posterra_portal.jwt_secret'.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import time

from odoo import http
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)

# ── Token lifetime constants ──────────────────────────────────────────────────
ACCESS_TOKEN_TTL  = 3600        # 1 hour
REFRESH_TOKEN_TTL = 86400 * 7   # 7 days

# ── JWT helpers ───────────────────────────────────────────────────────────────

def _get_jwt_secret():
    """Return (or generate) the HS256 signing secret from ir.config_parameter."""
    param = request.env['ir.config_parameter'].sudo()
    secret = param.get_param('posterra_portal.jwt_secret')
    if not secret:
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        param.set_param('posterra_portal.jwt_secret', secret)
    return secret


def _make_token(payload: dict) -> str:
    """Create a minimal HS256 JWT string from a payload dict.

    Token format:  base64url(header) . base64url(payload) . base64url(sig)
    Padding ('=') is stripped per the JWT spec (RFC 7519 §2).
    """
    secret = _get_jwt_secret()
    header = base64.urlsafe_b64encode(
        json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode()
    ).rstrip(b'=').decode()
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(',', ':')).encode()
    ).rstrip(b'=').decode()
    sig_input = f'{header}.{body}'.encode()
    sig = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), sig_input, hashlib.sha256).digest()
    ).rstrip(b'=').decode()
    return f'{header}.{body}.{sig}'


def _verify_token(token: str) -> dict:
    """Verify a JWT string and return its payload dict.

    Raises ValueError on:
      - malformed structure (not 3 dot-separated parts)
      - invalid signature
      - expired token (exp < now)
    """
    secret = _get_jwt_secret()
    parts = token.strip().split('.')
    if len(parts) != 3:
        raise ValueError('Malformed token: expected 3 segments')
    header, body, sig = parts
    # Verify signature — timing-safe comparison
    expected = base64.urlsafe_b64encode(
        hmac.new(
            secret.encode(),
            f'{header}.{body}'.encode(),
            hashlib.sha256,
        ).digest()
    ).rstrip(b'=').decode()
    if not hmac.compare_digest(sig, expected):
        raise ValueError('Invalid token signature')
    # Decode payload — restore stripped base64 padding with '==='
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + '==='))
    except Exception as exc:
        raise ValueError(f'Token payload decode error: {exc}')
    if payload.get('exp', 0) < time.time():
        raise ValueError('Token has expired')
    return payload


# ── HTTP response helpers (also imported by widget_api.py) ───────────────────

def _json_response(data, status=200):
    """Return a JSON HTTP response with CORS headers."""
    body = json.dumps(data, default=str)
    return request.make_response(
        body,
        headers=[
            ('Content-Type', 'application/json; charset=utf-8'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
        ],
        status=status,
    )


def _json_error(status, message):
    """Return a JSON error response."""
    return _json_response({'error': message, 'status': status}, status=status)


def _get_request_json():
    """Parse JSON body from the current HTTP request.  Returns {} on failure.

    Tries Werkzeug's built-in get_json() first (cached, handles content-type
    correctly), then falls back to reading .data directly.  In Odoo 19 with
    auth='none' routes, get_data(as_text=True) can return empty; get_json()
    is more reliable as it bypasses Odoo's parameter processing.
    """
    # Method 1: Werkzeug's own JSON parser — cached, most reliable
    try:
        data = request.httprequest.get_json(force=True, silent=True)
        if isinstance(data, dict):
            return data
    except Exception as exc:
        _logger.debug('_get_request_json: get_json failed: %s', exc)

    # Method 2: Read from cached .data bytes property
    try:
        raw = request.httprequest.data
        if raw:
            return json.loads(raw)
    except Exception as exc:
        _logger.debug('_get_request_json: .data parse failed: %s', exc)

    return {}


# ── Auth controller ───────────────────────────────────────────────────────────

class PosterraAuthAPI(http.Controller):

    @http.route(
        '/api/v1/auth/login',
        type='http',
        auth='none',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    def api_login(self, **kw):
        """Exchange Odoo credentials for a JWT access + refresh token pair.

        Request body (JSON):
            login      — user email / login
            password   — password
            app_key    — optional; app to log into (e.g. 'posterra', 'mssp').
                         Auto-detected when omitted.

        Response (200):
            access_token   — short-lived bearer token (1 h)
            refresh_token  — long-lived token (7 d) for renewing access tokens
            token_type     — 'Bearer'
            expires_in     — seconds until access_token expires (3600)
            app_key        — the resolved app key
            app_name       — human-readable app name
            user_id        — Odoo res.users ID
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        data = _get_request_json()
        login_val = (data.get('login') or kw.get('login', '')).strip()
        password  = data.get('password') or kw.get('password', '')
        app_key   = (data.get('app_key') or kw.get('app_key', '')).strip()

        if not login_val or not password:
            return _json_error(400, 'login and password are required')

        # ── 1. Authenticate user ──────────────────────────────────────────
        # Both _login() and _check_credentials() rebuild the user recordset
        # inside a new cursor/env, which returns res.users() (0 records) in
        # Odoo 19 auth='none' routes → "Expected singleton" crash.
        # Fix: look up user + password hash directly via SQL, then verify with
        # Odoo's own _crypt_context() (passlib pbkdf2/bcrypt).  Identical
        # security — same algorithm — zero ORM singleton complications.
        cr = request.env.cr
        cr.execute(
            "SELECT id, password FROM res_users "
            "WHERE login = %s AND active = true LIMIT 1",
            [login_val],
        )
        row = cr.fetchone()
        if not row or not row[1]:
            return _json_error(401, 'Invalid credentials')
        uid, stored_hash = row

        try:
            valid = request.env['res.users']._crypt_context().verify(
                password, stored_hash,
            )
        except Exception as exc:
            _logger.warning('api_login: hash verify error for %r: %s', login_val, exc)
            return _json_error(401, 'Invalid credentials')

        if not valid:
            return _json_error(401, 'Invalid credentials')

        user = request.env['res.users'].sudo().browse(uid)

        # ── 2. Resolve app ────────────────────────────────────────────────
        app = None
        if app_key:
            app = request.env['saas.app'].sudo().search(
                [('app_key', '=', app_key), ('is_active', '=', True)], limit=1,
            )

        if not app:
            # Auto-detect: group-based apps first (MSSP), then HHA-provider apps
            from .portal import _get_providers_for_user
            group_apps = request.env['saas.app'].sudo().search(
                [('access_mode', '=', 'group'), ('is_active', '=', True)],
                order='id asc',
            )
            for ga in group_apps:
                if ga.access_group_xmlid and user.has_group(ga.access_group_xmlid):
                    app = ga
                    break
            if not app:
                providers = _get_providers_for_user(user)
                if providers:
                    app = request.env['saas.app'].sudo().search(
                        [('access_mode', '=', 'hha_provider'), ('is_active', '=', True)],
                        limit=1,
                    )

        if not app:
            return _json_error(403, 'No accessible app found for this user')

        # ── 3. Issue tokens ───────────────────────────────────────────────
        now = int(time.time())
        access_token = _make_token({
            'type':    'access',
            'user_id': user.id,
            'app_id':  app.id,
            'app_key': app.app_key,
            'exp':     now + ACCESS_TOKEN_TTL,
            'iat':     now,
        })
        refresh_token = _make_token({
            'type':    'refresh',
            'user_id': user.id,
            'app_id':  app.id,
            'exp':     now + REFRESH_TOKEN_TTL,
            'iat':     now,
        })

        # ── 4. Collect pages for sidebar navigation ───────────────────────
        # React needs this to build the sidebar immediately after login —
        # no extra round-trip, no hardcoded page keys in the frontend.
        pages_records = request.env['dashboard.page'].sudo().search(
            [('app_id', '=', app.id), ('is_active', '=', True)],
            order='sequence asc',
        )
        pages_data = [
            {
                'id':         p.id,
                'key':        p.key,
                'name':       p.name,
                'icon':       p.icon or '',
                'nav_section': p.nav_section_id.name if p.nav_section_id else '',
                'sequence':   p.sequence,
            }
            for p in pages_records
        ]

        _logger.info('API login: user=%s app=%s pages=%s',
                     user.login, app.app_key, [p['key'] for p in pages_data])

        return _json_response({
            # ── OAuth2 standard token fields ──────────────────────────────
            'access_token':  access_token,
            'refresh_token': refresh_token,
            'token_type':    'Bearer',
            'expires_in':    ACCESS_TOKEN_TTL,

            # ── Authenticated user (for header/avatar display) ────────────
            'user': {
                'id':    user.id,
                'name':  user.name,
                'email': user.login,
            },

            # ── App context + branding ────────────────────────────────────
            'app': {
                'id':            app.id,
                'key':           app.app_key,
                'name':          app.name,
                'primary_color': app.primary_color or '#0066cc',
                'tagline':       app.tagline or '',
            },

            # ── Navigation: React builds the sidebar from this list ───────
            # default_page_key comes from the saas.app record (admin-configured)
            # with a fallback to the first active page in sequence order.
            'pages':            pages_data,
            'default_page_key': app.default_page_key or (pages_data[0]['key'] if pages_data else ''),
        })

    @http.route(
        '/api/v1/auth/refresh',
        type='http',
        auth='none',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    def api_refresh(self, **kw):
        """Exchange a refresh token for a new access token.

        Request body (JSON):
            refresh_token — the refresh token returned by /api/v1/auth/login

        Response (200):
            access_token — new short-lived bearer token (1 h)
            expires_in   — seconds until access_token expires (3600)
            token_type   — 'Bearer'
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        data = _get_request_json()
        refresh_tok = (data.get('refresh_token') or kw.get('refresh_token', '')).strip()
        if not refresh_tok:
            return _json_error(400, 'refresh_token is required')

        try:
            payload = _verify_token(refresh_tok)
        except ValueError as exc:
            return _json_error(401, str(exc))

        if payload.get('type') != 'refresh':
            return _json_error(401, 'Expected a refresh token, got access token')

        now = int(time.time())
        access_token = _make_token({
            'type':    'access',
            'user_id': payload['user_id'],
            'app_id':  payload['app_id'],
            'exp':     now + ACCESS_TOKEN_TTL,
            'iat':     now,
        })

        return _json_response({
            'access_token': access_token,
            'token_type':   'Bearer',
            'expires_in':   ACCESS_TOKEN_TTL,
        })
