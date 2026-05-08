# -*- coding: utf-8 -*-
"""P0-13: route-level HTTP bypass tests.

Helper unit tests in ``test_access_helper.py`` prove the contract of
``user_can_access_app`` and ``values_in_user_scope`` in isolation. These
tests prove the actual HTTP-layer behaviour Codex's review demanded:

  1. POST /api/v1/auth/login with ``app_key=B`` for a user in
     ``portal_app_ids=[A]`` → **403** (not silent token for A or B).
  2. POST /api/v1/auth/login with NO ``app_key`` for a user authorised
     for app B but app A comes first in DB → token for B (the bug
     Codex identified — first auto-detect always picked the first
     ``hha_provider`` app, returning 403 incorrectly).
  3. POST /api/v1/auth/refresh after admin removes user from
     ``portal_app_ids`` → **401**.
  4. GET /api/v1/widget/.../data after revocation → **401**.
  5. GET /api/v1/widget/.../data with ``?hha_ccn=<other_tenant_ccn>``
     → **403** (forged provider URL param).
  6. Archived (``active=False``) user is rejected at every JWT surface.

Run:
    odoo-bin --test-enable -i posterra_portal --test-tags posterra_p0_13 \\
             --stop-after-init -d <test_db>
"""

import json
import logging

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'posterra_p0_13', 'posterra_tenant')
class TestRouteBypass(HttpCase):
    """HTTP-layer assertions for the auth + URL-validation contracts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Two group-mode test apps with their own security groups.
        # Group apps are simpler to test against than hha_provider mode
        # because they don't require a provider link / scope group setup.
        Group = cls.env['res.groups'].sudo()
        IMD = cls.env['ir.model.data'].sudo()
        App = cls.env['saas.app'].sudo()
        Users = cls.env['res.users'].sudo()
        portal_group = cls.env.ref('base.group_portal')

        cls.group_a = Group.create({
            'name': 'P0-13 Test App A Users',
            'implied_ids': [(4, portal_group.id)],
        })
        IMD.create({
            'module': 'posterra_portal',
            'name': 'group_p0_13_app_a',
            'model': 'res.groups',
            'res_id': cls.group_a.id,
            'noupdate': True,
        })
        cls.group_b = Group.create({
            'name': 'P0-13 Test App B Users',
            'implied_ids': [(4, portal_group.id)],
        })
        IMD.create({
            'module': 'posterra_portal',
            'name': 'group_p0_13_app_b',
            'model': 'res.groups',
            'res_id': cls.group_b.id,
            'noupdate': True,
        })

        cls.app_a = App.create({
            'name': 'P0-13 App A',
            'app_key': 'p013a',
            'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_p0_13_app_a',
            'is_active': True,
        })
        cls.app_b = App.create({
            'name': 'P0-13 App B',
            'app_key': 'p013b',
            'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_p0_13_app_b',
            'is_active': True,
        })

        # ── User authorised ONLY for app A
        cls.user_a_login = 'p013_user_a@test.local'
        cls.user_a_pwd = 'pa$$word123!'
        cls.user_a = Users.create({
            'name': 'P0-13 User A',
            'login': cls.user_a_login,
            'email': cls.user_a_login,
            'password': cls.user_a_pwd,
            'groups_id': [(4, portal_group.id), (4, cls.group_a.id)],
        })
        cls.user_a.partner_id.sudo().portal_app_ids = [(6, 0, [cls.app_a.id])]

        # ── User authorised ONLY for app B.
        # Critical for the auto-detect regression test: app_a was created
        # first (lower id, comes first in default order). With the legacy
        # "first hha_provider app" / "first group app the user has" logic,
        # this user could be wrongly bounced to app_a (and 403'd by the
        # final guard) instead of correctly resolving to app_b.
        cls.user_b_login = 'p013_user_b@test.local'
        cls.user_b_pwd = 'pa$$word123!'
        cls.user_b = Users.create({
            'name': 'P0-13 User B',
            'login': cls.user_b_login,
            'email': cls.user_b_login,
            'password': cls.user_b_pwd,
            'groups_id': [(4, portal_group.id), (4, cls.group_b.id)],
        })
        cls.user_b.partner_id.sudo().portal_app_ids = [(6, 0, [cls.app_b.id])]

        # ── HHA-provider app fixture for forged-URL tests.
        # The forgery validation runs inside _build_portal_ctx when a
        # filter has scope_to_user_hha=True OR (is_provider_selector=True
        # AND access_mode='hha_provider'). To exercise the route at HTTP
        # level we need: an HHA-mode app, two providers (one in user's
        # scope, one not), a user authorised for that app with a scope
        # group, a page on that app, and a filter on the page that
        # triggers validation. The /api/v1/page/<id>/badges route is the
        # cheapest call site that runs _build_portal_ctx (no widget
        # SQL execution needed — empty badge list is fine).
        cls.app_c = App.create({
            'name': 'P0-13 App C HHA',
            'app_key': 'p013c',
            'access_mode': 'hha_provider',
            'is_active': True,
        })
        Provider = cls.env['hha.provider'].sudo()
        cls.provider_owned = Provider.create({
            'hha_ccn': 'P013OWN', 'hha_name': 'P0-13 Owned HHA',
        })
        cls.provider_other = Provider.create({
            'hha_ccn': 'P013OTHER', 'hha_name': 'P0-13 Other Tenant HHA',
        })
        ScopeGroup = cls.env['hha.scope.group'].sudo()
        cls.scope_group_c = ScopeGroup.create({
            'name': 'P0-13 Scope (owned only)',
            'provider_ids': [(6, 0, [cls.provider_owned.id])],
        })
        cls.user_c_login = 'p013_user_c@test.local'
        cls.user_c_pwd = 'pa$$word123!'
        cls.user_c = Users.create({
            'name': 'P0-13 User C',
            'login': cls.user_c_login,
            'email': cls.user_c_login,
            'password': cls.user_c_pwd,
            'groups_id': [(4, portal_group.id)],
        })
        partner_c = cls.user_c.partner_id.sudo()
        partner_c.hha_scope_group_id = cls.scope_group_c.id
        partner_c.portal_app_ids = [(6, 0, [cls.app_c.id])]

        Page = cls.env['dashboard.page'].sudo()
        cls.page_c = Page.create({
            'name': 'P0-13 Test Page',
            'key': 'p013_test',
            'app_id': cls.app_c.id,
            'is_active': True,
        })
        Filter = cls.env['dashboard.page.filter'].sudo()
        # is_provider_selector=True without scope_to_user_hha — Codex's
        # specific concern: the second opt-in to forgery validation.
        cls.filter_provider = Filter.create({
            'page_id': cls.page_c.id,
            'name': 'Provider',
            'param_name': 'hha_ccn',
            'field_name': 'hha_ccn',
            'is_provider_selector': True,
            'scope_to_user_hha': False,
            'is_active': True,
        })
        # Child filter that depends on the provider filter — needed to
        # exercise the legacy /api/v1/filters/cascade endpoint (which
        # passes ``parent_value`` of the depends_on_filter_id).
        cls.filter_child = Filter.create({
            'page_id': cls.page_c.id,
            'name': 'Child Geo',
            'param_name': 'child_geo',
            'field_name': 'child_geo',
            'depends_on_filter_id': cls.filter_provider.id,
            'is_active': True,
        })

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _post_json(self, path, payload, headers=None):
        """POST a JSON body to ``path`` on the test HTTP server."""
        h = {'Content-Type': 'application/json'}
        if headers:
            h.update(headers)
        return self.url_open(path, data=json.dumps(payload), headers=h)

    def _login_jwt(self, login, pwd, app_key=None):
        """Hit /api/v1/auth/login and return the (status, payload) tuple."""
        body = {'login': login, 'password': pwd}
        if app_key is not None:
            body['app_key'] = app_key
        resp = self._post_json('/api/v1/auth/login', body)
        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {}
        return resp.status_code, data

    # ─────────────────────────────────────────────────────────────────
    # Contract 1: explicit unauthorised app_key → 403, no fall-through
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.auth_api')
    def test_login_with_unauthorised_app_key_returns_403(self):
        status, data = self._login_jwt(
            self.user_a_login, self.user_a_pwd, app_key='p013b',
        )
        self.assertEqual(status, 403, f'Expected 403, got {status}: {data}')
        self.assertNotIn(
            'access_token', data,
            'Token must NOT be issued for an unauthorised app_key',
        )

    @mute_logger('odoo.http', 'posterra_portal.controllers.auth_api')
    def test_login_with_unauthorised_app_key_does_not_fall_through(self):
        # A's user passing app_key=B must NOT silently get a token for A
        # (the v1 fall-through bug). 403 is the only correct outcome.
        status, data = self._login_jwt(
            self.user_a_login, self.user_a_pwd, app_key='p013b',
        )
        self.assertEqual(status, 403)
        self.assertNotIn('app_key', data,
                         'Response must not echo a different app_key — that '
                         'would mask the bypass attempt')

    # ─────────────────────────────────────────────────────────────────
    # Contract 2: auto-detect picks the user's authorised app, even when
    # another active app comes first in DB. (Codex's regression catch.)
    # ─────────────────────────────────────────────────────────────────

    def test_login_auto_detect_picks_authorised_app_for_user_a(self):
        # User A in group_a → auto-detect picks app_a (id-asc first).
        status, data = self._login_jwt(self.user_a_login, self.user_a_pwd)
        self.assertEqual(status, 200, f'Expected 200, got {status}: {data}')
        self.assertEqual(data.get('app_key'), 'p013a',
                         f'Expected app_key=p013a, got {data.get("app_key")}')
        self.assertIn('access_token', data)

    def test_login_auto_detect_skips_unauthorised_first_app_for_user_b(self):
        # **The headline regression test.** User B is authorised ONLY for
        # app_b. App_a was created FIRST (lower id, comes first in the
        # default order='id asc' search). The legacy auto-detect would
        # have either:
        #   (a) returned the first matching app via per-mode shortcut
        #       (e.g. group_apps[0] = app_a) — wrong app
        #   (b) returned 403 because the final guard rejected app_a
        # The corrected helper-iteration must SKIP app_a (user lacks
        # access) and KEEP iterating until it finds app_b. The response
        # must be 200 with app_key='p013b'.
        status, data = self._login_jwt(self.user_b_login, self.user_b_pwd)
        self.assertEqual(status, 200,
                         f'Expected 200 (auto-detect found app_b), '
                         f'got {status}: {data}')
        self.assertEqual(data.get('app_key'), 'p013b',
                         f'Expected app_key=p013b (skipping app_a), '
                         f'got {data.get("app_key")}')
        self.assertIn('access_token', data)

    # ─────────────────────────────────────────────────────────────────
    # Contract 3: refresh after access revocation → 401
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.auth_api')
    def test_refresh_after_revocation_returns_401(self):
        # Step 1: log in successfully
        status, data = self._login_jwt(self.user_a_login, self.user_a_pwd)
        self.assertEqual(status, 200)
        refresh_token = data['refresh_token']
        # Step 2: revoke by removing user from portal_app_ids
        self.user_a.partner_id.sudo().portal_app_ids = [(5, 0, 0)]
        # Step 3: refresh should now 401
        resp = self._post_json('/api/v1/auth/refresh',
                               {'refresh_token': refresh_token})
        self.assertEqual(
            resp.status_code, 401,
            f'Refresh after revocation must 401, got {resp.status_code}',
        )

    # ─────────────────────────────────────────────────────────────────
    # Contract 4: archived user blocked at refresh
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.auth_api')
    def test_refresh_archived_user_returns_401(self):
        status, data = self._login_jwt(self.user_a_login, self.user_a_pwd)
        self.assertEqual(status, 200)
        refresh_token = data['refresh_token']
        self.user_a.sudo().active = False
        resp = self._post_json('/api/v1/auth/refresh',
                               {'refresh_token': refresh_token})
        self.assertEqual(resp.status_code, 401)
        self.user_a.sudo().active = True  # restore

    # ─────────────────────────────────────────────────────────────────
    # Contract 5: archived user blocked at login (already filters
    # active=true at the SQL layer — this verifies the contract holds)
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.auth_api')
    def test_login_archived_user_returns_401(self):
        self.user_a.sudo().active = False
        try:
            status, data = self._login_jwt(self.user_a_login, self.user_a_pwd)
            self.assertEqual(
                status, 401,
                f'Archived user login must 401, got {status}: {data}',
            )
            self.assertNotIn('access_token', data)
        finally:
            self.user_a.sudo().active = True

    # ─────────────────────────────────────────────────────────────────
    # Contract 6: nonexistent app_key → 404 (not silent fall-through)
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.auth_api')
    def test_login_unknown_app_key_returns_404(self):
        status, data = self._login_jwt(
            self.user_a_login, self.user_a_pwd, app_key='nonexistent',
        )
        self.assertEqual(status, 404, f'Expected 404, got {status}: {data}')

    # ─────────────────────────────────────────────────────────────────
    # Contract 7: revoked access denied at JWT validation (widget API)
    #
    # Note: this test stops short of fetching real widget data (which
    # requires a fully-seeded dashboard) — it verifies the auth layer
    # rejects after revocation. The full SQL-backed widget endpoint is
    # exercised by the integration test suite.
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_widget_api_after_revocation_returns_401(self):
        status, data = self._login_jwt(self.user_a_login, self.user_a_pwd)
        self.assertEqual(status, 200)
        access_token = data['access_token']

        # Revoke
        self.user_a.partner_id.sudo().portal_app_ids = [(5, 0, 0)]

        # Hit any /api/v1/* endpoint with the token; all share _get_api_user
        resp = self.url_open(
            '/api/v1/page/overview/config',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 401,
            f'Revoked access must 401 at widget API, got {resp.status_code}',
        )

    # ─────────────────────────────────────────────────────────────────
    # Contract 8: forged provider URL value → 403 at HTTP level.
    # Tests the is_provider_selector gate (Codex's P0-5 follow-up).
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_widget_api_forged_provider_value_returns_403(self):
        # User C is authorised for app_c (HHA-provider mode) and has a
        # scope group containing only ``provider_owned``. Passing the
        # CCN of ``provider_other`` in the URL must 403 — the user is
        # NOT authorised to view another tenant's HHA, even though the
        # filter is is_provider_selector=True (NOT scope_to_user_hha).
        # This is the gap Codex flagged: previously gated by
        # scope_to_user_hha alone; now also gated by is_provider_selector
        # for HHA-mode apps.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200,
                         f'Setup login failed: {status} {data}')
        access_token = data['access_token']

        # Forged: P013OTHER is NOT in user_c's scope group.
        forged_url = (
            f'/api/v1/page/{self.page_c.id}/badges?hha_ccn=P013OTHER'
        )
        resp = self.url_open(
            forged_url,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 403,
            f'Forged provider URL value must 403 at /badges, '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )

    def test_widget_api_authorised_provider_value_returns_200_json(self):
        # Sanity check (positive case): the same endpoint with a value
        # IN the user's scope must succeed. We assert 200 AND a parseable
        # JSON body — a lenient "not 403" assertion would let the test
        # pass even if the endpoint were broken (5xx) for legitimate
        # in-scope values, masking regressions.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200)
        access_token = data['access_token']

        ok_url = (
            f'/api/v1/page/{self.page_c.id}/badges?hha_ccn=P013OWN'
        )
        resp = self.url_open(
            ok_url,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 200,
            f'Authorised provider value must succeed (200), '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )
        try:
            body = resp.json()
        except ValueError:
            self.fail(f'Response is not JSON: {resp.content[:200]!r}')
        self.assertIsInstance(
            body, dict,
            f'Response must be a JSON object; got {type(body).__name__}',
        )
        # The badges endpoint returns a dict with a 'badges' key
        # (possibly empty list when no badges are configured).
        self.assertIn(
            'badges', body,
            f'Response is JSON but missing badges key: {body!r}',
        )

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_widget_api_csv_with_forged_value_returns_403(self):
        # CSV multi-select: one valid + one forged value must reject the
        # whole request. We do not silently clamp.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200)
        access_token = data['access_token']

        forged_csv_url = (
            f'/api/v1/page/{self.page_c.id}/badges'
            f'?hha_ccn=P013OWN,P013OTHER'
        )
        resp = self.url_open(
            forged_csv_url,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(resp.status_code, 403)

    # ─────────────────────────────────────────────────────────────────
    # Contract 9: cascade endpoints must reject forged values too.
    # _build_portal_ctx is bypassed here — the endpoints feed the URL
    # values directly into ``filter.get_options()`` which builds SQL.
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_cascade_multi_with_forged_constraint_returns_403(self):
        # /api/v1/filters/cascade/multi accepts a JSON ``constraints``
        # body keyed by source-filter-id. A forged provider value here
        # would be used as a SQL constraint when fetching options for
        # the target filter, leaking another tenant's option data.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200)
        access_token = data['access_token']

        # Constraint: filter <id of provider filter> = 'P013OTHER'.
        # The provider filter is is_provider_selector=True on an HHA app,
        # so the cascade gate triggers. P013OTHER is NOT in user_c's scope.
        constraints_json = json.dumps(
            {str(self.filter_provider.id): 'P013OTHER'}
        )
        url = (
            f'/api/v1/filters/cascade/multi'
            f'?filter_id={self.filter_provider.id}'
            f'&constraints={constraints_json}'
        )
        resp = self.url_open(
            url,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 403,
            f'Forged constraint in cascade/multi must 403, '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_cascade_multi_with_forged_all_values_returns_403(self):
        # Same endpoint, ``all_values`` body — keyed by param_name.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200)
        access_token = data['access_token']

        all_values_json = json.dumps({'hha_ccn': 'P013OTHER'})
        url = (
            f'/api/v1/filters/cascade/multi'
            f'?filter_id={self.filter_provider.id}'
            f'&all_values={all_values_json}'
        )
        resp = self.url_open(
            url,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 403,
            f'Forged all_values in cascade/multi must 403, '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_filters_resolve_with_forged_changed_value_returns_403(self):
        # /api/v1/filters/resolve accepts JSON body with
        # ``changed_filter_id`` + ``changed_value``. A forged provider
        # value here propagates to every downstream cascade target as a
        # constraint.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200)
        access_token = data['access_token']

        body = {
            'page_id': self.page_c.id,
            'changed_filter_id': self.filter_provider.id,
            'changed_value': 'P013OTHER',
            'current_values': {},
        }
        resp = self._post_json(
            '/api/v1/filters/resolve', body,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 403,
            f'Forged changed_value in /resolve must 403, '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_filters_resolve_with_forged_current_values_array_returns_403(self):
        # JSON array-of-pairs is a valid input to ``dict()``: the
        # endpoint coerces ``[["hha_ccn", "P013OTHER"]]`` into
        # ``{"hha_ccn": "P013OTHER"}`` later. The fix normalises BEFORE
        # validation; a previous gate of ``isinstance(current_values, dict)``
        # would have skipped validation here and let the forged value
        # become a cascade constraint.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200)
        access_token = data['access_token']

        body = {
            'page_id': self.page_c.id,
            'changed_filter_id': self.filter_provider.id,
            'changed_value': '',  # not the trigger; current_values is
            'current_values': [['hha_ccn', 'P013OTHER']],
        }
        resp = self._post_json(
            '/api/v1/filters/resolve', body,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 403,
            f'Forged current_values (array form) in /resolve must 403, '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )

    # ─────────────────────────────────────────────────────────────────
    # Contract 10 (P0-6): builder admin gate must reject non-admins.
    # ─────────────────────────────────────────────────────────────────

    @mute_logger('odoo.http', 'dashboard_builder.controllers.builder_api')
    def test_builder_api_internal_user_without_admin_group_returns_403(self):
        # **The headline P0-6 regression test.** An INTERNAL Odoo user
        # (``base.group_user`` member, ``share=False``) without the
        # builder admin group must be rejected. The previous gate of
        # ``base.group_user`` would have ACCEPTED this user — exactly
        # the bypass P0-6 closes. Earlier portal-user-based tests don't
        # prove this because portal users fail BOTH the old and new
        # gates for unrelated reasons.
        Users = self.env['res.users'].sudo()
        internal_login = 'p013_internal_no_admin@test.local'
        internal_pwd = 'pa$$word123!'
        internal_user = Users.create({
            'name': 'P0-13 Internal User (no builder admin)',
            'login': internal_login,
            'email': internal_login,
            'password': internal_pwd,
            'groups_id': [(4, self.env.ref('base.group_user').id)],
        })
        # Internal users still need portal_app_ids for JWT login to
        # succeed (user_can_access_app contract). Without it, the test
        # would 403 at login rather than at the builder admin gate —
        # not the contract we want to prove.
        internal_user.partner_id.sudo().portal_app_ids = [(6, 0, [self.app_a.id])]
        internal_user.partner_id.sudo().hha_provider_id = self.provider_owned.id

        status, data = self._login_jwt(internal_login, internal_pwd, app_key='p013a')
        # Internal user passes login because they're in portal_app_ids
        # of app_a. Now hit the builder API:
        self.assertEqual(status, 200, f'Setup login failed: {status} {data}')
        access_token = data['access_token']

        resp = self.url_open(
            '/api/v1/builder/sources',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 403,
            f'Internal-user-without-admin-group must 403 at builder API '
            f'(this is what P0-6 closes); got {resp.status_code}: '
            f'{resp.content[:200]!r}',
        )

    def test_builder_api_internal_user_with_admin_group_returns_200(self):
        # **Positive test for P0-6.** Same internal user, but with the
        # ``dashboard_builder.group_dashboard_builder_admin`` group —
        # must succeed (200 + JSON list of sources). Catches over-blocking
        # if the group XML ID changes or the gate logic gets too strict.
        Users = self.env['res.users'].sudo()
        admin_login = 'p013_internal_admin@test.local'
        admin_pwd = 'pa$$word123!'
        admin_group = self.env.ref(
            'dashboard_builder.group_dashboard_builder_admin')
        admin_user = Users.create({
            'name': 'P0-13 Internal User (builder admin)',
            'login': admin_login,
            'email': admin_login,
            'password': admin_pwd,
            'groups_id': [
                (4, self.env.ref('base.group_user').id),
                (4, admin_group.id),
            ],
        })
        admin_user.partner_id.sudo().portal_app_ids = [(6, 0, [self.app_a.id])]
        admin_user.partner_id.sudo().hha_provider_id = self.provider_owned.id

        status, data = self._login_jwt(admin_login, admin_pwd, app_key='p013a')
        self.assertEqual(status, 200, f'Setup login failed: {status} {data}')
        access_token = data['access_token']

        resp = self.url_open(
            '/api/v1/builder/sources',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 200,
            f'Builder-admin-group user must succeed at builder API; '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_legacy_cascade_with_forged_parent_value_returns_403(self):
        # Legacy /api/v1/filters/cascade endpoint takes a single
        # ``parent_value`` for the target filter's depends_on_filter_id.
        # We hit it on the child filter (depends on filter_provider) and
        # pass a forged parent_value (= a CCN outside user_c's scope).
        # The provider filter is is_provider_selector on an HHA app, so
        # the gate triggers on the parent.
        status, data = self._login_jwt(
            self.user_c_login, self.user_c_pwd, app_key='p013c',
        )
        self.assertEqual(status, 200)
        access_token = data['access_token']

        url = (
            f'/api/v1/filters/cascade'
            f'?filter_id={self.filter_child.id}'
            f'&parent_value=P013OTHER'
        )
        resp = self.url_open(
            url,
            headers={'Authorization': f'Bearer {access_token}'},
        )
        self.assertEqual(
            resp.status_code, 403,
            f'Forged parent_value in legacy /cascade must 403, '
            f'got {resp.status_code}: {resp.content[:200]!r}',
        )