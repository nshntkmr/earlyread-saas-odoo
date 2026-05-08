# -*- coding: utf-8 -*-

from odoo import api, fields, models


class DashboardNavSection(models.Model):
    _name        = 'dashboard.nav.section'
    _description = 'Sidebar Navigation Section'
    _order       = 'sequence asc, id asc'

    name      = fields.Char(required=True, string='Label')
    key       = fields.Char(required=True, index=True, string='Key',
                    help='Slug used for CSS / legacy mapping, e.g. my_hha')
    sequence  = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
    page_ids  = fields.One2many('dashboard.page', 'nav_section_id', string='Pages')

    @api.model
    def default_get(self, fields_list):
        """New nav sections land at the end of the list."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            last = self.search([], order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res


class DashboardPage(models.Model):
    _name = 'dashboard.page'
    _description = 'Dashboard Page'
    _order = 'sequence asc, id asc'

    # Per-app uniqueness on (app_id, key). Combined with the
    # ``portal.app_dashboard`` search using ``current_page.id`` (P0-7),
    # this is the DB-level guarantee that two apps cannot have a page
    # with the same key. The previous controller search by ``page_id.key``
    # would have happily mixed records across apps; this constraint
    # makes that impossible at write time.
    #
    # Migration note: if existing data already has duplicate (app_id, key)
    # pairs (admin-created pages), module upgrade will FAIL with a clear
    # error. Resolve by changing one of the duplicate keys via admin UI
    # before re-applying. Posterra's seed XML uses unique keys per app.
    _sql_constraints = [
        ('app_key_uniq',
         'unique(app_id, key)',
         'A page key must be unique within an app.'),
    ]

    name           = fields.Char(required=True)
    key            = fields.Char(required=True, index=True)
    nav_section_id = fields.Many2one(
        'dashboard.nav.section',
        required=True,
        ondelete='restrict',
        string='Sidebar Section',
    )
    app_id = fields.Many2one(
        'saas.app',
        string='Application',
        ondelete='restrict',
        index=True,
        help='Application this page belongs to. Resolved from the request host subdomain.',
    )
    # Note on ``app_id``: NOT marked required because the ``post_init_hook``
    # ``_populate_app_ids`` backfills app_id from ``portal_type`` AFTER
    # XML data files load. If we made the field required, fresh installs
    # would fail (XML loads first) and upgrades with pre-existing
    # NULL-app_id rows would fail the NOT NULL transition. The
    # ``unique(app_id, key)`` constraint enforces tenant isolation when
    # app_id is set; NULL-app_id pages are unreachable by the portal
    # route (which requires an app from the subdomain) and are
    # effectively dead records.
    # Pre-migration check (admin runs before upgrade):
    #     SELECT id, name, key FROM dashboard_page WHERE app_id IS NULL;
    # Any rows returned should be deleted or have app_id assigned.
    icon = fields.Char()
    icon_color = fields.Char(string='Icon Color',
        help='CSS color for the sidebar icon (e.g. #38b2ac, coral, rgb(100,200,50)). '
             'Leave empty for default sidebar text color.')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
    group_ids = fields.Many2many('res.groups', string='Visible to Groups')

    portal_type = fields.Selection([
        ('hha',  'HHA Portal'),
        ('mssp', 'MSSP Portal'),
        ('all',  'All Portals'),
    ], string='Portal Type', default='hha', required=True,
       help='Controls which portal subdomain shows this page.\n'
            'HHA Portal  → posterra.<host>  (provider-scoped, requires HHA match or direct assignment)\n'
            'MSSP Portal → mssp.<host>      (open access, requires Posterra MSSP User group)\n'
            'All Portals → visible in both subdomains')
    tab_ids = fields.One2many('dashboard.page.tab', 'page_id', string='Tabs')
    filter_ids = fields.One2many('dashboard.page.filter', 'page_id', string='Filters')
    filter_dependency_ids = fields.One2many(
        'dashboard.filter.dependency', 'page_id', string='Filter Dependencies')
    widget_ids = fields.One2many('dashboard.widget', 'page_id', string='Widgets')
    badge_ids = fields.One2many('dashboard.page.badge', 'page_id', string='Header Badges')

    # ── Annotations ────────────────────────────────────────────────────────
    subtitle  = fields.Char(string='Subtitle',
        help='Displayed under the page title in the header bar')
    footnote  = fields.Text(string='Footnote',
        help='Displayed at the bottom of the page content area')
    help_text = fields.Text(string='Help Text',
        help='Tooltip shown via info icon next to the page title')

    @api.model
    def default_get(self, fields_list):
        """New pages always land at the end of the sidebar, not the top."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            last = self.search([], order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res

    def action_save_as_template(self):
        """Save this page as a reusable template."""
        self.ensure_one()
        import json
        Template = self.env['dashboard.page.template'].sudo()
        page_config = Template.serialize_page(self)
        # Collect unique schema source table names
        source_tables = set()
        for w in self.widget_ids:
            if w.schema_source_id:
                source_tables.add(w.schema_source_id.table_name)
        template = Template.create({
            'name': f'{self.name} Template',
            'page_config': json.dumps(page_config, default=str),
            'schema_sources': json.dumps(list(source_tables)),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Page Template Created',
            'res_model': 'dashboard.page.template',
            'res_id': template.id,
            'view_mode': 'form',
        }


class DashboardPageTab(models.Model):
    _name = 'dashboard.page.tab'
    _description = 'Dashboard Page Tab'
    _order = 'sequence asc, id asc'

    # Per-page tab key uniqueness. Tabs belong to one page (page_id is
    # required + ondelete='cascade'), and tab key resolution in the
    # controller assumes uniqueness within a page. Without this, two
    # tabs with key='command_center' on the same page would be picked
    # ambiguously by ``current_tab_key`` matching.
    _sql_constraints = [
        ('page_key_uniq',
         'unique(page_id, key)',
         'A tab key must be unique within a page.'),
    ]

    name = fields.Char(required=True)
    key = fields.Char(required=True, index=True)
    page_id = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    @api.model
    def default_get(self, fields_list):
        """New tabs always land after the last tab on the same page."""
        res = super().default_get(fields_list)
        if 'sequence' in fields_list:
            page_id = self.env.context.get('default_page_id')
            domain = [('page_id', '=', page_id)] if page_id else []
            last = self.search(domain, order='sequence desc', limit=1)
            res['sequence'] = (last.sequence if last else 0) + 10
        return res
