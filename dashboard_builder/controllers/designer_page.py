# -*- coding: utf-8 -*-
"""
Dashboard Designer — Page Controller
======================================
Serves the standalone designer page at /dashboard/designer.
Uses Odoo session auth (admin is already logged into backend).
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DesignerPage(http.Controller):

    @http.route('/dashboard/designer', type='http', auth='user', website=False)
    def designer_index(self, **kw):
        """Render the Dashboard Designer single-page app."""
        user = request.env.user

        # Reject deactivated users up-front. Odoo auth='user' verifies
        # the session but may not invalidate cached sessions immediately
        # on archive — explicit check keeps the contract consistent with
        # the rest of the auth surfaces (portal.app_dashboard, builder
        # _auth_admin, designer _require_admin).
        if not user or user._is_public() or not user.active:
            return request.redirect('/web/login')

        # Admin check: dashboard builder admin OR system admin. Defensive
        # try/except in case the group XML ID isn't loaded yet during
        # install / upgrade.
        is_admin = False
        try:
            is_admin = (
                user.has_group('base.group_system')
                or user.has_group('dashboard_builder.group_dashboard_builder_admin')
            )
        except Exception:
            is_admin = False
        if not is_admin:
            return request.redirect('/web#action=&error=Access+Denied')

        # Collect apps if saas.app is available (posterra_portal installed)
        apps = []
        try:
            app_model = request.env['saas.app']
            for app in app_model.sudo().search([('is_active', '=', True)]):
                apps.append({
                    'id': app.id,
                    'name': app.name,
                    'app_key': app.app_key,
                })
        except KeyError:
            pass  # saas.app not installed — no apps to show

        context = {
            'user_name': user.name,
            'api_base': '/dashboard/designer/api',
            'apps_json': json.dumps(apps),
        }

        return request.render('dashboard_builder.designer_page', context)
