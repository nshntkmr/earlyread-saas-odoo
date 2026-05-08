# -*- coding: utf-8 -*-

import logging

from odoo import http
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.http import request

from ..utils.access import user_can_access_app
from ..utils.app_resolver import build_app_url, get_app_from_host

_logger = logging.getLogger(__name__)


class PosterraHome(Home):

    def _get_portal_app_for_user(self, uid):
        """Return the first saas.app this user can access, or None.

        Iterates active apps in id order and picks the first one the
        user is authorised for via ``user_can_access_app`` — the same
        helper used by login, session-refresh, JWT validation, and the
        browser dashboard route. Single source of truth for "can this
        user use this app?".

        Previously this used a per-mode shortcut ("any group app where
        user has the group, else first hha_provider app if user has
        any provider"), which ignored ``portal_app_ids`` and could send
        a user to the wrong app on /web/login redirect.

        Returns the first matching ``saas.app`` record or ``None``.
        """
        user = request.env['res.users'].sudo().browse(uid)
        candidates = request.env['saas.app'].sudo().search(
            [('is_active', '=', True)], order='id asc',
        )
        for app in candidates:
            if user_can_access_app(user, app):
                return app
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
