# -*- coding: utf-8 -*-
"""Projection publisher (spec §4.2) with a fake ClickHouse client: row
shape, state transitions, dead after MAX_ATTEMPTS, Republish, the daily
mirror check, and the executor factory refusing publisher connections.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_projections --stop-after-init -d <test_db>
"""

import json

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.posterra_portal.utils import projection_publisher as pub
from odoo.addons.posterra_portal.utils.query_executors import get_executor_for_connection


class FakeClient(object):
    def __init__(self, fail=False):
        self.rows = []
        self.fail = fail

    def insert(self, table, rows, column_names=None):
        if self.fail:
            raise RuntimeError('boom')
        self.rows.append((table, rows, column_names))


@tagged('post_install', '-at_install', 'posterra_projections')
class TestProjectionPublisher(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = cls.env['saas.app'].create({
            'name': 'Pub App', 'app_key': 'pubapp', 'access_mode': 'group'})
        cls.read_conn = cls.env['dashboard.connection'].create({
            'name': 'CH read (test)', 'engine': 'clickhouse', 'host': 'localhost',
            'database': 'shared', 'username': 'u', 'password': 'p'})
        cls.pub_conn = cls.env['dashboard.connection'].create({
            'name': 'CH publisher (test)', 'engine': 'clickhouse', 'host': 'localhost',
            'database': 'shared', 'username': 'w', 'password': 'p', 'purpose': 'publisher'})
        cls.source = cls.env['dashboard.schema.source'].create({
            'name': 'CH src', 'table_name': 'shared.fact', 'connection_id': cls.read_conn.id,
            'app_ids': [(6, 0, [cls.app.id])],
            'column_ids': [(0, 0, {'column_name': n, 'display_name': n, 'data_type': t})
                           for n, t in (('HUM_ID', 'text'), ('MEASURE_CAT', 'text'),
                                        ('YEAR_MONTH', 'integer'), ('COMPLIANT_CNT', 'integer'))],
        })
        col = {c.column_name: c for c in cls.source.column_ids}
        cls.config = cls.env['dashboard.projection.config'].create({
            'name': 'CH type', 'app_id': cls.app.id, 'key': 'quality_compliance',
            'source_id': cls.source.id,
            'identity_column_ids': [(0, 0, {'sequence': 1, 'column_id': col['HUM_ID'].id}),
                                    (0, 0, {'sequence': 2, 'column_id': col['MEASURE_CAT'].id})],
            'snapshot_column_id': col['YEAR_MONTH'].id,
            'status_column_id': col['COMPLIANT_CNT'].id,
            'publisher_connection_id': cls.pub_conn.id,
            'mirror_table': 'shared.dashboard_projections',
        })
        cls.rec = cls.env['dashboard.projection'].create({
            'config_id': cls.config.id, 'identity_hash': 'a' * 32,
            'identity_json': '["H1", "BCS"]', 'cycle_no': 1, 'revision': 1,
            'first_applies_from': '202606', 'applies_from': '202606',
            'attempt_months': '202606', 'owner_name': 'Alice', 'publish_state': 'pending',
        })

    def _event(self, revision, state='pending'):
        return self.env['dashboard.projection.event'].create({
            'projection_id': self.rec.id, 'config_id': self.config.id,
            'identity_hash': self.rec.identity_hash, 'cycle_no': 1, 'action': 'mark',
            'actor_id': self.env.user.id, 'actor_name': 'Alice', 'at': '2026-09-08 10:00:00',
            'revision': revision, 'publish_state': state,
            'payload_json': json.dumps(self.rec.to_publish_payload()),
        })

    def test_executor_factory_refuses_publisher_connection(self):
        with self.assertRaises(ValueError):
            get_executor_for_connection(self.env, self.pub_conn)
        # Data-reading callers that only opt into allow_inactive still refuse.
        with self.assertRaises(ValueError):
            get_executor_for_connection(self.env, self.pub_conn, allow_inactive=True)
        self.assertIsNotNone(get_executor_for_connection(self.env, self.read_conn))

    def test_test_connection_may_build_an_executor_for_a_publisher(self):
        # Test Connection opts in explicitly so a publisher can be verified.
        executor = get_executor_for_connection(
            self.env, self.pub_conn, allow_inactive=True, allow_publisher=True)
        self.assertIsNotNone(executor)

    def test_publisher_connection_constraints(self):
        with self.assertRaises(ValidationError):
            self.config.write({'publisher_connection_id': self.read_conn.id})
        with self.assertRaises(ValidationError):
            self.config.write({'mirror_table': False})

    def test_publish_row_shape_and_state(self):
        client = FakeClient()
        ev = self._event(1)
        published, failed = pub.publish_events(
            self.env, ev, client_factory=lambda env, conn: client)
        self.assertEqual((published, failed), (1, 0))
        table, rows, cols = client.rows[0]
        self.assertEqual(table, 'shared.dashboard_projections')
        self.assertEqual(cols, pub.MIRROR_COLUMNS)
        row = dict(zip(cols, rows[0]))
        self.assertEqual(row['tenant_id'], 'pubapp')
        self.assertEqual(row['config_key'], 'quality_compliance')
        self.assertEqual((row['cycle_no'], row['revision'], row['state']), (1, 1, 'active'))
        self.assertEqual(row['attempt_months'], ['202606'])
        self.assertEqual(row['note'], '')                      # mirror_note off
        self.assertEqual(row['expected_date'], '')             # no nullable columns
        self.assertEqual(ev.publish_state, 'published')
        self.assertTrue(ev.published_at)
        self.assertEqual((self.rec.published_revision, self.rec.publish_state), (1, 'published'))

    def test_failure_then_dead(self):
        client = FakeClient(fail=True)
        ev = self._event(1)
        for i in range(pub.MAX_ATTEMPTS - 1):
            pub.publish_events(self.env, ev, client_factory=lambda env, conn: client)
            self.assertEqual(ev.publish_state, 'failed')
            self.assertEqual(ev.attempts, i + 1)
            self.assertEqual(ev.last_error, 'boom')
        pub.publish_events(self.env, ev, client_factory=lambda env, conn: client)
        self.assertEqual((ev.publish_state, ev.attempts), ('dead', pub.MAX_ATTEMPTS))
        self.assertEqual(self.rec.publish_state, 'dead')
        # Republish resets the outbox state and the cron picks it up
        self.assertTrue(pub.republish_cycle(self.rec))
        self.assertEqual((ev.publish_state, ev.attempts, self.rec.publish_state),
                         ('pending', 0, 'pending'))
        good = FakeClient()
        published, failed = pub.publish_pending(self.env, client_factory=lambda env, conn: good)
        self.assertEqual((published, failed), (1, 0))
        self.assertEqual(ev.publish_state, 'published')

    def test_pg_events_are_never_published(self):
        ev = self._event(1, state='none')
        published, failed = pub.publish_events(
            self.env, ev, client_factory=lambda env, conn: FakeClient())
        self.assertEqual((published, failed), (0, 0))
        self.assertEqual(ev.publish_state, 'none')

    def test_missing_publisher_configuration_fails_cleanly(self):
        ev = self._event(1)
        cfg = self.config
        cfg.write({'publisher_connection_id': False})
        published, failed = pub.publish_events(self.env, ev, client_factory=lambda env, conn: FakeClient())
        self.assertEqual((published, failed), (0, 1))
        self.assertEqual(ev.publish_state, 'failed')
        self.assertIn('publisher connection', ev.last_error)
        cfg.write({'publisher_connection_id': self.pub_conn.id})

    def test_check_mirror_requeues_missing_revisions(self):
        ev = self._event(1, state='published')
        self.rec.write({'published_revision': 1, 'publish_state': 'published', 'revision': 2})

        class FakeExecutor(object):
            def execute(self, sql, params):
                self.sql, self.params = sql, params
                return ['identity_hash', 'cycle_no', 'rev'], [(self.rec_hash, 1, 1)]
        ex = FakeExecutor()
        ex.rec_hash = self.rec.identity_hash
        requeued = pub.check_mirror(self.env, self.config, executor_factory=lambda env, cfg: ex)
        self.assertEqual(requeued, 1)
        self.assertEqual(ex.params, {'tenant': 'pubapp', 'key': 'quality_compliance'})
        self.assertIn('"shared"."dashboard_projections"', ex.sql)
        self.assertEqual(ev.publish_state, 'pending')
        # mirror up to date → nothing re-queued
        ev.write({'publish_state': 'published'})
        ex2 = FakeExecutor()
        ex2.rec_hash = self.rec.identity_hash
        ex2.execute = lambda sql, params: (['h', 'c', 'r'], [(self.rec.identity_hash, 1, 2)])
        self.assertEqual(pub.check_mirror(self.env, self.config, executor_factory=lambda env, cfg: ex2), 0)
