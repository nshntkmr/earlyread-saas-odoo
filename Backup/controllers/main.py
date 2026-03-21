# -*- coding: utf-8 -*-

import logging

from odoo import http, _
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.http import request

_logger = logging.getLogger(__name__)


class PosterraHome(Home):

    def _find_hha_providers(self, uid):
        """Find HHA providers matching the user's email domain."""
        user = request.env['res.users'].sudo().browse(uid)
        return request.env['hha.provider'].find_by_email_domain(user.login)

    @http.route()
    def login_successful_external_user(self, **kwargs):
        """Override: redirect HHA users to Posterra dashboard."""
        if request.session.uid:
            providers = self._find_hha_providers(request.session.uid)
            if providers:
                return request.redirect('/my/posterra')
        return super().login_successful_external_user(**kwargs)

    def _login_redirect(self, uid, redirect=None):
        """Override to redirect HHA portal users to Posterra dashboard."""
        if not is_user_internal(uid):
            providers = self._find_hha_providers(uid)
            if providers:
                return '/my/posterra'
        return super()._login_redirect(uid, redirect=redirect)

    @http.route()
    def web_login(self, redirect=None, **kw):
        response = super().web_login(redirect=redirect, **kw)

        # Show custom error message for domain mismatch
        if request.params.get('error') == 'hha_domain_mismatch':
            if hasattr(response, 'qcontext'):
                response.qcontext['error'] = _(
                    "Your email domain does not match any registered "
                    "Home Health Agency. Please contact your administrator."
                )

        return response
