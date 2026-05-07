# -*- coding: utf-8 -*-
"""Subdomain-based saas.app resolution.

Posterra serves each app on its own subdomain (e.g. ``posterra.example.com``,
``mssp.example.com``). This module is the single source of truth for the
``host header → saas.app`` mapping. Both browser routes (portal.py) and the
post-login redirect chain (main.py) call ``get_app_from_host``.

For local dev the same mechanism works against ``*.localhost`` — modern
browsers resolve any ``<label>.localhost`` to 127.0.0.1 without an
``/etc/hosts`` entry.

The resolver is *fail-closed*: if no subdomain is present, the leftmost
label is reserved, or no matching ``saas.app`` exists, it returns
``False`` (not the bare-host fallback). Callers decide how to surface the
mismatch — typically a 404 or a redirect to a marketing landing.
"""

import logging
import re

from odoo.http import request

_logger = logging.getLogger(__name__)

# Subdomains that must NOT resolve to an app even if a saas.app record
# happens to share the name. Mirrors saas.app._RESERVED_APP_KEYS as a
# runtime guard for hostile / typo'd hosts (e.g. ``www.example.com``,
# ``api.example.com``).
_RESERVED_SUBDOMAINS = frozenset({
    'www', 'api', 'admin', 'mail', 'app', 'odoo',
    'web', 'static', 'longpolling', 'jsonrpc', 'websocket',
    'dashboard', 'portal', 'login', 'logout', 'signup',
    'auth', 'mailto',
})

_IPV4_RE = re.compile(r'^\d{1,3}(?:\.\d{1,3}){3}$')


def _split_host(host):
    """Return ``(host_no_port, port_suffix)`` for ``host`` (which may be empty).

    ``port_suffix`` includes the leading colon (``:8069``) when a port is
    present, or the empty string otherwise — letting callers reassemble a
    URL by simple concatenation.
    """
    if not host:
        return '', ''
    if ':' in host:
        host_no_port, port = host.rsplit(':', 1)
        return host_no_port, ':' + port
    return host, ''


def _leftmost_label(host_no_port):
    """Return the leftmost DNS label of ``host_no_port`` (lowercased).

    For an IPv4 address or a single-label host (``localhost``) returns ''.
    """
    if not host_no_port or _IPV4_RE.match(host_no_port):
        return ''
    parts = host_no_port.split('.')
    if len(parts) < 2:
        return ''  # bare 'localhost' or single-label host
    return parts[0].lower()


def get_app_from_host(env=None):
    """Resolve the ``saas.app`` record for the current request's host header.

    ``posterra.example.com:443`` → app with ``app_key='posterra'``
    ``inhome.localhost:8069``    → app with ``app_key='inhome'``
    ``localhost:8069``           → ``False`` (no subdomain to resolve)
    ``www.example.com``          → ``False`` (reserved label)
    ``192.168.0.10:8069``        → ``False`` (IPv4 — no subdomain semantics)

    Returns a sudo'd ``saas.app`` recordset (singleton) or ``False``.
    """
    if not request:
        return False
    env = env or request.env
    host = request.httprequest.host or ''
    host_no_port, _ = _split_host(host)
    label = _leftmost_label(host_no_port)
    if not label or label in _RESERVED_SUBDOMAINS:
        return False
    return env['saas.app'].sudo().search(
        [('app_key', '=', label), ('is_active', '=', True)],
        limit=1,
    )


def build_app_url(app, path='/'):
    """Build a full URL for ``app``'s subdomain on the current host base.

    Used for cross-subdomain redirects (e.g. after a user logs in on the
    bare ``/web/login`` and we need to bounce them to *their* app's
    subdomain).

    Substitution rules — based on the leftmost label of the current request:
      * leftmost label is *another* registered app_key → swap it
        (``inhome.example.com`` → ``posterra.example.com``)
      * leftmost label is in ``_RESERVED_SUBDOMAINS`` → swap it
        (``www.example.com`` → ``posterra.example.com``)
      * otherwise (bare ``localhost``, ``example.com``, IPv4) → prepend
        (``example.com`` → ``posterra.example.com``;
         ``localhost:8069`` → ``posterra.localhost:8069``)

    The scheme is preserved from the current request (http vs https).
    Falls back to a relative path when no request is bound (e.g. cron).
    """
    if not app or not app.app_key:
        return path
    if not request:
        return path  # no request context — caller handles it
    host = request.httprequest.host or ''
    host_no_port, port_suffix = _split_host(host)
    if not host_no_port:
        return path
    if _IPV4_RE.match(host_no_port):
        # Can't add subdomain to a raw IP — return relative path so the
        # browser stays on the same host. Caller is responsible for
        # showing a sensible error if the IP doesn't resolve to any app.
        return path
    parts = host_no_port.split('.')
    label = parts[0].lower()
    Apps = request.env['saas.app'].sudo()
    label_is_app = bool(Apps.search([('app_key', '=', label)], limit=1)) \
        if label else False
    if label and (label_is_app or label in _RESERVED_SUBDOMAINS):
        # Swap leftmost label
        new_host = '.'.join([app.app_key] + parts[1:])
    elif len(parts) < 2:
        # Single-label host (bare 'localhost') — prepend
        new_host = '%s.%s' % (app.app_key, host_no_port)
    else:
        # Multi-label host without a known app prefix — prepend
        new_host = '%s.%s' % (app.app_key, host_no_port)
    scheme = request.httprequest.scheme or 'http'
    if not path.startswith('/'):
        path = '/' + path
    return '%s://%s%s%s' % (scheme, new_host, port_suffix, path)
