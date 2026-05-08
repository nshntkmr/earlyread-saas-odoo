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
    # P0-16: ``hha_crm_integration`` removed — verified stale.
    # Grep across posterra_portal + dashboard_builder finds zero
    # references to crm.lead extensions, external_lead_id,
    # npi_physician, ccn_facility, or lead_type. The addon still
    # exists at the operator's Odoo install path and can be installed
    # standalone for its CRM features; it just isn't a hard dependency
    # of the portal. Removing the dep means a fresh Azure deploy
    # doesn't need to vendor / submodule that addon to make
    # posterra_portal load.
    'depends': ['base', 'portal', 'auth_signup', 'dashboard_builder'],
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
        'views/page_template_views.xml',
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
        'views/dashboard_builder_ext_views.xml',
        'views/dashboard_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'posterra_portal/static/src/css/posterra.css',
            # Phase 7 — React JS bundle loaded via <script defer> in dashboard template
            # (NOT through Odoo's asset system — AG Grid's bundled code contains module
            # name strings that Odoo's AMD resolver incorrectly tries to resolve).
            # AG Grid v35 uses Theming API (themeQuartz) — no separate CSS file needed.
            # Build: cd static/src/react && npm run build
        ],
    },
    'external_dependencies': {
        # The PyPI package is published as ``clickhouse-connect`` (hyphen)
        # — install it with ``pip install clickhouse-connect`` against
        # Odoo's bundled Python — but Odoo's external-dependency check
        # does ``importlib.import_module(name)``, which can only resolve
        # valid Python identifiers. So the manifest must use the IMPORT
        # name ``clickhouse_connect`` (underscore). Required only when
        # an admin creates a ClickHouse-backed dashboard.connection;
        # listing it here makes a missing install fail fast at module
        # load with a clear message rather than at first-query time.
        'python': ['clickhouse_connect'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    # Recomputes domain_match_name on every install or upgrade so existing
    # records always reflect the current DBA-first matching logic.
    'post_init_hook': 'post_init_hook',
}
