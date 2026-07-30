# -*- coding: utf-8 -*-
"""HTTP-layer tests for the Part D remote_autocomplete controller work.

Covers the search/hydration endpoint (POST /api/v1/filters/<id>/search), the
no-preload page-config path, the PHI cache headers, forgery rejection, and the
remote cascade target in /api/v1/filters/resolve. The query executor is mocked
(module-global patch is visible to the in-process test server thread) so no
real Schema Source table is needed.

Run:
    odoo-bin --test-enable -i posterra_portal --test-tags posterra_remote_ep \\
             --stop-after-init -d <test_db>
"""
import json
import logging
from unittest.mock import MagicMock, patch

from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)

EXEC_PATH = 'odoo.addons.posterra_portal.utils.query_executors.get_executor'


def _executor(rows):
    """Fake get_executor() whose .execute(sql, params) returns (cols, rows)."""
    def factory(env, source):
        ex = MagicMock()
        ex.execute.side_effect = lambda sql, params: (['eid', 'patient_name'], rows)
        return ex
    return factory


@tagged('post_install', '-at_install', 'posterra_remote_ep')
class TestRemoteFilterEndpoint(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Group = cls.env['res.groups'].sudo()
        IMD = cls.env['ir.model.data'].sudo()
        App = cls.env['saas.app'].sudo()
        Users = cls.env['res.users'].sudo()
        portal_group = cls.env.ref('base.group_portal')

        # ── Group-mode app (core endpoint tests; no provider scope) ──────────
        cls.grp = Group.create({
            'name': 'RA EP Users', 'implied_ids': [(4, portal_group.id)]})
        IMD.create({'module': 'posterra_portal', 'name': 'group_ra_ep',
                    'model': 'res.groups', 'res_id': cls.grp.id, 'noupdate': True})
        cls.app = App.create({
            'name': 'RA EP App', 'app_key': 'raep', 'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_ra_ep', 'is_active': True})
        cls.pwd = 'pa$$word123!'
        cls.user = Users.create({
            'name': 'RA EP User', 'login': 'ra_ep@test.local',
            'email': 'ra_ep@test.local', 'password': cls.pwd,
            'groups_id': [(4, portal_group.id), (4, cls.grp.id)]})
        cls.user.partner_id.sudo().portal_app_ids = [(6, 0, [cls.app.id])]

        Page = cls.env['dashboard.page'].sudo()
        cls.page = Page.create({
            'name': 'RA EP Page', 'key': 'ra_ep_page', 'app_id': cls.app.id,
            'is_active': True})
        Source = cls.env['dashboard.schema.source'].sudo()
        cls.source = Source.create({'name': 'ra_ep_src', 'table_name': 'patient_dim'})
        Col = cls.env['dashboard.schema.column'].sudo()
        cls.col_eid = Col.create({'source_id': cls.source.id, 'column_name': 'eid',
                                  'display_name': 'EID', 'data_type': 'text'})
        cls.col_name = Col.create({'source_id': cls.source.id, 'column_name': 'patient_name',
                                   'display_name': 'Name', 'data_type': 'text'})
        Filter = cls.env['dashboard.page.filter'].sudo()
        cls.remote = Filter.create({
            'page_id': cls.page.id, 'name': 'Find patient', 'param_name': 'EID',
            'ui_type': 'remote_autocomplete', 'schema_source_id': cls.source.id,
            'schema_column_id': cls.col_eid.id, 'display_template_source': 'schema',
            'display_template': '{patient_name}',
            'search_column_ids': [(6, 0, [cls.col_eid.id, cls.col_name.id])],
            'search_page_size': 50, 'search_min_chars': 2, 'is_active': True,
            'is_visible': True})
        # Sibling (cascade source + a known current_values param).
        cls.sibling = Filter.create({
            'page_id': cls.page.id, 'name': 'Year', 'param_name': 'year',
            'field_name': 'year', 'is_active': True})
        cls.dep = cls.env['dashboard.filter.dependency'].sudo().create({
            'page_id': cls.page.id, 'source_filter_id': cls.sibling.id,
            'target_filter_id': cls.remote.id, 'source_param': 'year',
            'target_param': 'EID', 'propagation': 'required', 'resets_target': False})

        # ── Second app (for cross-app 404) ───────────────────────────────────
        cls.grp2 = Group.create({
            'name': 'RA EP Users 2', 'implied_ids': [(4, portal_group.id)]})
        IMD.create({'module': 'posterra_portal', 'name': 'group_ra_ep2',
                    'model': 'res.groups', 'res_id': cls.grp2.id, 'noupdate': True})
        cls.app2 = App.create({
            'name': 'RA EP App2', 'app_key': 'raep2', 'access_mode': 'group',
            'access_group_xmlid': 'posterra_portal.group_ra_ep2', 'is_active': True})
        cls.page2 = Page.create({
            'name': 'RA EP Page2', 'key': 'ra_ep_page2', 'app_id': cls.app2.id,
            'is_active': True})
        cls.remote_other_app = Filter.create({
            'page_id': cls.page2.id, 'name': 'Find patient', 'param_name': 'EID',
            'ui_type': 'remote_autocomplete', 'schema_source_id': cls.source.id,
            'schema_column_id': cls.col_eid.id, 'display_template_source': 'schema',
            'display_template': '{patient_name}',
            'search_column_ids': [(6, 0, [cls.col_eid.id])],
            'search_page_size': 50, 'is_active': True, 'is_visible': True})

        # ── HHA-provider app (forgery 403) ───────────────────────────────────
        cls.app_hha = App.create({
            'name': 'RA EP HHA', 'app_key': 'raephha',
            'access_mode': 'hha_provider', 'is_active': True})
        Provider = cls.env['hha.provider'].sudo()
        cls.prov_own = Provider.create({'hha_ccn': 'RAEPOWN', 'hha_name': 'Owned'})
        cls.prov_other = Provider.create({'hha_ccn': 'RAEPOTHER', 'hha_name': 'Other'})
        ScopeGroup = cls.env['hha.scope.group'].sudo()
        cls.scope = ScopeGroup.create({
            'name': 'RA EP Scope', 'provider_ids': [(6, 0, [cls.prov_own.id])]})
        cls.user_hha = Users.create({
            'name': 'RA EP HHA User', 'login': 'ra_ep_hha@test.local',
            'email': 'ra_ep_hha@test.local', 'password': cls.pwd,
            'groups_id': [(4, portal_group.id)]})
        p = cls.user_hha.partner_id.sudo()
        p.hha_scope_group_id = cls.scope.id
        p.portal_app_ids = [(6, 0, [cls.app_hha.id])]
        cls.page_hha = Page.create({
            'name': 'RA EP HHA Page', 'key': 'ra_ep_hha_page',
            'app_id': cls.app_hha.id, 'is_active': True})
        cls.prov_filter = Filter.create({
            'page_id': cls.page_hha.id, 'name': 'Provider', 'param_name': 'hha_ccn',
            'field_name': 'hha_ccn', 'is_provider_selector': True, 'is_active': True})
        cls.remote_hha = Filter.create({
            'page_id': cls.page_hha.id, 'name': 'Find patient', 'param_name': 'EID',
            'ui_type': 'remote_autocomplete', 'schema_source_id': cls.source.id,
            'schema_column_id': cls.col_eid.id, 'display_template_source': 'schema',
            'display_template': '{patient_name}',
            'search_column_ids': [(6, 0, [cls.col_eid.id])],
            'search_page_size': 50, 'is_active': True, 'is_visible': True})

    # ── helpers ──────────────────────────────────────────────────────────────
    def _login(self, login=None, app_key='raep'):
        resp = self.url_open('/api/v1/auth/login', data=json.dumps(
            {'login': login or self.user.login, 'password': self.pwd, 'app_key': app_key}),
            headers={'Content-Type': 'application/json'})
        return resp.json()['access_token']

    def _search(self, filter_id, body, token=None):
        token = token or self._login()
        return self.url_open(
            f'/api/v1/filters/{filter_id}/search', data=json.dumps(body),
            headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {token}'})

    # ── no-preload config path ───────────────────────────────────────────────
    def test_config_api_no_preload_for_remote(self):
        token = self._login()
        # get_options must NOT be called for the remote filter on config build.
        with patch.object(type(self.remote), 'get_options',
                          side_effect=AssertionError('roster preloaded!')):
            resp = self.url_open('/api/v1/page/ra_ep_page/config',
                                 headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(resp.status_code, 200)
        filters = {f['id']: f for f in resp.json()['filters']}
        rf = filters[self.remote.id]
        self.assertEqual(rf['options'], [])
        self.assertEqual(rf['ui_type'], 'remote_autocomplete')
        self.assertEqual(rf['search_page_size'], 50)
        self.assertIn('display_region', rf)
        self.assertIn('apply_behavior', rf)

    # ── auth / access ────────────────────────────────────────────────────────
    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_missing_auth_401(self):
        resp = self.url_open(
            f'/api/v1/filters/{self.remote.id}/search', data='{}',
            headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 401)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_cross_app_filter_404(self):
        # Filter belongs to app2; token is for app → 404.
        resp = self._search(self.remote_other_app.id, {'query': 'ab'})
        self.assertEqual(resp.status_code, 404)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_non_remote_filter_400(self):
        resp = self._search(self.sibling.id, {'query': 'ab'})
        self.assertEqual(resp.status_code, 400)

    # ── shape / bounds validation ────────────────────────────────────────────
    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_mixed_shape_400(self):
        resp = self._search(self.remote.id, {'values': ['E1'], 'query': 'ab'})
        self.assertEqual(resp.status_code, 400)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_unknown_current_values_400(self):
        resp = self._search(self.remote.id,
                            {'query': 'ab', 'current_values': {'bogus_param': 'x'}})
        self.assertEqual(resp.status_code, 400)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_bad_offset_400(self):
        resp = self._search(self.remote.id, {'query': 'ab', 'offset': 'notint'})
        self.assertEqual(resp.status_code, 400)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_offset_out_of_range_400(self):
        resp = self._search(self.remote.id, {'query': 'ab', 'offset': 10 ** 9})
        self.assertEqual(resp.status_code, 400)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_bad_limit_400(self):
        resp = self._search(self.remote.id, {'query': 'ab', 'limit': 'notint'})
        self.assertEqual(resp.status_code, 400)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_query_not_string_400(self):
        resp = self._search(self.remote.id, {'query': {'a': 1}})
        self.assertEqual(resp.status_code, 400)

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_hydration_too_many_values_400(self):
        resp = self._search(self.remote.id, {'values': ['E1', 'E2']})
        self.assertEqual(resp.status_code, 400)

    # ── happy paths (executor mocked) ────────────────────────────────────────
    def test_search_happy_path(self):
        token = self._login()
        rows = [('E%d' % i, 'P%d' % i) for i in range(51)]  # page(50)+1
        with patch(EXEC_PATH, _executor(rows)):
            resp = self._search(self.remote.id, {'query': 'ab'}, token=token)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['has_more'])
        self.assertEqual(len(body['options']), 50)

    def test_hydration_happy_path(self):
        token = self._login()
        with patch(EXEC_PATH, _executor([('E1', 'Alice')])):
            resp = self._search(self.remote.id, {'values': ['E1']}, token=token)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['options'], [{'value': 'E1', 'label': 'Alice'}])

    # ── PHI cache headers ────────────────────────────────────────────────────
    def test_headers_no_store_and_vary_on_success(self):
        token = self._login()
        with patch(EXEC_PATH, _executor([])):
            resp = self._search(self.remote.id, {'query': 'ab'}, token=token)
        self.assertIn('no-store', resp.headers.get('Cache-Control', ''))
        self.assertIn('Authorization', resp.headers.get('Vary', ''))

    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_headers_no_store_and_vary_on_error(self):
        resp = self._search(self.remote.id, {'query': 'ab', 'offset': 'bad'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('no-store', resp.headers.get('Cache-Control', ''))
        self.assertIn('Authorization', resp.headers.get('Vary', ''))

    # ── forgery (hha_provider app) ───────────────────────────────────────────
    @mute_logger('odoo.http', 'posterra_portal.controllers.widget_api')
    def test_search_forged_provider_current_value_403(self):
        token = self._login(login=self.user_hha.login, app_key='raephha')
        # RAEPOTHER is not in the user's scope → 403 before any query.
        resp = self._search(self.remote_hha.id,
                            {'query': 'ab', 'current_values': {'hha_ccn': 'RAEPOTHER'}},
                            token=token)
        self.assertEqual(resp.status_code, 403)

    # ── cascade: remote target ───────────────────────────────────────────────
    def _resolve(self, token, changed_value, current_values):
        return self.url_open('/api/v1/filters/resolve', data=json.dumps({
            'page_id': self.page.id, 'changed_filter_id': self.sibling.id,
            'changed_value': changed_value, 'current_values': current_values,
        }), headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {token}'})

    def test_cascade_remote_target_hydrates_and_keeps(self):
        self.dep.sudo().resets_target = False
        token = self._login()
        with patch(EXEC_PATH, _executor([('E1', 'Alice')])):
            resp = self._resolve(token, '2024', {'EID': 'E1', 'year': ''})
        self.assertEqual(resp.status_code, 200)
        upd = resp.json()['updated_filters'][str(self.remote.id)]
        self.assertEqual(upd['new_value'], 'E1')
        self.assertEqual(upd['options'], [{'value': 'E1', 'label': 'Alice'}])

    def test_cascade_remote_target_resets_clears(self):
        self.dep.sudo().resets_target = True
        token = self._login()
        # resets_target=True → cleared without any roster enumeration.
        with patch.object(type(self.remote), 'get_options',
                          side_effect=AssertionError('roster enumerated on cascade!')):
            resp = self._resolve(token, '2024', {'EID': 'E1', 'year': ''})
        self.assertEqual(resp.status_code, 200)
        upd = resp.json()['updated_filters'][str(self.remote.id)]
        self.assertEqual(upd['new_value'], '')
        self.assertTrue(upd['value_changed'])
        self.dep.sudo().resets_target = False  # restore
