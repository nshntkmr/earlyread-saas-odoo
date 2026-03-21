# -*- coding: utf-8 -*-
"""
Shared JSON helpers for Dashboard Builder controllers.
Decoupled from posterra_portal so dashboard_builder can run standalone.
"""

import json
import logging

from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(data, status=200):
    """Return a JSON HTTP response."""
    body = json.dumps(data, default=str)
    return Response(
        body,
        status=status,
        content_type='application/json',
    )


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
