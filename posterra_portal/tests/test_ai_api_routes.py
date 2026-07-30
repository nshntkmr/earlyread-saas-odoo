# -*- coding: utf-8 -*-
"""AI Assist gateway route tests — authorization matrix + query behavior.

HttpCase over the real routes. ClickHouse is never contacted:
``QueryBuilder.execute_preview`` is patched for the execution test, and
every rejection case fails BEFORE execution by design.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_ai_assist --stop-after-init -d <test_db>
"""

import json
from unittest.mock import patch

from odoo.tests import HttpCase, tagged

SCOPE = 'posterra_ai'


@tagged('post_install', '-at_install', 'posterra_ai_assist')
class TestAiApiRoutes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.app = env['saas.app'].sudo().create({
            'name': 'AI Route App', 'app_key': 'ai-route-app',
            'access_mode': 'group',
            'access_group_xmlid': 'base.group_user',
            'ai_assist_enabled': True,
        })
        Conn = env['dashboard.connection'].sudo()
        cls.ch_conn = Conn.create({
            'name': 'CH Route', 'engine': 'clickhouse',
            'requires_tenant_filter': True, 'is_active': True,
        })
        cls.ch_conn2 = Conn.create({
            'name': 'CH Route 2', 'engine': 'clickhouse',
            'requires_tenant_filter': True, 'is_active': True,
        })
        Source = env['dashboard.schema.source'].sudo()
        cls.source = Source.create({
            'name': 'Route Src', 'table_name': 'route_src',
            'is_active': True, 'data_classification': 'non_phi',
            'connection_id': cls.ch_conn.id,
            'ai_app_ids': [(6, 0, [cls.app.id])],
        })
        # Visible source on a DIFFERENT connection + a relation to it —
        # must be omitted from advertised relations (cross-connection).
        cls.source_other_conn = Source.create({
            'name': 'Route Src Other', 'table_name': 'route_src_other',
            'is_active': True, 'data_classification': 'non_phi',
            'connection_id': cls.ch_conn2.id,
            'ai_app_ids': [(6, 0, [cls.app.id])],
        })
        env['dashboard.schema.relation'].sudo().create({
            'source_id': cls.source.id,
            'target_source_id': cls.source_other_conn.id,
            'join_type': 'left',
            'source_column': 'k', 'target_column': 'k',
        })
        # A source NOT AI-assigned — out-of-scope probe target.
        cls.hidden_source = Source.create({
            'name': 'Hidden Src', 'table_name': 'hidden_src',
            'is_active': True, 'data_classification': 'non_phi',
            'connection_id': cls.ch_conn.id,
        })

        Users = env['res.users'].sudo()
        group_internal = env.ref('base.group_user')
        group_ai = env.ref('posterra_portal.group_ai_assist_user')
        cls.analyst = Users.create({
            'name': 'AI Analyst', 'login': 'ai.analyst@test.local',
            'email': 'ai.analyst@test.local',
        })
        cls.no_group_user = Users.create({
            'name': 'No Group', 'login': 'ai.nogroup@test.local',
            'email': 'ai.nogroup@test.local',
        })
        # Odoo 19: group membership is managed from the res.groups side
        # (groups_id is not writable on res.users — see
        # wizard/create_portal_user.py for the same pattern).
        group_internal.sudo().write({
            'user_ids': [(4, cls.analyst.id), (4, cls.no_group_user.id)]})
        group_ai.sudo().write({'user_ids': [(4, cls.analyst.id)]})
        for u in (cls.analyst, cls.no_group_user):
            u.partner_id.sudo().write(
                {'portal_app_ids': [(4, cls.app.id)]})

        # Dedicated user for the rate-limit test — the daily counter is
        # per-user, and the analyst accumulates rows in other tests.
        cls.rate_user = Users.create({
            'name': 'Rate User', 'login': 'ai.rate@test.local',
            'email': 'ai.rate@test.local',
        })
        group_internal.sudo().write({'user_ids': [(4, cls.rate_user.id)]})
        group_ai.sudo().write({'user_ids': [(4, cls.rate_user.id)]})
        cls.rate_user.partner_id.sudo().write(
            {'portal_app_ids': [(4, cls.app.id)]})

        cls.analyst_key = cls._make_key(cls.analyst)
        cls.no_group_key = cls._make_key(cls.no_group_user)
        cls.rate_key = cls._make_key(cls.rate_user)

    @classmethod
    def _make_key(cls, user):
        Apikeys = cls.env['res.users.apikeys'].with_user(user)
        try:
            return Apikeys._generate(SCOPE, 'route-test', False)
        except TypeError:
            return Apikeys._generate(SCOPE, 'route-test')

    def _open(self, path, key=None, app_key='ai-route-app', method='GET',
              payload=None):
        headers = {'X-App-Key': app_key}
        if key:
            headers['X-API-Key'] = key
        data = None
        if payload is not None:
            data = json.dumps(payload)
            headers['Content-Type'] = 'application/json'
        return self.url_open(path, data=data, headers=headers)

    # ── guard matrix ────────────────────────────────────────────────────

    def test_missing_key_401(self):
        self.assertEqual(self._open('/api/v1/ai/scope').status_code, 401)

    def test_invalid_key_401(self):
        self.assertEqual(
            self._open('/api/v1/ai/scope', key='not-a-real-key')
            .status_code, 401)

    def test_no_ai_group_403(self):
        self.assertEqual(
            self._open('/api/v1/ai/scope', key=self.no_group_key)
            .status_code, 403)

    def test_app_toggle_off_403(self):
        self.app.ai_assist_enabled = False
        try:
            self.assertEqual(
                self._open('/api/v1/ai/scope', key=self.analyst_key)
                .status_code, 403)
        finally:
            self.app.ai_assist_enabled = True

    def test_unknown_app_401(self):
        self.assertEqual(
            self._open('/api/v1/ai/scope', key=self.analyst_key,
                       app_key='no-such-app').status_code, 401)

    # ── scope payload ───────────────────────────────────────────────────

    def test_scope_lists_only_visible_and_same_conn_relations(self):
        resp = self._open('/api/v1/ai/scope', key=self.analyst_key)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        tables = {s['table_name'] for s in data['sources']}
        self.assertIn('route_src', tables)
        self.assertIn('route_src_other', tables)
        self.assertNotIn('hidden_src', tables)
        # Cross-connection relation must not be advertised.
        route_src = next(s for s in data['sources']
                         if s['table_name'] == 'route_src')
        self.assertEqual(route_src.get('relations', []), [])

    # ── query route ─────────────────────────────────────────────────────

    def test_query_out_of_scope_source_403(self):
        resp = self._open(
            '/api/v1/ai/query', key=self.analyst_key, method='POST',
            payload={'source_id': self.hidden_source.id,
                     'sql': 'SELECT 1 FROM hidden_src'})
        self.assertEqual(resp.status_code, 403)

    def test_query_comma_join_probe_400(self):
        probe = 'SELECT * FROM route_src, secret_table'
        resp = self._open(
            '/api/v1/ai/query', key=self.analyst_key, method='POST',
            payload={'source_id': self.source.id, 'sql': probe})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('secret_table', resp.json().get('error', ''))
        # Audit contract: rejection stores the SUBMITTED sql only —
        # nothing executed, so the executed column must be empty.
        log = self.env['ai.query.log'].sudo().search(
            [('user_id', '=', self.analyst.id),
             ('status', '=', 'validation_error')],
            limit=1, order='id desc')
        self.assertEqual(log.requested_sql, probe)
        self.assertFalse(log.sql)

    def test_query_settings_probe_400(self):
        resp = self._open(
            '/api/v1/ai/query', key=self.analyst_key, method='POST',
            payload={'source_id': self.source.id,
                     'sql': "SELECT * FROM route_src "
                            "SETTINGS SQL_tenant_id = 'other'"})
        self.assertEqual(resp.status_code, 400)

    def test_query_executes_rewritten_sql_and_caps_rows(self):
        captured = {}

        def fake_execute_preview(self_qb, sql, params=None, limit=25,
                                 schema_source=None):
            captured['sql'] = sql
            captured['limit'] = limit
            return ['a'], [(i,) for i in range(limit + 10)]

        with patch('odoo.addons.dashboard_builder.services.query_builder.'
                   'QueryBuilder.execute_preview', fake_execute_preview):
            resp = self._open(
                '/api/v1/ai/query', key=self.analyst_key, method='POST',
                payload={'source_id': self.source.id,
                         'sql': 'SELECT a FROM route_src', 'limit': 40})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # The EXECUTED sql is the policy's rewrite — outer LIMIT present.
        self.assertIn('LIMIT 40', captured['sql'])
        # Fetch-side truncation caps the response even when the executor
        # returned more.
        self.assertEqual(data['row_count'], 40)
        self.assertTrue(data['truncated'])
        # Audit contract on success: BOTH the submitted and the executed
        # (rewritten) SQL are stored.
        log = self.env['ai.query.log'].sudo().search(
            [('user_id', '=', self.analyst.id), ('status', '=', 'ok')],
            limit=1, order='id desc')
        self.assertTrue(log)
        self.assertEqual(log.requested_sql, 'SELECT a FROM route_src')
        self.assertIn('LIMIT 40', log.sql)

    def test_rate_limit_429_and_audit(self):
        ICP = self.env['ir.config_parameter'].sudo()
        old = ICP.get_param('posterra_ai.daily_query_limit', False)
        ICP.set_param('posterra_ai.daily_query_limit', '1')

        def fake_execute_preview(self_qb, sql, params=None, limit=25,
                                 schema_source=None):
            return ['a'], [(1,)]

        try:
            with patch('odoo.addons.dashboard_builder.services.'
                       'query_builder.QueryBuilder.execute_preview',
                       fake_execute_preview):
                r1 = self._open(
                    '/api/v1/ai/query', key=self.rate_key, method='POST',
                    payload={'source_id': self.source.id,
                             'sql': 'SELECT a FROM route_src'})
                self.assertEqual(r1.status_code, 200)
                r2 = self._open(
                    '/api/v1/ai/query', key=self.rate_key, method='POST',
                    payload={'source_id': self.source.id,
                             'sql': 'SELECT a FROM route_src'})
            self.assertEqual(r2.status_code, 429)
            self.assertIn('resets_at', r2.json())
            # Audit contract when rate-limited: submitted SQL recorded,
            # executed column empty (nothing ran).
            log = self.env['ai.query.log'].sudo().search(
                [('user_id', '=', self.rate_user.id),
                 ('status', '=', 'rate_limited')],
                limit=1, order='id desc')
            self.assertTrue(log)
            self.assertEqual(log.requested_sql, 'SELECT a FROM route_src')
            self.assertFalse(log.sql)
        finally:
            ICP.set_param('posterra_ai.daily_query_limit', old or '200')

    def test_query_negative_limit_clamped(self):
        captured = {}

        def fake_execute_preview(self_qb, sql, params=None, limit=25,
                                 schema_source=None):
            captured['sql'] = sql
            return ['a'], [(1,), (2,)]

        with patch('odoo.addons.dashboard_builder.services.query_builder.'
                   'QueryBuilder.execute_preview', fake_execute_preview):
            resp = self._open(
                '/api/v1/ai/query', key=self.analyst_key, method='POST',
                payload={'source_id': self.source.id,
                         'sql': 'SELECT a FROM route_src', 'limit': -5})
        self.assertEqual(resp.status_code, 200)
        # Clamped to the floor of 1, enforced in the rewritten SQL.
        self.assertIn('LIMIT 1', captured['sql'])
        self.assertEqual(resp.json()['row_count'], 1)
