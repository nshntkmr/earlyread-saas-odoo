# -*- coding: utf-8 -*-

import json
import logging

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, route

_logger = logging.getLogger(__name__)


# Full sidebar/tab structure from the Posterra design spec
SIDEBAR_STRUCTURE = {
    'sections': [
        {'name': 'MY HHA', 'key': 'my_hha'},
        {'name': 'PORTFOLIO', 'key': 'portfolio'},
        {'name': 'DATA EXPLORER', 'key': 'data_explorer'},
    ],
    'pages': [
        # MY HHA section
        {
            'key': 'overview', 'name': 'Overview', 'section': 'my_hha', 'icon': 'fa-home',
            'tabs': [
                {'key': 'command_center', 'name': 'Command Center'},
                {'key': 'insights', 'name': 'Insights'},
                {'key': 'quality', 'name': 'Quality'},
            ],
        },
        {
            'key': 'hospitals', 'name': 'Hospitals', 'section': 'my_hha', 'icon': 'fa-hospital-o',
            'tabs': [
                {'key': 'performance', 'name': 'Performance'},
                {'key': 'timely_access', 'name': 'Timely Access'},
                {'key': 'quality_metrics', 'name': 'Quality Metrics'},
                {'key': 'financial', 'name': 'Financial'},
            ],
        },
        {
            'key': 'physicians', 'name': 'Physicians', 'section': 'my_hha', 'icon': 'fa-user-md',
            'tabs': [
                {'key': 'referral_activity', 'name': 'Referral Activity'},
                {'key': 'outcomes', 'name': 'Outcomes'},
                {'key': 'leakage', 'name': 'Leakage'},
            ],
        },
        {
            'key': 'competitive_intel', 'name': 'Competitive Intel', 'section': 'my_hha', 'icon': 'fa-line-chart',
            'tabs': [
                {'key': 'market_share', 'name': 'Market Share'},
                {'key': 'competitor_detail', 'name': 'Competitor Detail'},
                {'key': 'trends', 'name': 'Trends'},
            ],
        },
        # PORTFOLIO section
        {
            'key': 'command_center', 'name': 'Command Center', 'section': 'portfolio', 'icon': 'fa-dashboard',
            'tabs': [
                {'key': 'operations', 'name': 'Operations'},
                {'key': 'staffing', 'name': 'Staffing'},
                {'key': 'compliance', 'name': 'Compliance'},
            ],
        },
        {
            'key': 'leaderboard', 'name': 'Leaderboard', 'section': 'portfolio', 'icon': 'fa-trophy',
            'tabs': [
                {'key': 'overall_rank', 'name': 'Overall Rank'},
                {'key': 'by_metric', 'name': 'By Metric'},
                {'key': 'trending', 'name': 'Trending'},
            ],
        },
        {
            'key': 'market_threats', 'name': 'Market Threats', 'section': 'portfolio', 'icon': 'fa-exclamation-triangle',
            'tabs': [
                {'key': 'active_threats', 'name': 'Active Threats'},
                {'key': 'watchlist', 'name': 'Watchlist'},
                {'key': 'history', 'name': 'History'},
            ],
        },
        {
            'key': 'strategy', 'name': 'Strategy', 'section': 'portfolio', 'icon': 'fa-compass',
            'tabs': [
                {'key': 'goals', 'name': 'Goals'},
                {'key': 'initiatives', 'name': 'Initiatives'},
                {'key': 'timeline', 'name': 'Timeline'},
            ],
        },
        # DATA EXPLORER section
        {
            'key': 'reports', 'name': 'Reports', 'section': 'data_explorer', 'icon': 'fa-file-text-o',
            'tabs': [
                {'key': 'builder', 'name': 'Builder'},
                {'key': 'saved_reports', 'name': 'Saved Reports'},
                {'key': 'scheduled', 'name': 'Scheduled'},
            ],
        },
        {
            'key': 'episodes', 'name': 'Episodes', 'section': 'data_explorer', 'icon': 'fa-list-alt',
            'tabs': [
                {'key': 'overview', 'name': 'Overview'},
                {'key': 'by_diagnosis', 'name': 'By Diagnosis'},
                {'key': 'outcomes', 'name': 'Outcomes'},
                {'key': 'costs', 'name': 'Costs'},
            ],
        },
        {
            'key': 'referral_sources', 'name': 'Referral Sources', 'section': 'data_explorer', 'icon': 'fa-share-alt',
            'tabs': [
                {'key': 'by_source', 'name': 'By Source'},
                {'key': 'trends', 'name': 'Trends'},
                {'key': 'leakage', 'name': 'Leakage'},
            ],
        },
    ],
}


def _get_providers_for_user(user):
    """Find HHA providers matching the user's email domain.

    Uses: HHA DBA if set, otherwise HHA Name.
    Returns a recordset of matching hha.provider records.
    """
    return request.env['hha.provider'].find_by_email_domain(user.login or user.email)


class PosterraPortal(CustomerPortal):

    @route()
    def home(self, **kw):
        """Override /my and /my/home: redirect HHA users to Posterra dashboard."""
        providers = _get_providers_for_user(request.env.user)
        if providers:
            return request.redirect('/my/posterra')
        return super().home(**kw)

    @route([
        '/my/posterra',
        '/my/posterra/<string:page_key>',
        '/my/posterra/<string:page_key>/<string:tab_key>',
    ], type='http', auth='user', website=True)
    def posterra_dashboard(self, page_key='overview', tab_key=None, hha_id=None,
                          ctx_state=None, ctx_county=None, ctx_locations=None,
                          ctx_year=None, ctx_payer=None, **kw):
        user = request.env.user
        providers = _get_providers_for_user(user)
        if not providers:
            return request.redirect('/my')

        # ------------------------------------------------------------------ #
        # HHA SELECTION LOGIC                                                  #
        # ------------------------------------------------------------------ #
        # ?hha_id=<int>  → show a single specific provider from the matched set
        # ?hha_id=all    → aggregate / "All HHAs" view  (default for multi-HHA)
        # (no param)     → auto-select when only 1 provider, else "All"

        selected_provider = None        # None == "All HHAs" aggregate view
        hha_id_str = (hha_id or kw.get('hha_id') or '').strip()

        if len(providers) == 1:
            # Single match: always show that one provider
            selected_provider = providers[0]
        elif hha_id_str and hha_id_str != 'all':
            try:
                hha_id_int = int(hha_id_str)
                matched = providers.filtered(lambda p: p.id == hha_id_int)
                if matched:
                    selected_provider = matched[0]
            except (ValueError, TypeError):
                pass

        # The "primary" provider drives the page header / breadcrumbs.
        provider = selected_provider or providers[0]

        # Build the selector dropdown list shown in the filter bar.
        # Format: [{'id': <int|'all'>, 'label': 'CCN - HHA Brand Name', 'selected': bool}]
        # Label priority: HHA Brand Name → HHA Name (Brand Name is the user-facing identity)
        selector_options = []
        if len(providers) > 1:
            selector_options.append({
                'id': 'all',
                'label': f'All {len(providers)} HHAs',
                'selected': selected_provider is None,
            })
        for p in providers:
            display_name = p.hha_brand_name or p.hha_name
            ccn_label = f"{p.hha_ccn} - {display_name}" if p.hha_ccn else display_name
            selector_options.append({
                'id': p.id,
                'label': ccn_label,
                'selected': bool(selected_provider and selected_provider.id == p.id),
            })

        # Organisation display name shown in the filter bar chip (e.g. "ELARA CARING").
        # HHA DBA if set, otherwise HHA Name.
        org_display_name = (
            providers[0].hha_dba
            or providers[0].hha_name
            or ''
        ).upper()

        # Current selection label for the active-filter pill and chip
        # Uses Brand Name → HHA Name priority, same as dropdown options
        if selected_provider:
            display_name = selected_provider.hha_brand_name or selected_provider.hha_name
            current_hha_label = (
                f"{selected_provider.hha_ccn} - {display_name}"
                if selected_provider.hha_ccn
                else display_name
            )
        else:
            current_hha_label = f'All {len(providers)} HHAs'

        # ------------------------------------------------------------------ #
        # PAGE / TAB RESOLUTION                                                #
        # ------------------------------------------------------------------ #
        current_page = None
        for page in SIDEBAR_STRUCTURE['pages']:
            if page['key'] == page_key:
                current_page = page
                break

        # Fall back to overview if page_key not found
        if not current_page:
            current_page = SIDEBAR_STRUCTURE['pages'][0]
            page_key = current_page['key']

        tabs = current_page.get('tabs', [])
        current_tab_key = tab_key or (tabs[0]['key'] if tabs else None)

        # Verify the tab_key is valid for this page
        if current_tab_key and tabs:
            valid_keys = [t['key'] for t in tabs]
            if current_tab_key not in valid_keys:
                current_tab_key = tabs[0]['key']

        # Find current tab name for display
        current_tab_name = ''
        for tab in tabs:
            if tab['key'] == current_tab_key:
                current_tab_name = tab['name']
                break

        # ------------------------------------------------------------------ #
        # CONTEXT FILTER (Overview page)                                       #
        # ------------------------------------------------------------------ #
        ctx_state = (ctx_state or '').strip()
        ctx_county = (ctx_county or '').strip()
        ctx_year = (ctx_year or '2025').strip()
        ctx_payer = (ctx_payer or 'all').strip()
        ctx_locations_raw = (ctx_locations or '').strip()

        # ctx_locations stores comma-separated city names (from HHA City column)
        ctx_cities = []
        for city in ctx_locations_raw.split(','):
            city = city.strip()
            if city:
                ctx_cities.append(city)

        # ── Determine geo data source ──────────────────────────────────────
        # When a specific HHA is selected → scope geo data to that one provider.
        # When "All HHAs" → union of all matched providers' geographies.
        # Use .read() to ensure the ORM cache is warm for geographic fields.
        geo_provider_ids = [selected_provider.id] if selected_provider else providers.ids
        geo_records = request.env['hha.provider'].sudo().browse(geo_provider_ids).read(
            ['id', 'hha_ccn', 'hha_state', 'hha_county', 'hha_city',
             'hha_brand_name', 'hha_name']
        )

        # Auto-populate ctx geo filters from the selected provider when the
        # user hasn't explicitly set them (e.g. first time clicking an HHA).
        if selected_provider and not ctx_state:
            ctx_state = (selected_provider.hha_state or '').strip()
        if selected_provider and not ctx_county:
            ctx_county = (selected_provider.hha_county or '').strip()
        if selected_provider and not ctx_cities:
            sp_city = (selected_provider.hha_city or '').strip()
            if sp_city:
                ctx_cities = [sp_city]

        # Build geo data: {state: {county: [city1, city2, ...]}}
        # Populated from HHA State, HHA County, HHA City columns (deduplicated, sorted)
        provider_geo_data = {}
        for rec in geo_records:
            state = (rec.get('hha_state') or '').strip()
            county = (rec.get('hha_county') or '').strip()
            city = (rec.get('hha_city') or '').strip()
            if not state:
                continue
            if state not in provider_geo_data:
                provider_geo_data[state] = {}
            if county not in provider_geo_data[state]:
                provider_geo_data[state][county] = []
            if city and city not in provider_geo_data[state][county]:
                provider_geo_data[state][county].append(city)

        # Sort cities alphabetically within each county
        for state_data in provider_geo_data.values():
            for county in state_data:
                state_data[county] = sorted(state_data[county])

        all_states = sorted(provider_geo_data.keys())
        _logger.debug(
            "posterra ctx_filter: %d geo_records, %d states found, source=%s",
            len(geo_records),
            len(all_states),
            'selected_provider' if selected_provider else 'all_providers',
        )

        counties_for_ctx = []
        if ctx_state and ctx_state in provider_geo_data:
            counties_for_ctx = sorted(provider_geo_data[ctx_state].keys())

        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'posterra',
            # Provider context
            'provider': provider,
            'providers': providers,
            'provider_count': len(providers),
            'selected_provider': selected_provider,
            'selector_options': selector_options,
            'org_display_name': org_display_name,
            'current_hha_label': current_hha_label,
            'current_hha_id': hha_id_str or ('all' if len(providers) > 1 else str(providers[0].id)),
            # Navigation
            'sidebar': SIDEBAR_STRUCTURE,
            'current_page': current_page,
            'current_page_key': page_key,
            'tabs': tabs,
            'current_tab_key': current_tab_key,
            'current_tab_name': current_tab_name,
            # Context filter
            'provider_geo_data_json': json.dumps(provider_geo_data),
            'all_states': all_states,
            'counties_for_ctx': counties_for_ctx,
            'ctx_state': ctx_state,
            'ctx_county': ctx_county,
            'ctx_cities': ctx_cities,
            'ctx_locations_str': ','.join(ctx_cities),
            'ctx_year': ctx_year,
            'ctx_payer': ctx_payer,
        })
        return request.render('posterra_portal.dashboard', values)
