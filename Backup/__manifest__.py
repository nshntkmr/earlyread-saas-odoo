# -*- coding: utf-8 -*-
{
    'name': 'Posterra Portal',
    'version': '19.0.1.0.0',
    'category': 'Healthcare',
    'summary': 'Branded login portal and dashboard for Home Health Agency clients',
    'description': """
        Posterra Portal
        ================
        - Branded login page for HHA clients (username@homehealthname.com)
        - Email domain validation against HHA provider data
        - Dashboard skeleton with 3-section sidebar and 11-page navigation
        - CSV import for HHA provider data
        - Multi-tenant security (portal users see only their own HHA data)
    """,
    'author': 'Posterra',
    'website': 'https://posterra.com',
    'depends': ['base', 'portal', 'auth_signup', 'hha_crm_integration'],
    'data': [
        # Security (load order matters: groups first, then ACLs)
        'security/posterra_security.xml',
        'security/ir.model.access.csv',
        # Base views/actions used by menus
        'views/hha_provider_views.xml',
        'views/res_partner_views.xml',
        'wizard/hha_csv_import_views.xml',
        'wizard/create_portal_user_views.xml',
        # Menus and templates
        'views/menuitems.xml',
        'views/login_templates.xml',
        'views/dashboard_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'posterra_portal/static/src/css/posterra.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    # Recomputes domain_match_name on every install or upgrade so existing
    # records always reflect the current DBA-first matching logic.
    'post_init_hook': 'post_init_hook',
}
