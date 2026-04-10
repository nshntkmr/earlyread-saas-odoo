from . import controllers
from . import models
from . import wizard


def _fix_filter_noupdate(env):
    """Force noupdate=False on geo filter ir.model.data entries.

    The geo filters were originally shipped with noupdate="1" and later
    changed to noupdate="0" in the XML.  However, existing ir.model.data
    rows still have noupdate=True so Odoo skips them on upgrade.  This
    forces them to noupdate=False so seed data values (scope_to_user_hha,
    depends_on_filter_id, auto_fill_from_hha) are applied.
    """
    geo_xmlids = [
        'filter_overview_state',
        'filter_overview_county',
        'filter_overview_city',
        'filter_hospitals_state',
        'filter_physicians_state',
        'filter_competitive_state',
        'filter_mt_state',
        'filter_episodes_state',
        'filter_rs_state',
    ]
    IMD = env['ir.model.data']
    for name in geo_xmlids:
        rec = IMD.search([
            ('module', '=', 'posterra_portal'),
            ('name', '=', name),
        ], limit=1)
        if rec and rec.noupdate:
            rec.write({'noupdate': False})


def _cleanup_duplicate_filters(env):
    """Remove duplicate hha_city filter records created by the noupdate bug.

    When an xmlid had noupdate=True and the XML was changed to noupdate=0,
    Odoo could create a second record instead of updating the first.
    We keep the one linked to the xmlid and delete the duplicate.
    """
    Filter = env['dashboard.page.filter'].sudo()
    IMD = env['ir.model.data']

    # Check all pages for duplicate hha_city filters
    pages = env['dashboard.page'].sudo().search([])
    for page in pages:
        city_filters = Filter.search([
            ('page_id', '=', page.id),
            ('field_name', '=', 'hha_city'),
        ])
        if len(city_filters) <= 1:
            continue
        # Find the one linked to an xmlid — that's the canonical record
        keep_ids = set()
        for f in city_filters:
            imd_rec = IMD.search([
                ('module', '=', 'posterra_portal'),
                ('model', '=', 'dashboard.page.filter'),
                ('res_id', '=', f.id),
            ], limit=1)
            if imd_rec:
                keep_ids.add(f.id)
        if not keep_ids:
            # No xmlid-linked record; keep the first one
            keep_ids.add(city_filters[0].id)
        dupes = city_filters.filtered(lambda f: f.id not in keep_ids)
        if dupes:
            dupes.unlink()


def _populate_app_ids(env):
    """Populate dashboard.page.app_id for pages that don't have one yet.

    Phase 5 migration: the pages seed data uses noupdate="1" so the XML
    won't re-apply during upgrade.  We use portal_type to decide which
    saas.app each existing page belongs to:
      portal_type in ('hha', 'all')  → app_posterra
      portal_type == 'mssp'          → app_mssp
    Only pages where app_id is still False are updated (idempotent).
    """
    app_posterra = env.ref('posterra_portal.app_posterra', raise_if_not_found=False)
    app_mssp     = env.ref('posterra_portal.app_mssp',     raise_if_not_found=False)

    if not app_posterra and not app_mssp:
        # saas_apps_data.xml not yet committed — skip (will run again on next upgrade)
        return

    Page = env['dashboard.page']
    pages_no_app = Page.search([('app_id', '=', False)])
    if not pages_no_app:
        return

    if app_posterra:
        hha_pages = pages_no_app.filtered(lambda p: p.portal_type in ('hha', 'all'))
        if hha_pages:
            hha_pages.write({'app_id': app_posterra.id})

    if app_mssp:
        mssp_pages = pages_no_app.filtered(lambda p: p.portal_type == 'mssp')
        if mssp_pages:
            mssp_pages.write({'app_id': app_mssp.id})


def _migrate_depends_on_to_dependency_graph(env):
    """Migrate legacy depends_on_filter_id to the new dependency graph table.

    For each filter that has depends_on_filter_id set, create a corresponding
    dashboard.filter.dependency record:
      source = depends_on_filter_id (the parent)
      target = the filter itself (the child)
      propagation = 'required', resets_target = True

    Idempotent: skips if the edge already exists.
    """
    Filter = env['dashboard.page.filter'].sudo()
    Dep = env['dashboard.filter.dependency'].sudo()

    filters_with_dep = Filter.search([('depends_on_filter_id', '!=', False)])
    created = 0
    for f in filters_with_dep:
        parent = f.depends_on_filter_id
        if not parent or not parent.exists():
            continue
        # Check if edge already exists
        existing = Dep.search([
            ('source_filter_id', '=', parent.id),
            ('target_filter_id', '=', f.id),
        ], limit=1)
        if existing:
            continue
        Dep.create({
            'page_id': f.page_id.id,
            'source_filter_id': parent.id,
            'target_filter_id': f.id,
            'propagation': 'required',
            'resets_target': True,
            'sequence': 10,
        })
        created += 1
    if created:
        import logging
        logging.getLogger(__name__).info(
            'Migrated %d legacy depends_on_filter_id edges to dashboard.filter.dependency',
            created,
        )


def _ensure_app_access_groups(env):
    """Auto-create security groups for group-based apps that are missing them.

    Handles:
    - Apps where the group was manually created but deleted by a module upgrade
    - Apps where access_group_xmlid is set but points to a non-existent group
    - Apps where access_group_xmlid was never set

    Idempotent: skips apps that already have a valid group.
    """
    import logging
    _logger = logging.getLogger(__name__)
    App = env['saas.app'].sudo()
    group_apps = App.search([('access_mode', '=', 'group')])
    for app in group_apps:
        if app._needs_access_group():
            _logger.info(
                'Auto-creating security group for app %s (%s)',
                app.name, app.app_key,
            )
            app._ensure_access_group()


def post_init_hook(env):
    """Post-install/upgrade hook for posterra_portal.

    1. Recompute domain_match_name for all HHA providers.
    2. Fix noupdate flags on geo filter ir.model.data entries.
    3. Clean up duplicate filter records from the noupdate bug.
    4. Populate dashboard.page.app_id from portal_type (Phase 5 migration).
    5. Migrate legacy depends_on_filter_id to dependency graph.
    6. Auto-create security groups for group-based apps missing their group.
    """
    # Fix noupdate flags BEFORE Odoo processes the XML data files
    _fix_filter_noupdate(env)

    # Clean up duplicate city filters
    _cleanup_duplicate_filters(env)

    # Recompute domain_match_name
    providers = env['hha.provider'].search([])
    if providers:
        providers.invalidate_recordset(['domain_match_name'])
        providers._compute_domain_match_name()

    # Phase 5: populate app_id on existing pages
    _populate_app_ids(env)

    # Phase 8: migrate legacy filter dependencies to graph table
    _migrate_depends_on_to_dependency_graph(env)

    # Auto-create security groups for group-based apps missing their group
    _ensure_app_access_groups(env)

    # Load ZIP centroid data for map widgets
    from .data.load_zip_centroids import load_zip_centroids
    load_zip_centroids(env)