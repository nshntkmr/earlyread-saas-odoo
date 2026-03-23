# -*- coding: utf-8 -*-
"""
Extend dashboard_builder models with app scoping.

These fields live here (not in dashboard_builder) because dashboard_builder
depends only on 'base', while saas.app is defined in posterra_portal.
Adding posterra_portal as a dependency of dashboard_builder would create
a circular dependency.
"""

from odoo import fields, models


class DashboardSchemaSourceExt(models.Model):
    _inherit = 'dashboard.schema.source'

    app_ids = fields.Many2many(
        'saas.app', 'schema_source_app_rel', 'source_id', 'app_id',
        string='Available in Apps',
        help='Leave empty for global availability. Set to restrict to specific apps.')


class DashboardWidgetDefinitionExt(models.Model):
    _inherit = 'dashboard.widget.definition'

    app_ids = fields.Many2many(
        'saas.app', 'widget_def_app_rel', 'definition_id', 'app_id',
        string='Available in Apps',
        help='Leave empty for global availability. Set to restrict to specific apps.')
