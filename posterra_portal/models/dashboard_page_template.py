# -*- coding: utf-8 -*-
"""
Page Templates — Save / Reuse entire page layouts.

Captures a complete page snapshot (tabs, filters, filter dependencies,
widgets, sections) as a JSON blob. On apply, creates a new page with
all children under a target app and nav section.

Works for any US healthcare data domain (HHA, ACO, MSSP, MA, Hospice,
SNF, Claims, EMR). After applying, admin edits widget SQL for the new
data source.
"""

import json
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DashboardPageTemplate(models.Model):
    _name = 'dashboard.page.template'
    _description = 'Dashboard Page Template'
    _order = 'name'

    name = fields.Char(required=True, string='Template Name')
    description = fields.Text(string='Description',
        help='What this template is for, which pages/metrics it includes.')
    business_type = fields.Selection([
        ('hha', 'HHA'),
        ('aco', 'ACO'),
        ('mssp', 'MSSP'),
        ('ma', 'MA'),
        ('hospice', 'Hospice'),
        ('snf', 'SNF'),
        ('claims', 'Claims'),
        ('emr', 'EMR'),
        ('general', 'General'),
    ], string='Business Type', help='Optional categorization for the template gallery.')
    category = fields.Selection([
        ('overview', 'Overview'),
        ('quality', 'Quality'),
        ('financial', 'Financial'),
        ('operational', 'Operational'),
        ('clinical', 'Clinical'),
        ('competitive', 'Competitive'),
    ], string='Category', help='Optional categorization for the template gallery.')
    preview_image = fields.Binary(string='Preview Image', attachment=True)
    is_published = fields.Boolean(default=True, string='Published',
        help='Visible in the template gallery.')

    # The complete page snapshot as JSON
    page_config = fields.Text(string='Page Config (JSON)',
        help='Complete page snapshot: tabs, filters, filter_dependencies, widgets, sections.')
    # Schema sources referenced by widgets in this template
    schema_sources = fields.Text(string='Schema Sources (JSON)',
        help='List of schema source table names referenced in widget SQL.')

    # Computed
    widget_count = fields.Integer(compute='_compute_counts', string='Widgets')
    filter_count = fields.Integer(compute='_compute_counts', string='Filters')
    tab_count = fields.Integer(compute='_compute_counts', string='Tabs')

    @api.depends('page_config')
    def _compute_counts(self):
        for rec in self:
            try:
                cfg = json.loads(rec.page_config or '{}')
                rec.widget_count = len(cfg.get('widgets', []))
                rec.filter_count = len(cfg.get('filters', []))
                rec.tab_count = len(cfg.get('tabs', []))
            except (json.JSONDecodeError, TypeError):
                rec.widget_count = 0
                rec.filter_count = 0
                rec.tab_count = 0

    # ── Serialization: Page → JSON ──────────────────────────────────────

    @api.model
    def serialize_page(self, page):
        """Serialize a dashboard.page record into a portable JSON dict.

        Replaces database IDs with portable references (table names, keys).
        The resulting JSON can be stored and later deserialized to create
        a new page under a different app.
        """
        page.ensure_one()

        # ── Page metadata ──────────────────────────────────────────
        page_data = {
            'name': page.name,
            'key': page.key,
            'icon': page.icon or '',
            'portal_type': page.portal_type or 'hha',
            'subtitle': page.subtitle or '',
            'footnote': page.footnote or '',
            'help_text': page.help_text or '',
        }

        # ── Tabs ───────────────────────────────────────────────────
        tabs = []
        for tab in page.tab_ids.sorted('sequence'):
            tabs.append({
                'name': tab.name,
                'key': tab.key,
                'sequence': tab.sequence,
                'is_active': tab.is_active,
            })

        # ── Filters ────────────────────────────────────────────────
        filters = []
        for f in page.filter_ids.sorted('sequence'):
            fdata = {
                'param_name': f.param_name or '',
                'label': f.label or '',
                'sequence': f.sequence,
                'is_active': f.is_active,
                'is_required': f.is_required,
                'is_multiselect': f.is_multiselect,
                'is_searchable': f.is_searchable,
                'is_visible': f.is_visible,
                'include_all_option': f.include_all_option,
                'hide_all_option': f.hide_all_option,
                'scope_to_user_hha': f.scope_to_user_hha,
                'auto_fill_from_hha': f.auto_fill_from_hha,
                'is_provider_selector': f.is_provider_selector,
                'default_value': f.default_value or '',
                'default_strategy': f.default_strategy or 'static',
                'placeholder': f.placeholder or '',
                'display_template': f.display_template or '',
                'display_template_source': f.display_template_source or '',
                'option_sort': f.option_sort or '',
                'manual_options': f.manual_options or '',
                # D1/D2: placement + apply behavior + remote-search config.
                'ui_type': f.ui_type or 'default',
                'display_region': f.display_region or '',
                'apply_behavior': f.apply_behavior or 'manual',
                'search_page_size': f.search_page_size or 0,
                'search_min_chars': f.search_min_chars or 0,
                'control_width_px': f.control_width_px or 0,
                'search_column_names': f.search_column_ids.mapped('column_name'),
                # Portable schema references (table_name + column_name instead of IDs)
                'schema_source_table': f.schema_source_id.table_name if f.schema_source_id else '',
                'schema_column_name': f.schema_column_id.column_name if f.schema_column_id else '',
                # Portable Schema-Source IDENTITY — the same table name can exist
                # on several connections, so table_name alone is ambiguous. Carry
                # the connection name (or an explicit local-PG marker) + engine.
                'schema_source_engine': f.schema_source_id.engine if f.schema_source_id else '',
                'schema_source_connection': (
                    f.schema_source_id.connection_id.name
                    if f.schema_source_id and f.schema_source_id.connection_id
                    else ('__local_pg__' if f.schema_source_id else '')),
                # ORM references (model + field names instead of IDs)
                'model_name': f.model_name or '',
                'field_name': f.field_name or '',
            }
            # Optional: hha_scope_column
            if hasattr(f, 'hha_scope_column_id') and f.hha_scope_column_id:
                fdata['hha_scope_column_name'] = f.hha_scope_column_id.column_name
            filters.append(fdata)

        # ── Filter dependencies ────────────────────────────────────
        filter_deps = []
        for dep in page.filter_dependency_ids:
            filter_deps.append({
                'source_param': dep.source_filter_id.param_name or dep.source_filter_id.field_name or '',
                'target_param': dep.target_filter_id.param_name or dep.target_filter_id.field_name or '',
                'resets_target': dep.resets_target,
                'propagation': dep.propagation or 'required',
                'sequence': dep.sequence,
            })

        # ── Widgets ────────────────────────────────────────────────
        widgets = []
        for w in page.widget_ids.sorted('sequence'):
            wdata = {
                'name': w.name,
                'chart_type': w.chart_type,
                'tab_key': w.tab_id.key if w.tab_id else '',
                'sequence': w.sequence,
                'is_active': w.is_active,
                # Display
                'col_span': w.col_span,
                'row_span': w.row_span,
                'width_pct': w.width_pct,
                'max_width_pct': w.max_width_pct,
                'chart_height': w.chart_height,
                'render_region': w.render_region or 'tab_content',
                'display_mode': w.display_mode or 'standard',
                'kpi_layout': w.kpi_layout or 'vertical',
                'text_align': w.text_align or 'center',
                'color_palette': w.color_palette or 'healthcare',
                'color_custom_json': w.color_custom_json or '',
                # Icon
                'icon_name': w.icon_name or 'none',
                'icon_color': w.icon_color or 'default',
                'icon_custom_color': w.icon_custom_color or '',
                'icon_custom_bg': w.icon_custom_bg or '',
                # Metric direction (controls trend coloring)
                'metric_direction': w.metric_direction or 'higher_better',
                # Typography
                'label_font_weight': w.label_font_weight or 'normal',
                'value_font_weight': w.value_font_weight or 'bold',
                'label_color': w.label_color or 'default',
                'value_color': w.value_color or 'default',
                'card_label_style': w.card_label_style or 'plain',
                'card_label_badge_bg': w.card_label_badge_bg or '',
                'card_label_badge_text': w.card_label_badge_text or '',
                # Query
                'query_type': w.query_type or 'sql',
                'query_sql': w.query_sql or '',
                'x_column': w.x_column or '',
                'y_columns': w.y_columns or '',
                'series_column': w.series_column or '',
                'schema_source_table': w.schema_source_id.table_name if w.schema_source_id else '',
                'where_clause_exclude': w.where_clause_exclude or '',
                # Download (per-widget data export)
                'download_enabled': bool(w.download_enabled),
                'download_formats': w.download_formats or 'csv',
                'download_sql': w.download_sql or '',
                'download_schema_source_table': (
                    w.download_schema_source_id.table_name
                    if w.download_schema_source_id else ''),
                'download_icon_position': w.download_icon_position or 'header_right',
                'download_icon_color': w.download_icon_color or '',
                'download_filename': w.download_filename or '',
                'download_row_limit': w.download_row_limit or 0,
                # KPI
                'kpi_format': w.kpi_format or 'number',
                'kpi_prefix': w.kpi_prefix or '',
                'kpi_suffix': w.kpi_suffix or '',
                'status_column': w.status_column or '',
                # Gauge
                'gauge_min': w.gauge_min,
                'gauge_max': w.gauge_max,
                'gauge_color_mode': w.gauge_color_mode or 'traffic_light',
                'gauge_warn_threshold': w.gauge_warn_threshold,
                'gauge_good_threshold': w.gauge_good_threshold,
                # Visual config (JSON)
                'visual_config': w.visual_config or '',
                'echart_override': w.echart_override or '',
                'builder_config': w.builder_config or '',
                'table_column_config': w.table_column_config or '',
                'detail_drawer_config': w.detail_drawer_config or '',
                'column_link_config': w.column_link_config or '',
                # v5 widget configs (JSON) — icon keys referenced inside are
                # bundled by _collect_icon_keys at export.
                'attribute_grid_config': w.attribute_grid_config or '',
                'metric_list_config': w.metric_list_config or '',
                'bar_stack': w.bar_stack,
                # Actions
                'click_action': w.click_action or 'none',
                'action_page_key': w.action_page_key or '',
                'action_tab_key': w.action_tab_key or '',
                'action_pass_value_as': w.action_pass_value_as or '',
                'action_url_template': w.action_url_template or '',
                'drill_detail_columns': w.drill_detail_columns or '',
                # Annotations
                'subtitle': w.subtitle or '',
                'footnote': w.footnote or '',
                'annotation_type': w.annotation_type or 'none',
                'annotation_text': w.annotation_text or '',
                'annotation_position': w.annotation_position or 'top_right',
            }
            # Battle card fields (only if chart_type is battle_card)
            if w.chart_type == 'battle_card':
                wdata.update({
                    'you_column': w.you_column or '',
                    'them_column': w.them_column or '',
                    'label_column': w.label_column or '',
                    'win_threshold': w.win_threshold or 'higher',
                    'competitor_name': w.competitor_name or '',
                })
            # Insight panel fields
            if w.chart_type == 'insight_panel':
                wdata.update({
                    'metric1_label': w.metric1_label or '',
                    'metric2_label': w.metric2_label or '',
                    'metric3_label': w.metric3_label or '',
                    'narrative_template': w.narrative_template or '',
                })
            # Gauge KPI fields
            if w.chart_type == 'gauge_kpi':
                wdata.update({
                    'gauge_sub_kpi_columns': w.gauge_sub_kpi_columns or '',
                    'gauge_sub_kpi_labels': w.gauge_sub_kpi_labels or '',
                    'gauge_sub_label_columns': w.gauge_sub_label_columns or '',
                    'gauge_alert_column': w.gauge_alert_column or '',
                })
            # Scope control fields
            wdata.update({
                'scope_mode': w.scope_mode or 'none',
                'scope_ui': w.scope_ui or 'dropdown',
                'scope_query_mode': w.scope_query_mode or 'parameter',
                'scope_param_name': w.scope_param_name or '',
                'scope_label': w.scope_label or '',
                'scope_default_value': w.scope_default_value or '',
                'scope_filter_param': (
                    (w.scope_filter_id.param_name or '') if w.scope_filter_id else ''),
                'scope_schema_source_table': (
                    w.scope_schema_source_id.table_name if w.scope_schema_source_id else ''),
                'scope_value_column': w.scope_value_column or '',
                'scope_label_column': w.scope_label_column or '',
                'search_enabled': w.search_enabled,
                'search_placeholder': w.search_placeholder or '',
            })
            # Scope options (child records)
            scope_opts = []
            for o in w.scope_option_ids.filtered('is_active').sorted('sequence'):
                scope_opts.append({
                    'label': o.label,
                    'value': o.value or '',
                    'icon': o.icon or '',
                    'color': o.color or '',
                    'icon_color': o.icon_color or '',
                    'sequence': o.sequence,
                    'query_sql': o.query_sql or '',
                    'schema_source_table': (
                        o.schema_source_id.table_name if o.schema_source_id else ''),
                    'where_clause_exclude': o.where_clause_exclude or '',
                    'table_column_config': o.table_column_config or '',
                    'x_column': o.x_column or '',
                    'y_columns': o.y_columns or '',
                    'series_column': o.series_column or '',
                    'click_action': o.click_action or 'none',
                    'action_page_key': o.action_page_key or '',
                    'action_tab_key': o.action_tab_key or '',
                    'action_pass_value_as': o.action_pass_value_as or '',
                    'drill_detail_columns': o.drill_detail_columns or '',
                    'action_url_template': o.action_url_template or '',
                    # Per-option geo metadata (map choropleth drill)
                    'default_geo_level': o.default_geo_level or 'state',
                    'allowed_geo_levels': o.allowed_geo_levels or 'state',
                    'supports_drill': bool(o.supports_drill),
                })
            if scope_opts:
                wdata['scope_options'] = scope_opts

            # ── Composite items ────────────────────────────────────────
            # Round-trip invariant: any field copied to the transient
            # .new() payload in dashboard_widget._build_composite_data MUST
            # be threaded here too. Otherwise template export/import
            # silently drops it.
            if w.chart_type == 'composite':
                wdata['composite_items'] = [{
                    'sequence':             c.sequence,
                    'is_active':            c.is_active,
                    'name':                 c.name or '',
                    'chart_type':           c.chart_type,
                    'data_mode':            c.data_mode,
                    'query_sql':            c.query_sql or '',
                    'where_clause_exclude': c.where_clause_exclude or '',
                    'schema_source_table':  c.schema_source_id.table_name
                                            if c.schema_source_id else '',
                    'x_column':             c.x_column or '',
                    'y_columns':            c.y_columns or '',
                    'series_column':        c.series_column or '',
                    'status_column':        c.status_column or '',
                    'kpi_format':           c.kpi_format,
                    'kpi_prefix':           c.kpi_prefix or '',
                    'kpi_suffix':           c.kpi_suffix or '',
                    'kpi_layout':           c.kpi_layout or 'vertical',
                    'display_mode':         c.display_mode or 'standard',
                    'text_align':           c.text_align or 'center',
                    'metric_direction':     c.metric_direction or 'higher_better',
                    'icon_name':            c.icon_name or 'none',
                    'icon_position':        c.icon_position or 'title',
                    'title_icon_color':     c.title_icon_color or 'default',
                    'color_custom_json':    c.color_custom_json or '',
                    'visual_config':        c.visual_config or '{}',
                    'bar_stack':            c.bar_stack or False,
                    'echart_override':      c.echart_override or '',
                    'gauge_min':            c.gauge_min or 0,
                    'gauge_max':            c.gauge_max or 100,
                    'gauge_color_mode':     c.gauge_color_mode or 'traffic_light',
                    'gauge_warn_threshold': c.gauge_warn_threshold or 50,
                    'gauge_good_threshold': c.gauge_good_threshold or 80,
                    'table_column_config':  c.table_column_config or '',
                    'column_link_config':   c.column_link_config or '',
                    'ranked_master_config': c.ranked_master_config or '',
                    'ranked_detail_config': c.ranked_detail_config or '',
                    'text_note_body':       c.text_note_body or '',
                    'col_start':            c.col_start,
                    'col_span':             c.col_span,
                    'row_start':            c.row_start,
                    'row_span':             c.row_span,
                    'min_height_px':        c.min_height_px or 240,
                } for c in w.composite_item_ids]

            widgets.append(wdata)

        # ── Sections ───────────────────────────────────────────────
        sections = []
        Section = self.env.get('dashboard.page.section')
        if Section:
            page_sections = Section.search([('page_id', '=', page.id)], order='sequence asc')
            for s in page_sections:
                sdata = {
                    'name': s.name,
                    'section_type': s.section_type,
                    'tab_key': s.tab_id.key if s.tab_id else '',
                    'sequence': s.sequence,
                    'is_active': s.is_active,
                    'icon': s.icon or '',
                    'action_label': s.action_label or '',
                    'max_rows': s.max_rows,
                    'subtitle': s.subtitle or '',
                    'description': s.description or '',
                    'footnote': s.footnote or '',
                    'query_sql': s.query_sql or '',
                    'schema_source_table': s.schema_source_id.table_name if s.schema_source_id else '',
                    'where_clause_exclude': s.where_clause_exclude or '',
                    # Scope
                    'scope_mode': s.scope_mode or 'none',
                    'scope_param_name': s.scope_param_name or '',
                    'scope_label': s.scope_label or '',
                    'scope_default_value': s.scope_default_value or '',
                    'scope_value_column': s.scope_value_column or '',
                    'scope_label_column': s.scope_label_column or '',
                    'scope_schema_source_table': s.scope_schema_source_id.table_name if s.scope_schema_source_id else '',
                    # Comparison bar columns
                    'cb_label_col': s.cb_label_col or '',
                    'cb_value_col': s.cb_value_col or '',
                    'cb_status_col': s.cb_status_col or '',
                    'cb_desc_col': s.cb_desc_col or '',
                    'cb_sublabel_col': s.cb_sublabel_col or '',
                    # Leaderboard table columns
                    'lt_rank_col': s.lt_rank_col or '',
                    'lt_name_col': s.lt_name_col or '',
                    'lt_sub_name_cols': s.lt_sub_name_cols or '',
                    'lt_display_cols': s.lt_display_cols or '',
                    'lt_display_labels': s.lt_display_labels or '',
                    'lt_you_col': s.lt_you_col or '',
                    'lt_color_col': s.lt_color_col or '',
                    'lt_good_threshold': s.lt_good_threshold,
                    'lt_warn_threshold': s.lt_warn_threshold,
                }
                sections.append(sdata)

        # ── Badges ──
        badges = []
        for b in page.badge_ids.filtered('is_active'):
            badges.append({
                'name': b.name,
                'icon': b.icon or '',
                'sequence': b.sequence,
                'is_active': b.is_active,
                'query_sql': b.query_sql or '',
                'schema_source_table': b.schema_source_id.table_name if b.schema_source_id else '',
                'where_clause_exclude': b.where_clause_exclude or '',
                'font_size': b.font_size,
                'text_color': b.text_color or '',
                'icon_color': b.icon_color or '',
                'is_link': b.is_link,
            })

        return {
            'page': page_data,
            'tabs': tabs,
            'filters': filters,
            'filter_dependencies': filter_deps,
            'widgets': widgets,
            'sections': sections,
            'badges': badges,
            # v5: registry entries for every icon key the widgets reference
            # (discoverable set: static keys, fallbacks, allowed_keys,
            # leading_visual). Restores on a fresh tenant can then create
            # missing icons at preflight instead of rendering blanks.
            'icons': self._collect_icon_bundle(widgets),
        }

    # ── Deserialization: JSON → Page ────────────────────────────────────

    def action_use_template(self):
        """Open wizard to apply this template."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Use Template: {self.name}',
            'res_model': 'dashboard.page.template.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_template_id': self.id},
        }

    def _resolve_template_source(self, fdict):
        """Resolve a serialized Schema-Source reference to its record.

        Uses the portable connector IDENTITY (connection name + table) when the
        template carries it; falls back to a table-only lookup for legacy
        (pre-identity) templates — but ONLY when exactly one source matches.
        Raises ValidationError (never picks arbitrarily) so a restore can't
        silently bind to the wrong tenant's table. Returns the source recordset
        (empty if the filter has no schema source at all).
        """
        table = fdict.get('schema_source_table', '')
        if not table:
            return self.env['dashboard.schema.source'].sudo().browse()
        Source = self.env['dashboard.schema.source'].sudo()
        conn_name = fdict.get('schema_source_connection', '')
        if conn_name == '__local_pg__':
            src = Source.search(
                [('table_name', '=', table), ('connection_id', '=', False)], limit=2)
            where = "local Postgres"
        elif conn_name:
            conn = self.env['dashboard.connection'].sudo().search(
                [('name', '=', conn_name)], limit=1)
            if not conn:
                raise ValidationError(
                    "Template references connection '%s' which does not exist in "
                    "this environment." % conn_name)
            src = Source.search(
                [('table_name', '=', table), ('connection_id', '=', conn.id)], limit=2)
            where = "connection '%s'" % conn_name
        else:
            # Legacy template: table only. Accept ONLY when unambiguous.
            src = Source.search([('table_name', '=', table)], limit=2)
            where = "any connection"
        if not src:
            raise ValidationError(
                "Template references Schema Source table '%s' (%s) which does "
                "not exist in this environment." % (table, where))
        if len(src) > 1:
            raise ValidationError(
                "Template references table '%s' which exists on multiple "
                "connections and the template predates connector identity; "
                "resolve the ambiguity manually before applying." % table)
        return src[:1]

    def _preflight_filters(self, filters_cfg):
        """Resolve + validate every filter's schema references BEFORE any record
        is created, so a restore never yields a partial page or a Remote Search
        filter silently downgraded to a plain dropdown.

        Returns {index: {source_id, column_id, search_column_ids,
        hha_scope_column_id}}. Raises ValidationError on any unresolved
        reference.
        """
        resolved = {}
        for i, f in enumerate(filters_cfg):
            r = {}
            source = self._resolve_template_source(f)
            if source:
                r['source_id'] = source.id
                src_cols = {c.column_name: c.id for c in source.column_ids}

                def _need(col_name, kind):
                    if col_name not in src_cols:
                        raise ValidationError(
                            "Template filter '%s' references %s '%s' which is not "
                            "a column of Schema Source '%s'." % (
                                f.get('param_name') or f.get('label') or '?',
                                kind, col_name, source.table_name))
                    return src_cols[col_name]

                col_name = f.get('schema_column_name', '')
                if col_name:
                    r['column_id'] = _need(col_name, 'value column')
                for sc in f.get('search_column_names') or []:
                    _need(sc, 'search column')
                r['search_column_ids'] = [src_cols[sc] for sc in (f.get('search_column_names') or [])]
                scope_name = f.get('hha_scope_column_name', '')
                if scope_name:
                    r['hha_scope_column_id'] = _need(scope_name, 'HHA scope column')
                # Display-Template placeholders must all exist in the source.
                missing = set(re.findall(r'\{(\w+)\}', f.get('display_template', '') or '')) - set(src_cols)
                if missing:
                    raise ValidationError(
                        "Template filter '%s' Display Template references columns "
                        "not in Schema Source '%s': %s" % (
                            f.get('param_name') or '?', source.table_name,
                            ', '.join(sorted(missing))))
            # Remote Search invariants — validate here so Filter.create's
            # @api.constrains can't fail mid-restore (partial page) and so the
            # filter is never silently downgraded to a plain preloading dropdown.
            if f.get('ui_type') == 'remote_autocomplete':
                param = f.get('param_name') or f.get('label') or '?'
                if not source:
                    raise ValidationError("Remote Search filter '%s' requires a Schema Source." % param)
                if not f.get('schema_column_name'):
                    raise ValidationError("Remote Search filter '%s' requires a Value Column." % param)
                if not (f.get('search_column_names') or []):
                    raise ValidationError("Remote Search filter '%s' requires at least one Search Column." % param)
                if f.get('is_multiselect'):
                    raise ValidationError("Remote Search filter '%s' cannot be multi-select." % param)
                if f.get('default_strategy') in ('all_values', 'first', 'latest'):
                    raise ValidationError("Remote Search filter '%s' requires a Static default." % param)
                if f.get('scope_to_user_hha') and not f.get('hha_scope_column_name'):
                    raise ValidationError(
                        "Remote Search filter '%s' with HHA scoping requires an HHA Scope Column." % param)
            resolved[i] = r
        return resolved

    # ── v5: icon bundle + widget preflight helpers ───────────────────────

    @staticmethod
    def _collect_icon_keys(chart_type, raw_config):
        """Discoverable icon keys referenced by one widget config: static
        keys, fallbacks, every allowed_keys entry, leading_visual.icon_key.
        (Arbitrary SQL output is NOT discoverable — that is exactly why
        column-mode icons require allowed_keys.)"""
        from odoo.addons.dashboard_builder.services.widget_config_normalizer import (
            normalize_attribute_grid, normalize_metric_list,
        )
        keys = set()
        if not isinstance(raw_config, dict):
            return keys
        if chart_type == 'attribute_grid':
            cfg = normalize_attribute_grid(raw_config)
            if cfg['leading_visual'].get('icon_key'):
                keys.add(cfg['leading_visual']['icon_key'])
            for f in cfg['fields']:
                icon = f.get('icon') or {}
                keys.update(k for k in [icon.get('key'),
                                        icon.get('fallback_key')] if k)
                keys.update(k for k in icon.get('allowed_keys') or [] if k)
            ri = cfg['row_icon']
            if ri.get('fallback_key'):
                keys.add(ri['fallback_key'])
            keys.update(k for k in ri.get('allowed_keys') or [] if k)
        elif chart_type == 'metric_list':
            cfg = normalize_metric_list(raw_config)
            if cfg['icon'].get('fallback_key'):
                keys.add(cfg['icon']['fallback_key'])
            keys.update(k for k in cfg['icon'].get('allowed_keys') or [] if k)
        return keys

    def _collect_icon_bundle(self, widgets):
        """Registry entries for every discoverable key across the serialized
        widgets. Keys with no registry record are skipped (nothing to bundle)."""
        all_keys = set()
        for w in widgets:
            for ct, cfg_field in (('attribute_grid', 'attribute_grid_config'),
                                  ('metric_list', 'metric_list_config')):
                raw = w.get(cfg_field)
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    continue
                all_keys |= self._collect_icon_keys(ct, parsed)
        if not all_keys or 'dashboard.icon' not in self.env:
            return []
        rows = self.env['dashboard.icon'].sudo().with_context(
            active_test=False).search_read(
            [('key', 'in', sorted(all_keys))],
            ['key', 'label', 'fa_class', 'category'])
        return [{'key': r['key'], 'label': r['label'],
                 'fa_class': r['fa_class'], 'category': r['category'] or ''}
                for r in rows]

    def _preflight_widgets(self, widgets_cfg, icon_bundle):
        """Parse + validate every widget's v5 config and resolve the icon
        bundle BEFORE any record is written. Returns the list of registry
        vals to create. Conflict contract: missing key + bundled → create;
        existing key with identical fa_class → reuse; different fa_class →
        fail with the conflict list; a template never overwrites a global
        registry entry."""
        from odoo.addons.dashboard_builder.services.widget_config_validators import (
            validate_attribute_grid_config, validate_metric_list_config,
        )
        needed_keys = set()
        for w in widgets_cfg:
            for ct, cfg_field, validate in (
                    ('attribute_grid', 'attribute_grid_config',
                     validate_attribute_grid_config),
                    ('metric_list', 'metric_list_config',
                     validate_metric_list_config)):
                raw = w.get(cfg_field)
                if not raw:
                    if w.get('chart_type') == ct:
                        raise ValidationError(
                            "Widget '%s' is a %s but its template carries no "
                            "%s." % (w.get('name', '?'), ct, cfg_field))
                    continue
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                except (json.JSONDecodeError, TypeError):
                    raise ValidationError(
                        "Widget '%s': %s is not valid JSON."
                        % (w.get('name', '?'), cfg_field))
                errors = validate(parsed)
                if errors:
                    raise ValidationError(
                        "Widget '%s': invalid %s:\n- %s"
                        % (w.get('name', '?'), cfg_field,
                           '\n- '.join(errors)))
                needed_keys |= self._collect_icon_keys(ct, parsed)

        if not needed_keys or 'dashboard.icon' not in self.env:
            return []
        bundle_by_key = {b.get('key'): b for b in (icon_bundle or [])
                         if b.get('key')}
        Icon = self.env['dashboard.icon'].sudo().with_context(
            active_test=False)
        existing = {r['key']: r['fa_class'] for r in Icon.search_read(
            [('key', 'in', sorted(needed_keys))], ['key', 'fa_class'])}
        to_create, conflicts, unresolvable = [], [], []
        for key in sorted(needed_keys):
            if key in existing:
                bundled = bundle_by_key.get(key)
                if bundled and bundled.get('fa_class') \
                        and bundled['fa_class'] != existing[key]:
                    conflicts.append(
                        '%s (template: %s, registry: %s)'
                        % (key, bundled['fa_class'], existing[key]))
                continue  # identical or unbundled → reuse
            bundled = bundle_by_key.get(key)
            if not bundled or not bundled.get('fa_class'):
                unresolvable.append(key)
                continue
            to_create.append({
                'key': key,
                'label': bundled.get('label') or key,
                'fa_class': bundled['fa_class'],
                'category': bundled.get('category') or 'general',
            })
        if conflicts:
            raise ValidationError(
                'Icon key conflicts between this template and the global '
                'registry (a template never overwrites registry entries): '
                '%s. Rename the keys in the template or align the registry '
                'first.' % '; '.join(conflicts))
        if unresolvable:
            raise ValidationError(
                'Template references icon keys that exist neither in the '
                'registry nor in the template bundle: %s.'
                % ', '.join(unresolvable))
        return to_create

    def create_page_from_template(self, app_id, nav_section_id, name_override=None, key_override=None):
        """Create a new page with all children from this template's page_config.

        Preflight-first, then one savepoint around EVERYTHING that writes —
        icon upserts, page, tabs, filters, widgets, sections, badges. A
        failure anywhere leaves no partial page AND no stray registry rows
        (registry writes are global state, unlike page children).
        """
        self.ensure_one()
        cfg = json.loads(self.page_config or '{}')
        if not cfg:
            raise ValueError('Template has no page configuration.')

        # Resolve + validate all filter schema references up front — raises
        # before anything is created if a source/column/template is unresolvable.
        filter_resolutions = self._preflight_filters(cfg.get('filters', []))
        # v5: parse/validate widget configs + resolve icon bundle — zero writes.
        icons_to_create = self._preflight_widgets(
            cfg.get('widgets', []), cfg.get('icons', []))

        with self.env.cr.savepoint():
            if icons_to_create:
                self.env['dashboard.icon'].sudo().create(icons_to_create)
                _logger.info('Template %s: created %d missing icon(s): %s',
                             self.name, len(icons_to_create),
                             ', '.join(i['key'] for i in icons_to_create))
            return self._create_page_children(
                cfg, app_id, nav_section_id, name_override, key_override,
                filter_resolutions)

    def _create_page_children(self, cfg, app_id, nav_section_id,
                              name_override, key_override,
                              filter_resolutions):
        """The original creation body — runs entirely inside the caller's
        savepoint."""
        Page = self.env['dashboard.page'].sudo()
        Tab = self.env['dashboard.page.tab'].sudo()
        Filter = self.env['dashboard.page.filter'].sudo()
        Dep = self.env['dashboard.filter.dependency'].sudo()
        Widget = self.env['dashboard.widget'].sudo()
        Source = self.env['dashboard.schema.source'].sudo()

        page_meta = cfg.get('page', {})

        # ── Create page ────────────────────────────────────────────
        page = Page.create({
            'name': name_override or page_meta.get('name', self.name),
            'key': key_override or page_meta.get('key', re.sub(r'\W+', '_', self.name.lower())),
            'app_id': app_id,
            'nav_section_id': nav_section_id,
            'icon': page_meta.get('icon', ''),
            'portal_type': page_meta.get('portal_type', 'hha'),
            'subtitle': page_meta.get('subtitle', ''),
            'footnote': page_meta.get('footnote', ''),
            'help_text': page_meta.get('help_text', ''),
            'is_active': True,
        })
        _logger.info('Template %s: created page %s (id=%d)', self.name, page.name, page.id)

        # ── Create tabs (map old key → new ID) ─────────────────────
        tab_map = {}  # old_key → new_tab_id
        for t in cfg.get('tabs', []):
            tab = Tab.create({
                'page_id': page.id,
                'name': t['name'],
                'key': t['key'],
                'sequence': t.get('sequence', 10),
                'is_active': t.get('is_active', True),
            })
            tab_map[t['key']] = tab.id

        # ── Create filters (map param_name → new filter ID) ───────
        filter_map = {}  # param_name → new_filter_id
        for i, f in enumerate(cfg.get('filters', [])):
            fvals = {
                'page_id': page.id,
                'param_name': f.get('param_name', ''),
                'label': f.get('label', ''),
                'sequence': f.get('sequence', 10),
                'is_active': f.get('is_active', True),
                'is_required': f.get('is_required', False),
                'is_multiselect': f.get('is_multiselect', False),
                'is_searchable': f.get('is_searchable', False),
                'is_visible': f.get('is_visible', True),
                'include_all_option': f.get('include_all_option', False),
                'hide_all_option': f.get('hide_all_option', False),
                'scope_to_user_hha': f.get('scope_to_user_hha', False),
                'auto_fill_from_hha': f.get('auto_fill_from_hha', False),
                'is_provider_selector': f.get('is_provider_selector', False),
                'default_value': f.get('default_value', ''),
                'default_strategy': f.get('default_strategy', 'static'),
                'placeholder': f.get('placeholder', ''),
                'display_template': f.get('display_template', ''),
                'manual_options': f.get('manual_options', ''),
                # D1/D2: placement + apply behavior + remote-search config.
                'ui_type': f.get('ui_type', 'default'),
                'apply_behavior': f.get('apply_behavior', 'manual'),
                'search_page_size': f.get('search_page_size') or 50,
                'search_min_chars': f.get('search_min_chars', 2),
                'control_width_px': f.get('control_width_px') or 0,
            }
            # display_region is nullable → set only when present (else the model
            # default_get normalizes to 'filter_bar'). Same for the two optional
            # template/source-source selectors.
            if f.get('display_region'):
                fvals['display_region'] = f['display_region']
            if f.get('display_template_source'):
                fvals['display_template_source'] = f['display_template_source']
            if f.get('option_sort'):
                fvals['option_sort'] = f['option_sort']
            # Remote Search always resolves labels via the schema template path
            # and is single-select (mirrors _onchange_ui_type_remote, which does
            # not fire on programmatic create) — guarantees the model constraint
            # passes even for a hand-edited template.
            if fvals['ui_type'] == 'remote_autocomplete':
                fvals['display_template_source'] = 'schema'
                fvals['is_multiselect'] = False
            # Schema source + columns — resolved AND validated in preflight, so
            # this binds by connector identity (never an arbitrary table match).
            r = filter_resolutions.get(i, {})
            if r.get('source_id'):
                fvals['schema_source_id'] = r['source_id']
            if r.get('column_id'):
                fvals['schema_column_id'] = r['column_id']
            if r.get('search_column_ids'):
                fvals['search_column_ids'] = [(6, 0, r['search_column_ids'])]
            if r.get('hha_scope_column_id'):
                fvals['hha_scope_column_id'] = r['hha_scope_column_id']
            # Resolve ORM model by name
            model_name = f.get('model_name', '')
            if model_name:
                model = self.env['ir.model'].sudo().search(
                    [('model', '=', model_name)], limit=1)
                if model:
                    fvals['model_id'] = model.id
                    field_name = f.get('field_name', '')
                    if field_name:
                        fld = self.env['ir.model.fields'].sudo().search(
                            [('model_id', '=', model.id), ('name', '=', field_name)], limit=1)
                        if fld:
                            fvals['field_id'] = fld.id

            new_filter = Filter.create(fvals)
            param = f.get('param_name') or f.get('field_name') or ''
            if param:
                filter_map[param] = new_filter.id

        # ── Create filter dependencies ─────────────────────────────
        for dep in cfg.get('filter_dependencies', []):
            src_param = dep.get('source_param', '')
            tgt_param = dep.get('target_param', '')
            src_id = filter_map.get(src_param)
            tgt_id = filter_map.get(tgt_param)
            if src_id and tgt_id:
                Dep.create({
                    'page_id': page.id,
                    'source_filter_id': src_id,
                    'target_filter_id': tgt_id,
                    'resets_target': dep.get('resets_target', True),
                    'propagation': dep.get('propagation', 'required'),
                    'sequence': dep.get('sequence', 10),
                })

        # ── Create widgets ─────────────────────────────────────────
        for w in cfg.get('widgets', []):
            wvals = {
                'page_id': page.id,
                'name': w.get('name', 'Widget'),
                'chart_type': w.get('chart_type', 'bar'),
                'sequence': w.get('sequence', 10),
                'is_active': w.get('is_active', True),
                'col_span': w.get('col_span', '6'),
                'row_span': w.get('row_span', 1),
                'width_pct': w.get('width_pct', 0),
                'max_width_pct': w.get('max_width_pct', 0),
                'chart_height': w.get('chart_height', 350),
                'display_mode': w.get('display_mode', 'standard'),
                'kpi_layout': w.get('kpi_layout', 'vertical'),
                'text_align': w.get('text_align', 'center'),
                'color_palette': w.get('color_palette', 'healthcare'),
                'color_custom_json': w.get('color_custom_json', ''),
                'icon_name': w.get('icon_name', 'none'),
                'icon_color': w.get('icon_color', 'default'),
                'icon_custom_color': w.get('icon_custom_color', ''),
                'icon_custom_bg': w.get('icon_custom_bg', ''),
                'metric_direction': w.get('metric_direction', 'higher_better'),
                'label_font_weight': w.get('label_font_weight', 'normal'),
                'value_font_weight': w.get('value_font_weight', 'bold'),
                'label_color': w.get('label_color', 'default'),
                'value_color': w.get('value_color', 'default'),
                'card_label_style': w.get('card_label_style', 'plain'),
                'card_label_badge_bg': w.get('card_label_badge_bg', ''),
                'card_label_badge_text': w.get('card_label_badge_text', ''),
                'query_type': w.get('query_type', 'sql'),
                'query_sql': w.get('query_sql', ''),
                'x_column': w.get('x_column', ''),
                'y_columns': w.get('y_columns', ''),
                'series_column': w.get('series_column', ''),
                'where_clause_exclude': w.get('where_clause_exclude', ''),
                'kpi_format': w.get('kpi_format', 'number'),
                'kpi_prefix': w.get('kpi_prefix', ''),
                'kpi_suffix': w.get('kpi_suffix', ''),
                'status_column': w.get('status_column', ''),
                'gauge_min': w.get('gauge_min', 0),
                'gauge_max': w.get('gauge_max', 100),
                'gauge_color_mode': w.get('gauge_color_mode', 'traffic_light'),
                'gauge_warn_threshold': w.get('gauge_warn_threshold', 50),
                'gauge_good_threshold': w.get('gauge_good_threshold', 70),
                'visual_config': w.get('visual_config', ''),
                'echart_override': w.get('echart_override', ''),
                'builder_config': w.get('builder_config', ''),
                'table_column_config': w.get('table_column_config', ''),
                'detail_drawer_config': w.get('detail_drawer_config', ''),
                'column_link_config': w.get('column_link_config', ''),
                'bar_stack': w.get('bar_stack', False),
                'click_action': w.get('click_action', 'none'),
                'action_page_key': w.get('action_page_key', ''),
                'action_tab_key': w.get('action_tab_key', ''),
                'action_pass_value_as': w.get('action_pass_value_as', ''),
                'action_url_template': w.get('action_url_template', ''),
                'drill_detail_columns': w.get('drill_detail_columns', ''),
                'subtitle': w.get('subtitle', ''),
                'footnote': w.get('footnote', ''),
                'annotation_type': w.get('annotation_type', 'none'),
                'annotation_text': w.get('annotation_text', ''),
                'annotation_position': w.get('annotation_position', 'top_right'),
                'render_region': w.get('render_region', 'tab_content'),
            }
            # Resolve tab reference
            tab_key = w.get('tab_key', '')
            if tab_key and tab_key in tab_map:
                wvals['tab_id'] = tab_map[tab_key]
            # Resolve schema source
            table_name = w.get('schema_source_table', '')
            if table_name:
                source = Source.search([('table_name', '=', table_name)], limit=1)
                if source:
                    wvals['schema_source_id'] = source.id
            # Battle card fields
            for fld in ('you_column', 'them_column', 'label_column', 'win_threshold', 'competitor_name'):
                if fld in w:
                    wvals[fld] = w[fld]
            # Insight panel fields
            for fld in ('metric1_label', 'metric2_label', 'metric3_label', 'narrative_template'):
                if fld in w:
                    wvals[fld] = w[fld]
            # Gauge KPI fields
            for fld in ('gauge_sub_kpi_columns', 'gauge_sub_kpi_labels',
                        'gauge_sub_label_columns', 'gauge_alert_column'):
                if fld in w:
                    wvals[fld] = w[fld]
            # v5 widget configs — restore verbatim; the mixin constraint
            # re-validates on create (and _preflight_widgets already parsed
            # them before any record was written).
            for fld in ('attribute_grid_config', 'metric_list_config'):
                if fld in w:
                    wvals[fld] = w[fld]

            # Scope control fields
            for fld in ('scope_mode', 'scope_ui', 'scope_query_mode',
                        'scope_param_name', 'scope_label', 'scope_default_value',
                        'scope_value_column', 'scope_label_column',
                        'search_enabled', 'search_placeholder'):
                if fld in w:
                    wvals[fld] = w[fld]
            # Resolve scope_filter by param_name
            scope_fp = w.get('scope_filter_param', '')
            if scope_fp and filter_map.get(scope_fp):
                wvals['scope_filter_id'] = filter_map[scope_fp]
            # Resolve scope_schema_source
            scope_table = w.get('scope_schema_source_table', '')
            if scope_table:
                scope_src = Source.search([('table_name', '=', scope_table)], limit=1)
                if scope_src:
                    wvals['scope_schema_source_id'] = scope_src.id

            # Download fields — `if fld in w` keeps templates saved before
            # this feature restoring cleanly (keys absent → widget defaults).
            for fld in ('download_enabled', 'download_formats', 'download_sql',
                        'download_icon_position', 'download_icon_color',
                        'download_filename', 'download_row_limit'):
                if fld in w:
                    wvals[fld] = w[fld]
            # Resolve download schema source by table name
            dl_table = w.get('download_schema_source_table', '')
            if dl_table:
                dl_src = Source.search([('table_name', '=', dl_table)], limit=1)
                if dl_src:
                    wvals['download_schema_source_id'] = dl_src.id

            new_widget = Widget.create(wvals)

            # Create scope options (child records)
            ScopeOption = self.env['dashboard.widget.scope.option']
            for opt in w.get('scope_options', []):
                opt_vals = {
                    'widget_id': new_widget.id,
                    'label': opt.get('label', ''),
                    'value': opt.get('value', ''),
                    'icon': opt.get('icon', ''),
                    'color': opt.get('color', ''),
                    'icon_color': opt.get('icon_color', ''),
                    'sequence': opt.get('sequence', 10),
                    'query_sql': opt.get('query_sql', ''),
                    'where_clause_exclude': opt.get('where_clause_exclude', ''),
                    'table_column_config': opt.get('table_column_config', ''),
                    'x_column': opt.get('x_column', ''),
                    'y_columns': opt.get('y_columns', ''),
                    'series_column': opt.get('series_column', ''),
                    'click_action': opt.get('click_action', 'none'),
                    'action_page_key': opt.get('action_page_key', ''),
                    'action_tab_key': opt.get('action_tab_key', ''),
                    'action_pass_value_as': opt.get('action_pass_value_as', ''),
                    'drill_detail_columns': opt.get('drill_detail_columns', ''),
                    'action_url_template': opt.get('action_url_template', ''),
                    # Per-option geo metadata (map choropleth drill)
                    'default_geo_level': opt.get('default_geo_level', 'state') or 'state',
                    'allowed_geo_levels': opt.get('allowed_geo_levels', 'state') or 'state',
                    'supports_drill': bool(opt.get('supports_drill', False)),
                }
                opt_table = opt.get('schema_source_table', '')
                if opt_table:
                    opt_src = Source.search([('table_name', '=', opt_table)], limit=1)
                    if opt_src:
                        opt_vals['schema_source_id'] = opt_src.id
                ScopeOption.create(opt_vals)

            # Create composite items (child records for chart_type='composite')
            if w.get('chart_type') == 'composite' and w.get('composite_items'):
                CompositeItem = self.env['dashboard.widget.composite.item']
                for ci in w['composite_items']:
                    ci_vals = {
                        'parent_widget_id':     new_widget.id,
                        'sequence':             ci.get('sequence', 10),
                        'is_active':            ci.get('is_active', True),
                        'name':                 ci.get('name', ''),
                        'chart_type':           ci.get('chart_type', 'kpi'),
                        'data_mode':            ci.get('data_mode', 'inherit_parent'),
                        'query_sql':            ci.get('query_sql', ''),
                        'where_clause_exclude': ci.get('where_clause_exclude', ''),
                        'x_column':             ci.get('x_column', ''),
                        'y_columns':            ci.get('y_columns', ''),
                        'series_column':        ci.get('series_column', ''),
                        'status_column':        ci.get('status_column', ''),
                        'kpi_format':           ci.get('kpi_format', 'number'),
                        'kpi_prefix':           ci.get('kpi_prefix', ''),
                        'kpi_suffix':           ci.get('kpi_suffix', ''),
                        'kpi_layout':           ci.get('kpi_layout', 'vertical'),
                        'display_mode':         ci.get('display_mode', 'standard'),
                        'text_align':           ci.get('text_align', 'center'),
                        'metric_direction':     ci.get('metric_direction', 'higher_better'),
                        'icon_name':            ci.get('icon_name', 'none'),
                        'icon_position':        ci.get('icon_position', 'title'),
                        'title_icon_color':     ci.get('title_icon_color', 'default'),
                        'color_custom_json':    ci.get('color_custom_json', ''),
                        'visual_config':        ci.get('visual_config', '{}'),
                        'bar_stack':            ci.get('bar_stack', False),
                        'echart_override':      ci.get('echart_override', ''),
                        'gauge_min':            ci.get('gauge_min', 0),
                        'gauge_max':            ci.get('gauge_max', 100),
                        'gauge_color_mode':     ci.get('gauge_color_mode', 'traffic_light'),
                        'gauge_warn_threshold': ci.get('gauge_warn_threshold', 50),
                        'gauge_good_threshold': ci.get('gauge_good_threshold', 80),
                        'table_column_config':  ci.get('table_column_config', ''),
                        'column_link_config':   ci.get('column_link_config', ''),
                        'ranked_master_config': ci.get('ranked_master_config', ''),
                        'ranked_detail_config': ci.get('ranked_detail_config', ''),
                        'text_note_body':       ci.get('text_note_body', ''),
                        'col_start':            ci.get('col_start', 1),
                        'col_span':             ci.get('col_span', 12),
                        'row_start':            ci.get('row_start', 0),
                        'row_span':             ci.get('row_span', 1),
                        'min_height_px':        ci.get('min_height_px', 240),
                    }
                    ci_table = ci.get('schema_source_table', '')
                    if ci_table:
                        ci_src = Source.search([('table_name', '=', ci_table)], limit=1)
                        if ci_src:
                            ci_vals['schema_source_id'] = ci_src.id
                    CompositeItem.create(ci_vals)

        # ── Create sections ────────────────────────────────────────
        Section = self.env.get('dashboard.page.section')
        if Section:
            for s in cfg.get('sections', []):
                svals = {
                    'page_id': page.id,
                    'name': s.get('name', 'Section'),
                    'section_type': s.get('section_type', 'comparison_bar'),
                    'sequence': s.get('sequence', 10),
                    'is_active': s.get('is_active', True),
                    'icon': s.get('icon', ''),
                    'action_label': s.get('action_label', ''),
                    'max_rows': s.get('max_rows', 0),
                    'subtitle': s.get('subtitle', ''),
                    'description': s.get('description', ''),
                    'footnote': s.get('footnote', ''),
                    'query_sql': s.get('query_sql', ''),
                    'where_clause_exclude': s.get('where_clause_exclude', ''),
                    'scope_mode': s.get('scope_mode', 'none'),
                    'scope_param_name': s.get('scope_param_name', ''),
                    'scope_label': s.get('scope_label', ''),
                    'scope_default_value': s.get('scope_default_value', ''),
                    'scope_value_column': s.get('scope_value_column', ''),
                    'scope_label_column': s.get('scope_label_column', ''),
                    'cb_label_col': s.get('cb_label_col', ''),
                    'cb_value_col': s.get('cb_value_col', ''),
                    'cb_status_col': s.get('cb_status_col', ''),
                    'cb_desc_col': s.get('cb_desc_col', ''),
                    'cb_sublabel_col': s.get('cb_sublabel_col', ''),
                    'lt_rank_col': s.get('lt_rank_col', ''),
                    'lt_name_col': s.get('lt_name_col', ''),
                    'lt_sub_name_cols': s.get('lt_sub_name_cols', ''),
                    'lt_display_cols': s.get('lt_display_cols', ''),
                    'lt_display_labels': s.get('lt_display_labels', ''),
                    'lt_you_col': s.get('lt_you_col', ''),
                    'lt_color_col': s.get('lt_color_col', ''),
                    'lt_good_threshold': s.get('lt_good_threshold', 70),
                    'lt_warn_threshold': s.get('lt_warn_threshold', 50),
                }
                # Resolve tab reference
                tab_key = s.get('tab_key', '')
                if tab_key and tab_key in tab_map:
                    svals['tab_id'] = tab_map[tab_key]
                # Resolve schema source
                table_name = s.get('schema_source_table', '')
                if table_name:
                    source = Source.search([('table_name', '=', table_name)], limit=1)
                    if source:
                        svals['schema_source_id'] = source.id
                # Resolve scope schema source
                scope_table = s.get('scope_schema_source_table', '')
                if scope_table:
                    scope_source = Source.search([('table_name', '=', scope_table)], limit=1)
                    if scope_source:
                        svals['scope_schema_source_id'] = scope_source.id

                Section.sudo().create(svals)

        # ── Badges ──
        Badge = self.env['dashboard.page.badge']
        for bdata in cfg.get('badges', []):
            bvals = {
                'page_id': page.id,
                'name': bdata.get('name', 'Badge'),
                'icon': bdata.get('icon', ''),
                'sequence': bdata.get('sequence', 10),
                'is_active': bdata.get('is_active', True),
                'query_sql': bdata.get('query_sql', ''),
                'where_clause_exclude': bdata.get('where_clause_exclude', ''),
                'font_size': bdata.get('font_size', 0),
                'text_color': bdata.get('text_color', ''),
                'icon_color': bdata.get('icon_color', ''),
                'is_link': bdata.get('is_link', False),
            }
            table_name = bdata.get('schema_source_table', '')
            if table_name:
                source = Source.search([('table_name', '=', table_name)], limit=1)
                if source:
                    bvals['schema_source_id'] = source.id
            Badge.sudo().create(bvals)

        widget_count = len(cfg.get('widgets', []))
        badge_count = len(cfg.get('badges', []))
        _logger.info(
            'Template %s: created %d tabs, %d filters, %d deps, %d widgets, %d sections, %d badges on page %s',
            self.name, len(cfg.get('tabs', [])), len(cfg.get('filters', [])),
            len(cfg.get('filter_dependencies', [])), widget_count,
            len(cfg.get('sections', [])), badge_count, page.name,
        )
        return page


class DashboardPageTemplateWizard(models.TransientModel):
    """Wizard for applying a page template to create a new page."""
    _name = 'dashboard.page.template.wizard'
    _description = 'Use Page Template Wizard'

    template_id = fields.Many2one('dashboard.page.template', required=True, string='Template')
    app_id = fields.Many2one('saas.app', required=True, string='Target App')
    nav_section_id = fields.Many2one('dashboard.nav.section', required=True, string='Nav Section')
    page_name = fields.Char(string='Page Name', help='Leave empty to use template name.')
    page_key = fields.Char(string='Page Key', help='Leave empty to auto-generate from name.')

    def action_apply(self):
        """Apply the template and open the created page."""
        self.ensure_one()
        page = self.template_id.create_page_from_template(
            app_id=self.app_id.id,
            nav_section_id=self.nav_section_id.id,
            name_override=self.page_name or None,
            key_override=self.page_key or None,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': page.name,
            'res_model': 'dashboard.page',
            'res_id': page.id,
            'view_mode': 'form',
        }
