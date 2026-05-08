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
      → ``request.tenant_id = app.app_key`` is stashed on the request
      → executor's ``get_tenant_id()`` reads it back

For non-HTTP code paths (cron jobs, queue workers, tests), we fall back
to the user's first accessible app — but only if exactly one app is
visible. Ambiguous cases raise rather than silently picking, because
silently leaking data across tenants is the failure mode this whole
system is built to prevent.
"""


def get_current_tenant_id(env, request=None):
    """Resolve the tenant_id for the current execution context.

    Returns the stable string ``saas.app.app_key`` (e.g. ``'posterra'``,
    ``'mssp'``, ``'inhome'``). ClickHouse stores tenant IDs as
    ``LowCardinality(String)`` and reads via
    ``getSetting('SQL_tenant_id')`` for row policies. The string app_key
    is stable across PG rebuilds (a fresh Azure deploy keeps the same
    tenant tags in CH), human-readable in ``system.query_log``, and
    matches the DNS subdomain.

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

    return accessible.app_key


def _user_has_access(user, app):
    """Mirror of ``posterra_portal.utils.access.user_can_access_app``.

    Kept as a thin wrapper so the fallback path in
    ``get_current_tenant_id`` (used by cron / queue workers / tests
    without an HTTP request) shares the same authorisation contract as
    the HTTP surfaces. The contract: ``portal_app_ids`` membership AND
    a per-mode data-scope precondition (group membership for
    ``access_mode='group'`` apps; provider linkage for ``hha_provider``
    apps).

    Importing the helper at call time keeps this module load-order safe
    — ``utils.access`` doesn't import anything that re-enters here.
    """
    from .access import user_can_access_app
    return user_can_access_app(user, app)
