# -*- coding: utf-8 -*-
"""
Shared JSON helpers for Dashboard Builder controllers.
Decoupled from posterra_portal so dashboard_builder can run standalone.
"""

import json
import logging

from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(data, status=200, sensitive=False):
    """Return a JSON HTTP response.

    ``sensitive=True`` (opt-in at the call site — a generic helper cannot infer
    PHI classification) adds no-store / no-cache / nosniff headers so a PHI
    payload is never cached by browsers or intermediaries. Default False keeps
    every existing non-PHI response byte-identical.
    """
    headers = [('Content-Type', 'application/json')]
    if sensitive:
        headers += [
            ('Cache-Control', 'private, no-store, no-cache, must-revalidate'),
            ('Pragma', 'no-cache'),
            ('X-Content-Type-Options', 'nosniff'),
        ]
    body = json.dumps(data, default=str)
    return Response(body, status=status, headers=headers)


def _json_error(status, message):
    """Return an error JSON HTTP response."""
    return _json_response({'error': message}, status=status)


def _get_request_json():
    """Parse JSON body from the current HTTP request."""
    try:
        raw = request.httprequest.get_data(as_text=True)
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning('Invalid JSON body: %s', e)
        return {}
