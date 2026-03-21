# -*- coding: utf-8 -*-
"""
Phase 6 — Widget & Page Config JSON API
========================================
All endpoints require a valid JWT Bearer token from /api/v1/auth/login.

Endpoints:
    GET /api/v1/page/<page_key>/config
        Returns page structure: tabs, filter definitions + initial options,
        widget metadata (no data), HHA selector options.

    GET /api/v1/widget/<widget_id>/data
        Returns a single widget's computed data with the supplied filter params.
        Calls dashboard.widget.get_portal_data() — identical to QWeb rendering.

    GET /api/v1/filters/cascade
        Returns dynamic options for a cascade-dependent filter.
        Calls dashboard.page.filter.get_options() — identical to the AJAX endpoint.

Key principle: all Python computation is unchanged.  The API is just a JSON
delivery layer on top of the existing model methods.
"""

import json
import logging

from odoo import http
from odoo.http import request

from .auth_api import _json_error, _json_response, _verify_token
from .portal import _get_providers_for_user

_logger = logging.getLogger(__name__)


# ── JWT validation helper ─────────────────────────────────────────────────────

def _get_api_user():
    """Extract and validate the Bearer JWT from the request headers.

    Returns:
        (user, app) — both are sudo() recordsets.

    Raises:
        ValueError — with a human-readable message on any auth failure.
    """
    auth_header = request.httprequest.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise ValueError('Missing or invalid Authorization header (expected: Bearer <token>)')
    token = auth_header[7:].strip()
    payload = _verify_token(token)      # raises ValueError on bad/expired token
    if payload.get('type') != 'access':
        raise ValueError('Expected an access token, not a refresh token')

    user = request.env['res.users'].sudo().browse(payload['user_id'])
    if not user.exists():
        raise ValueError('Token references a user that no longer exists')

    app = request.env['saas.app'].sudo().browse(payload.get('app_id'))
    if not app.exists():
        raise ValueError('Token references an app that no longer exists')

    return user, app


# ── portal_ctx builder for API calls ─────────────────────────────────────────

def _build_portal_ctx(page, user, app, kw):
    """Build the portal_ctx dict that widget.get_portal_data() expects.

    Mirrors the filter/HHA resolution logic of portal.py app_dashboard(),
    but reads filter values from the API query-string (kw) instead of
    request.params.

    Args:
        page  — dashboard.page record (already sudo'd)
        user  — res.users record (already sudo'd)
        app   — saas.app record (already sudo'd)
        kw    — dict of query-string params from the API request

    Returns:
        portal_ctx dict with keys: sql_params, filter_values_by_name,
        selected_hha
    """
    providers = request.env['hha.provider'].sudo().browse()
    selected_provider = None

    if app.access_mode == 'hha_provider':
        providers = _get_providers_for_user(user)

    # ── Load page filters first (need filter config for provider resolution) ──
    page_filters = request.env['dashboard.page.filter'].sudo().search(
        [('page_id', '=', page.id), ('is_active', '=', True)],
        order='sequence asc',
    )

    # ── Generic provider resolution (reads param from filter config) ──────
    if app.access_mode == 'hha_provider' and providers:
        if len(providers) == 1:
            selected_provider = providers[0]
        else:
            provider_filter = page_filters.filtered(
                lambda f: f.is_provider_selector
            )
            if provider_filter:
                pf = provider_filter[0]
                pf_param = pf.param_name or pf.field_name or ''
                pf_field = pf.field_name or pf.schema_column_name or pf.param_name or ''
                pf_value = (kw.get(pf_param) or '').strip()

                if pf_value and pf_value != 'all' and pf_field:
                    if pf_field == 'id':
                        try:
                            matched = providers.filtered(
                                lambda p: p.id == int(pf_value))
                            if matched:
                                selected_provider = matched[0]
                        except (ValueError, TypeError):
                            pass
                    else:
                        matched = providers.filtered(
                            lambda p, fld=pf_field, val=pf_value:
                                str(getattr(p, fld, '')) == val)
                        if matched:
                            selected_provider = matched[0]

    # ── Auto-fill from selected HHA ───────────────────────────────────────
    # Use the actual ORM field_name for getattr, but store under param_name
    # (or field_name) so the key matches URL params and SQL placeholders.
    hha_auto_fill = {}
    if selected_provider:
        for f in page_filters:
            if f.auto_fill_from_hha:
                actual_field = f.field_name or f.param_name or f.schema_column_name or ''
                param_key = f.param_name or f.field_name or ''
                if actual_field and param_key and hasattr(selected_provider, actual_field):
                    val = getattr(selected_provider, actual_field, '') or ''
                    hha_auto_fill[param_key] = str(val).strip()

    # ── Resolve filter values from query params ───────────────────────────
    filter_values = {}
    for f in page_filters:
        eff_param = f.param_name or f.field_name or ''
        if eff_param:
            url_val  = (kw.get(eff_param) or '').strip()
            auto_val = hha_auto_fill.get(eff_param, '')
            filter_values[f.id] = url_val or auto_val or f.default_value or ''
        else:
            filter_values[f.id] = f.default_value or ''

    filter_values_by_name = {}
    for f in page_filters:
        key = f.param_name or f.field_name
        if key:
            filter_values_by_name[key] = filter_values.get(f.id, '')

    # Derive current_hha_id from whichever param the Provider filter uses.
    # Uses is_provider_selector (admin-configured) — never hardcoded model_name.
    pf_param_name = ''
    _pf = page_filters.filtered(lambda f: f.is_provider_selector)
    if _pf:
        pf_param_name = _pf[0].param_name or _pf[0].field_name or ''
    current_hha_id = (kw.get(pf_param_name) or 'all').strip() if pf_param_name else 'all'

    # Convert multi-select params from CSV strings to tuples for psycopg2.
    # psycopg2 adapts tuples to SQL tuple syntax — IN %(param)s works.
    # When value is empty/all, use ('__all__',) sentinel so
    # DashboardFilterBuilder and manual SQL can detect "no filter".
    multiselect_params = {
        (f.param_name or f.field_name)
        for f in page_filters if f.is_multiselect
    }
    sql_params = {}
    for key, val in filter_values_by_name.items():
        if key in multiselect_params:
            if val and val not in ('', 'all'):
                parts = tuple(v.strip() for v in val.split(',') if v.strip())
                sql_params[key] = parts
                # Helper params for single-value numeric selections
                numeric = [v for v in parts if v.isdigit()]
                if len(parts) == 1 and numeric:
                    sql_params['_%s_single' % key] = int(numeric[0])
                    sql_params['_%s_prior' % key] = int(numeric[0]) - 1
                else:
                    sql_params['_%s_single' % key] = None
                    sql_params['_%s_prior' % key] = None
            else:
                sql_params[key] = ('__all__',)
                sql_params['_%s_single' % key] = None
                sql_params['_%s_prior' % key] = None
        else:
            sql_params[key] = val

    return {
        'selected_hha':          selected_provider,
        'filter_values_by_name': filter_values_by_name,
        'sql_params':            sql_params,
        '_filter_defs':          page_filters.to_filter_defs(),
    }


# ── Normalise widget data for JSON serialisation ──────────────────────────────

def _normalise_widget_data(data: dict) -> dict:
    """Convert widget data dict into a clean JSON-serialisable form.

    The main transformation: echart_json (a pre-serialised JSON string)
    is parsed back to a dict and stored as echart_option so the entire
    API response is a single consistent JSON object.
    """
    if not isinstance(data, dict):
        return data
    result = dict(data)
    if 'echart_json' in result:
        raw = result.pop('echart_json')
        try:
            result['echart_option'] = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            result['echart_option'] = {}
    return result


# ── Widget API controller ─────────────────────────────────────────────────────

class PosterraWidgetAPI(http.Controller):

    # ------------------------------------------------------------------ #
    # GET /api/v1/page/<page_key>/config                                  #
    # ------------------------------------------------------------------ #
    @http.route(
        '/api/v1/page/<string:page_key>/config',
        type='http',
        auth='none',
        methods=['GET', 'OPTIONS'],
        csrf=False,
        readonly=True,
    )
    def api_page_config(self, page_key, **kw):
        """Return full page configuration for the React shell.

        Includes: page metadata, app branding, tabs, filter definitions
        with initial options, widget metadata (NOT data), HHA selector,
        and the filter dependency map.

        No widget data is returned here — each widget fetches its own
        data via GET /api/v1/widget/<id>/data.
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))

        # ── Resolve page ──────────────────────────────────────────────────
        page = request.env['dashboard.page'].sudo().search(
            [('app_id', '=', app.id), ('key', '=', page_key), ('is_active', '=', True)],
            limit=1,
        )
        if not page:
            return _json_error(404, f"Page '{page_key}' not found for app '{app.app_key}'")

        # ── Tabs ──────────────────────────────────────────────────────────
        tabs = page.tab_ids.filtered(lambda t: t.is_active).sorted('sequence')
        tabs_data = [
            {'id': t.id, 'key': t.key, 'name': t.name, 'sequence': t.sequence}
            for t in tabs
        ]

        # ── Filters + initial options ─────────────────────────────────────
        page_filters = request.env['dashboard.page.filter'].sudo().search(
            [('page_id', '=', page.id), ('is_active', '=', True)],
            order='sequence asc',
        )

        # Resolve accessible HHA IDs for scoped filters
        accessible_provider_ids = []
        if app.access_mode == 'hha_provider':
            providers = _get_providers_for_user(user)
            accessible_provider_ids = providers.ids

        # Default filter values (no URL params on config fetch)
        filter_values = {f.id: (f.default_value or '') for f in page_filters}

        # ── Build filter dependency graph (new system) ───────────────────
        dep_records = request.env['dashboard.filter.dependency'].sudo().search(
            [('page_id', '=', page.id)], order='sequence asc',
        )
        filter_dependencies = []
        for d in dep_records:
            # Resolve params with fallback — stored compute may be stale.
            src = d.source_filter_id
            tgt = d.target_filter_id
            src_param = (d.source_param
                         or src.param_name or src.field_name or '') if src else ''
            tgt_param = (d.target_param
                         or tgt.param_name or tgt.field_name or '') if tgt else ''
            filter_dependencies.append({
                'source_filter_id': src.id,
                'source_param':     src_param,
                'target_filter_id': tgt.id,
                'target_param':     tgt_param,
                'propagation':      d.propagation,
                'resets_target':    d.resets_target,
            })

        # Legacy filter_dep_map for backward compat
        filter_dep_map = {}
        filters_data = []
        for f in page_filters:
            eff_param = f.param_name or f.field_name or ''

            # Initial filter options — use new dependency graph for constraints
            options = []
            if f.manual_options or (f.model_id and f.field_id) or (f.schema_source_id and f.schema_column_id):
                # Build constraint_values from incoming dependencies with defaults
                constraint_values = {}
                for d in dep_records:
                    if d.target_filter_id.id == f.id:
                        src_val = filter_values.get(d.source_filter_id.id) or ''
                        if src_val:
                            constraint_values[d.source_filter_id.id] = src_val
                # Fall back to legacy depends_on_filter_id if no new deps
                if not constraint_values and f.depends_on_filter_id:
                    parent_val = filter_values.get(f.depends_on_filter_id.id) or None
                    if parent_val:
                        constraint_values[f.depends_on_filter_id.id] = parent_val
                pids = accessible_provider_ids if f.scope_to_user_hha else None
                options = f.get_options(
                    constraint_values=constraint_values or None,
                    provider_ids=pids,
                )

            # Legacy dependency map
            dep_field_name = (
                (f.depends_on_filter_id.param_name or f.depends_on_filter_id.field_name)
                if f.depends_on_filter_id else ''
            )
            if eff_param and dep_field_name:
                filter_dep_map[eff_param] = dep_field_name

            filters_data.append({
                'id':                    f.id,
                'name':                  f.display_label or f.field_name or f.param_name or '',
                'param_name':            f.param_name or f.field_name or '',
                'field_name':            f.field_name or '',
                'default_value':         f.default_value or '',
                'depends_on_filter_id':  f.depends_on_filter_id.id if f.depends_on_filter_id else None,
                'depends_on_field_name': dep_field_name or None,
                'options':               options,
                'sequence':              f.sequence,
                'scope_to_user_hha':     f.scope_to_user_hha,
                'auto_fill_from_hha':    f.auto_fill_from_hha,
                'placeholder':           f.placeholder or '',
                'is_multiselect':        f.is_multiselect,
                'is_searchable':         f.is_searchable,
                'is_visible':            f.is_visible,
                'include_all_option':    f.include_all_option,
            })

        # ── Widgets (metadata only) ───────────────────────────────────────
        widgets_raw = request.env['dashboard.widget'].sudo().search(
            [('page_id', '=', page.id), ('is_active', '=', True)],
            order='sequence asc',
        )
        widgets_data = []
        for w in widgets_raw:
            tab_key = w.tab_id.key if w.tab_id else None
            # Typography overrides (only include non-default values)
            typo = w._get_typography_overrides()

            wdata = {
                'id':           w.id,
                'name':         w.name,
                'chart_type':   w.chart_type,
                'col_span':     w.width_pct or {'3': 25, '4': 33, '6': 50, '8': 67, '12': 100}.get(w.col_span, 50),
                'max_col_span': w.max_width_pct or 0,
                'chart_height': w.chart_height,
                'tab_id':       w.tab_id.id if w.tab_id else None,
                'tab_key':      tab_key,
                'sequence':     w.sequence,
            }
            if typo:
                wdata.update(typo)
            widgets_data.append(wdata)

        # ── HHA selector (hha_provider apps only) ────────────────────────
        hha_selector = {'options': [], 'current_hha_id': 'all'}
        if app.access_mode == 'hha_provider' and accessible_provider_ids:
            providers = request.env['hha.provider'].sudo().browse(accessible_provider_ids)
            selector_options = []
            if len(providers) > 1:
                selector_options.append({
                    'id':       'all',
                    'label':    f'All {len(providers)} HHAs',
                    'selected': True,
                })
            for p in providers:
                display_name = p.hha_brand_name or p.hha_name
                ccn_label = f"{p.hha_ccn} - {display_name}" if p.hha_ccn else display_name
                selector_options.append({
                    'id':       p.id,
                    'label':    ccn_label,
                    'selected': len(providers) == 1,
                })
            hha_selector = {
                'options':        selector_options,
                'current_hha_id': 'all' if len(providers) > 1 else str(providers[0].id),
            }

        return _json_response({
            'page': {
                'id':   page.id,
                'key':  page.key,
                'name': page.name,
            },
            'app': {
                'id':            app.id,
                'key':           app.app_key,
                'name':          app.name,
                'primary_color': app.primary_color or '#0066cc',
                'tagline':       app.tagline or '',
            },
            'tabs':                tabs_data,
            'filters':             filters_data,
            'filter_dep_map':      filter_dep_map,
            'filter_dependencies': filter_dependencies,
            'widgets':             widgets_data,
            'hha_selector':        hha_selector,
        })

    # ------------------------------------------------------------------ #
    # GET /api/v1/widget/<widget_id>/data                                 #
    # ------------------------------------------------------------------ #
    @http.route(
        '/api/v1/widget/<int:widget_id>/data',
        type='http',
        auth='none',
        methods=['GET', 'OPTIONS'],
        csrf=False,
        readonly=True,
    )
    def api_widget_data(self, widget_id, **kw):
        """Return computed data for a single widget.

        Query parameters should match the page's filter field names, e.g.:
            ?hha_state=Arkansas&hha_county=Pulaski&year=2024&hha_id=123

        The computation is identical to QWeb rendering — only the delivery
        format changes (JSON vs QWeb context).

        Response shape:
            {
              "widget_id": <int>,
              "chart_type": "<type>",
              "data": {
                "echart_option": {...}   // for ECharts widget types
                -- or --
                "formatted_value": "...", "label": "..."  // for kpi / status_kpi
                -- or --
                "cols": [...], "rows": [[...]]  // for table
                -- etc --
              }
            }
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))

        # ── Load widget ───────────────────────────────────────────────────
        widget = request.env['dashboard.widget'].sudo().browse(widget_id)
        if not widget.exists() or not widget.is_active:
            return _json_error(404, f'Widget {widget_id} not found or inactive')

        # ── Access control: widget must belong to the JWT's app ───────────
        if widget.page_id.app_id.id != app.id:
            return _json_error(403, 'Widget does not belong to your app')

        # ── Build portal_ctx from query params ────────────────────────────
        try:
            portal_ctx = _build_portal_ctx(widget.page_id, user, app, kw)
        except Exception as exc:
            _logger.warning('api_widget_data: portal_ctx error widget=%s: %s', widget_id, exc)
            return _json_error(500, f'Context build error: {exc}')

        # ── Execute widget data logic (unchanged) ─────────────────────────
        raw_data = widget.get_portal_data(portal_ctx)

        # ── Normalise for JSON (parse echart_json string → echart_option dict)
        clean_data = _normalise_widget_data(raw_data)

        return _json_response({
            'widget_id':  widget.id,
            'chart_type': widget.chart_type,
            'data':       clean_data,
        })

    # ------------------------------------------------------------------ #
    # GET /api/v1/filters/cascade                                         #
    # ------------------------------------------------------------------ #
    @http.route(
        '/api/v1/filters/cascade',
        type='http',
        auth='none',
        methods=['GET', 'OPTIONS'],
        csrf=False,
        readonly=True,
    )
    def api_filters_cascade(self, **kw):
        """Return dynamic options for a cascade-dependent filter.

        Called by React when the parent filter value changes (e.g. State →
        County, County → Locations).

        Query parameters:
            filter_id     — ID of the dashboard.page.filter to refresh
            parent_value  — current value of the parent filter (e.g. 'Arkansas')

        Response:
            {"filter_id": <int>, "options": [{"value":"...", "label":"..."}, ...]}
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))

        filter_id_str = (kw.get('filter_id') or '').strip()
        parent_value  = (kw.get('parent_value') or '').strip() or None

        if not filter_id_str:
            return _json_error(400, 'filter_id is required')

        try:
            fid = int(filter_id_str)
        except ValueError:
            return _json_error(400, 'filter_id must be an integer')

        # ── Load filter ───────────────────────────────────────────────────
        f = request.env['dashboard.page.filter'].sudo().browse(fid)
        if not f.exists():
            return _json_error(404, f'Filter {fid} not found')

        # ── Access control: filter must belong to the JWT's app ───────────
        if f.page_id.app_id.id != app.id:
            return _json_error(403, 'Filter does not belong to your app')

        # ── Resolve provider_ids for scoped filters ───────────────────────
        provider_ids = None
        if f.scope_to_user_hha:
            accessible = _get_providers_for_user(user)
            provider_ids = accessible.ids or None

        # ── Fetch options (unchanged) ─────────────────────────────────────
        try:
            options = f.get_options(
                parent_value=parent_value,
                provider_ids=provider_ids,
            )
        except Exception as exc:
            _logger.warning('api_filters_cascade filter=%s error: %s', fid, exc)
            return _json_error(500, f'Options fetch error: {exc}')

        return _json_response({
            'filter_id': fid,
            'options':   options,
        })

    # ------------------------------------------------------------------ #
    # GET /api/v1/filters/cascade/multi                                    #
    # ------------------------------------------------------------------ #
    @http.route(
        '/api/v1/filters/cascade/multi',
        type='http',
        auth='none',
        methods=['GET', 'OPTIONS'],
        csrf=False,
        readonly=True,
    )
    def api_filters_cascade_multi(self, **kw):
        """Return dynamic options for a filter constrained by multiple sources.

        Called by React when any filter in a multi-directional dependency
        graph changes.

        Query parameters:
            filter_id    — ID of the target filter to refresh
            constraints  — JSON object: {"<source_filter_id>": "<value>", ...}

        Response:
            {"filter_id": <int>, "options": [{"value":"...", "label":"..."}, ...]}
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))

        filter_id_str = (kw.get('filter_id') or '').strip()
        constraints_json = (kw.get('constraints') or '').strip()
        all_values_json = (kw.get('all_values') or '').strip()

        if not filter_id_str:
            return _json_error(400, 'filter_id is required')

        try:
            fid = int(filter_id_str)
        except ValueError:
            return _json_error(400, 'filter_id must be an integer')

        # Parse constraints JSON
        constraint_values = None
        if constraints_json:
            try:
                raw = json.loads(constraints_json)
                if isinstance(raw, dict):
                    constraint_values = {
                        int(k): str(v) for k, v in raw.items()
                        if str(v).strip() and str(v).strip() != 'all'
                    }
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                return _json_error(400, f'Invalid constraints JSON: {exc}')

        # Parse all_values JSON (full filter state: {param_name: value})
        all_filter_values = None
        if all_values_json:
            try:
                raw_all = json.loads(all_values_json)
                if isinstance(raw_all, dict):
                    all_filter_values = {
                        str(k): str(v) for k, v in raw_all.items()
                        if str(v).strip() and str(v).strip() != 'all'
                    }
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                return _json_error(400, f'Invalid all_values JSON: {exc}')

        # ── Load filter ───────────────────────────────────────────────────
        f = request.env['dashboard.page.filter'].sudo().browse(fid)
        if not f.exists():
            return _json_error(404, f'Filter {fid} not found')

        # ── Access control ────────────────────────────────────────────────
        if f.page_id.app_id.id != app.id:
            return _json_error(403, 'Filter does not belong to your app')

        # ── Resolve provider_ids for scoped filters ───────────────────────
        provider_ids = None
        if f.scope_to_user_hha:
            accessible = _get_providers_for_user(user)
            provider_ids = accessible.ids or None

        # ── Fetch options ─────────────────────────────────────────────────
        _logger.info(
            '[CASCADE-API] cascade/multi: target_filter=%s(id=%s), '
            'constraint_values=%s, all_filter_values=%s, provider_ids=%s',
            f.display_label, fid, constraint_values, all_filter_values, provider_ids,
        )
        try:
            options = f.get_options(
                constraint_values=constraint_values,
                provider_ids=provider_ids,
                all_filter_values=all_filter_values,
            )
        except Exception as exc:
            _logger.warning('api_filters_cascade_multi filter=%s error: %s', fid, exc)
            return _json_error(500, f'Options fetch error: {exc}')

        _logger.info('[CASCADE-API] cascade/multi: filter=%s returned %d options', fid, len(options))
        return _json_response({
            'filter_id': fid,
            'options':   options,
        })

    # ------------------------------------------------------------------ #
    # POST /api/v1/filters/resolve                                        #
    # ------------------------------------------------------------------ #
    @http.route(
        '/api/v1/filters/resolve',
        type='http',
        auth='none',
        methods=['POST', 'OPTIONS'],
        csrf=False,
        readonly=True,
    )
    def api_filters_resolve(self, **kw):
        """Batch-resolve the full cascade DAG in a single round-trip.

        Instead of the frontend making N sequential HTTP calls (one per
        cascade tier), this endpoint accepts the changed filter + current
        state and walks the entire dependency graph server-side.

        Request body (JSON):
            {
              "page_id": <int>,
              "changed_filter_id": <int>,
              "changed_value": "<str>",
              "current_values": { "<param_name>": "<value>", ... }
            }

        Response:
            {
              "updated_filters": {
                "<filter_id>": {
                  "param_name": "<str>",
                  "options": [{"value":"...", "label":"..."}, ...],
                  "new_value": "<str>",
                  "value_changed": true|false
                },
                ...
              }
            }
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))

        # Parse JSON body
        try:
            body = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except json.JSONDecodeError as exc:
            return _json_error(400, f'Invalid JSON body: {exc}')

        page_id = body.get('page_id')
        changed_filter_id = body.get('changed_filter_id')
        changed_value = body.get('changed_value', '')
        current_values = body.get('current_values', {})

        if not page_id or not changed_filter_id:
            return _json_error(400, 'page_id and changed_filter_id are required')

        try:
            page_id = int(page_id)
            changed_filter_id = int(changed_filter_id)
        except (ValueError, TypeError):
            return _json_error(400, 'page_id and changed_filter_id must be integers')

        # ── Load page and validate access ──────────────────────────────────
        page = request.env['dashboard.page'].sudo().browse(page_id)
        if not page.exists() or page.app_id.id != app.id:
            return _json_error(404, 'Page not found or access denied')

        # ── Load all dependencies for this page ────────────────────────────
        deps = request.env['dashboard.filter.dependency'].sudo().search([
            ('page_id', '=', page_id),
        ])

        # Build adjacency: source_id → [(target_id, edge)]
        source_to_targets = {}
        target_to_sources = {}
        filters_on_page = {}

        page_filters = page.filter_ids
        for f in page_filters:
            filters_on_page[f.id] = f

        for dep in deps:
            sid = dep.source_filter_id.id
            tid = dep.target_filter_id.id
            source_to_targets.setdefault(sid, []).append({
                'target_id': tid,
                'propagation': dep.propagation,
                'resets_target': dep.resets_target,
            })
            target_to_sources.setdefault(tid, []).append({
                'source_id': sid,
                'source_param': dep.source_param,
            })

        # ── Update snapshot with changed value ──────────────────────────────
        changed_filter = filters_on_page.get(changed_filter_id)
        if not changed_filter:
            return _json_error(404, f'Filter {changed_filter_id} not found on page')

        snapshot = dict(current_values)
        changed_param = changed_filter.param_name or changed_filter.field_name
        snapshot[changed_param] = changed_value

        # Pre-clear targets with resets_target=True so that stale values
        # don't leak into all_filter_values as sibling WHERE constraints.
        # Without this, changing Provider would send old State/County/City
        # values, artificially restricting cascade results.
        for edge in source_to_targets.get(changed_filter_id, []):
            if edge['resets_target']:
                tf = filters_on_page.get(edge['target_id'])
                if tf:
                    tp = tf.param_name or tf.field_name
                    if tp and snapshot.get(tp):
                        snapshot[tp] = ''

        # ── Walk DAG using BFS (Kahn's-inspired) ───────────────────────────
        updated_filters = {}
        visited = {changed_filter_id}
        queue = [changed_filter_id]  # BFS queue

        _logger.info(
            '[RESOLVE] START: page=%s, changed=%s(id=%s), value="%s"',
            page_id, changed_param, changed_filter_id, changed_value,
        )

        while queue:
            current_id = queue.pop(0)
            targets = source_to_targets.get(current_id, [])

            for edge in targets:
                tid = edge['target_id']
                if tid in visited:
                    continue  # cycle/revisit prevention

                target_filter = filters_on_page.get(tid)
                if not target_filter:
                    continue

                target_param = target_filter.param_name or target_filter.field_name

                # Check optional propagation: skip if target has value
                if edge['propagation'] == 'optional':
                    current_target_val = snapshot.get(target_param, '')
                    if current_target_val and current_target_val != 'all':
                        continue

                visited.add(tid)

                # Build constraints from ALL sources of this target
                sources = target_to_sources.get(tid, [])
                constraint_values = {}
                for src in sources:
                    src_param = src['source_param']
                    val = snapshot.get(src_param, '')
                    if val and val != 'all':
                        constraint_values[src['source_id']] = val

                # Build all_filter_values from snapshot
                all_filter_values = {
                    k: v for k, v in snapshot.items()
                    if v and v != 'all'
                }

                # Resolve provider_ids for scoped filters
                provider_ids = None
                if target_filter.scope_to_user_hha:
                    accessible = _get_providers_for_user(user)
                    provider_ids = accessible.ids or None

                # Fetch options
                try:
                    options = target_filter.get_options(
                        constraint_values=constraint_values,
                        provider_ids=provider_ids,
                        all_filter_values=all_filter_values,
                    )
                except Exception as exc:
                    _logger.warning(
                        '[RESOLVE] filter=%s(id=%s) get_options error: %s',
                        target_param, tid, exc,
                    )
                    options = []

                # Determine new value (same logic as FilterBar.jsx)
                old_value = snapshot.get(target_param, '')
                new_value = old_value
                value_changed = False

                if edge['resets_target']:
                    if len(options) == 1 and not target_filter.include_all_option:
                        new_value = options[0]['value']
                    else:
                        new_value = ''
                    value_changed = (new_value != old_value)
                else:
                    # Keep value if still valid
                    if old_value and options:
                        valid_values = {o['value'] for o in options}
                        if target_filter.is_multiselect and ',' in old_value:
                            kept = [v for v in old_value.split(',')
                                    if v.strip() in valid_values]
                            pruned = ','.join(kept)
                            if pruned != old_value:
                                new_value = pruned
                                value_changed = True
                        else:
                            if old_value not in valid_values:
                                new_value = ''
                                value_changed = True

                snapshot[target_param] = new_value

                # Pre-clear this target's own reset-targets too (recursive)
                for child_edge in source_to_targets.get(tid, []):
                    if child_edge['resets_target']:
                        child_f = filters_on_page.get(child_edge['target_id'])
                        if child_f:
                            child_p = child_f.param_name or child_f.field_name
                            if child_p and snapshot.get(child_p):
                                snapshot[child_p] = ''

                updated_filters[str(tid)] = {
                    'param_name': target_param,
                    'options': options,
                    'new_value': new_value,
                    'value_changed': value_changed,
                }

                # Enqueue this target so its children get processed next
                queue.append(tid)

        _logger.info(
            '[RESOLVE] END: updated %d filters: %s',
            len(updated_filters),
            [f'{v["param_name"]}={v["new_value"]}' for v in updated_filters.values()],
        )

        return _json_response({'updated_filters': updated_filters})

    # ------------------------------------------------------------------ #
    # POST /api/v1/filter-state/save                                      #
    # ------------------------------------------------------------------ #
    @http.route(
        '/api/v1/filter-state/save',
        type='http',
        auth='none',
        methods=['POST', 'OPTIONS'],
        csrf=False,
    )
    def api_filter_state_save(self, **kw):
        """Save filter state and return a short permalink key.

        Request body (JSON):
            {
              "page_id": <int>,
              "filter_config": { "<param_name>": "<value>", ... }
            }

        Response:
            { "key": "a3f8b2c1d4e5" }
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))

        try:
            body = json.loads(request.httprequest.get_data(as_text=True) or '{}')
        except json.JSONDecodeError as exc:
            return _json_error(400, f'Invalid JSON body: {exc}')

        page_id = body.get('page_id')
        filter_config = body.get('filter_config', {})

        if not page_id:
            return _json_error(400, 'page_id is required')
        if not isinstance(filter_config, dict):
            return _json_error(400, 'filter_config must be a JSON object')

        try:
            page_id = int(page_id)
        except (ValueError, TypeError):
            return _json_error(400, 'page_id must be an integer')

        # Validate page belongs to user's app
        page = request.env['dashboard.page'].sudo().browse(page_id)
        if not page.exists() or page.app_id.id != app.id:
            return _json_error(404, 'Page not found or access denied')

        key = request.env['dashboard.filter.state'].sudo().save_state(
            app_id=app.id,
            page_id=page_id,
            filter_config=filter_config,
            user_id=user.id,
        )

        return _json_response({'key': key})

    # ------------------------------------------------------------------ #
    # GET /api/v1/filter-state/load                                       #
    # ------------------------------------------------------------------ #
    @http.route(
        '/api/v1/filter-state/load',
        type='http',
        auth='none',
        methods=['GET', 'OPTIONS'],
        csrf=False,
        readonly=True,
    )
    def api_filter_state_load(self, **kw):
        """Load filter state by permalink key.

        Query parameters:
            key — the permalink token

        Response:
            { "filter_config": { "<param_name>": "<value>", ... } }
            or { "filter_config": {} } if not found/expired.
        """
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})

        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _json_error(401, str(exc))

        key = (kw.get('key') or '').strip()
        if not key:
            return _json_error(400, 'key is required')

        # Scope by app_id to prevent cross-app state leakage
        config = request.env['dashboard.filter.state'].sudo().load_state(
            key, app_id=app.id)

        return _json_response({'filter_config': config})
