# -*- coding: utf-8 -*-
{
    'name': 'Posterra Portal',
    'version': '19.0.1.3.0',
    'category': 'Healthcare',
    'summary': 'Branded login portal and dashboard for Home Health Agency clients',
    'description': """
        Posterra Portal
        ================
        - Branded login portal and dashboard for Home Health Agency clients
        - Scope Group system for admin-configurable HHA access
        - Dashboard skeleton with DB-driven pages, tabs, and context filters
        - CSV import for HHA provider data
        - Multi-tenant security (portal users see only their scoped HHA data)
    """,
    'author': 'Posterra',
    'website': 'https://posterra.com',
    'depends': ['base', 'portal', 'auth_signup', 'hha_crm_integration', 'dashboard_builder'],
    'data': [
        # Security — groups must load first
        'security/posterra_security.xml',
        # ACL for hha.provider (pre-existing model, xmlid already registered)
        'security/ir.model.access.csv',
        # Phase 0 — Dashboard pages, tabs, filters
        # Phase 1 — Dashboard widgets
        # View files load before seed data so ir.ui.view records exist first.
        'views/nav_section_views.xml',
        'views/page_views.xml',
        'views/saas_app_views.xml',        # Phase 5: Applications admin menu
        'views/widget_views.xml',
        'views/section_views.xml',
        'data/saas_apps_data.xml',         # Phase 5: Posterra + MSSP app seed records
        'data/nav_sections_data.xml',
        'data/pages_data.xml',
        'data/filters_data.xml',
        'data/sections_data.xml',
        'data/widget_templates_data.xml',  # WB-6: Healthcare widget templates
        # ACL for Phase 0 + Phase 1 models — loaded AFTER seed data so ir.model
        # records for dashboard.* are fully committed; uses model= search.
        'security/dashboard_access.xml',
        # Base views/actions used by menus
        'views/hha_scope_group_views.xml',
        'views/hha_provider_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/hha_csv_import_views.xml',
        'wizard/create_portal_user_views.xml',
        # Menus and templates
        'views/menuitems.xml',
        'views/login_templates.xml',
        'views/error_templates.xml',       # Phase 4: branded error pages (404/403/500)
        'views/dashboard_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'posterra_portal/static/src/css/posterra.css',
            # Phase 7 — React bundle (Vite build output, fixed filename)
            # Build: cd static/src/react && npm run build
            # ECharts 5 is bundled via npm (no CDN script needed).
            # No portal.css — React components use posterra.css for styling.
            'posterra_portal/static/src/react/dist/portal.js',
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
