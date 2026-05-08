# -*- coding: utf-8 -*-
"""Unit tests for ``posterra_portal.utils.access.user_can_access_app``.

P0-1: the helper is the single source of truth for "may this user
access this app?". It must enforce ``portal_app_ids`` membership AS
a hard precondition AND the per-mode data-scope check on top.

The first-attempt helper conflated "has any provider link" with
"authorised for any HHA app", letting a user assigned only to app A
authenticate against app B. These tests guard that the corrected
combo check holds.

P0-13 covers the HTTP-layer bypass paths (login, refresh, browser
route, forged URL params, builder admin gate) in a separate HttpCase
test module.

Run:
    odoo-bin --test-enable -i posterra_portal --test-tags posterra_p0_1 \\
             --stop-after-init -d <test_db>
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from ..utils.access import user_can_access_app, values_in_user_scope
from ..utils.tenant_context import get_current_tenant_id


@tagged('post_install', '-at_install', 'posterra_p0_1', 'posterra_tenant')
class TestUserCanAccessApp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        Group = cls.env['res.groups'].sudo()
        IMD = cls.env['ir.model.data'].sudo()
        App = cls.env['saas.app'].sudo()
        Provider = cls.env['hha.provider'].sudo()
        Users = cls.env['res.users'].sudo()
        portal_group = cls.env.ref('base.group_portal')

        # ── Two group-mode apps (A and C) with their own security groups ──
        cls.group_a = Group.create({
            'name': 'Test App A Users',
            'implied_ids': [(4, portal_group.id)],
        })
        IMD.create({
            'module': 'posterra_portal',
            'name': 'group_p0test_app_a',
            'model': 'res.groups',
            'res_id': cls.group_a.id,
            'noupdate': True,
        })
        cls.app_a = App.create({
            'name': 'P0 Test App A',
            'app_key': 'p0testa',
            'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_p0test_app_a',
            'is_active': True,
        })

        cls.group_c = Group.create({
            'name': 'Test App C Users',
            'implied_ids': [(4, portal_group.id)],
        })
        IMD.create({
            'module': 'posterra_portal',
            'name': 'group_p0test_app_c',
            'model': 'res.groups',
            'res_id': cls.group_c.id,
            'noupdate': True,
        })
        cls.app_c = App.create({
            'name': 'P0 Test App C',
            'app_key': 'p0testc',
            'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_p0test_app_c',
            'is_active': True,
        })

        # ── Two hha_provider-mode apps (B1 and B2). The bypass test in
        # ``test_hha_user_in_app_b1_cannot_access_app_b2`` is the new-helper
        # contract: membership in ``portal_app_ids`` must gate, not just
        # "has any provider link".
        cls.app_b1 = App.create({
            'name': 'P0 Test App B1',
            'app_key': 'p0testb1',
            'access_mode': 'hha_provider',
            'is_active': True,
        })
        cls.app_b2 = App.create({
            'name': 'P0 Test App B2',
            'app_key': 'p0testb2',
            'access_mode': 'hha_provider',
            'is_active': True,
        })

        # ── Inactive group app (xmlid points to group_a so any test user
        # in group_a would succeed via the data-scope check; we want the
        # is_active=False check to short-circuit BEFORE that).
        cls.app_inactive = App.create({
            'name': 'P0 Test App Inactive',
            'app_key': 'p0testinact',
            'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_p0test_app_a',
            'is_active': False,
        })

        # ── Test provider record ──────────────────────────────────────────
        cls.provider = Provider.create({
            'hha_ccn': 'P0TEST001',
            'hha_name': 'P0 Test Provider',
        })

        # ── Users ─────────────────────────────────────────────────────────
        # U1: HHA provider link AND portal_app_ids=[B1].
        # Expected: access B1 yes; access B2 NO (not in portal_app_ids
        # — exactly the bypass the prior helper allowed).
        cls.user_b1_only = Users.create({
            'name': 'U1 B1 Only',
            'login': 'p0_u1@test.local',
            'email': 'p0_u1@test.local',
            'groups_id': [(4, portal_group.id)],
        })
        partner1 = cls.user_b1_only.partner_id.sudo()
        partner1.hha_provider_id = cls.provider.id
        partner1.portal_app_ids = [(6, 0, [cls.app_b1.id])]

        # U2: in group A, portal_app_ids=[A]. Plain group-app member.
        cls.user_a_only = Users.create({
            'name': 'U2 A Only',
            'login': 'p0_u2@test.local',
            'email': 'p0_u2@test.local',
            'groups_id': [(4, portal_group.id), (4, cls.group_a.id)],
        })
        cls.user_a_only.partner_id.sudo().portal_app_ids = [(6, 0, [cls.app_a.id])]

        # U3: in group A AND has HHA provider, portal_app_ids=[A, B1].
        # Multi-app authorised.
        cls.user_ab1 = Users.create({
            'name': 'U3 A+B1',
            'login': 'p0_u3@test.local',
            'email': 'p0_u3@test.local',
            'groups_id': [(4, portal_group.id), (4, cls.group_a.id)],
        })
        partner3 = cls.user_ab1.partner_id.sudo()
        partner3.hha_provider_id = cls.provider.id
        partner3.portal_app_ids = [(6, 0, [cls.app_a.id, cls.app_b1.id])]

        # U4: HHA provider link, portal_app_ids EMPTY.
        # The "loose helper" trap: provider exists, but no portal_app_ids.
        # Must be denied for every app.
        cls.user_provider_no_app = Users.create({
            'name': 'U4 Provider But No App',
            'login': 'p0_u4@test.local',
            'email': 'p0_u4@test.local',
            'groups_id': [(4, portal_group.id)],
        })
        cls.user_provider_no_app.partner_id.sudo().hha_provider_id = cls.provider.id

        # U5: in group A and group C, portal_app_ids=[A] only.
        # The "group-without-portal_app_ids" trap: legacy group memberships
        # mustn't authorise apps not in portal_app_ids.
        cls.user_group_legacy = Users.create({
            'name': 'U5 Group A+C, App A only',
            'login': 'p0_u5@test.local',
            'email': 'p0_u5@test.local',
            'groups_id': [
                (4, portal_group.id), (4, cls.group_a.id), (4, cls.group_c.id),
            ],
        })
        cls.user_group_legacy.partner_id.sudo().portal_app_ids = [(6, 0, [cls.app_a.id])]

        # U6: no portal_app_ids, no provider, no groups (other than portal).
        cls.user_none = Users.create({
            'name': 'U6 None',
            'login': 'p0_u6@test.local',
            'email': 'p0_u6@test.local',
            'groups_id': [(4, portal_group.id)],
        })

    # ──────────────────────────────────────────────────────────────────
    # The headline contract: portal_app_ids gates access for HHA apps
    # ──────────────────────────────────────────────────────────────────

    def test_hha_user_in_app_b1_can_access_b1(self):
        self.assertTrue(user_can_access_app(self.user_b1_only, self.app_b1))

    def test_hha_user_in_app_b1_cannot_access_app_b2(self):
        # The bypass the first-attempt helper allowed. With the corrected
        # helper, B1's user is NOT in B2's portal_app_ids and must be denied
        # even though they have a valid provider link.
        self.assertFalse(user_can_access_app(self.user_b1_only, self.app_b2))

    def test_hha_user_with_no_portal_app_denied_for_every_hha_app(self):
        # U4 has a provider but no portal_app_ids — old helper would say yes.
        # New helper: deny for any app.
        self.assertFalse(user_can_access_app(self.user_provider_no_app, self.app_b1))
        self.assertFalse(user_can_access_app(self.user_provider_no_app, self.app_b2))

    # ──────────────────────────────────────────────────────────────────
    # portal_app_ids gates access for group apps too
    # ──────────────────────────────────────────────────────────────────

    def test_group_member_with_portal_app_can_access(self):
        self.assertTrue(user_can_access_app(self.user_a_only, self.app_a))

    def test_legacy_group_membership_without_portal_app_denied(self):
        # U5 is in group_c via groups_id, but portal_app_ids only contains A.
        # The legacy path that granted group membership without going through
        # portal_app_ids.write() must NOT authorise C.
        self.assertFalse(user_can_access_app(self.user_group_legacy, self.app_c))
        # Sanity: U5 IS authorised for A
        self.assertTrue(user_can_access_app(self.user_group_legacy, self.app_a))

    # ──────────────────────────────────────────────────────────────────
    # Combined / edge cases
    # ──────────────────────────────────────────────────────────────────

    def test_multi_app_authorised_user(self):
        self.assertTrue(user_can_access_app(self.user_ab1, self.app_a))
        self.assertTrue(user_can_access_app(self.user_ab1, self.app_b1))
        # U3 not in app_b2's portal_app_ids → denied even though they have
        # a provider link.
        self.assertFalse(user_can_access_app(self.user_ab1, self.app_b2))
        # U3 not in app_c → denied even though they're not in group_c either.
        self.assertFalse(user_can_access_app(self.user_ab1, self.app_c))

    def test_no_membership_user_denied_everywhere(self):
        for app in [self.app_a, self.app_b1, self.app_b2, self.app_c]:
            self.assertFalse(
                user_can_access_app(self.user_none, app),
                f'U6 (no memberships) should be denied for {app.app_key}',
            )

    # ──────────────────────────────────────────────────────────────────
    # Inactive app — short-circuit BEFORE membership/data-scope checks
    # ──────────────────────────────────────────────────────────────────

    def test_inactive_app_denied_even_for_authorised_user(self):
        # Add U2 to inactive app's portal_app_ids; access still denied
        # because is_active=False.
        self.user_a_only.partner_id.sudo().portal_app_ids = [
            (4, self.app_inactive.id),
        ]
        self.assertFalse(user_can_access_app(self.user_a_only, self.app_inactive))

    # ──────────────────────────────────────────────────────────────────
    # Group app misconfiguration — fail closed
    # ──────────────────────────────────────────────────────────────────

    def test_group_app_with_blank_xmlid_denied(self):
        broken = self.env['saas.app'].sudo().create({
            'name': 'P0 Broken Group App',
            'app_key': 'p0broken1',
            'access_mode': 'group',
            'access_group_xmlid': '',
            'is_active': True,
        })
        self.user_a_only.partner_id.sudo().portal_app_ids = [
            (4, broken.id),
        ]
        self.assertFalse(user_can_access_app(self.user_a_only, broken))

    def test_group_app_with_invalid_xmlid_denied(self):
        broken = self.env['saas.app'].sudo().create({
            'name': 'P0 Bad Xmlid App',
            'app_key': 'p0broken2',
            'access_mode': 'group',
            'access_group_xmlid': 'no_such_module.no_such_group',
            'is_active': True,
        })
        self.user_a_only.partner_id.sudo().portal_app_ids = [
            (4, broken.id),
        ]
        self.assertFalse(user_can_access_app(self.user_a_only, broken))

    # ──────────────────────────────────────────────────────────────────
    # Degenerate inputs — fail closed
    # ──────────────────────────────────────────────────────────────────

    def test_falsy_user_returns_false(self):
        self.assertFalse(user_can_access_app(False, self.app_a))
        self.assertFalse(user_can_access_app(None, self.app_a))

    def test_falsy_app_returns_false(self):
        self.assertFalse(user_can_access_app(self.user_a_only, False))
        self.assertFalse(user_can_access_app(self.user_a_only, None))

    # ──────────────────────────────────────────────────────────────────
    # Inactive (archived) user — revocation contract
    # ──────────────────────────────────────────────────────────────────

    def test_archived_user_denied_even_when_authorised(self):
        # U2 (group A member, portal_app_ids=[A]) is normally authorised
        # for app_a. Archiving the user must immediately revoke access —
        # callers that bypass for superadmins still rely on the helper,
        # so this contract is the canonical "user revoked" signal.
        self.assertTrue(
            user_can_access_app(self.user_a_only, self.app_a),
            'precondition: user must be authorised before archiving',
        )
        self.user_a_only.sudo().active = False
        self.assertFalse(user_can_access_app(self.user_a_only, self.app_a))
        # Restore so other tests aren't affected (TransactionCase rolls back
        # but explicit restore makes intent obvious):
        self.user_a_only.sudo().active = True

    def test_archived_hha_user_denied(self):
        self.user_b1_only.sudo().active = False
        self.assertFalse(user_can_access_app(self.user_b1_only, self.app_b1))
        self.user_b1_only.sudo().active = True


@tagged('post_install', '-at_install', 'posterra_p0_5', 'posterra_tenant')
class TestValuesInUserScope(TransactionCase):
    """P0-5: forged URL provider values must be rejected before SQL.

    Validates ``values_in_user_scope`` against the matching contract used
    by widget SQL: filter's ``field_name`` (or schema column / param key
    fallback) keys against the user's accessible providers. Empty / 'all'
    sentinels pass; CSV multi-select must reject if ANY value is forged.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Provider = cls.env['hha.provider'].sudo()
        cls.provider_a = Provider.create({
            'hha_ccn': 'P05A001', 'hha_name': 'P0-5 Test A',
        })
        cls.provider_b = Provider.create({
            'hha_ccn': 'P05B002', 'hha_name': 'P0-5 Test B',
        })
        cls.provider_other = Provider.create({
            'hha_ccn': 'OTHER999', 'hha_name': 'Other tenant — forbidden',
        })
        cls.user_scope = cls.provider_a + cls.provider_b
        # Minimal mock filter: tests don't need a real dashboard.page.filter,
        # they only need ``field_name`` / ``param_name`` attrs read by the
        # helper. ``MockFilter`` keeps the test self-contained.
        cls.filter_ccn = type('MockFilter', (), {
            'field_name': 'hha_ccn',
            'schema_column_name': '',
            'param_name': 'hha_ccn',
        })()
        cls.filter_id = type('MockFilter', (), {
            'field_name': 'id',
            'schema_column_name': '',
            'param_name': 'hha_id',
        })()

    # ── empty / 'all' sentinels pass ──────────────────────────────────

    def test_empty_value_passes(self):
        self.assertTrue(values_in_user_scope('', self.filter_ccn, self.user_scope))
        self.assertTrue(values_in_user_scope(None, self.filter_ccn, self.user_scope))
        self.assertTrue(values_in_user_scope('   ', self.filter_ccn, self.user_scope))

    def test_all_sentinel_passes(self):
        self.assertTrue(values_in_user_scope('all', self.filter_ccn, self.user_scope))
        self.assertTrue(values_in_user_scope('ALL', self.filter_ccn, self.user_scope))

    # ── single-value match ────────────────────────────────────────────

    def test_authorised_value_passes(self):
        self.assertTrue(values_in_user_scope(
            'P05A001', self.filter_ccn, self.user_scope))
        self.assertTrue(values_in_user_scope(
            'P05B002', self.filter_ccn, self.user_scope))

    def test_forged_value_rejected(self):
        # The headline contract: a CCN belonging to ANOTHER tenant must
        # NOT pass the helper, regardless of how it was supplied (URL
        # forgery, browser-store tampering, etc.).
        self.assertFalse(values_in_user_scope(
            'OTHER999', self.filter_ccn, self.user_scope))

    def test_unknown_value_rejected(self):
        # Value not matching any provider in the user's scope OR the wider
        # population — could be a typo or an attacker probing IDs.
        self.assertFalse(values_in_user_scope(
            'NONEXISTENT', self.filter_ccn, self.user_scope))

    # ── multi-select (CSV) ────────────────────────────────────────────

    def test_csv_all_authorised_passes(self):
        self.assertTrue(values_in_user_scope(
            'P05A001,P05B002', self.filter_ccn, self.user_scope))

    def test_csv_one_forged_rejects_all(self):
        # Single forged value in a CSV → reject the whole request. We do
        # not silently clamp — clamping hides bypass attempts.
        self.assertFalse(values_in_user_scope(
            'P05A001,OTHER999', self.filter_ccn, self.user_scope))
        self.assertFalse(values_in_user_scope(
            'OTHER999,P05A001', self.filter_ccn, self.user_scope))

    def test_csv_with_whitespace_handled(self):
        self.assertTrue(values_in_user_scope(
            ' P05A001 , P05B002 ', self.filter_ccn, self.user_scope))

    # ── id-field matching ─────────────────────────────────────────────

    def test_id_field_match(self):
        # When field_name='id', helper compares against str(provider.id)
        scope_id = str(self.provider_a.id)
        forged_id = str(self.provider_other.id)
        self.assertTrue(values_in_user_scope(
            scope_id, self.filter_id, self.user_scope))
        self.assertFalse(values_in_user_scope(
            forged_id, self.filter_id, self.user_scope))

    # ── empty user scope ──────────────────────────────────────────────

    def test_empty_scope_rejects_any_value(self):
        # User with no providers (e.g. group-mode user) can't pass any
        # provider-scoped filter value — the helper returns False so the
        # caller raises 403. Caller should gate this with
        # ``f.scope_to_user_hha=True`` to avoid breaking legitimate
        # group-app filters that don't user-scope.
        empty_scope = self.env['hha.provider'].browse()
        self.assertFalse(values_in_user_scope(
            'P05A001', self.filter_ccn, empty_scope))
        # 'all' / empty still pass because they're "no filter" sentinels:
        self.assertTrue(values_in_user_scope(
            '', self.filter_ccn, empty_scope))
        self.assertTrue(values_in_user_scope(
            'all', self.filter_ccn, empty_scope))

    # ── Non-string defensive coercion (P0-5 robustness) ────────────────

    def test_none_value_passes(self):
        # ``None`` is treated as the no-filter sentinel; no AttributeError.
        self.assertTrue(values_in_user_scope(
            None, self.filter_ccn, self.user_scope))

    def test_int_value_coerced_to_string(self):
        # JSON payload can deliver an int where the contract expects str.
        # The helper must not raise — it coerces via ``str()`` and matches
        # against the accepted set. Since 'P05A001' is the accepted CCN,
        # an int input fails the match cleanly (False), no exception.
        self.assertFalse(values_in_user_scope(
            12345, self.filter_ccn, self.user_scope))

    def test_int_value_for_id_field_matches(self):
        # When the filter is field_name='id', an int input must coerce
        # cleanly and match the provider id.
        self.assertTrue(values_in_user_scope(
            self.provider_a.id, self.filter_id, self.user_scope))

    def test_list_value_does_not_raise(self):
        # JSON list input — repr-of-list won't match any CCN, returns
        # False. Critically: must NOT raise AttributeError.
        self.assertFalse(values_in_user_scope(
            ['P05A001', 'P05B002'], self.filter_ccn, self.user_scope))

    def test_dict_value_does_not_raise(self):
        self.assertFalse(values_in_user_scope(
            {'foo': 'bar'}, self.filter_ccn, self.user_scope))


@tagged('post_install', '-at_install', 'posterra_p0_8', 'posterra_tenant')
class TestAppKeyValidatorAndNormalisation(TransactionCase):
    """P0-8: app_key DNS validator + write-time normalisation.

    Validates two contracts:
      1. ``_check_app_key_valid`` rejects DNS-invalid characters
         (underscores, uppercase, leading/trailing hyphens, length > 63).
      2. ``create()`` / ``write()`` normalise via .strip().lower() BEFORE
         the validator runs, so e.g. ``"INHOME "`` becomes ``"inhome"``
         in the DB. A constraint alone validates a transient copy; only
         write-time normalisation guarantees the stored value matches
         what the validator checks.
    """

    def _make_app(self, key, name=None):
        return self.env['saas.app'].sudo().create({
            'name': name or f'App {key}',
            'app_key': key,
            'access_mode': 'hha_provider',
            'is_active': True,
        })

    # ── DNS regex: valid forms accepted ───────────────────────────────

    def test_lowercase_alphanumeric_accepted(self):
        app = self._make_app('inhome')
        self.assertEqual(app.app_key, 'inhome')

    def test_hyphenated_accepted(self):
        app = self._make_app('inhome-v1')
        self.assertEqual(app.app_key, 'inhome-v1')

    def test_leading_digit_accepted(self):
        # RFC 1123 relaxed RFC 1035 to allow leading digits.
        app = self._make_app('1nhome')
        self.assertEqual(app.app_key, '1nhome')

    # ── DNS regex: invalid forms rejected ─────────────────────────────

    def test_underscore_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_app('inhome_v1')

    def test_leading_hyphen_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_app('-inhome')

    def test_trailing_hyphen_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_app('inhome-')

    def test_dot_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_app('in.home')

    def test_too_long_rejected(self):
        # RFC 1035 caps DNS label length at 63 chars.
        with self.assertRaises(ValidationError):
            self._make_app('a' * 64)

    def test_admin_probe_rejected(self):
        # admin-probe is reserved for K8s liveness/readiness probe Host
        # headers — must not be usable as a tenant subdomain.
        with self.assertRaises(ValidationError):
            self._make_app('admin-probe')

    # ── Write-time normalisation ─────────────────────────────────────

    def test_create_normalises_uppercase(self):
        # ``"Inhome"`` (capital I) is DNS-invalid raw; normalisation to
        # ``"inhome"`` happens in create() BEFORE the validator runs,
        # so the record is created with the lowercased value. This is
        # the contract that closes the "stored value differs from
        # validated value" gap.
        app = self._make_app('Inhome', name='Inhome Capitalised')
        self.assertEqual(app.app_key, 'inhome',
                         'create() must lowercase app_key before validation')

    def test_create_normalises_trailing_whitespace(self):
        app = self._make_app('  inhome  ', name='Inhome Padded')
        self.assertEqual(app.app_key, 'inhome',
                         'create() must strip app_key before validation')

    def test_write_normalises_uppercase(self):
        app = self._make_app('inhome')
        app.app_key = 'POSTERRA'
        self.assertEqual(app.app_key, 'posterra',
                         'write() must lowercase app_key before validation')

    def test_write_normalises_trailing_whitespace(self):
        app = self._make_app('inhome')
        app.app_key = ' mssp '
        self.assertEqual(app.app_key, 'mssp')

    def test_normalised_value_still_invalid_rejects(self):
        # ``"In_home"`` lowercases to ``"in_home"`` which is still
        # DNS-invalid (underscore). Must reject.
        with self.assertRaises(ValidationError):
            self._make_app('In_home')


@tagged('post_install', '-at_install', 'posterra_p0_10', 'posterra_tenant')
class TestTenantIdContract(TransactionCase):
    """P0-10: ``request.tenant_id`` and ``get_current_tenant_id`` return
    the stable string ``saas.app.app_key``, not the integer id.

    Stable string keys survive PG rebuilds (a fresh Azure deploy keeps
    the same tenant tags in CH ``system.query_log``), are
    human-readable, and match the DNS subdomain. Integer ids would shift
    on every fresh-seed deploy.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Group = cls.env['res.groups'].sudo()
        IMD = cls.env['ir.model.data'].sudo()
        App = cls.env['saas.app'].sudo()
        Users = cls.env['res.users'].sudo()
        portal_group = cls.env.ref('base.group_portal')

        # One group-mode app + a user with portal_app_ids set.
        cls.group = Group.create({
            'name': 'P0-10 Test Group',
            'implied_ids': [(4, portal_group.id)],
        })
        IMD.create({
            'module': 'posterra_portal',
            'name': 'group_p0_10_app',
            'model': 'res.groups',
            'res_id': cls.group.id,
            'noupdate': True,
        })
        cls.app = App.create({
            'name': 'P0-10 Test App',
            'app_key': 'p010app',
            'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_p0_10_app',
            'is_active': True,
        })
        cls.user = Users.create({
            'name': 'P0-10 User',
            'login': 'p010_user@test.local',
            'email': 'p010_user@test.local',
            'groups_id': [(4, portal_group.id), (4, cls.group.id)],
        })
        cls.user.partner_id.sudo().portal_app_ids = [(6, 0, [cls.app.id])]

    def test_tenant_id_is_app_key_string_not_int(self):
        # Single-app user: fallback returns app_key (string)
        env = self.env(user=self.user)
        result = get_current_tenant_id(env, request=None)
        self.assertEqual(result, 'p010app',
                         'tenant_id must be the string app_key, not int id')
        self.assertIsInstance(
            result, str,
            f'tenant_id must be a string; got {type(result).__name__}',
        )

    def test_tenant_id_from_request_is_stringified(self):
        # When request.tenant_id is set (HTTP path), the helper
        # returns ``str(request.tenant_id)``. The contract is that the
        # value is ALREADY a string app_key (set by callsites in this
        # patch series), so str() is a no-op. Verify the helper passes
        # the value through unchanged.
        class FakeRequest:
            tenant_id = 'mssp'
        result = get_current_tenant_id(self.env, request=FakeRequest())
        self.assertEqual(result, 'mssp')

    def test_tenant_id_no_request_no_user_raises(self):
        env = self.env(user=self.env.ref('base.public_user'))
        with self.assertRaises(ValueError):
            get_current_tenant_id(env, request=None)
