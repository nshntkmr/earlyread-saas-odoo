# -*- coding: utf-8 -*-
"""Projection API — Mark / Edit / Re-project / Undo (JWT, POST, JSON body).

    POST /api/v1/projections/mark
    POST /api/v1/projections/edit
    POST /api/v1/projections/reproject
    POST /api/v1/projections/undo

Body (JSON):
    type_key, widget_id, section_id, row_key, identity_hash, snapshot,
    expected_revision, request_id, [cycle_no], [note], [expected_date],
    [evidence], [filters: {<page filter params and _wf_* values>}]

``filters`` carries the applied page filter values exactly as the drawer
fetch does, so the section SQL resolves ``%(param)s`` identically. Every
route is ``readonly=False`` (``auth='none'`` routes default to read-only
cursors in Odoo 19) and goes through ``_get_api_user`` like the widget API.
"""

import logging

from odoo import http
from odoo.http import request

from .auth_api import _get_request_json, _json_error, _json_response
from .portal import _get_providers_for_user
from .widget_api import _apply_widget_filters, _build_portal_ctx, _get_api_user
from ..services import projection_service as svc

_logger = logging.getLogger(__name__)


class PosterraProjectionAPI(http.Controller):

    def _run(self, action):
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})
        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))
        body = _get_request_json() or {}
        filters = body.get('filters') or {}
        if not isinstance(filters, dict):
            filters = {}
        try:
            widget = request.env['dashboard.widget'].sudo().browse(
                int(body.get('widget_id') or 0))
        except (TypeError, ValueError):
            return _json_error(400, 'widget_id must be an integer')
        if not widget.exists() or not widget.is_active:
            return _json_error(404, 'Widget not found')
        if widget.page_id.app_id.id != app.id:
            return _json_error(403, 'Widget does not belong to your app')

        from ..utils.access import ForgedProviderValueError
        kw = dict(filters)
        try:
            portal_ctx = _build_portal_ctx(widget.page_id, user, app, kw, consumer=widget)
        except ForgedProviderValueError as exc:
            return _json_error(403, str(exc))
        except Exception as exc:  # noqa: BLE001
            return _json_error(500, 'Context build error: %s' % exc)
        portal_ctx = _apply_widget_filters(widget, kw, portal_ctx)

        providers = None
        try:
            providers = _get_providers_for_user(user)
        except Exception:  # noqa: BLE001 — app-scoped types never need them
            providers = None

        try:
            result = svc.mutate(request.env, user, app, action, body, portal_ctx, providers)
        except svc.ProjectionError as exc:
            return _json_response(exc.to_dict(), status=exc.status)
        return _json_response(result)

    @http.route('/api/v1/projections/mark', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, readonly=False)
    def api_projection_mark(self, **kw):
        return self._run('mark')

    @http.route('/api/v1/projections/edit', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, readonly=False)
    def api_projection_edit(self, **kw):
        return self._run('edit')

    @http.route('/api/v1/projections/reproject', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, readonly=False)
    def api_projection_reproject(self, **kw):
        return self._run('reproject')

    @http.route('/api/v1/projections/undo', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, readonly=False)
    def api_projection_undo(self, **kw):
        return self._run('undo')
