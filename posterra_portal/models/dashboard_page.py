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
        help='Application this page belongs to. Used by the generic /my/<app_key>/ route.',
    )
    icon = fields.Char()
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
    group_ids = fields.Many2many('res.groups', string='Visible to Groups')

    portal_type = fields.Selection([
        ('hha',  'HHA Portal'),
        ('mssp', 'MSSP Portal'),
        ('all',  'All Portals'),
    ], string='Portal Type', default='hha', required=True,
       help='Controls which portal route shows this page.\n'
            'HHA Portal  → /my/posterra  (provider-scoped, requires HHA match or direct assignment)\n'
            'MSSP Portal → /my/mssp      (open access, requires Posterra MSSP User group)\n'
            'All Portals → visible in both routes')
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
