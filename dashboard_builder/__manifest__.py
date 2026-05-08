# -*- coding: utf-8 -*-
{
    'name': 'Dashboard Builder',
    'version': '19.0.1.4.0',
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
        'views/dashboard_connection_views.xml',
        'views/dashboard_schema_views.xml',
        'views/widget_definition_views.xml',
        'views/widget_template_views.xml',
        'views/menuitems.xml',
        'views/designer_templates.xml',
    ],
    'external_dependencies': {
        # ``anthropic`` (PyPI: ``anthropic``) powers the AI SQL Generator
        # in services/ai_sql_generator.py. Import name matches PyPI name
        # (``from anthropic import AnthropicFoundry``). Required as soon
        # as an admin clicks "Generate SQL with AI"; declaring it here
        # surfaces a clear missing-install error at module load rather
        # than at first call.
        'python': ['anthropic'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
