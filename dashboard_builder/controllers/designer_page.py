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

        # Admin check
        is_admin = (
            user.has_group('dashboard_builder.group_dashboard_builder_admin')
            or user.has_group('base.group_system')
        )
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
