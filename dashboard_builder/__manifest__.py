# -*- coding: utf-8 -*-
{
    'name': 'Dashboard Builder',
    'version': '19.0.1.1.0',
    'category': 'Productivity',
    'summary': 'Visual widget builder with schema registry and query generation',
    'description': """
        Dashboard Builder
        =================
        - Schema Registry: register database tables, columns, and JOIN relationships
        - Query Builder: auto-generate safe SQL from structured configuration
        - Widget Action System: click presets (filter, navigate, drill-down, URL)
        - Builder API: REST endpoints for preview, create, update widgets
        - Widget Templates: pre-built widget patterns for rapid dashboard creation
        - AI Integration: Azure AI Foundry stub (Track B provisioning)
    """,
    'author': 'Posterra',
    'website': 'https://posterra.com',
    'depends': ['base'],
    'data': [
        'security/builder_security.xml',
        'security/ir.model.access.csv',
        'views/dashboard_schema_views.xml',
        'views/widget_definition_views.xml',
        'views/widget_template_views.xml',
        'views/page_template_views.xml',
        'views/menuitems.xml',
        'views/designer_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
