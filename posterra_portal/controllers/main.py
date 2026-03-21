# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.http import request

from .portal import _get_providers_for_user

_logger = logging.getLogger(__name__)


class PosterraHome(Home):

    def _get_portal_app_for_user(self, uid):
        """Return the first saas.app this user can access, or None.

        Mirrors the priority of portal.py home():
          1. group-based apps (id asc)   — e.g. MSSP Portal
          2. hha_provider apps (id asc)  — e.g. Posterra

        Fully driven by admin-configured saas.app records; no app_key is hardcoded.
        """
        user = request.env['res.users'].sudo().browse(uid)
        # Group-based apps first (so MSSP users are never accidentally matched as HHA)
        group_apps = request.env['saas.app'].sudo().search(
            [('access_mode', '=', 'group'), ('is_active', '=', True)], order='id asc')
        for app in group_apps:
            if app.access_group_xmlid and user.has_group(app.access_group_xmlid):
                return app
        # HHA-provider apps
        if _get_providers_for_user(user):
            hha_app = request.env['saas.app'].sudo().search(
                [('access_mode', '=', 'hha_provider'), ('is_active', '=', True)], limit=1)
            if hha_app:
                return hha_app
        return None

    @http.route()
    def login_successful_external_user(self, **kwargs):
        """Override: redirect portal users to the correct app dashboard after login."""
        if request.session.uid:
            app = self._get_portal_app_for_user(request.session.uid)
            if app:
                return request.redirect('/my/%s' % app.app_key)
        return super().login_successful_external_user(**kwargs)

    def _login_redirect(self, uid, redirect=None):
        """Override: send portal users directly to their app; skip the /my double-hop.

        Uses _get_portal_app_for_user so any new saas.app added by the admin
        is automatically picked up without code changes.
        """
        if not is_user_internal(uid):
            app = self._get_portal_app_for_user(uid)
            if app:
                return redirect or '/my/%s' % app.app_key
        return super()._login_redirect(uid, redirect=redirect)
