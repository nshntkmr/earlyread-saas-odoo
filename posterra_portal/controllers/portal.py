# -*- coding: utf-8 -*-

import json
import logging
import time as _time

import odoo.exceptions

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.web.controllers.utils import ensure_db
from odoo.http import request, route

_logger = logging.getLogger(__name__)


# ── Admin check helper ────────────────────────────────────────────────────────

def _is_dashboard_admin(user):
    """Check if user is a dashboard admin. Fault-tolerant for missing groups."""
    if user.has_group('base.group_system'):
        return True
    try:
        return user.has_group('dashboard_builder.group_dashboard_builder_admin')
    except (ValueError, Exception):
        return False


# ── Phase 7: React shell helpers ──────────────────────────────────────────────

def _make_portal_access_token(user, app):
    """Generate a short-lived JWT for the current Odoo session user.

    Embeds the token in the QWeb shell so React can call the JSON API
    (Phase 6) for filter-driven widget refetches without a separate login.
    """
    from .auth_api import _make_token, ACCESS_TOKEN_TTL
    now = int(_time.time())
    return _make_token({
        'type':    'access',
        'user_id': user.id,
        'app_id':  app.id,
        'app_key': app.app_key,
        'exp':     now + ACCESS_TOKEN_TTL,
        'iat':     now,
    })


def _build_page_config_json(app, page, tabs, page_filters, filter_options,
                             filter_dep_map_json, current_tab_key,
                             filter_values=None):
    """Serialise page configuration as JSON for the data-page-config attribute."""
    # Build filter dependency graph (new multi-directional system).
    env = page.env
    dep_records = env['dashboard.filter.dependency'].sudo().search(
        [('page_id', '=', page.id)], order='sequence asc',
    )
    filter_dependencies = []
    for d in dep_records:
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

    return json.dumps({
        'app': {
            'id':            app.id,
            'key':           app.app_key,
            'name':          app.name,
            'primary_color': app.primary_color or '#0066cc',
            'tagline':       app.tagline or '',
            'access_mode':   app.access_mode,
        },
        'page': {
            'id':   page.id,
            'key':  page.key,
            'name': page.name,
        },
        'tabs': [
            {'id': t.id, 'key': t.key, 'name': t.name, 'sequence': t.sequence}
            for t in tabs
        ],
        'current_tab_key': current_tab_key or '',
        'filters': [
            {
                'id':                    pf.id,
                'field_name':            pf.field_name or pf.param_name or '',
                'param_name':            pf.param_name or pf.field_name or '',
                # display_label = label override → field description → field_name
                'name':                  pf.display_label or pf.field_name or '',
                'default_value':         (filter_values or {}).get(pf.id, pf.default_value or ''),
                'depends_on_filter_id':  pf.depends_on_filter_id.id if pf.depends_on_filter_id else None,
                # Use param_name for cascade matching (React uses param_name as state key)
                'depends_on_field_name': (
                    pf.depends_on_filter_id.param_name
                    or pf.depends_on_filter_id.field_name
                ) if pf.depends_on_filter_id else None,
                'scope_to_user_hha':     pf.scope_to_user_hha,
                'include_all_option':    pf.include_all_option,
                'is_provider_selector': pf.is_provider_selector,
                'is_visible':            pf.is_visible,
                'is_multiselect':        pf.is_multiselect,
                'is_searchable':         pf.is_searchable,
                'options':               filter_options.get(pf.id, []),
                'sequence':              pf.sequence,
            }
            for pf in page_filters
        ],
        'filter_dep_map': json.loads(filter_dep_map_json or '{}'),
        'filter_dependencies': filter_dependencies,
    }, default=str)


def _extract_vc_field(widget, field, default=''):
    """Extract a field from widget.visual_config JSON, with fallback."""
    try:
        vc = json.loads(widget.visual_config or '{}') or {}
        return vc.get(field, default)
    except (json.JSONDecodeError, TypeError, AttributeError):
        return default


def _build_initial_widgets_json(widgets, widget_data):
    """Serialise initial widget data as JSON for the data-initial-widgets attribute.

    Normalises echart_json string → echart_option dict so React's EChartWidget
    can call setOption() directly without a JSON.parse() call.
    """
    result = {}
    for w in widgets:
        wd = dict(widget_data.get(w.id, {}))
        # Normalise echart_json string → echart_option dict
        if 'echart_json' in wd and isinstance(wd.get('echart_json'), str):
            try:
                wd['echart_option'] = json.loads(wd.pop('echart_json'))
            except Exception:
                wd.pop('echart_json', None)
        # Use SQL-resolved annotations when available (from _interpolate_annotations),
        # falling back to the static admin-configured values.
        resolved_subtitle = wd.pop('_resolved_subtitle', '') or w.subtitle or ''
        resolved_footnote = wd.pop('_resolved_footnote', '') or w.footnote or ''
        resolved_annotation_text = wd.pop('_resolved_annotation_text', '') or w.annotation_text or ''

        result[str(w.id)] = {
            'id':           w.id,
            'chart_type':   w.chart_type,
            'tab_key':      w.tab_id.key if w.tab_id else None,
            'col_span':     w.width_pct or {'3': 25, '4': 33, '6': 50, '8': 67, '12': 100}.get(w.col_span, 50),
            'max_col_span': w.max_width_pct or 0,
            'height':       w.chart_height,
            'name':         w.name,
            'sequence':     w.sequence,
            'display_mode': w.display_mode or 'standard',
            'display_density': _extract_vc_field(w, 'display_density', 'standard'),
            'card_padding': _extract_vc_field(w, 'card_padding', 'standard'),
            'icon_name':    w.icon_name or 'none',
            'icon_position': w.icon_position or 'title',
            'title_icon_color': w._resolve_title_icon_color(),
            'title_text_color': w._resolve_title_text_color(),
            # Annotations (SQL-interpolated when %(col)s syntax used)
            'subtitle':           resolved_subtitle,
            'footnote':           resolved_footnote,
            'annotation_type':    w.annotation_type or 'none',
            'annotation_text':    resolved_annotation_text,
            'annotation_position': w.annotation_position or 'top_right',
            'data':         wd,
        }
    return json.dumps(result, default=str)


def _build_initial_sections_json(page_sections, section_data):
    """Serialise section config + initial data as JSON for React."""
    result = {}
    for sec in page_sections:
        sd = section_data.get(sec.id, {})
        # Build scope config
        scope = {'mode': sec.scope_mode or 'none'}
        if sec.scope_mode == 'dependent' and sec.scope_filter_id:
            pf = sec.scope_filter_id
            scope['filter_param'] = pf.param_name or pf.field_name or ''
            scope['filter_id'] = pf.id
            scope['label'] = sec.scope_label or pf.display_label or pf.field_name or ''
            scope['default_value'] = sec.scope_default_value or ''
            scope['param_name'] = pf.param_name or pf.field_name or ''
            scope['options'] = []  # React reads from pageConfig.filters
        elif sec.scope_mode == 'independent':
            scope['label'] = sec.scope_label or sec.scope_value_column or ''
            scope['default_value'] = sec.scope_default_value or ''
            scope['param_name'] = sec.scope_param_name or ''
            scope['options'] = sec.get_scope_options()
        result[str(sec.id)] = {
            'id':           sec.id,
            'name':         sec.name,
            'icon':         sec.icon or 'fa-star-o',
            'section_type': sec.section_type,
            'tab_key':      sec.tab_id.key if sec.tab_id else '',
            'action_label': sec.action_label or '',
            'subtitle':     sec.subtitle or '',
            'description':  sec.description or '',
            'footnote':     sec.footnote or '',
            'max_rows':     sec.max_rows or 0,
            'sequence':     sec.sequence,
            'scope':        scope,
            'data':         sd,
        }
    return json.dumps(result, default=str)


def _get_providers_for_user(user):
    """Find HHA providers for a portal user.

    Stage 1 — Direct assignment:
        If the user's partner has hha_provider_id set, return that provider.
        Admin sets it via Contacts form → HHA Provider field or
        HHA Provider form → Associated Users tab.

    Stage 2 — Scope Group:
        If no direct assignment, check for a scope group on the partner.
        The scope group contains a pre-resolved Many2many of providers
        determined by column + value matching (configured by admin).

    Returns a recordset of hha.provider records (may be empty).
    """
    partner = user.partner_id.sudo()
    if partner.hha_provider_id:
        # Stage 1: admin explicitly assigned this user to a single provider
        return request.env['hha.provider'].sudo().browse(partner.hha_provider_id.id)
    # Stage 2: scope group → multiple providers
    if partner.hha_scope_group_id and partner.hha_scope_group_id.provider_ids:
        return partner.hha_scope_group_id.sudo().provider_ids
    return request.env['hha.provider'].browse()  # empty recordset


class PosterraPortal(CustomerPortal):

    # ------------------------------------------------------------------ #
    # SESSION-BASED TOKEN REFRESH                                         #
    # Called by React when the JWT is about to expire or after a 401.     #
    # Uses the Odoo session cookie (auth='user') — no refresh token       #
    # needed.  Returns a fresh 1-hour access token.                       #
    # ------------------------------------------------------------------ #
    @route('/api/v1/auth/session-refresh', type='http', auth='user',
           methods=['POST'], csrf=False)
    def session_refresh_token(self, **kw):
        """Issue a fresh JWT access token for the current session user.

        The Odoo session cookie authenticates the request, so no
        refresh token is required.  React calls this proactively
        before the current token expires (and as a 401 fallback).
        """
        from .auth_api import _json_response, _json_error, ACCESS_TOKEN_TTL

        user = request.env.user
        if not user or user._is_public():
            return _json_error(401, 'Not authenticated')

        # Resolve the app from the query param or auto-detect
        app_key = (kw.get('app_key') or '').strip()
        app = None
        if app_key:
            app = request.env['saas.app'].sudo().search(
                [('app_key', '=', app_key), ('is_active', '=', True)], limit=1,
            )
        if not app:
            # Auto-detect: same logic as home()
            group_apps = request.env['saas.app'].sudo().search(
                [('access_mode', '=', 'group'), ('is_active', '=', True)],
                order='id asc',
            )
            for ga in group_apps:
                if ga.access_group_xmlid and user.has_group(ga.access_group_xmlid):
                    app = ga
                    break
            if not app:
                providers = _get_providers_for_user(user)
                if providers:
                    app = request.env['saas.app'].sudo().search(
                        [('access_mode', '=', 'hha_provider'), ('is_active', '=', True)],
                        limit=1,
                    )
        if not app:
            return _json_error(403, 'No accessible app found for this user')

        token = _make_portal_access_token(user, app)
        return _json_response({
            'access_token': token,
            'token_type':   'Bearer',
            'expires_in':   ACCESS_TOKEN_TTL,
        })

    # ------------------------------------------------------------------ #
    # AJAX: return filtered options for a dependent filter                #
    # Called by the cascade JS when a parent filter changes so the child  #
    # dropdown is rebuilt dynamically without a full page reload.         #
    # ------------------------------------------------------------------ #
    @route('/posterra/filter_options', type='jsonrpc', auth='user', methods=['POST'])
    def posterra_filter_options(self, filter_id, parent_value=None, **kw):
        """Return {options: [{value, label}, ...]} for a given filter record.

        parent_value is the currently-selected value of the parent filter
        (e.g. 'Illinois').  Passed to get_options() which applies a domain
        filter when the parent and child share the same model.

        When the filter has scope_to_user_hha=True, provider_ids is resolved
        server-side from the current user's email domain — no client-supplied
        IDs are needed (and client-supplied values cannot be trusted).
        """
        try:
            f = request.env['dashboard.page.filter'].sudo().browse(int(filter_id))
            if not f.exists():
                return {'options': [], 'error': 'Filter not found'}

            # Resolve the accessible HHA IDs for the current user so that
            # HHA-scoped filters (scope_to_user_hha=True) query only the user's
            # own providers.  This runs server-side and is not controllable by
            # the browser — the client only sends parent_value.
            provider_ids = None
            if f.scope_to_user_hha:
                accessible = _get_providers_for_user(request.env.user)
                provider_ids = accessible.ids or None
                _logger.debug(
                    'posterra_filter_options filter=%s scope=hha providers=%d',
                    filter_id, len(provider_ids) if provider_ids else 0,
                )

            options = f.get_options(
                parent_value=parent_value or None,
                provider_ids=provider_ids,
            )
            return {'options': options}
        except Exception as exc:
            _logger.warning('posterra_filter_options id=%s error: %s', filter_id, exc)
            return {'options': [], 'error': str(exc)}

    @route()
    def home(self, **kw):
        """Override /my and /my/home: redirect Posterra users to the right portal.

        Priority:
          1. Group-based apps (e.g. MSSP) — checked in saas.app order
          2. HHA-provider apps (e.g. Posterra) — requires provider match
          3. No match → standard Odoo /my page
        """
        user = request.env.user

        # Check group-based apps first so those users are never matched as HHA
        group_apps = request.env['saas.app'].sudo().search(
            [('access_mode', '=', 'group'), ('is_active', '=', True)],
            order='id asc',
        )
        for app in group_apps:
            if app.access_group_xmlid and user.has_group(app.access_group_xmlid):
                return request.redirect('/my/%s' % app.app_key)

        # HHA flow: direct assignment (Stage 1) or scope group (Stage 2)
        providers = _get_providers_for_user(user)
        if providers:
            hha_app = request.env['saas.app'].sudo().search(
                [('access_mode', '=', 'hha_provider'), ('is_active', '=', True)],
                limit=1,
            )
            if hha_app:
                return request.redirect('/my/%s' % hha_app.app_key)
            return request.redirect('/my/posterra')  # safe fallback

        return super().home(**kw)

    # ------------------------------------------------------------------ #
    # GENERIC DASHBOARD ROUTE (Phase 5)                                   #
    # Replaces the two hardcoded /my/posterra and /my/mssp routes.        #
    # Any registered saas.app with a matching app_key is served here.    #
    # ------------------------------------------------------------------ #
    @route([
        '/my/<string:app_key>',
        '/my/<string:app_key>/<string:page_key>',
        '/my/<string:app_key>/<string:page_key>/<string:tab_key>',
    ], type='http', auth='user', website=True)
    def app_dashboard(self, app_key, page_key=None, tab_key=None, **kw):
        """Generic portal dashboard for any registered saas.app.

        1. Resolve the app from the URL's app_key.
        2. Check access (HHA provider or security group).
        3. Load pages scoped to this app via app_id.
        4. Run the full filter / widget / section pipeline.
        5. Render posterra_portal.dashboard with an 'app' value in context.
        """

        # ── 1. Resolve app ─────────────────────────────────────────────
        app = request.env['saas.app'].sudo().search(
            [('app_key', '=', app_key), ('is_active', '=', True)], limit=1,
        )
        if not app:
            return request.redirect('/my')

        # ── 2. Access check ────────────────────────────────────────────
        providers = request.env['hha.provider'].sudo().browse()  # empty default

        # System admins and dashboard builder admins bypass access checks
        is_superadmin = _is_dashboard_admin(request.env.user)

        if app.access_mode == 'hha_provider':
            providers = _get_providers_for_user(request.env.user)
            if not providers and not is_superadmin:
                return request.redirect('/my')
        elif app.access_mode == 'group':
            if not is_superadmin and (
                not app.access_group_xmlid
                or not request.env.user.has_group(app.access_group_xmlid)
            ):
                return request.redirect('/my')

        # ── 4. Pages scoped to this app ────────────────────────────────
        pages = request.env['dashboard.page'].sudo().search(
            [('app_id', '=', app.id), ('is_active', '=', True)],
            order='sequence asc',
        )

        # ── 5. Sidebar nav sections ────────────────────────────────────
        nav_sections = request.env['dashboard.nav.section'].sudo().search(
            [('is_active', '=', True)], order='sequence asc'
        )
        sections_with_pages = []
        for ns in nav_sections:
            ns_pages = pages.filtered(lambda p: p.nav_section_id.id == ns.id)
            if ns_pages:
                sections_with_pages.append({'section': ns, 'pages': ns_pages})

        # ── 6. Current page / tab ──────────────────────────────────────
        effective_page_key = page_key or app.default_page_key or 'overview'
        matched = pages.filtered(lambda p: p.key == effective_page_key)
        if matched:
            current_page = matched[0]
        else:
            current_page = pages[0] if pages else None
            effective_page_key = current_page.key if current_page else effective_page_key

        tabs = (
            current_page.tab_ids.filtered(lambda t: t.is_active).sorted('sequence')
            if current_page else request.env['dashboard.page.tab']
        )
        current_tab_key = tab_key or (tabs[0].key if tabs else None)
        if current_tab_key and tabs:
            if current_tab_key not in tabs.mapped('key'):
                current_tab_key = tabs[0].key

        current_tab_name = ''
        for tab in tabs:
            if tab.key == current_tab_key:
                current_tab_name = tab.name
                break

        # ── 7. Page filters ───────────────────────────────────────────
        page_filters = (
            request.env['dashboard.page.filter'].sudo().search([
                ('page_id.key', '=', effective_page_key),
                ('is_active', '=', True),
            ], order='sequence asc')
            if current_page
            else request.env['dashboard.page.filter']
        )

        # ── 7b. Permalink resolution ─────────────────────────────────
        # If ?state=<key> is in the URL, load the saved filter config
        # and merge into kw (URL params override permalink values).
        # Scoped by app_id to prevent cross-app state injection.
        permalink_key = kw.pop('state', None)
        if permalink_key:
            saved_config = request.env['dashboard.filter.state'].sudo().load_state(
                permalink_key.strip(), app_id=app.id)
            if saved_config:
                # Permalink values are defaults; explicit URL params take priority
                for k, v in saved_config.items():
                    if k not in kw:
                        kw[k] = v

        # ── 8. Provider resolution (generic — reads param from filter config) ──
        # Now that page_filters are loaded, we can dynamically discover which
        # URL param and field the Provider filter uses (no hardcoded field names).
        selected_provider = None
        org_display_name = ''
        current_hha_id = ''

        # Find the Provider filter for this page (admin marks it via is_provider_selector)
        provider_filter = page_filters.filtered(
            lambda f: f.is_provider_selector
        ) if (app.access_mode == 'hha_provider' and providers) else None

        matched_providers = None  # All providers matching URL param (for multi-select auto-fill)
        if app.access_mode == 'hha_provider' and providers:
            if len(providers) == 1:
                selected_provider = providers[0]
                matched_providers = providers
            elif provider_filter:
                pf = provider_filter[0]
                pf_param = pf.param_name or pf.field_name or ''
                # For matching against hha.provider ORM records, prefer:
                # 1. field_name (ORM field), 2. schema_column_name (DB column
                #    which often matches ORM field name), 3. param_name (URL key)
                pf_field = pf.field_name or pf.schema_column_name or pf.param_name or ''
                pf_value = (kw.get(pf_param) or '').strip()

                if pf_value and pf_value != 'all' and pf_field:
                    # Split CSV for multi-select (e.g. "047114,077163")
                    val_list = [v.strip() for v in pf_value.split(',') if v.strip()]

                    if pf_field == 'id':
                        try:
                            id_set = {int(v) for v in val_list}
                            matched_providers = providers.filtered(
                                lambda p, ids=id_set: p.id in ids)
                        except (ValueError, TypeError):
                            pass
                    else:
                        val_set = set(val_list)
                        matched_providers = providers.filtered(
                            lambda p, fld=pf_field, vals=val_set:
                                str(getattr(p, fld, '')) in vals)

                    # Single match → use as selected_provider (existing behavior)
                    if matched_providers and len(matched_providers) == 1:
                        selected_provider = matched_providers[0]

            org_display_name = (
                providers[0].hha_dba or providers[0].hha_name or ''
            ).upper()

            # Derive current_hha_id from whichever param the Provider filter uses
            pf_param_name = (
                (provider_filter[0].param_name or provider_filter[0].field_name or '')
                if provider_filter else ''
            )
            current_hha_id = (kw.get(pf_param_name) or '').strip() if pf_param_name else ''
            if not current_hha_id and len(providers) == 1:
                current_hha_id = str(providers[0].id)

        # ── 9. Geo data (hha_provider apps only) ─────────────────────
        provider_geo_data = {}
        provider_map = {}

        if app.access_mode == 'hha_provider' and providers:
            geo_provider_ids = (
                matched_providers.ids if matched_providers
                else ([selected_provider.id] if selected_provider else providers.ids)
            )
            geo_records = request.env['hha.provider'].sudo().browse(geo_provider_ids).read(
                ['id', 'hha_state', 'hha_county', 'hha_city']
            )
            for rec in geo_records:
                state  = (rec.get('hha_state')  or '').strip()
                county = (rec.get('hha_county') or '').strip()
                city   = (rec.get('hha_city')   or '').strip()
                if not state:
                    continue
                if state not in provider_geo_data:
                    provider_geo_data[state] = {}
                if county not in provider_geo_data[state]:
                    provider_geo_data[state][county] = []
                if city and city not in provider_geo_data[state][county]:
                    provider_geo_data[state][county].append(city)
            for state_data in provider_geo_data.values():
                for county_key in state_data:
                    state_data[county_key] = sorted(state_data[county_key])

            all_provider_records = request.env['hha.provider'].sudo().browse(
                providers.ids
            ).read(['id', 'hha_state', 'hha_county', 'hha_city'])
            for rec in all_provider_records:
                provider_map[str(rec['id'])] = {
                    'state':  (rec.get('hha_state')  or '').strip(),
                    'county': (rec.get('hha_county') or '').strip(),
                    'city':   (rec.get('hha_city')   or '').strip(),
                }

        # Auto-fill from selected HHA (hha_provider apps only)
        # Use the actual ORM field_name for getattr, but store under param_name
        # (or field_name) so the key matches URL params and SQL placeholders.
        # Supports multi-provider: auto-fill only when ALL matched providers
        # share the same value for a field; otherwise leave as "All".
        hha_auto_fill = {}
        auto_fill_source = matched_providers if matched_providers else (
            providers[:1] if selected_provider else None
        )
        if auto_fill_source:
            for f in page_filters:
                if f.auto_fill_from_hha:
                    actual_field = f.field_name or f.param_name or f.schema_column_name or ''
                    param_key = f.param_name or f.field_name or ''
                    if actual_field and param_key:
                        values = set()
                        for p in auto_fill_source:
                            if hasattr(p, actual_field):
                                val = str(getattr(p, actual_field, '') or '').strip()
                                if val:
                                    values.add(val)
                        if len(values) == 1:
                            # All providers share same value → auto-fill
                            hha_auto_fill[param_key] = values.pop()
                        # else: different values or empty → leave as "All"

        filter_values = {}
        for f in page_filters:
            eff_param = f.param_name or f.field_name or ''
            if eff_param:
                url_val  = (kw.get(eff_param) or '').strip()
                auto_val = hha_auto_fill.get(eff_param, '')
                # For auto-fill filters, prefer the server-derived value
                # over any stale URL value that may have leaked from the client.
                if f.auto_fill_from_hha and auto_val:
                    filter_values[f.id] = auto_val
                elif url_val or auto_val:
                    filter_values[f.id] = url_val or auto_val
                elif (f.default_strategy or 'static') != 'static':
                    # Dynamic default — needs options; defer to second pass
                    filter_values[f.id] = '__DEFERRED__'
                else:
                    filter_values[f.id] = f.default_value or ''
            else:
                if (f.default_strategy or 'static') != 'static':
                    filter_values[f.id] = '__DEFERRED__'
                else:
                    filter_values[f.id] = f.default_value or ''

        # Geo context is NOT extracted separately — filter values already flow
        # through filter_values_by_name / sql_params to widgets and annotations
        # via their param_name (e.g. %(hha_state)s). No special geo handling needed.

        accessible_provider_ids = providers.ids if providers else []

        # Load dependency graph for constraint-aware option building
        dep_records = request.env['dashboard.filter.dependency'].sudo().search(
            [('page_id', '=', current_page.id)], order='sequence asc',
        )

        # ── Early-resolve deferred defaults for ROOT filters (no parents) ────
        # Root filters have no parent dependencies, so their options need no
        # constraints.  Resolve them first so child filters can use their
        # real values as constraints instead of the '__DEFERRED__' sentinel.
        #
        # NOTE: In bidirectional (cyclic) dependency graphs, ALL filters are
        # targets, so this loop resolves zero filters.  This is correct — on
        # first login all constraints are '__DEFERRED__' (skipped by the main
        # filter_options loop below), so every filter gets unfiltered options,
        # and compute_default_value() runs in the post-loop phase.
        filters_that_are_targets = set()
        for d in dep_records:
            filters_that_are_targets.add(d.target_filter_id.id)

        filter_options = {}
        for f in page_filters:
            if filter_values.get(f.id) == '__DEFERRED__' and f.id not in filters_that_are_targets:
                pids = accessible_provider_ids if f.scope_to_user_hha else None
                root_opts = f.get_options(provider_ids=pids)
                filter_options[f.id] = root_opts
                filter_values[f.id] = f.compute_default_value(root_opts)

        for f in page_filters:
            if f.manual_options or (f.model_id and f.field_id) or (f.schema_source_id and f.schema_column_id):
                # Build constraint_values from incoming dependencies (new system)
                constraint_values = {}
                for d in dep_records:
                    if d.target_filter_id.id == f.id:
                        src_val = filter_values.get(d.source_filter_id.id) or ''
                        if src_val and src_val != '__DEFERRED__':
                            constraint_values[d.source_filter_id.id] = src_val
                # Fall back to legacy depends_on_filter_id if no new deps
                if not constraint_values and f.depends_on_filter_id:
                    parent_val = filter_values.get(f.depends_on_filter_id.id) or None
                    if parent_val and parent_val != '__DEFERRED__':
                        constraint_values[f.depends_on_filter_id.id] = parent_val
                pids = accessible_provider_ids if f.scope_to_user_hha else None
                filter_options[f.id] = f.get_options(
                    constraint_values=constraint_values or None,
                    provider_ids=pids,
                )

        # Auto-select filters with exactly 1 cascaded option (no "All" option).
        # Handles: multi-CCN URLs where all providers share the same state,
        # or any cascade scenario where only one value is valid.
        for f in page_filters:
            if not f.include_all_option and f.id in filter_options:
                opts = filter_options[f.id]
                fval = filter_values.get(f.id, '')
                if not fval and len(opts) == 1:
                    filter_values[f.id] = opts[0]['value']

        # ── Resolve deferred dynamic defaults (need filter_options) ──────
        for f in page_filters:
            if filter_values.get(f.id) == '__DEFERRED__':
                opts = filter_options.get(f.id, [])
                filter_values[f.id] = f.compute_default_value(opts)

        filter_dep_map = {}
        for f in page_filters:
            child_key = f.param_name or f.field_name or ''
            dep = f.depends_on_filter_id
            parent_key = (dep.param_name or dep.field_name or '') if dep else ''
            if child_key and parent_key:
                filter_dep_map[child_key] = parent_key
        filter_dep_map_json = json.dumps(filter_dep_map)

        # ── 9. Widgets ─────────────────────────────────────────────────
        filter_values_by_name = {}
        for f in page_filters:
            key = f.param_name or f.field_name
            if key:
                filter_values_by_name[key] = filter_values.get(f.id, '')

        # Convert multi-select params from CSV strings to tuples for psycopg2.
        from ..utils.sql_params import build_sql_params
        multiselect_params = {
            (f.param_name or f.field_name)
            for f in page_filters if f.is_multiselect
        }
        sql_params = build_sql_params(filter_values_by_name, multiselect_params)

        portal_ctx = {
            'selected_hha':          selected_provider,
            'filter_values_by_name': filter_values_by_name,
            'sql_params':            sql_params,
            '_filter_defs':          page_filters.to_filter_defs(),
        }

        # Load ALL widgets for the page (all tabs). Execute SQL only for
        # current-tab widgets. Other-tab widgets get deferred metadata —
        # React lazy-loads them via per-widget API when the tab is clicked.
        widgets = request.env['dashboard.widget'].sudo().search([
            ('page_id.key', '=', effective_page_key),
            ('is_active', '=', True),
        ], order='sequence asc')
        widget_data = {}
        for w in widgets:
            w_tab_key = w.tab_id.key if w.tab_id else None
            if not w_tab_key or w_tab_key == current_tab_key:
                # Current tab or no-tab widget → execute SQL, full data
                widget_data[w.id] = w.get_portal_data(portal_ctx)
            else:
                # Other tab → deferred metadata only (no SQL execution)
                widget_data[w.id] = {'_deferred': True}

        # ── 10. Page sections ──────────────────────────────────────────
        page_sections = request.env['dashboard.page.section'].sudo().search([
            ('page_id.key', '=', effective_page_key),
            ('is_active', '=', True),
        ], order='sequence asc')
        section_data = {sec.id: sec.get_portal_data(portal_ctx) for sec in page_sections}

        # ── 11. Phase 7 — React shell data ─────────────────────────────
        # Build JSON blobs and a fresh JWT for the React app-root div.
        # These are embedded as data-* attributes; React reads them on mount.
        portal_access_token = _make_portal_access_token(request.env.user, app)
        page_config_json = _build_page_config_json(
            app, current_page, tabs, page_filters, filter_options,
            filter_dep_map_json, current_tab_key,
            filter_values=filter_values,
        )
        initial_widget_data_json = _build_initial_widgets_json(widgets, widget_data)
        initial_sections_json = _build_initial_sections_json(page_sections, section_data)

        # ── 12. Render ─────────────────────────────────────────────────
        values = self._prepare_portal_layout_values()
        values.update({
            'app':        app,
            'page_name':  'posterra',
            'portal_type': app.access_mode,   # kept for backward compat with template conditions
            'page_title': app.name + ' — ' + (current_page.name if current_page else 'Dashboard'),
            # Provider context
            'providers':           providers,
            'provider_count':      len(providers),
            'selected_provider':   selected_provider,
            'org_display_name':    org_display_name,
            'current_hha_id':      current_hha_id,
            # Navigation
            'sections_with_pages': sections_with_pages,
            'pages':               pages,
            'current_page':        current_page,
            'current_page_key':    effective_page_key,
            'tabs':                tabs,
            'current_tab_key':     current_tab_key,
            'current_tab_name':    current_tab_name,
            # Context filters
            'page_filters':        page_filters,
            'filter_values':       filter_values,
            'filter_options':      filter_options,
            'filter_dep_map_json': filter_dep_map_json,
            'accessible_provider_ids_json': json.dumps(accessible_provider_ids),
            # Geo data
            'provider_geo_data_json': json.dumps(provider_geo_data),
            'provider_map_json':      json.dumps(provider_map),
            # Widgets
            'widgets':      widgets,
            'widget_data':  widget_data,
            # Page sections
            'page_sections': page_sections,
            'section_data':  section_data,
            # Phase 7 — React shell data (embedded as data-* on #app-root)
            'portal_access_token':      portal_access_token,
            'page_config_json':         page_config_json,
            'initial_widget_data_json': initial_widget_data_json,
            'initial_sections_json':    initial_sections_json,
            # is_admin removed — admin controls are in Odoo backend, not portal
        })
        return request.render('posterra_portal.dashboard', values)

    # ------------------------------------------------------------------ #
    # WHITE-LABEL LOGIN (Phase 4, updated in Phase 5)                     #
    # Branded login page at /my/<app_key>/login — no Odoo chrome.         #
    # app_key is resolved against saas.app for per-app branding.          #
    # ------------------------------------------------------------------ #
    @route(['/my/<string:app_key>/login'], type='http', auth='none',
           methods=['GET', 'POST'], readonly=False, website=True)
    def posterra_login(self, app_key='posterra', redirect=None, **kw):
        """Branded login page for any registered saas.app.

        GET  — render the login form (unauthenticated).
        POST — authenticate; on success redirect to the right dashboard.
        """
        ensure_db()

        # Set up a public env so request.env is usable even before login
        if request.env.uid is None:
            if request.session.uid is None:
                request.env['ir.http']._auth_method_public()
            else:
                request.update_env(user=request.session.uid)

        # Validate app_key against saas.app registry
        app = request.env['saas.app'].sudo().search(
            [('app_key', '=', app_key), ('is_active', '=', True)], limit=1,
        )
        if not app:
            return request.redirect('/web/login')

        # Already authenticated → send to the right dashboard
        if request.session.uid:
            target = redirect or '/my/%s' % app_key
            return request.redirect(target)

        login_url = '/my/%s/login' % app_key
        values = {
            'app':       app,
            'login_url': login_url,
            'redirect':  redirect or '',
            'login_val': '',
            'error':     None,
            'message':   None,
        }

        if request.httprequest.method == 'POST':
            login_val = kw.get('login', '').strip()
            password  = kw.get('password', '')
            values['login_val'] = login_val
            try:
                credential = {
                    'login':    login_val,
                    'password': password,
                    'type':     'password',
                }
                request.session.authenticate(request.env, credential)
                # Redirect to the explicit redirect param, or to this app's
                # dashboard.  We don't use _login_redirect() here because that
                # method lives on Home (a different controller hierarchy) and is
                # not accessible from CustomerPortal.  The branded login page is
                # always app-specific so the correct destination is /my/<app_key>.
                target = redirect or '/my/%s' % app_key
                return request.redirect(target)
            except odoo.exceptions.AccessDenied as e:
                if e.args == odoo.exceptions.AccessDenied().args:
                    values['error'] = 'Wrong email or password'
                else:
                    values['error'] = e.args[0]

        response = request.render('posterra_portal.login', values)
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        return response
