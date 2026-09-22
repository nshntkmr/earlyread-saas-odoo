# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
    # Opt-in header look (blank/plain = today's muted line, byte-identical).
    subtitle_style = fields.Selection([
        ('plain', 'Plain'),
        ('accent_bar', 'Accent bar'),
    ], string='Subtitle Style', default='plain',
        help='Plain = muted line under the title (default). Accent bar = a '
             'coloured left rule with darker, slightly larger text.')
    subtitle_color = fields.Char(string='Subtitle Color',
        help='Hex text colour for the subtitle (e.g. #374151). Blank = default.')
    subtitle_accent_color = fields.Char(string='Accent Color',
        help='Hex colour of the accent bar (e.g. #15803d). Blank = app primary.')
    footnote  = fields.Text(string='Footnote',
        help='Displayed at the bottom of the page content area')
    help_text = fields.Text(string='Help Text',
        help='Tooltip shown via info icon next to the page title')

    # ── PDF export (config-driven; off by default → zero change) ──────────
    pdf_export_enabled = fields.Boolean(
        string='Enable PDF Export', default=False,
        help='Shows an "Export PDF" button that prints the current tab '
             '(record headers, KPIs, tables and charts) with the applied filters. '
             'Enabling PDF export makes every included table\'s rows '
             'exportable as PDF, regardless of the widget\'s Download '
             'settings. Use "Include in PDF" on each widget to leave a '
             'widget out.')
    pdf_orientation = fields.Selection(
        [('landscape', 'Landscape'), ('portrait', 'Portrait')],
        string='PDF Orientation', default='landscape')
    pdf_paper = fields.Selection(
        [('letter', 'US Letter'), ('a4', 'A4')],
        string='PDF Paper Size', default='letter')
    pdf_title_template = fields.Char(
        string='PDF Title',
        help='Title printed at the top of the PDF. Placeholders: {app_name}, '
             '{page_name}, {tab_name}, {date} and any visible filter\'s '
             'parameter name (prints the selected option label). '
             'Blank = "{app_name} — {page_name} — {tab_name}".')
    pdf_show_filters = fields.Boolean(
        string='PDF: Print Applied Filters', default=True)
    pdf_show_logo = fields.Boolean(
        string='PDF: Print App Logo', default=True)
    pdf_footer_text = fields.Char(
        string='PDF Footer Text',
        help='Printed at the bottom-left of every PDF page (page numbers are '
             'always printed on the right). Supports {app_name}.')
    pdf_row_limit = fields.Integer(
        string='PDF Row Limit', default=500,
        help='Maximum rows printed per table (the database is asked for one '
             'more row to detect truncation; a notice is printed when rows '
             'were left out). Hard maximum 5,000.')
    pdf_max_columns = fields.Integer(
        string='PDF Column Limit', default=16,
        help='Maximum columns printed per table (a notice is printed when '
             'columns were left out). Hard maximum 24.')
    pdf_keynote_enabled = fields.Boolean(
        string='PDF: Allow Keynote', default=True,
        help='Let users type a short keynote in the export dialog; it is '
             'printed near the top of the PDF.')
    pdf_tab_ids = fields.Many2many(
        'dashboard.page.tab', 'dashboard_page_pdf_tab_rel', 'page_id', 'tab_id',
        string='PDF Button on Tabs',
        help='Tabs that show the Export PDF button (and may be exported). '
             'Leave empty to allow every tab of this page.')
    pdf_button_bg_color = fields.Char(
        string='PDF Button Color',
        help='Background colour of the Export PDF button (e.g. #0b6e4f). '
             'Blank = the standard outline button.')
    pdf_button_text_color = fields.Char(
        string='PDF Button Text Color',
        help='Text and icon colour of the Export PDF button. Blank = white '
             'on a custom background, the standard grey otherwise.')

    def pdf_tab_allowed(self, tab):
        """True when ``tab`` (a dashboard.page.tab or empty) may be exported.
        No tab restriction configured, or a page without tabs → allowed."""
        self.ensure_one()
        if not self.pdf_tab_ids or not tab:
            return True
        return tab.id in self.pdf_tab_ids.ids

    @api.constrains('pdf_tab_ids')
    def _check_pdf_tab_ids(self):
        for page in self:
            foreign = page.pdf_tab_ids.filtered(lambda t: t.page_id != page)
            if foreign:
                raise ValidationError(
                    'PDF Button on Tabs may only list tabs of this page (%s).'
                    % ', '.join(foreign.mapped('name')))

    @api.constrains('pdf_button_bg_color', 'pdf_button_text_color')
    def _check_pdf_button_colors(self):
        from ..services.pdf_export.cell_format import safe_color
        for page in self:
            for label, value in (('PDF Button Color', page.pdf_button_bg_color),
                                 ('PDF Button Text Color', page.pdf_button_text_color)):
                if value and not safe_color(value):
                    raise ValidationError(
                        f'{label} must be a colour such as #0b6e4f, rgb(11,110,79) or a '
                        f'CSS colour name.')

    @api.constrains('pdf_row_limit', 'pdf_max_columns')
    def _check_pdf_limits(self):
        from ..services.pdf_export.limits import (
            PDF_ROW_LIMIT_MAX, PDF_COLUMN_LIMIT_MAX)
        for page in self:
            if not (1 <= (page.pdf_row_limit or 0) <= PDF_ROW_LIMIT_MAX):
                raise ValidationError(
                    f'PDF Row Limit must be between 1 and {PDF_ROW_LIMIT_MAX:,}.')
            if not (1 <= (page.pdf_max_columns or 0) <= PDF_COLUMN_LIMIT_MAX):
                raise ValidationError(
                    f'PDF Column Limit must be between 1 and {PDF_COLUMN_LIMIT_MAX}.')

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

    def unlink(self):
        """Phase T tab-deletion contract (ADDITIVE — preserves existing
        behavior): a tab with NO tab-scoped filters deletes exactly as today
        (widgets/sections set-null to global). A tab WITH tab-scoped filters
        blocks deletion until those filters are moved or safely deleted; the
        block lists only consumers that actually REFERENCE those filters.
        The filter-side ondelete='cascade' stays as a DB backstop only."""
        from ..utils import filter_scope_inspector as insp
        Filter = self.env['dashboard.page.filter'].sudo()
        blockers = []
        for tab in self:
            tab_filters = Filter.search([('tab_id', '=', tab.id)])
            if not tab_filters:
                continue  # today's deletion behavior, unchanged
            details = []
            for flt in tab_filters:
                refs = insp.filter_references(self.env, flt)
                details.append(
                    "filter '%s'%s" % (
                        flt.display_name,
                        (' — referenced by: %s' % '; '.join(refs))
                        if refs else ''))
            blockers.append(
                "Tab '%s' has %d tab-scoped filter(s): %s"
                % (tab.name, len(tab_filters), ' | '.join(details)))
        if blockers:
            raise ValidationError(
                'Cannot delete tab(s) with tab-scoped filters:\n%s\n'
                'Move or delete those filters first.' % '\n'.join(blockers))
        return super().unlink()

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
