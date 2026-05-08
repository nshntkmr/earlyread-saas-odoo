# -*- coding: utf-8 -*-
"""Tenant access enforcement.

Single source of truth for "may this user access this app?".

Authorisation contract
----------------------
``res.partner.portal_app_ids`` (Many2many) is the authoritative list of
apps a contact may sign into. Helper docstring on the field reads:
"Apps this contact can sign into." Adding/removing entries in this
Many2many auto-syncs the corresponding security groups on the linked
user (see ``ResPartner.write`` in ``models/res_partner.py``).

Membership in ``portal_app_ids`` is necessary but NOT sufficient. On top
of the Many2many, each ``access_mode`` adds a data-scope precondition:

  * ``group``: the user must also belong to ``app.access_group_xmlid``
    (legacy / superadmin path consistency).
  * ``hha_provider``: the user must have a provider link (direct
    ``partner.hha_provider_id`` or a non-empty
    ``partner.hha_scope_group_id.provider_ids``). Without this, the user
    has no row scope and would see empty results — so we deny early.

The earlier first-attempt helper (rolled back at ``stash@{0}``) treated
"has any provider" as authorisation for every HHA app. That conflated
authorisation with data scope and let a user assigned only to app A
authenticate against app B. The corrected combo check below closes that
gap.

Callers
-------
Every code path that issues a JWT or honours a user-supplied ``app_key``
MUST call ``user_can_access_app`` before treating the app as authorised:

  * ``posterra_portal.controllers.auth_api.api_login`` (JWT issuance)
  * ``posterra_portal.controllers.portal.session_refresh_token``
  * ``posterra_portal.controllers.auth_api.api_refresh_token``
  * ``posterra_portal.controllers.widget_api._get_api_user`` (JWT
    validation; defence in depth for revocation between issue and use)
  * ``posterra_portal.controllers.portal.app_dashboard`` (browser route)

Fails closed: returns False on missing records, inactive apps, unknown
``access_mode``, or any exception during membership lookup.
"""

import logging

_logger = logging.getLogger(__name__)


def user_can_access_app(user, app):
    """Return True iff ``user`` may access ``app``.

    Args:
        user: ``res.users`` record. May be sudo'd; we only read fields.
        app:  ``saas.app`` record. May be sudo'd. Must already be
              browsed; this helper does not search.

    Returns:
        bool. False on any of: missing record, inactive app, user not
        in app's ``portal_app_ids``, missing data-scope precondition
        (group membership or provider link), unknown access_mode,
        exception during the membership check. Always fails closed.
    """
    if not user or not app:
        return False
    if not getattr(user, 'id', False):
        return False
    # Reject deactivated users. Archiving a res.users record (active=False)
    # is the standard "revocation" handle in Odoo — sessions / refresh
    # tokens issued before deactivation must stop working immediately.
    # We check active up-front so the helper is canonical: inactive users
    # never pass, regardless of access_mode or portal_app_ids state.
    if not getattr(user, 'active', True):
        return False
    if not app.exists() or not app.is_active:
        return False

    # ── Authoritative contract: per-contact app access list ──────────
    # portal_app_ids is the documented "Apps this contact can sign into"
    # list. Membership here is a HARD precondition; without it we deny
    # regardless of provider links or group memberships the user might
    # otherwise have. (Group memberships in particular can be granted by
    # legacy paths that bypassed portal_app_ids.write() — those users
    # should NOT be authorised under the new contract.)
    try:
        partner = user.partner_id.sudo()
        if app not in partner.portal_app_ids:
            return False
    except Exception as exc:
        _logger.warning(
            'user_can_access_app: portal_app_ids lookup raised: %s', exc,
        )
        return False

    # ── Data-scope precondition layered on top ──────────────────────
    if app.access_mode == 'group':
        if not app.access_group_xmlid:
            return False
        try:
            return user.has_group(app.access_group_xmlid)
        except Exception as exc:
            _logger.warning(
                'user_can_access_app: has_group(%s) raised: %s',
                app.access_group_xmlid, exc,
            )
            return False

    if app.access_mode == 'hha_provider':
        # Direct or scope-group provider linkage. We don't call into
        # ``controllers.portal._get_providers_for_user`` because that
        # helper relies on ``request.env`` and is not safe to call from
        # cron / test contexts. The boolean we need (has any provider?)
        # can be derived from the partner record alone.
        try:
            if partner.hha_provider_id:
                return True
            scope_group = getattr(partner, 'hha_scope_group_id', False)
            if scope_group and scope_group.provider_ids:
                return True
            return False
        except Exception as exc:
            _logger.warning(
                'user_can_access_app: hha_provider check raised: %s', exc,
            )
            return False

    _logger.warning(
        'user_can_access_app: app %r has unknown access_mode=%r — denying',
        app.app_key, app.access_mode,
    )
    return False


class ForgedProviderValueError(ValueError):
    """Raised when a URL filter param contains a provider value that is not
    in the user's accessible provider set.

    Subclasses ``ValueError`` so callers can let it propagate through
    existing ``except ValueError`` catch blocks (which return 401), but
    HTTP routes that want a 403 should catch ``ForgedProviderValueError``
    specifically BEFORE catching ``ValueError`` / ``Exception``.
    """


def values_in_user_scope(url_val, filter_record, accessible_providers):
    """Return True iff every CSV value in ``url_val`` matches a provider
    in ``accessible_providers``.

    Used to block the bypass where a forged URL param (e.g.
    ``?hha_ccn=<other_tenant_ccn>``) flows directly into widget SQL.

    Validation rules:
        * Empty value or the string ``'all'`` (case-insensitive) → True.
          These are the "no filter" sentinels and never represent forgery.
        * If the filter has no resolvable match field → True (nothing to
          validate against; treat as non-provider filter).
        * Otherwise: every comma-separated value in ``url_val`` MUST appear
          in the set of values produced by reading the filter's match
          field on each accessible provider.

    The match field is derived from the filter record:
        1. ``field_name`` (ORM field — most common)
        2. ``schema_column_name`` (when filter is schema-source-backed)
        3. ``param_name`` (URL key) as a last resort

    Special case: ``field_name='id'`` compares against ``provider.id``
    casted to string, so URL-supplied numeric IDs match correctly.

    Args:
        url_val: raw URL value (str). May be CSV for multi-select filters.
        filter_record: a ``dashboard.page.filter`` record.
        accessible_providers: ``hha.provider`` recordset of providers the
            user is authorised to see (typically the result of
            ``_get_providers_for_user(user)``).

    Returns:
        bool. False on any forged value; True otherwise.

    Defensive against non-string inputs: any non-string value is coerced
    via ``str()`` before stripping. JSON payloads can deliver ints,
    lists, or dicts in places the contract expects strings — without
    coercion, ``.strip()`` would raise ``AttributeError`` and the caller
    would 500 instead of returning a controlled 403/True.
    """
    if url_val is None:
        return True
    val = str(url_val).strip() if not isinstance(url_val, str) else url_val.strip()
    if not val or val.lower() == 'all':
        return True

    field = (
        getattr(filter_record, 'field_name', '')
        or getattr(filter_record, 'schema_column_name', '')
        or getattr(filter_record, 'param_name', '')
        or ''
    )
    if not field:
        return True  # nothing to match against

    # Build the set of acceptable values for this user
    if field == 'id':
        accepted = {str(p.id) for p in accessible_providers}
    else:
        accepted = {
            str(getattr(p, field, '') or '').strip()
            for p in accessible_providers
        }
    accepted.discard('')  # never accept empty as a valid match

    requested = [v.strip() for v in val.split(',') if v.strip()]
    if not requested:
        return True  # only commas / whitespace — treat as no filter
    return all(v in accepted for v in requested)


def assert_provider_url_values_authorised(
    values_by_key, page_filters, app, accessible_providers, is_superadmin,
):
    """Walk a {filter-key: url-value} map; raise ``ForgedProviderValueError``
    if any value that maps to a provider-scoped filter is not in the user's
    accessible provider set.

    Used by cascade endpoints that don't go through ``_build_portal_ctx``:
    ``/api/v1/filters/cascade``, ``/api/v1/filters/cascade/multi``,
    ``/api/v1/filters/resolve``. These endpoints accept client-controlled
    values (``parent_value``, ``constraints``, ``all_values``,
    ``changed_value``, ``current_values``) and feed them into
    ``filter.get_options()``, which builds SQL filters. Without this
    validation, a forged provider value flows directly into option SQL.

    Args:
        values_by_key: dict mapping a filter identifier → URL value (str).
            Keys may be any of:
              * ``dashboard.page.filter`` records
              * filter IDs as int or str-of-int
              * param-name strings (matched against
                ``filter.param_name`` or ``filter.field_name``)
            Mixed types in one dict are fine.
        page_filters: recordset of ``dashboard.page.filter`` on the page.
            Used to look up filters by id / param-name.
        app: ``saas.app`` record for the current request. Determines
            whether the ``is_provider_selector`` opt-in fires.
        accessible_providers: ``hha.provider`` recordset of providers the
            user is authorised to view.
        is_superadmin: bool — bypass validation entirely.

    Validation gate (mirrors ``widget_api._build_portal_ctx`` and
    ``portal.app_dashboard``): a filter triggers validation when EITHER
    ``scope_to_user_hha=True`` OR (``is_provider_selector=True`` AND
    ``app.access_mode='hha_provider'``).

    Raises:
        ForgedProviderValueError on the first forged value found.
    """
    if is_superadmin:
        return
    is_hha_app = (app.access_mode == 'hha_provider')

    by_id = {f.id: f for f in page_filters}
    by_param = {}
    for f in page_filters:
        param = f.param_name or f.field_name or ''
        if param:
            by_param[param] = f

    for key, val in values_by_key.items():
        if not val:
            continue

        # Resolve key → filter record
        filt = None
        if hasattr(key, '_name') and key._name == 'dashboard.page.filter':
            filt = key
        elif isinstance(key, int):
            filt = by_id.get(key)
        elif isinstance(key, str):
            if key.isdigit():
                filt = by_id.get(int(key))
            else:
                filt = by_param.get(key)
        if not filt:
            continue  # unknown key — skip (don't reject for unrelated state)

        should_validate = (
            getattr(filt, 'scope_to_user_hha', False)
            or (is_hha_app and getattr(filt, 'is_provider_selector', False))
        )
        if not should_validate:
            continue

        if not values_in_user_scope(val, filt, accessible_providers):
            raise ForgedProviderValueError(
                f'Provider value not in your accessible set '
                f'for filter {(filt.param_name or filt.field_name)!r}'
            )
