# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.http import request

from .portal import _get_providers_for_user
from ..utils.app_resolver import build_app_url, get_app_from_host

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
        """Override: send portal users to the right app after login.

        Honor the subdomain context first — if the user logged in on an
        app's own subdomain (e.g. ``inhome_v1.example.com/web/login``),
        keep them on that app. Only fall back to the user's first
        accessible app for bare-host logins, where there's no subdomain
        signal to disambiguate.
        """
        if request.session.uid:
            host_app = get_app_from_host()
            if host_app:
                # Same-host redirect — relative path keeps the user on
                # the subdomain they were already on.
                return request.redirect('/')
            app = self._get_portal_app_for_user(request.session.uid)
            if app:
                return request.redirect(build_app_url(app, '/'))
        return super().login_successful_external_user(**kwargs)

    def _login_redirect(self, uid, redirect=None):
        """Override: send portal users to the right app after Odoo login.

        Honor the subdomain context first — a user who hit
        ``inhome_v1.example.com/web/login`` clearly wants the inhome_v1
        app and shouldn't be silently bounced to whichever app comes
        first in the DB.

        For bare-host login (no subdomain), fall back to the user's
        first accessible app via ``build_app_url`` (returns an absolute
        URL so Odoo's redirect chain hops onto the right subdomain).
        """
        if not is_user_internal(uid):
            if get_app_from_host():
                # Already on an app subdomain — same-host redirect
                return redirect or '/'
            app = self._get_portal_app_for_user(uid)
            if app:
                return redirect or build_app_url(app, '/')
        return super()._login_redirect(uid, redirect=redirect)
