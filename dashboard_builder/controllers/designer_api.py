# -*- coding: utf-8 -*-
"""
Dashboard Designer — Session-Auth REST API
============================================
Mirrors the JWT-based builder_api.py but uses Odoo session auth (auth='user').
All routes prefixed with /dashboard/designer/api/.

The admin is already logged into Odoo backend, so session cookies handle auth.
"""

import json
import logging

from odoo import http
from odoo.http import request

from .utils import _json_response, _json_error, _get_request_json

_logger = logging.getLogger(__name__)


# ── Auth helper ──────────────────────────────────────────────────────────────

def _require_admin():
    """Check that the current session user is a builder admin."""
    user = request.env.user
    if not (user.has_group('dashboard_builder.group_dashboard_builder_admin')
            or user.has_group('base.group_system')):
        raise ValueError('Dashboard Builder Admin access required')
    return user


# ═══════════════════════════════════════════════════════════════════════════════
# DESIGNER API CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════════

class DesignerAPI(http.Controller):

    # =========================================================================
    # SCHEMA ENDPOINTS
    # =========================================================================

    @http.route(
        '/dashboard/designer/api/sources',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def sources(self, **kw):
        """List schema sources."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        source_domain = [('is_active', '=', True)]
        if kw.get('app_id') and 'app_ids' in request.env['dashboard.schema.source']._fields:
            app_id = int(kw['app_id'])
            source_domain.append('|')
            source_domain.append(('app_ids', '=', False))
            source_domain.append(('app_ids', 'in', [app_id]))
        sources = request.env['dashboard.schema.source'].sudo().search(
            source_domain, order='name asc')

        return _json_response([{
            'id': s.id,
            'name': s.name,
            'table_name': s.table_name,
            'alias': s.table_alias or '',
            'column_count': s.column_count,
            'description': s.description or '',
        } for s in sources])

    @http.route(
        '/dashboard/designer/api/sources/<int:source_id>',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def source_detail(self, source_id, **kw):
        """Source detail with columns."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        src = request.env['dashboard.schema.source'].sudo().browse(source_id)
        if not src.exists():
            return _json_error(404, 'Schema source not found')

        return _json_response({
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
        })

    @http.route(
        '/dashboard/designer/api/chart-flags/<string:chart_type>',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def chart_flags(self, chart_type, **kw):
        """Return visual config flag schema for a chart type.

        The React builder uses this to dynamically render chart-specific
        controls (checkboxes, dropdowns, number inputs). Flags are pure
        rendering instructions — no column names, params, or app references.
        """
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        from ..services.chart_flags import get_flags_for_chart
        return _json_response(get_flags_for_chart(chart_type))

    @http.route(
        '/dashboard/designer/api/sources/<int:source_id>/relations',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def source_relations(self, source_id, **kw):
        """Relations for a schema source."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        src = request.env['dashboard.schema.source'].sudo().browse(source_id)
        if not src.exists():
            return _json_error(404, 'Schema source not found')

        return _json_response([{
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
        } for r in src.relation_ids])

    # =========================================================================
    # AI SQL GENERATION ENDPOINT
    # =========================================================================

    @http.route(
        '/dashboard/designer/api/ai-generate',
        type='http', auth='user', methods=['POST'], csrf=False,
    )
    def ai_generate(self, **kw):
        """Generate SQL from natural language using Claude on Azure AI Foundry.

        Assembles schema context dynamically from the selected source/page,
        then calls Claude with the admin's prompt. Returns structured SQL
        with column mapping and explanation.

        Request body:
            source_id:     int — schema source ID (table/MV)
            page_id:       int — page ID (for filter params)
            chart_type:    str — bar, line, gauge, kpi, etc.
            gauge_style:   str — bullet, traffic_light_rag, etc. (optional)
            line_style:    str — waterfall, combo, benchmark (optional)
            donut_style:   str — nested, multi_ring (optional)
            rag_layout:    str — circles, scorecard (optional)
            prompt:        str — natural language description
            previous_sql:  str — existing SQL for refinement (optional)
            error_message: str — error from failed SQL for self-healing (optional)

        Returns:
            {sql, x_column, y_columns, explanation, warnings}
        """
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        body = _get_request_json()
        if not body:
            return _json_error(400, 'Request body is required')

        source_id = body.get('source_id')
        page_id = body.get('page_id')
        chart_type = body.get('chart_type', 'bar')
        gauge_style = body.get('gauge_style')
        line_style = body.get('line_style')
        donut_style = body.get('donut_style')
        rag_layout = body.get('rag_layout')
        kpi_style = body.get('kpi_style')
        sparkline_metric = body.get('sparkline_metric')
        value_display = body.get('value_display')
        mode = body.get('mode', 'generate')   # 'generate' | 'suggest'
        prompt = body.get('prompt', '')
        previous_sql = body.get('previous_sql')
        error_message = body.get('error_message')

        previous_intent = body.get('previous_intent')  # for intent-mode round-tripping

        if mode != 'suggest' and not prompt and not error_message:
            return _json_error(400, 'A prompt or error_message is required')

        try:
            from ..services.ai_sql_generator import AiSqlGenerator
            ai = AiSqlGenerator(request.env)
            context = ai.assemble_context(
                source_id, page_id, chart_type,
                gauge_style=gauge_style,
                line_style=line_style,
                donut_style=donut_style,
                rag_layout=rag_layout,
                kpi_style=kpi_style,
                sparkline_metric=sparkline_metric,
                value_display=value_display,
            )

            # Suggest mode: return schema-aware query suggestions
            if mode == 'suggest':
                result = ai.suggest_queries(context)
                return _json_response(result)

            # ── Intent pipeline ──────────────────────────────────────
            # AI generates structured intent -> SqlAssembler builds SQL.
            #
            # Feature gate: dashboard_builder.ai_use_intent_mode
            #   Missing           -> intent pipeline (default True)
            #   'True' (any case) -> intent pipeline
            #   'False'/'0'/'no'  -> legacy pipeline (explicit opt-out only)
            #
            # When the intent pipeline is active, there is NO silent fallback
            # to the legacy generator. If generate_intent() fails, the error
            # propagates to the frontend with a clear message.
            use_intent_raw = request.env['ir.config_parameter'].sudo().get_param(
                'dashboard_builder.ai_use_intent_mode'
            )
            # Default to True when the parameter is missing, empty, or False.
            # Odoo's get_param() returns False (not None) for missing params,
            # so we use a truthiness check rather than identity check.
            if not use_intent_raw:
                use_intent = True
            else:
                # Coerce to string in case Odoo returns a non-string value
                use_intent = str(use_intent_raw).strip().lower() not in ('false', '0', 'no')

            if use_intent:
                _logger.info(
                    "AI Intent Generate: chart=%s, prompt=%s",
                    chart_type, (prompt or '')[:80],
                )
                return self._ai_generate_intent(
                    ai, context, prompt, previous_intent, error_message,
                    source_id, page_id, body,
                )

            # ── Legacy pipeline (opt-in only via feature gate) ───────
            _logger.info(
                "AI Legacy Generate: chart=%s, prompt=%s",
                chart_type, (prompt or '')[:80],
            )
            if error_message and previous_sql:
                result = ai.fix_sql(context, previous_sql, error_message)
            elif previous_sql:
                result = ai.refine_sql(context, previous_sql, prompt)
            else:
                result = ai.generate_sql(context, prompt)

            # Validate generated SQL using existing QueryBuilder
            from ..services.query_builder import QueryBuilder
            qb = QueryBuilder(request.env)
            is_valid, err = qb.validate_query(result.get('sql', ''))
            if not is_valid:
                return _json_error(400, f'AI generated invalid SQL: {err}')

            return _json_response(result)

        except ValueError as e:
            return _json_error(400, str(e))
        except Exception as e:
            _logger.error('AI SQL generation failed: %s', e, exc_info=True)
            return _json_error(500, f'AI SQL generation failed: {e}')

    def _ai_generate_intent(self, ai, context, prompt, previous_intent,
                            error_message, source_id, page_id, body=None):
        """Intent pipeline: AI returns intent -> SqlAssembler builds SQL.

        This eliminates WHERE clause bugs by construction -- the AI never
        writes WHERE/filter clauses; the deterministic assembler does.

        NO silent fallback to the legacy pipeline. If intent generation
        fails, the error is surfaced to the frontend with a clear message.

        Routing (based on request body):
          - error_message + previous_intent -> fix_intent()
          - previous_intent                 -> refine_intent()
          - (no previous_intent)            -> generate_intent() fresh

        If the frontend sent previous_sql but no previous_intent
        (legacy-generated result being refined), we start a fresh intent
        generation using the user's current prompt. We do NOT call the
        legacy refine_sql() -- that path produced the double-AND bug.
        """
        # 1. Get intent from AI
        if error_message and previous_intent:
            _logger.info('Intent route: fix_intent')
            intent = ai.fix_intent(context, previous_intent, error_message)
        elif previous_intent:
            _logger.info('Intent route: refine_intent')
            intent = ai.refine_intent(context, previous_intent, prompt)
        else:
            # Fresh generation -- also covers the transition case where the
            # frontend has previous_sql but no previous_intent. We do NOT
            # fall back to the legacy refine_sql here: the assembler is the
            # only trusted SQL producer.
            _logger.info('Intent route: generate_intent (fresh)')
            intent = ai.generate_intent(context, prompt)

        # 2. Load filter defs and source columns for the assembler
        filter_defs = []
        source_columns = None

        if page_id:
            PageFilter = request.env['dashboard.page.filter'].sudo()
            filters = PageFilter.search([
                ('page_id', '=', int(page_id)),
                ('is_active', '=', True),
            ])
            filter_defs = [{
                'param_name': f.param_name or f.field_name or '',
                'db_column': (
                    f.schema_column_id.column_name
                    if f.schema_column_id
                    else f.field_name or f.param_name or ''
                ),
                'is_multiselect': f.is_multiselect,
                'col_type': (
                    f.schema_column_id.data_type
                    if f.schema_column_id
                    else 'text'
                ),
            } for f in filters if (f.param_name or f.field_name)]

        if source_id:
            Source = request.env['dashboard.schema.source'].sudo()
            source = Source.browse(int(source_id))
            if source.exists():
                source_columns = {c.column_name for c in source.column_ids}
                table_name = source.table_name
            else:
                return _json_error(400, 'Schema source not found')
        else:
            return _json_error(400, 'source_id is required for intent mode')

        # 3. Assemble SQL from intent + filter defs
        from ..services.sql_assembler import SqlAssembler
        chart_type = context.get('chart_type', 'bar')
        _logger.info(
            'Intent pipeline: chart_type=%s, mode=%s, measures=%d, dimensions=%d',
            chart_type,
            intent.get('mode', 'simple'),
            len(intent.get('measures', [])),
            len(intent.get('dimensions', [])),
        )
        assembler = SqlAssembler(table_name, filter_defs, source_columns, chart_type=chart_type)
        try:
            result = assembler.assemble(intent)
        except ValueError as assembler_err:
            _logger.warning(
                'SqlAssembler validation failed: %s | intent=%s',
                assembler_err, intent,
            )
            return _json_error(400, str(assembler_err))

        # 4. Validate the assembled SQL
        from ..services.query_builder import QueryBuilder
        qb = QueryBuilder(request.env)
        is_valid, err = qb.validate_query(result.get('sql', ''))
        if not is_valid:
            return _json_error(400, 'Assembled SQL is invalid: %s' % err)

        return _json_response(result)

    # =========================================================================
    # PREVIEW ENDPOINT
    # =========================================================================

    @http.route(
        '/dashboard/designer/api/preview',
        type='http', auth='user', methods=['POST'], csrf=False,
    )
    def preview(self, **kw):
        """Execute query preview."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        body = _get_request_json()
        mode = body.get('mode', 'visual')

        try:
            from ..services.query_builder import QueryBuilder
            qb = QueryBuilder(request.env)

            # ── Normalize raw params from JSON ─────────────────────────
            # JavaScript may send lists (multi-select), booleans, or nulls.
            # First pass: coerce everything to strings (CSV for lists).
            raw_params = body.get('params', {})
            normalized = {}
            for k, v in raw_params.items():
                if isinstance(v, list):
                    normalized[k] = ','.join(str(i) for i in v) if v else ''
                elif isinstance(v, bool):
                    normalized[k] = str(v).lower()
                else:
                    normalized[k] = v if v is not None else ''

            # ── Filter-aware conversion (when page context available) ──
            # Uses the same build_sql_params() as portal.py and widget_api.py
            # so preview params match runtime params exactly.
            page_id = body.get('page_id')
            multiselect_params = set()
            if page_id:
                try:
                    PageFilter = request.env['dashboard.page.filter'].sudo()
                    page_filters = PageFilter.search([
                        ('page_id', '=', int(page_id)),
                        ('is_active', '=', True),
                    ])
                    multiselect_params = {
                        (f.param_name or f.field_name)
                        for f in page_filters if f.is_multiselect
                    }
                    from odoo.addons.posterra_portal.utils.sql_params import build_sql_params
                    params = build_sql_params(normalized, multiselect_params)
                except Exception as e:
                    _logger.warning(
                        'Preview: filter-aware param build failed (page_id=%s): %s. '
                        'Falling back to string params.', page_id, e)
                    params = normalized
                    multiselect_params = set()
            else:
                # No page context — use plain string params (safety net)
                params = normalized

            if mode == 'custom_sql':
                sql = body.get('sql', '')
                is_valid, err = qb.validate_query(sql)
                if not is_valid:
                    return _json_error(400, f'Invalid SQL: {err}')
                _logger.info('Preview [custom_sql] params: %s', params)
                _logger.info('Preview [custom_sql] SQL: %s', sql)
                columns, rows = qb.execute_preview(sql, params)
            else:
                config = body.get('config', {})
                sql = qb.build_select_query(config, multiselect_params=multiselect_params)
                _logger.info('Preview [visual] multiselect_params: %s', multiselect_params)
                _logger.info('Preview [visual] params: %s', params)
                _logger.info('Preview [visual] SQL: %s', sql)
                columns, rows = qb.execute_preview(sql, params)

            rows_list = [list(row) for row in rows]

            # Format preview data based on widget type
            from ..services.preview_formatter import format_preview
            chart_type = body.get('chart_type', 'table')
            widget_config = body.get('widget_config', {})
            visual_config = widget_config.get('visual_config', {})
            formatted = format_preview(chart_type, columns, rows_list, widget_config, visual_config)

            return _json_response({
                'sql': sql,
                'columns': columns,
                'rows': rows_list,
                **formatted,
            })

        except ValueError as e:
            return _json_error(400, str(e))
        except Exception as e:
            _logger.exception("Designer preview error")
            return _json_error(500, f'Preview failed: {e}')

    # =========================================================================
    # WIDGET LIBRARY ENDPOINTS
    # =========================================================================

    @http.route(
        '/dashboard/designer/api/library',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def library_list(self, **kw):
        """List widget definitions."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        domain = [('is_active', '=', True)]
        if kw.get('category'):
            domain.append(('category', '=', kw['category']))
        if kw.get('chart_type'):
            domain.append(('chart_type', '=', kw['chart_type']))
        if kw.get('search'):
            domain.append(('name', 'ilike', kw['search']))
        has_app_ids = 'app_ids' in request.env['dashboard.widget.definition']._fields
        if kw.get('app_id') and has_app_ids:
            # Show definitions scoped to this app OR global (no app_ids set)
            app_id = int(kw['app_id'])
            domain.append('|')
            domain.append(('app_ids', '=', False))
            domain.append(('app_ids', 'in', [app_id]))

        # Page/Tab filter: find definitions placed on a specific page/tab
        if kw.get('page_id'):
            try:
                Widget = request.env['dashboard.widget'].sudo()
                widget_domain = [('page_id', '=', int(kw['page_id']))]
                if kw.get('tab_id'):
                    widget_domain.append(('tab_id', '=', int(kw['tab_id'])))
                widgets = Widget.search(widget_domain)
                def_ids = list(set(widgets.mapped('definition_id').ids))
                if def_ids:
                    domain.append(('id', 'in', def_ids))
                else:
                    return _json_response([])  # no widgets on this page/tab
            except (KeyError, ValueError):
                pass  # dashboard.widget not installed or invalid ID

        defs = request.env['dashboard.widget.definition'].sudo().search(
            domain, order='chart_type, name')

        return _json_response([{
            'id': d.id,
            'name': d.name,
            'description': d.description or '',
            'category': d.category,
            'chart_type': d.chart_type,
            'instance_count': d.instance_count,
            'data_mode': d.data_mode,
            'app_names': [a.name for a in d.app_ids] if has_app_ids and d.app_ids else [],
        } for d in defs])

    @http.route(
        '/dashboard/designer/api/library/<int:def_id>',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def library_detail(self, def_id, **kw):
        """Full definition detail."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        defn = request.env['dashboard.widget.definition'].sudo().browse(def_id)
        if not defn.exists():
            return _json_error(404, 'Widget definition not found')

        return _json_response({
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
            'default_row_span': defn.default_row_span or 1,
            'chart_height': defn.chart_height,
            'color_palette': defn.color_palette,
            'bar_stack': defn.bar_stack,
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
            'echart_override': defn.echart_override or '',
            'visual_config': defn.visual_config or '',
            'table_column_config': defn.table_column_config or '',
            'instance_count': defn.instance_count,
        })

    @http.route(
        '/dashboard/designer/api/library/create',
        type='http', auth='user', methods=['POST'], csrf=False,
    )
    def library_create(self, **kw):
        """Create a new widget definition."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        body = _get_request_json()

        try:
            mode = body.get('data_mode', 'custom_sql')
            chart_type = body.get('chart_type', 'bar')

            def_vals = {
                'name': body.get('name', 'New Widget'),
                'description': body.get('description', ''),
                'chart_type': chart_type,
                'data_mode': mode,
                'category': body.get('category', 'chart'),
                'default_col_span': str(body.get('col_span', 6)),
                'default_row_span': int(body.get('row_span', 1)),
                'chart_height': body.get('chart_height', 350),
                'color_palette': body.get('color_palette', 'healthcare'),
                'bar_stack': bool(body.get('bar_stack', False)),
                'click_action': body.get('click_action', 'none'),
                'action_page_key': body.get('action_page_key', ''),
                'action_tab_key': body.get('action_tab_key', ''),
                'action_pass_value_as': body.get('action_pass_value_as', ''),
                'drill_detail_columns': body.get('drill_detail_columns', ''),
                'action_url_template': body.get('action_url_template', ''),
                'column_link_config': body.get('column_link_config', ''),
            }

            if mode == 'custom_sql':
                def_vals.update({
                    'query_sql': body.get('query_sql', ''),
                    'x_column': body.get('x_column', ''),
                    'y_columns': body.get('y_columns', ''),
                    'series_column': body.get('series_column', ''),
                })
            else:
                config = body.get('builder_config', {})
                if isinstance(config, dict):
                    def_vals['builder_config'] = json.dumps(config)
                else:
                    def_vals['builder_config'] = config or ''

                # Set column mappings from body (same fields as custom_sql)
                def_vals['x_column'] = body.get('x_column', '')
                def_vals['y_columns'] = body.get('y_columns', '')
                def_vals['series_column'] = body.get('series_column', '')

                # Set schema_source from the first source in config
                if isinstance(config, dict) and config.get('source_ids'):
                    source_id = config['source_ids'][0]
                    # Find the dashboard.schema.source matching this ID
                    schema_src = request.env['dashboard.schema.source'].sudo().browse(source_id)
                    if schema_src.exists():
                        def_vals['schema_source_id'] = schema_src.id

                # Generate SQL from visual builder config (skip for table type —
                # tables use table_column_config for column definitions, and their
                # SQL is a simple SELECT of all configured columns without aggregation)
                if chart_type != 'table':
                    from ..services.query_builder import QueryBuilder
                    qb = QueryBuilder(request.env)
                    if isinstance(config, dict) and config.get('source_ids'):
                        def_vals['generated_sql'] = qb.build_select_query(config, save_mode=True)
                else:
                    # For tables: build a simple SELECT from the configured columns
                    if isinstance(config, dict) and config.get('source_ids') and config.get('columns'):
                        from ..services.query_builder import QueryBuilder
                        qb = QueryBuilder(request.env)
                        try:
                            def_vals['generated_sql'] = qb.build_select_query(config, save_mode=True)
                        except (ValueError, Exception):
                            # Table columns may not have agg functions — build a
                            # simple SELECT col1, col2, ... FROM source instead
                            pass

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

            if body.get('echart_override'):
                def_vals['echart_override'] = body['echart_override']

            # Visual config (chart-specific flags from builder UI)
            if body.get('visual_config'):
                vc = body['visual_config']
                def_vals['visual_config'] = vc if isinstance(vc, str) else json.dumps(vc)

            # Table column config (AG Grid columnDefs from TableConfigurator)
            if 'table_column_config' in body:
                tcc = body['table_column_config']
                def_vals['table_column_config'] = tcc if isinstance(tcc, str) else json.dumps(tcc) if tcc else ''

            # App scoping (field added by posterra_portal via _inherit)
            if body.get('app_ids') and 'app_ids' in request.env['dashboard.widget.definition']._fields:
                def_vals['app_ids'] = [(6, 0, body['app_ids'])]

            definition = request.env['dashboard.widget.definition'].sudo().create(def_vals)

            return _json_response({
                'id': definition.id,
                'name': definition.name,
                'chart_type': definition.chart_type,
            })

        except Exception as e:
            _logger.exception("Designer create error")
            return _json_error(500, f'Create failed: {e}')

    @http.route(
        '/dashboard/designer/api/library/<int:def_id>',
        type='http', auth='user', methods=['PUT'], csrf=False,
    )
    def library_update(self, def_id, **kw):
        """Update an existing widget definition."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        defn = request.env['dashboard.widget.definition'].sudo().browse(def_id)
        if not defn.exists():
            return _json_error(404, 'Widget definition not found')

        body = _get_request_json()
        update_vals = {}

        field_map = {
            'name': 'name', 'description': 'description',
            'chart_type': 'chart_type', 'category': 'category',
            'chart_height': 'chart_height', 'color_palette': 'color_palette',
            'click_action': 'click_action', 'action_page_key': 'action_page_key',
            'action_tab_key': 'action_tab_key',
            'action_pass_value_as': 'action_pass_value_as',
            'drill_detail_columns': 'drill_detail_columns',
            'action_url_template': 'action_url_template',
            'column_link_config': 'column_link_config',
            'echart_override': 'echart_override',
            'query_sql': 'query_sql',
            'x_column': 'x_column', 'y_columns': 'y_columns',
            'series_column': 'series_column',
            'kpi_format': 'kpi_format', 'kpi_prefix': 'kpi_prefix',
            'kpi_suffix': 'kpi_suffix',
            'bar_stack': 'bar_stack',
        }

        for body_key, field_name in field_map.items():
            if body_key in body:
                update_vals[field_name] = body[body_key]

        if 'col_span' in body:
            update_vals['default_col_span'] = str(body['col_span'])
        if 'row_span' in body:
            update_vals['default_row_span'] = int(body['row_span'])

        if 'builder_config' in body:
            config = body['builder_config']
            if isinstance(config, dict):
                update_vals['builder_config'] = json.dumps(config)
                if config.get('source_ids'):
                    from ..services.query_builder import QueryBuilder
                    qb = QueryBuilder(request.env)
                    update_vals['generated_sql'] = qb.build_select_query(config, save_mode=True)
            else:
                update_vals['builder_config'] = config or ''

        # Visual config (chart-specific flags from builder UI)
        if 'visual_config' in body:
            vc = body['visual_config']
            update_vals['visual_config'] = vc if isinstance(vc, str) else json.dumps(vc)

        # Table column config (AG Grid columnDefs)
        if 'table_column_config' in body:
            tcc = body['table_column_config']
            update_vals['table_column_config'] = tcc if isinstance(tcc, str) else json.dumps(tcc)

        if 'app_ids' in body and 'app_ids' in request.env['dashboard.widget.definition']._fields:
            update_vals['app_ids'] = [(6, 0, body['app_ids'] or [])]

        try:
            defn.write(update_vals)

            # ── Propagate data fields to all linked widget instances ──────
            # Instance-specific fields (name, page_id, tab_id, col_span,
            # chart_height, color_palette, sequence) are NOT synced — they
            # may have been customized per-instance by the admin.
            try:
                Widget = request.env['dashboard.widget'].sudo()
                instances = Widget.search([('definition_id', '=', defn.id)])
                if instances:
                    sync_vals = {
                        'query_sql': defn.get_effective_sql() or '',
                        'chart_type': defn.chart_type,
                        'x_column': defn.x_column or '',
                        'y_columns': defn.y_columns or '',
                        'series_column': defn.series_column or '',
                        'visual_config': defn.visual_config or '',
                        'echart_override': defn.echart_override or '',
                        'builder_config': defn.builder_config or '',
                        'table_column_config': defn.table_column_config or '',
                        'column_link_config': defn.column_link_config or '',
                        'click_action': defn.click_action,
                        'action_page_key': defn.action_page_key or '',
                        'action_tab_key': defn.action_tab_key or '',
                        'action_pass_value_as': defn.action_pass_value_as or '',
                        'drill_detail_columns': defn.drill_detail_columns or '',
                        'action_url_template': defn.action_url_template or '',
                        'schema_source_id': defn.schema_source_id.id if defn.schema_source_id else False,
                        'bar_stack': defn.bar_stack,
                    }
                    if hasattr(defn, 'where_clause_exclude'):
                        sync_vals['where_clause_exclude'] = defn.where_clause_exclude or ''
                    if defn.chart_type in ('kpi', 'status_kpi'):
                        sync_vals['kpi_format'] = defn.kpi_format
                        sync_vals['kpi_prefix'] = defn.kpi_prefix or ''
                        sync_vals['kpi_suffix'] = defn.kpi_suffix or ''
                    instances.write(sync_vals)
                    _logger.info(
                        'Synced definition %s (%s) → %d instance(s)',
                        defn.id, defn.name, len(instances),
                    )
            except KeyError:
                pass  # dashboard.widget not installed

            return _json_response({'id': defn.id, 'name': defn.name})
        except Exception as e:
            _logger.exception("Designer update error")
            return _json_error(500, f'Update failed: {e}')

    @http.route(
        '/dashboard/designer/api/library/<int:def_id>',
        type='http', auth='user', methods=['DELETE'], csrf=False,
    )
    def library_delete(self, def_id, **kw):
        """Delete a widget definition (only if no instances exist)."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        defn = request.env['dashboard.widget.definition'].sudo().browse(def_id)
        if not defn.exists():
            return _json_error(404, 'Widget definition not found')

        if defn.instance_count > 0:
            return _json_error(400,
                f'Cannot delete: {defn.instance_count} instance(s) still reference this definition.')

        try:
            name = defn.name
            defn.unlink()
            return _json_response({'deleted': True, 'name': name})
        except Exception as e:
            _logger.exception("Designer delete error")
            return _json_error(500, f'Delete failed: {e}')

    # =========================================================================
    # TEMPLATE ENDPOINTS
    # =========================================================================

    @http.route(
        '/dashboard/designer/api/templates',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def templates_list(self, **kw):
        """List widget templates with slot info for parameterized templates."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        templates = request.env['dashboard.widget.template'].sudo().search(
            [], order='category, name')

        result = []
        for t in templates:
            item = {
                'id': t.id,
                'name': t.name,
                'description': t.description or '',
                'category': t.category,
                'template_mode': t.template_mode or 'legacy_json',
                'chart_type': t.chart_type or '',
                'creates_count': t.creates_count,
            }
            if t.template_mode == 'parameterized':
                item['slots'] = [{
                    'slot_name': s.slot_name,
                    'label': s.label,
                    'slot_type': s.slot_type,
                    'column_filter': s.column_filter or 'any',
                    'required': s.required,
                    'default_value': s.default_value or '',
                    'help_text': s.help_text or '',
                } for s in t.slot_ids.sorted('sequence')]
                try:
                    item['multi_instance_configs'] = json.loads(
                        t.multi_instance_configs or '[]')
                except (json.JSONDecodeError, TypeError):
                    item['multi_instance_configs'] = []
                item['sql_pattern'] = t.sql_pattern or ''
                item['title_pattern'] = t.title_pattern or ''
                item['col_span'] = t.col_span or '6'
                item['chart_height'] = t.chart_height or 350
                item['color_palette'] = t.color_palette or 'healthcare'
                item['kpi_format'] = t.kpi_format or 'number'
                item['kpi_prefix'] = t.kpi_prefix or ''
                item['kpi_suffix'] = t.kpi_suffix or ''
                item['where_clause_exclude'] = t.where_clause_exclude or ''
            result.append(item)

        return _json_response(result)

    @http.route(
        '/dashboard/designer/api/templates/<int:tpl_id>/use',
        type='http', auth='user', methods=['POST'], csrf=False,
    )
    def template_use(self, tpl_id, **kw):
        """Use a template to create widgets. Supports both legacy and parameterized."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        tpl = request.env['dashboard.widget.template'].sudo().browse(tpl_id)
        if not tpl.exists():
            return _json_error(404, 'Template not found')

        body = _get_request_json()
        page_id = body.get('page_id')
        tab_id = body.get('tab_id')

        if not page_id:
            return _json_error(400, 'page_id is required')

        try:
            if tpl.template_mode == 'parameterized':
                schema_source_id = body.get('schema_source_id')
                slot_mappings = body.get('slot_mappings', {})
                instances = body.get('instances')
                if not schema_source_id:
                    return _json_error(400, 'schema_source_id is required for parameterized templates')
                widget_ids = tpl.action_use_parameterized(
                    page_id, tab_id, schema_source_id,
                    slot_mappings, instances)
            else:
                widget_ids = tpl.action_use_template(page_id, tab_id)
            return _json_response({'widget_ids': widget_ids})
        except ValueError as e:
            return _json_error(400, str(e))
        except Exception as e:
            _logger.exception("Template use error")
            return _json_error(500, f'Template failed: {e}')

    # =========================================================================
    # PAGE FILTER ENDPOINTS (for designer preview with real filters)
    # =========================================================================

    @http.route(
        '/dashboard/designer/api/pages/<int:page_id>/filters',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def page_filters(self, page_id, **kw):
        """Return filter definitions + options for a page (designer preview)."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        try:
            PageFilter = request.env['dashboard.page.filter'].sudo()
            filters = PageFilter.search(
                [('page_id', '=', page_id), ('is_active', '=', True)],
                order='sequence asc')

            result = []
            for f in filters:
                try:
                    options = f.get_options()
                except Exception:
                    options = []

                result.append({
                    'id': f.id,
                    'param_name': f.param_name or '',
                    'label': f.display_name or f.param_name or '',
                    'field_name': f.field_name or '',
                    'is_visible': f.is_visible,
                    'is_multiselect': f.is_multiselect,
                    'include_all_option': f.include_all_option,
                    'default_value': f.default_value or '',
                    'options': options if isinstance(options, list) else [],
                })
            return _json_response(result)
        except KeyError:
            return _json_response([])
        except Exception as e:
            _logger.exception("Page filters error")
            return _json_error(500, f'Failed to load page filters: {e}')

    # =========================================================================
    # APP & PAGE ENDPOINTS (graceful when posterra_portal not installed)
    # =========================================================================

    @http.route(
        '/dashboard/designer/api/apps',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def apps_list(self, **kw):
        """List apps (saas.app model, if available)."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        try:
            apps = request.env['saas.app'].sudo().search(
                [('is_active', '=', True)], order='name asc')
            return _json_response([{
                'id': a.id,
                'name': a.name,
                'app_key': a.app_key,
            } for a in apps])
        except KeyError:
            return _json_response([])

    @http.route(
        '/dashboard/designer/api/apps/<int:app_id>/pages',
        type='http', auth='user', methods=['GET'], csrf=False, readonly=True,
    )
    def app_pages(self, app_id, **kw):
        """List pages for an app, with tabs."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        try:
            pages = request.env['dashboard.page'].sudo().search(
                [('app_id', '=', app_id), ('is_active', '=', True)],
                order='sequence asc')

            data = []
            for p in pages:
                tabs = []
                try:
                    tab_recs = request.env['dashboard.page.tab'].sudo().search(
                        [('page_id', '=', p.id), ('is_active', '=', True)],
                        order='sequence asc')
                    tabs = [{'id': t.id, 'key': t.key, 'name': t.name} for t in tab_recs]
                except KeyError:
                    pass

                data.append({
                    'id': p.id,
                    'key': p.key,
                    'name': p.name,
                    'tabs': tabs,
                })

            return _json_response(data)
        except KeyError:
            return _json_response([])

    @http.route(
        '/dashboard/designer/api/library/<int:def_id>/place',
        type='http', auth='user', methods=['POST'], csrf=False,
    )
    def library_place(self, def_id, **kw):
        """Place a widget definition on a page/tab as a widget instance."""
        try:
            _require_admin()
        except ValueError as e:
            return _json_error(403, str(e))

        defn = request.env['dashboard.widget.definition'].sudo().browse(def_id)
        if not defn.exists():
            return _json_error(404, 'Widget definition not found')

        body = _get_request_json()
        page_id = body.get('page_id')
        if not page_id:
            return _json_error(400, 'page_id is required')

        try:
            Widget = request.env['dashboard.widget'].sudo()

            vals = {
                'definition_id': defn.id,
                'name': body.get('name_override') or defn.name,
                'chart_type': defn.chart_type,
                'page_id': page_id,
                'col_span': body.get('col_span', defn.default_col_span) or '6',
                'row_span': defn.default_row_span or 1,
                'chart_height': defn.chart_height,
                'color_palette': defn.color_palette,
                'bar_stack': defn.bar_stack,
                'click_action': defn.click_action,
                'action_page_key': defn.action_page_key or '',
                'action_tab_key': defn.action_tab_key or '',
                'action_pass_value_as': defn.action_pass_value_as or '',
                'drill_detail_columns': defn.drill_detail_columns or '',
                'action_url_template': defn.action_url_template or '',
                'column_link_config': defn.column_link_config or '',
                'table_column_config': defn.table_column_config or '',
                'builder_config': defn.builder_config or '',
                'query_type': 'sql',
                'query_sql': defn.get_effective_sql() or '',
                'x_column': defn.x_column or '',
                'y_columns': defn.y_columns or '',
                'series_column': defn.series_column or '',
                'echart_override': defn.echart_override or '',
                'visual_config': defn.visual_config or '',
                'schema_source_id': defn.schema_source_id.id if defn.schema_source_id else False,
                'where_clause_exclude': defn.where_clause_exclude or '' if hasattr(defn, 'where_clause_exclude') else '',
            }

            if body.get('tab_id'):
                vals['tab_id'] = body['tab_id']

            # KPI fields
            if defn.chart_type in ('kpi', 'status_kpi'):
                vals['kpi_format'] = defn.kpi_format
                vals['kpi_prefix'] = defn.kpi_prefix or ''
                vals['kpi_suffix'] = defn.kpi_suffix or ''

            # Dedup safeguard: if an instance already exists for this
            # definition on this page, update it instead of creating a duplicate.
            existing = Widget.search([
                ('definition_id', '=', defn.id),
                ('page_id', '=', page_id),
            ], limit=1)
            if existing:
                existing.write(vals)
                _logger.info(
                    'Place dedup: updated existing instance %s for definition %s on page %s',
                    existing.id, defn.id, page_id,
                )
                return _json_response({'widget_id': existing.id, 'name': existing.name, 'updated': True})

            widget = Widget.create(vals)
            return _json_response({'widget_id': widget.id, 'name': widget.name})

        except KeyError:
            return _json_error(501, 'dashboard.widget model not available (consuming module not installed)')
        except Exception as e:
            _logger.exception("Designer place error")
            return _json_error(500, f'Place failed: {e}')
