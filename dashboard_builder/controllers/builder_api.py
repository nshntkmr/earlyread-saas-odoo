# -*- coding: utf-8 -*-
"""
Phase WB-4 — Builder REST API
==============================
JWT-authenticated endpoints for the Widget Builder.

Auth helpers are imported from posterra_portal.controllers.auth_api:
  _verify_token, _json_response, _json_error, _get_request_json

All admin-only endpoints require the user to be an internal user (not portal).
The drill endpoint is accessible to any authenticated user.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


# ── JSON helpers — local to dashboard_builder ────────────────────────────────
from .utils import _json_response, _json_error, _get_request_json


def _get_verify_token():
    """Lazy import JWT verifier from posterra_portal (only dependency)."""
    from odoo.addons.posterra_portal.controllers.auth_api import _verify_token
    return _verify_token


def _auth_admin():
    """Extract JWT, verify, return user. Raises ValueError if not admin."""
    _verify_token = _get_verify_token()

    auth_header = request.httprequest.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise ValueError('Missing or invalid Authorization header')
    token = auth_header[7:].strip()
    payload = _verify_token(token)
    if payload.get('type') != 'access':
        raise ValueError('Expected an access token')

    user = request.env['res.users'].sudo().browse(payload['user_id'])
    if not user.exists():
        raise ValueError('Token references a nonexistent user')

    # Admin check: must be internal user (not portal)
    if not user.has_group('base.group_user'):
        raise ValueError('Admin access required')

    return user


def _auth_any():
    """Extract JWT, verify, return user (any role)."""
    _verify_token = _get_verify_token()

    auth_header = request.httprequest.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise ValueError('Missing or invalid Authorization header')
    token = auth_header[7:].strip()
    payload = _verify_token(token)
    if payload.get('type') != 'access':
        raise ValueError('Expected an access token')

    user = request.env['res.users'].sudo().browse(payload['user_id'])
    if not user.exists():
        raise ValueError('Token references a nonexistent user')

    return user


def _json_resp(data, status=200):
    """JSON response wrapper — uses local utils."""
    return _json_response(data, status)


def _json_err(status, message):
    """JSON error wrapper — uses local utils."""
    return _json_error(status, message)


def _get_body():
    """Parse JSON body from request."""
    return _get_request_json()


# ═══════════════════════════════════════════════════════════════════════════════
# BUILDER API CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════════

class BuilderAPI(http.Controller):

    # ─────────────────────────────────────────────────────────────────────────
    # CORS preflight for all /api/v1/builder/* routes
    # ─────────────────────────────────────────────────────────────────────────
    @http.route(
        '/api/v1/builder/<path:subpath>',
        type='http', auth='none', methods=['OPTIONS'], csrf=False,
    )
    def builder_options(self, subpath=None, **kw):
        return request.make_response(
            '', headers=[
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
                ('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS'),
                ('Access-Control-Max-Age', '86400'),
            ])

    # =========================================================================
    # SCHEMA ENDPOINTS
    # =========================================================================

    @http.route(
        '/api/v1/builder/sources',
        type='http', auth='none', methods=['GET'], csrf=False, readonly=True,
    )
    def get_sources(self, **kw):
        """GET /api/v1/builder/sources → list of schema sources."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        sources = request.env['dashboard.schema.source'].sudo().search(
            [('is_active', '=', True)], order='name asc')

        data = [{
            'id': s.id,
            'name': s.name,
            'table_name': s.table_name,
            'alias': s.table_alias or '',
            'column_count': s.column_count,
            'description': s.description or '',
        } for s in sources]

        return _json_resp(data)

    @http.route(
        '/api/v1/builder/sources/<int:source_id>',
        type='http', auth='none', methods=['GET'], csrf=False, readonly=True,
    )
    def get_source_detail(self, source_id, **kw):
        """GET /api/v1/builder/sources/<id> → source with columns."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        src = request.env['dashboard.schema.source'].sudo().browse(source_id)
        if not src.exists():
            return _json_err(404, 'Schema source not found')

        data = {
            'id': src.id,
            'name': src.name,
            'table_name': src.table_name,
            'alias': src.table_alias or '',
            'columns': [{
                'id': c.id,
                'column_name': c.column_name,
                'display_name': c.display_name,
                'data_type': c.data_type,
                'is_measure': c.is_measure,
                'is_dimension': c.is_dimension,
                'is_filterable': c.is_filterable,
            } for c in src.column_ids],
        }

        return _json_resp(data)

    @http.route(
        '/api/v1/builder/sources/<int:source_id>/relations',
        type='http', auth='none', methods=['GET'], csrf=False, readonly=True,
    )
    def get_source_relations(self, source_id, **kw):
        """GET /api/v1/builder/sources/<id>/relations → outgoing relations."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        src = request.env['dashboard.schema.source'].sudo().browse(source_id)
        if not src.exists():
            return _json_err(404, 'Schema source not found')

        data = [{
            'id': r.id,
            'name': r.name or '',
            'target': {
                'id': r.target_source_id.id,
                'name': r.target_source_id.name,
                'table_name': r.target_source_id.table_name,
                'alias': r.target_source_id.table_alias or '',
            },
            'join_type': r.join_type,
            'source_column': r.source_column,
            'target_column': r.target_column,
        } for r in src.relation_ids]

        return _json_resp(data)

    # =========================================================================
    # WIDGET BUILDER ENDPOINTS
    # =========================================================================

    @http.route(
        '/api/v1/builder/preview',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def builder_preview(self, **kw):
        """POST /api/v1/builder/preview → execute query and return data."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        body = _get_body()
        mode = body.get('mode', 'visual')

        try:
            from ..services.query_builder import QueryBuilder
            qb = QueryBuilder(request.env)

            if mode == 'custom_sql':
                sql = body.get('sql', '')
                is_valid, err = qb.validate_query(sql)
                if not is_valid:
                    return _json_err(400, f'Invalid SQL: {err}')
                columns, rows = qb.execute_preview(sql, body.get('params', {}))
            else:
                config = body.get('config', {})
                sql = qb.build_select_query(config)
                columns, rows = qb.execute_preview(sql, body.get('params', {}))

            # Convert rows to list of lists for JSON
            rows_list = [list(row) for row in rows]

            # Format preview data based on widget type
            from ..services.preview_formatter import format_preview
            chart_type = body.get('chart_type', 'table')
            widget_config = body.get('widget_config', {})
            formatted = format_preview(chart_type, columns, rows_list, widget_config)

            return _json_resp({
                'sql': sql,
                'columns': columns,
                'rows': rows_list,
                **formatted,
            })

        except ValueError as e:
            return _json_err(400, str(e))
        except Exception as e:
            _logger.exception("Builder preview error")
            return _json_err(500, f'Preview failed: {e}')

    @http.route(
        '/api/v1/builder/create',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def builder_create(self, **kw):
        """POST /api/v1/builder/create → create widget definition + instance."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        body = _get_body()

        try:
            mode = body.get('mode', 'visual')
            name = body.get('name', 'New Widget')
            chart_type = body.get('chart_type', 'bar')
            page_id = body.get('page_id')
            tab_id = body.get('tab_id')

            # Build widget definition
            def_vals = {
                'name': name,
                'chart_type': chart_type,
                'data_mode': 'custom_sql' if mode == 'custom_sql' else 'visual',
                'category': body.get('category', 'chart'),
                'default_col_span': str(body.get('col_span', 6)),
                'chart_height': body.get('chart_height', 350),
                'color_palette': body.get('color_palette', 'healthcare'),
                'color_custom_json': body.get('color_custom_json', ''),
                'click_action': body.get('click_action', 'none'),
                'action_page_key': body.get('action_page_key', ''),
                'action_tab_key': body.get('action_tab_key', ''),
                'action_pass_value_as': body.get('action_pass_value_as', ''),
                'drill_detail_columns': body.get('drill_detail_columns', ''),
                'action_url_template': body.get('action_url_template', ''),
                'column_link_config': body.get('column_link_config', ''),
                # Widget-Scoped Controls
                'scope_mode': body.get('scope_mode', 'none'),
                'scope_ui': body.get('scope_ui', 'dropdown'),
                'scope_query_mode': body.get('scope_query_mode', 'parameter'),
                'scope_param_name': body.get('scope_param_name', ''),
                'scope_label': body.get('scope_label', ''),
                'scope_default_value': body.get('scope_default_value', ''),
                'search_enabled': body.get('search_enabled', False),
                'search_placeholder': body.get('search_placeholder', 'Search...'),
            }

            if mode == 'custom_sql':
                def_vals.update({
                    'query_sql': body.get('sql', ''),
                    'x_column': body.get('x_column', ''),
                    'y_columns': body.get('y_columns', ''),
                    'series_column': body.get('series_column', ''),
                })
            else:
                config = body.get('config', {})
                def_vals['builder_config'] = json.dumps(config)

                # Generate SQL from config
                from ..services.query_builder import QueryBuilder
                qb = QueryBuilder(request.env)
                def_vals['generated_sql'] = qb.build_select_query(config)

            # KPI fields
            if chart_type in ('kpi', 'status_kpi'):
                def_vals.update({
                    'kpi_format': body.get('kpi_format', 'number'),
                    'kpi_prefix': body.get('kpi_prefix', ''),
                    'kpi_suffix': body.get('kpi_suffix', ''),
                })

            # Gauge fields
            if chart_type in ('gauge', 'gauge_kpi'):
                def_vals.update({
                    'gauge_min': body.get('gauge_min', 0),
                    'gauge_max': body.get('gauge_max', 100),
                    'gauge_color_mode': body.get('gauge_color_mode', 'single'),
                })

            # ECharts override
            if body.get('echart_override'):
                def_vals['echart_override'] = body['echart_override']

            # Create definition
            definition = request.env['dashboard.widget.definition'].sudo().create(def_vals)

            result = {'definition_id': definition.id, 'name': definition.name}

            # If page_id provided, also create widget instance on that page
            if page_id:
                widget_vals = _build_widget_vals_from_definition(definition, body)
                widget_vals['page_id'] = page_id
                if tab_id:
                    widget_vals['tab_id'] = tab_id

                widget = request.env['dashboard.widget'].sudo().create(widget_vals)
                result['widget_id'] = widget.id

                # Create scope option child records (from builder payload)
                scope_options = body.get('scope_options', [])
                if scope_options:
                    ScopeOption = request.env['dashboard.widget.scope.option']
                    Source = request.env['dashboard.schema.source']
                    for opt in scope_options:
                        opt_vals = {
                            'widget_id': widget.id,
                            'label': opt.get('label', ''),
                            'value': opt.get('value', ''),
                            'icon': opt.get('icon', ''),
                            'sequence': opt.get('sequence', 10),
                            'query_sql': opt.get('query_sql', ''),
                            'table_column_config': opt.get('table_column_config', ''),
                            'x_column': opt.get('x_column', ''),
                            'y_columns': opt.get('y_columns', ''),
                            'series_column': opt.get('series_column', ''),
                            # Per-option click actions
                            'click_action': opt.get('click_action', 'none'),
                            'action_page_key': opt.get('action_page_key', ''),
                            'action_tab_key': opt.get('action_tab_key', ''),
                            'action_pass_value_as': opt.get('action_pass_value_as', ''),
                            'drill_detail_columns': opt.get('drill_detail_columns', ''),
                            'action_url_template': opt.get('action_url_template', ''),
                        }
                        table_name = opt.get('schema_source_table', '')
                        if table_name:
                            src = Source.search(
                                [('table_name', '=', table_name)], limit=1)
                            if src:
                                opt_vals['schema_source_id'] = src.id
                        ScopeOption.sudo().create(opt_vals)

            return _json_resp(result)

        except ValueError as e:
            return _json_err(400, str(e))
        except Exception as e:
            _logger.exception("Builder create error")
            return _json_err(500, f'Create failed: {e}')

    @http.route(
        '/api/v1/builder/widget/<int:widget_id>',
        type='http', auth='none', methods=['PUT'], csrf=False,
    )
    def builder_update(self, widget_id, **kw):
        """PUT /api/v1/builder/widget/<id> → update widget."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        widget = request.env['dashboard.widget'].sudo().browse(widget_id)
        if not widget.exists():
            return _json_err(404, 'Widget not found')

        body = _get_body()
        update_vals = {}

        # Direct field updates
        field_map = {
            'name': 'name', 'chart_type': 'chart_type',
            'chart_height': 'chart_height', 'color_palette': 'color_palette',
            'color_custom_json': 'color_custom_json',
            'click_action': 'click_action', 'action_page_key': 'action_page_key',
            'action_tab_key': 'action_tab_key',
            'action_pass_value_as': 'action_pass_value_as',
            'drill_detail_columns': 'drill_detail_columns',
            'action_url_template': 'action_url_template',
            'column_link_config': 'column_link_config',
            'echart_override': 'echart_override',
            # Widget-Scoped Controls
            'scope_mode': 'scope_mode', 'scope_ui': 'scope_ui',
            'scope_query_mode': 'scope_query_mode',
            'scope_param_name': 'scope_param_name',
            'scope_label': 'scope_label',
            'scope_default_value': 'scope_default_value',
            'search_enabled': 'search_enabled',
            'search_placeholder': 'search_placeholder',
        }
        for body_key, field_name in field_map.items():
            if body_key in body:
                update_vals[field_name] = body[body_key]

        if 'col_span' in body:
            update_vals['col_span'] = str(body['col_span'])

        # SQL fields
        if 'sql' in body:
            update_vals['query_sql'] = body['sql']
        for key in ('x_column', 'y_columns', 'series_column'):
            if key in body:
                update_vals[key] = body[key]

        # Builder config → regenerate SQL
        if 'config' in body:
            config = body['config']
            update_vals['builder_config'] = json.dumps(config)
            from ..services.query_builder import QueryBuilder
            qb = QueryBuilder(request.env)
            # Also update the definition if linked
            if widget.definition_id:
                widget.definition_id.sudo().write({
                    'builder_config': json.dumps(config),
                    'generated_sql': qb.build_select_query(config),
                })

        # Sync scope fields to definition (so Edit/GET returns current values)
        if widget.definition_id:
            scope_sync = {}
            for fld in ('scope_mode', 'scope_ui', 'scope_query_mode',
                        'scope_param_name', 'scope_label', 'scope_default_value',
                        'search_enabled', 'search_placeholder'):
                if fld in body:
                    scope_sync[fld] = body[fld]
            if scope_sync:
                widget.definition_id.sudo().write(scope_sync)

        try:
            widget.write(update_vals)

            # Recreate scope_option child records (only when scope_options key present)
            if 'scope_options' in body:
                widget.scope_option_ids.unlink()  # Delete old options
                scope_options = body.get('scope_options') or []
                if scope_options:
                    ScopeOption = request.env['dashboard.widget.scope.option']
                    Source = request.env['dashboard.schema.source']
                    for opt in scope_options:
                        opt_vals = {
                            'widget_id': widget.id,
                            'label': opt.get('label', ''),
                            'value': opt.get('value', ''),
                            'icon': opt.get('icon', ''),
                            'sequence': opt.get('sequence', 10),
                            'query_sql': opt.get('query_sql', ''),
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
                        }
                        table_name = opt.get('schema_source_table', '')
                        if table_name:
                            src = Source.search(
                                [('table_name', '=', table_name)], limit=1)
                            if src:
                                opt_vals['schema_source_id'] = src.id
                        ScopeOption.sudo().create(opt_vals)

            return _json_resp({'widget_id': widget.id, 'name': widget.name})
        except Exception as e:
            _logger.exception("Builder update error")
            return _json_err(500, f'Update failed: {e}')

    @http.route(
        '/api/v1/builder/widget/<int:widget_id>/drill',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def builder_drill(self, widget_id, **kw):
        """POST /api/v1/builder/widget/<id>/drill → drill-down query."""
        try:
            _auth_any()
        except ValueError as e:
            return _json_err(403, str(e))

        widget = request.env['dashboard.widget'].sudo().browse(widget_id)
        if not widget.exists():
            return _json_err(404, 'Widget not found')

        body = _get_body()
        click_column = body.get('click_column', '')
        click_value = body.get('click_value', '')
        detail_cols = body.get('detail_columns')

        if not click_column:
            return _json_err(400, 'click_column is required')

        try:
            from ..services.query_builder import QueryBuilder
            qb = QueryBuilder(request.env)

            # Use definition's builder_config if available, else widget's
            target = widget.definition_id if widget.definition_id else widget
            detail_list = None
            if detail_cols:
                detail_list = [c.strip() for c in detail_cols.split(',') if c.strip()]
            elif widget.drill_detail_columns:
                detail_list = [c.strip() for c in widget.drill_detail_columns.split(',') if c.strip()]

            sql = qb.build_drill_query(target, click_column, detail_list)

            # Build params: click_value + any filter params from body
            params = {k: v for k, v in body.items()
                      if k not in ('click_column', 'click_value', 'detail_columns')}
            params['click_value'] = click_value

            columns, rows = qb.execute_preview(sql, params, limit=50)
            rows_list = [list(row) for row in rows]

            return _json_resp({
                'columns': columns,
                'rows': rows_list,
            })

        except ValueError as e:
            return _json_err(400, str(e))
        except Exception as e:
            _logger.exception("Drill-down error")
            return _json_err(500, f'Drill-down failed: {e}')

    # =========================================================================
    # NAVIGATION ENDPOINTS
    # =========================================================================

    @http.route(
        '/api/v1/builder/pages',
        type='http', auth='none', methods=['GET'], csrf=False, readonly=True,
    )
    def get_pages(self, **kw):
        """GET /api/v1/builder/pages → page list for dropdowns."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        try:
            pages = request.env['dashboard.page'].sudo().search(
                [('is_active', '=', True)], order='name asc')

            data = []
            for p in pages:
                filters = request.env['dashboard.page.filter'].sudo().search(
                    [('page_id', '=', p.id), ('is_active', '=', True)],
                    order='sequence asc',
                )
                data.append({
                    'id': p.id,
                    'key': p.page_key,
                    'name': p.name,
                    'filters': [{
                        'field_name': f.field_name or f.param_name or '',
                        'label': f.label or f.field_name or '',
                    } for f in filters],
                })

            return _json_resp(data)
        except Exception as e:
            _logger.exception("Get pages error")
            return _json_err(500, str(e))

    # =========================================================================
    # WIDGET LIBRARY ENDPOINTS
    # =========================================================================

    @http.route(
        '/api/v1/builder/library',
        type='http', auth='none', methods=['GET'], csrf=False, readonly=True,
    )
    def get_library(self, **kw):
        """GET /api/v1/builder/library → list of widget definitions."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        domain = [('is_active', '=', True)]
        if kw.get('category'):
            domain.append(('category', '=', kw['category']))

        defs = request.env['dashboard.widget.definition'].sudo().search(
            domain, order='category, name')

        data = [{
            'id': d.id,
            'name': d.name,
            'description': d.description or '',
            'category': d.category,
            'chart_type': d.chart_type,
            'instance_count': d.instance_count,
            'data_mode': d.data_mode,
        } for d in defs]

        return _json_resp(data)

    @http.route(
        '/api/v1/builder/library/<int:def_id>',
        type='http', auth='none', methods=['GET'], csrf=False, readonly=True,
    )
    def get_library_detail(self, def_id, **kw):
        """GET /api/v1/builder/library/<id> → full definition detail."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        defn = request.env['dashboard.widget.definition'].sudo().browse(def_id)
        if not defn.exists():
            return _json_err(404, 'Widget definition not found')

        data = {
            'id': defn.id,
            'name': defn.name,
            'description': defn.description or '',
            'category': defn.category,
            'chart_type': defn.chart_type,
            'data_mode': defn.data_mode,
            'builder_config': defn.builder_config or '',
            'query_sql': defn.query_sql or '',
            'generated_sql': defn.generated_sql or '',
            'x_column': defn.x_column or '',
            'y_columns': defn.y_columns or '',
            'series_column': defn.series_column or '',
            'default_col_span': defn.default_col_span,
            'chart_height': defn.chart_height,
            'color_palette': defn.color_palette,
            'color_custom_json': defn.color_custom_json or '',
            'click_action': defn.click_action,
            'action_page_key': defn.action_page_key or '',
            'action_tab_key': defn.action_tab_key or '',
            'action_pass_value_as': defn.action_pass_value_as or '',
            'drill_detail_columns': defn.drill_detail_columns or '',
            'action_url_template': defn.action_url_template or '',
            'column_link_config': defn.column_link_config or '',
            'kpi_format': defn.kpi_format,
            'kpi_prefix': defn.kpi_prefix or '',
            'kpi_suffix': defn.kpi_suffix or '',
            'gauge_min': defn.gauge_min,
            'gauge_max': defn.gauge_max,
            'gauge_color_mode': defn.gauge_color_mode,
            'echart_override': defn.echart_override or '',
            'instance_count': defn.instance_count,
            # Widget-Scoped Controls
            'scope_mode': defn.scope_mode or 'none',
            'scope_ui': defn.scope_ui or 'dropdown',
            'scope_query_mode': defn.scope_query_mode or 'parameter',
            'scope_param_name': defn.scope_param_name or '',
            'scope_label': defn.scope_label or '',
            'scope_default_value': defn.scope_default_value or '',
            'search_enabled': defn.search_enabled or False,
            'search_placeholder': defn.search_placeholder or 'Search...',
            'visual_config': defn.visual_config or '',
            'default_width_pct': defn.default_width_pct or 0,
            'default_row_span': defn.default_row_span or 1,
            'bar_stack': defn.bar_stack or False,
            'table_column_config': '',
        }

        # Include scope options from the first widget instance (if any)
        scope_options = []
        try:
            Widget = request.env['dashboard.widget']
            instances = Widget.sudo().search(
                [('definition_id', '=', defn.id)], limit=1)
            if instances:
                for o in instances[0].scope_option_ids.sorted('sequence'):
                    scope_options.append({
                        'label': o.label or '',
                        'value': o.value or '',
                        'icon': o.icon or '',
                        'sequence': o.sequence,
                        'query_sql': o.query_sql or '',
                        'schema_source_table': (
                            o.schema_source_id.table_name
                            if o.schema_source_id else ''),
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
                    })
                # Also get table_column_config from instance
                if instances[0].table_column_config:
                    data['table_column_config'] = instances[0].table_column_config
        except Exception:
            pass  # dashboard.widget may not exist
        data['scope_options'] = scope_options

        return _json_resp(data)

    @http.route(
        '/api/v1/builder/library/<int:def_id>/place',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def place_from_library(self, def_id, **kw):
        """POST /api/v1/builder/library/<id>/place → create widget instance."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        defn = request.env['dashboard.widget.definition'].sudo().browse(def_id)
        if not defn.exists():
            return _json_err(404, 'Widget definition not found')

        body = _get_body()
        page_id = body.get('page_id')

        # Support page_key + tab_key (from portal LibraryPicker)
        if not page_id and body.get('page_key'):
            Page = request.env['dashboard.page'].sudo()
            page = Page.search([('key', '=', body['page_key'])], limit=1)
            if page:
                page_id = page.id

        if not page_id:
            return _json_err(400, 'page_id or page_key is required')

        # Resolve tab_key → tab_id if needed
        tab_id = body.get('tab_id')
        if not tab_id and body.get('tab_key') and page_id:
            Tab = request.env['dashboard.page.tab'].sudo()
            tab = Tab.search([
                ('page_id', '=', page_id),
                ('key', '=', body['tab_key']),
            ], limit=1)
            if tab:
                tab_id = tab.id

        try:
            widget_vals = _build_widget_vals_from_definition(defn, body)
            widget_vals['page_id'] = page_id
            if tab_id:
                widget_vals['tab_id'] = tab_id

            widget = request.env['dashboard.widget'].sudo().create(widget_vals)

            # Create scope_option child records (forwarded from React)
            scope_options = body.get('scope_options', [])
            if scope_options:
                ScopeOption = request.env['dashboard.widget.scope.option']
                Source = request.env['dashboard.schema.source']
                for opt in scope_options:
                    opt_vals = {
                        'widget_id': widget.id,
                        'label': opt.get('label', ''),
                        'value': opt.get('value', ''),
                        'icon': opt.get('icon', ''),
                        'sequence': opt.get('sequence', 10),
                        'query_sql': opt.get('query_sql', ''),
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
                    }
                    table_name = opt.get('schema_source_table', '')
                    if table_name:
                        src = Source.search(
                            [('table_name', '=', table_name)], limit=1)
                        if src:
                            opt_vals['schema_source_id'] = src.id
                    ScopeOption.sudo().create(opt_vals)

            return _json_resp({'widget_id': widget.id, 'name': widget.name})

        except Exception as e:
            _logger.exception("Place from library error")
            return _json_err(500, f'Place failed: {e}')

    # =========================================================================
    # REORDER ENDPOINT
    # =========================================================================

    @http.route(
        '/api/v1/builder/reorder',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def reorder_widgets(self, **kw):
        """POST /api/v1/builder/reorder → update widget sequence."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        body = _get_body()
        widget_ids = body.get('widget_ids', [])

        if not widget_ids or not isinstance(widget_ids, list):
            return _json_err(400, 'widget_ids must be a non-empty list')

        try:
            Widget = request.env['dashboard.widget'].sudo()
            for seq, wid in enumerate(widget_ids, start=1):
                w = Widget.browse(wid)
                if w.exists():
                    w.write({'sequence': seq * 10})

            return _json_resp({'ok': True})
        except Exception as e:
            _logger.exception("Reorder error")
            return _json_err(500, f'Reorder failed: {e}')

    # =========================================================================
    # TEMPLATE ENDPOINTS
    # =========================================================================

    @http.route(
        '/api/v1/builder/templates',
        type='http', auth='none', methods=['GET'], csrf=False, readonly=True,
    )
    def get_templates(self, **kw):
        """GET /api/v1/builder/templates → list available templates."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        try:
            Template = request.env['dashboard.widget.template'].sudo()
            templates = Template.search([], order='category, name')

            data = [{
                'id': t.id,
                'name': t.name,
                'description': t.description or '',
                'category': t.category,
            } for t in templates]

            return _json_resp(data)
        except KeyError:
            # Template model not yet installed (WB-6)
            return _json_resp([])

    @http.route(
        '/api/v1/builder/templates/<int:tpl_id>/use',
        type='http', auth='none', methods=['POST'], csrf=False,
    )
    def use_template(self, tpl_id, **kw):
        """POST /api/v1/builder/templates/<id>/use → create widgets from template."""
        try:
            _auth_admin()
        except ValueError as e:
            return _json_err(403, str(e))

        try:
            Template = request.env['dashboard.widget.template'].sudo()
            tpl = Template.browse(tpl_id)
            if not tpl.exists():
                return _json_err(404, 'Template not found')

            body = _get_body()
            page_id = body.get('page_id')
            tab_id = body.get('tab_id')

            if not page_id:
                return _json_err(400, 'page_id is required')

            widget_ids = tpl.action_use_template(page_id, tab_id)
            return _json_resp({'widget_ids': widget_ids})

        except KeyError:
            return _json_err(501, 'Template system not yet available (WB-6)')
        except Exception as e:
            _logger.exception("Use template error")
            return _json_err(500, f'Template failed: {e}')


# ── Helper: build widget vals from a definition ─────────────────────────────

def _build_widget_vals_from_definition(defn, body):
    """Build dashboard.widget create values from a widget definition record."""
    vals = {
        'definition_id': defn.id,
        'name': body.get('title_override') or defn.name,
        'chart_type': defn.chart_type,
        'col_span': body.get('col_span', defn.default_col_span) or '6',
        'chart_height': defn.chart_height,
        'color_palette': defn.color_palette,
        'color_custom_json': defn.color_custom_json or '',
        'click_action': defn.click_action,
        'action_page_key': defn.action_page_key or '',
        'action_tab_key': defn.action_tab_key or '',
        'action_pass_value_as': defn.action_pass_value_as or '',
        'drill_detail_columns': defn.drill_detail_columns or '',
        'action_url_template': defn.action_url_template or '',
        'column_link_config': defn.column_link_config or '',
        'builder_config': defn.builder_config or '',
        'query_type': 'sql',
        'echart_override': defn.echart_override or '',
        # Widget-Scoped Controls
        'scope_mode': defn.scope_mode or 'none',
        'scope_ui': defn.scope_ui or 'dropdown',
        'scope_query_mode': defn.scope_query_mode or 'parameter',
        'scope_param_name': defn.scope_param_name or '',
        'scope_label': defn.scope_label or '',
        'scope_default_value': defn.scope_default_value or '',
        'search_enabled': defn.search_enabled or False,
        'search_placeholder': defn.search_placeholder or 'Search...',
    }

    # Copy SQL
    effective_sql = defn.get_effective_sql() or ''
    vals['query_sql'] = effective_sql
    vals['x_column'] = defn.x_column or ''
    vals['y_columns'] = defn.y_columns or ''
    vals['series_column'] = defn.series_column or ''
    if defn.schema_source_id:
        vals['schema_source_id'] = defn.schema_source_id.id

    # KPI fields
    if defn.chart_type in ('kpi', 'status_kpi'):
        vals['kpi_format'] = defn.kpi_format
        vals['kpi_prefix'] = defn.kpi_prefix or ''
        vals['kpi_suffix'] = defn.kpi_suffix or ''

    # Gauge fields
    if defn.chart_type in ('gauge', 'gauge_kpi'):
        vals['gauge_min'] = defn.gauge_min
        vals['gauge_max'] = defn.gauge_max
        vals['gauge_color_mode'] = defn.gauge_color_mode

    return vals
