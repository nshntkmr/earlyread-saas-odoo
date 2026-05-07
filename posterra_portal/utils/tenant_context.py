# -*- coding: utf-8 -*-
"""Tenant context resolution.

The tenant boundary in Posterra is ``saas.app`` — every request lands on
an app subdomain (e.g. ``posterra.example.com``) which implicitly scopes
the session to one app. Executors that talk to external backends
(ClickHouse) must know which tenant to set on the query so row policies
enforce isolation.

Flow:
    Host ``posterra.example.com`` (or ``posterra.localhost:8069`` in dev)
      → ``controllers/portal.py:app_dashboard`` calls
        ``utils/app_resolver.get_app_from_host()`` → ``saas.app``
      → ``request.tenant_id = app.id`` is stashed on the request
      → executor's ``get_tenant_id()`` reads it back

For non-HTTP code paths (cron jobs, queue workers, tests), we fall back
to the user's first accessible app — but only if exactly one app is
visible. Ambiguous cases raise rather than silently picking, because
silently leaking data across tenants is the failure mode this whole
system is built to prevent.
"""


def get_current_tenant_id(env, request=None):
    """Resolve the tenant_id for the current execution context.

    Returns a string (e.g. ``'1'``, ``'2'``) — ClickHouse stores tenant
    IDs as ``LowCardinality(String)`` so we keep them strings end-to-end
    and leave room to switch to UUIDs later without a schema change.

    Raises:
        ValueError if no tenant can be determined unambiguously. Callers
        that have a connection with ``requires_tenant_filter=False``
        should catch and ignore this.
    """
    if request is not None and getattr(request, 'tenant_id', None):
        return str(request.tenant_id)

    user = env.user
    if not user or user._is_public():
        raise ValueError("Cannot resolve tenant_id: no authenticated user")

    apps = env['saas.app'].sudo().search([('is_active', '=', True)])
    accessible = apps.filtered(lambda a: _user_has_access(user, a))

    if not accessible:
        raise ValueError(f"User {user.login!r} has no accessible saas.app")

    if len(accessible) > 1:
        raise ValueError(
            f"User {user.login!r} has access to multiple apps "
            f"({', '.join(accessible.mapped('app_key'))}); "
            "cannot pick a tenant without an HTTP request context"
        )

    return str(accessible.id)


def _user_has_access(user, app):
    """Replicate the access checks from controllers/portal.py:app_dashboard.

    HHA-provider apps: user has access if they have any HHA provider
    visible to them (direct hha_provider_id or via scope group).

    Group apps: user has access if they belong to the configured group.
    """
    if not app.is_active:
        return False
    if app.access_mode == 'hha_provider':
        partner = user.partner_id
        if partner.hha_provider_id:
            return True
        scope_group = getattr(partner, 'hha_scope_group_id', False)
        if scope_group and getattr(scope_group, 'provider_ids', False):
            return True
        return False
    if app.access_mode == 'group':
        if not app.access_group_xmlid:
            return False
        try:
            return user.has_group(app.access_group_xmlid)
        except Exception:
            return False
    return False
