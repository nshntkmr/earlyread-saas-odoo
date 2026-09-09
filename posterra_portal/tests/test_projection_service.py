# -*- coding: utf-8 -*-
"""Projection service end-to-end on a Postgres-backed Projection Type:
Mark / Edit / Re-project / Undo / admin Void, revisions, idempotent replay,
stale-edit conflicts, cycle targeting, the latest-month rule, append-only
history, and agreement between the Python rule and the rendered Postgres
reporting view.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_projections --stop-after-init -d <test_db>
"""

import json
import uuid

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.posterra_portal.services import projection_service as svc
from odoo.addons.posterra_portal.utils import projection_identity as pid
from odoo.addons.posterra_portal.utils.projection_outcomes import Evaluation, Row

JUN, JUL, AUG, SEP, OCT, NOV = 202606, 202607, 202608, 202609, 202610, 202611

DRAWER = {
    'enabled': True, 'trigger': 'row', 'row_key_column': 'hum_id',
    'sections': [{
        'id': 'measures', 'type': 'measure_cards', 'source': 'sql',
        'sql': ('SELECT hum_id, measure_cat, measurement_year, year_month, compliant_cnt, '
                'eligible_cnt, measure_cat AS title FROM proj_src '
                'WHERE hum_id = %(row_key)s [[ AND year_month = %(month)s ]] ORDER BY year_month'),
        'card': {
            'title_column': 'title', 'status_column': 'compliant_cnt',
            'projection': {
                'type_key': 'quality_compliance',
                'identity': {'hum_id': 'hum_id', 'measure_cat': 'measure_cat',
                             'measurement_year': 'measurement_year'},
                'snapshot_alias': 'year_month',
                'member_key_column': 'hum_id',
                'month_filter_param': 'month',
                'allow_when': 'not_positive',
            },
        },
    }],
}


@tagged('post_install', '-at_install', 'posterra_projections')
class TestProjectionService(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.cr.execute("""
            CREATE TEMP TABLE proj_src (
                hum_id text, measure_cat text, measurement_year int, year_month int,
                compliant_cnt int, eligible_cnt int)
        """)
        cls.app = cls.env['saas.app'].create({
            'name': 'Proj App', 'app_key': 'projapp', 'access_mode': 'group'})
        cls.nav = cls.env['dashboard.nav.section'].create(
            {'name': 'Proj Nav', 'key': 'proj_nav'})
        cls.page = cls.env['dashboard.page'].create({
            'name': 'Proj Page', 'key': 'proj_page', 'app_id': cls.app.id,
            'nav_section_id': cls.nav.id, 'portal_type': 'all', 'is_active': True})
        cls.env['dashboard.page.filter'].create({
            'page_id': cls.page.id, 'param_name': 'month',
            'manual_options': '202606\n202607\n202608', 'is_active': True})
        cols = [('hum_id', 'text'), ('measure_cat', 'text'), ('measurement_year', 'integer'),
                ('year_month', 'integer'), ('compliant_cnt', 'integer'),
                ('eligible_cnt', 'integer')]
        cls.source = cls.env['dashboard.schema.source'].create({
            'name': 'Proj Src', 'table_name': 'proj_src',
            'app_ids': [(6, 0, [cls.app.id])],
            'column_ids': [(0, 0, {'column_name': n, 'display_name': n, 'data_type': t})
                           for n, t in cols],
        })
        cls.col = {c.column_name: c for c in cls.source.column_ids}
        cls.widget = cls.env['dashboard.widget'].create({
            'page_id': cls.page.id, 'name': 'Proj Table', 'chart_type': 'table',
            'query_type': 'sql', 'query_sql': 'SELECT * FROM proj_src',
            'schema_source_id': cls.source.id,
            'detail_drawer_config': json.dumps(DRAWER),
        })
        cls.config = cls.env['dashboard.projection.config'].create({
            'name': 'Quality compliance', 'app_id': cls.app.id, 'key': 'quality_compliance',
            'source_id': cls.source.id,
            'identity_column_ids': [
                (0, 0, {'sequence': 1, 'column_id': cls.col['hum_id'].id}),
                (0, 0, {'sequence': 2, 'column_id': cls.col['measure_cat'].id}),
                (0, 0, {'sequence': 3, 'column_id': cls.col['measurement_year'].id})],
            'snapshot_column_id': cls.col['year_month'].id,
            'status_column_id': cls.col['compliant_cnt'].id, 'status_true_values': '1',
            'eligibility_column_id': cls.col['eligible_cnt'].id, 'eligible_values': '1',
            'evidence_options': 'appt|Appointment scheduled\nchart|Chart chase',
        })
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.alice = Users.create({'name': 'Alice', 'login': 'alice_proj'})
        cls.bob = Users.create({'name': 'Bob', 'login': 'bob_proj'})
        cls.h1 = pid.identity_hash(['H1', 'BCS', 2026])
        cls.h2 = pid.identity_hash(['H1', 'COL', 2026])

    # ── helpers ──────────────────────────────────────────────────────────

    def _insert(self, hum, meas, ym, compliant, eligible=1, year=2026):
        self.env.cr.execute(
            'INSERT INTO proj_src VALUES (%s, %s, %s, %s, %s, %s)',
            [hum, meas, year, ym, compliant, eligible])

    def _call(self, action, user, **over):
        params = {
            'type_key': 'quality_compliance', 'widget_id': self.widget.id,
            'section_id': 'measures', 'row_key': 'H1', 'identity_hash': self.h1,
            'snapshot': JUN, 'expected_revision': 0, 'request_id': uuid.uuid4().hex,
        }
        params.update(over)
        snap = str(params['snapshot'] or '').strip()
        ctx = {'sql_params': {'month': int(snap) if snap else None},
               'filter_values_by_name': {}}
        return svc.mutate(self.env, user, self.app, action, params, ctx, None)

    def _err(self, action, user, code, **over):
        with self.assertRaises(svc.ProjectionError) as cm:
            self._call(action, user, **over)
        self.assertEqual(cm.exception.code, code, cm.exception.message)
        return cm.exception

    def _records(self, h=None):
        return self.env['dashboard.projection'].search(
            [('config_id', '=', self.config.id), ('identity_hash', '=', h or self.h1)],
            order='cycle_no')

    def _events(self, h=None):
        return self.env['dashboard.projection.event'].search(
            [('config_id', '=', self.config.id), ('identity_hash', '=', h or self.h1)],
            order='id')

    def _view_outcomes(self, h):
        """{month: pv_outcome} for identity ``h`` from the rendered PG view SQL."""
        self.env.flush_all()
        self.env.cr.execute(self.config._render_view_select_postgres())
        cols = [d[0] for d in self.env.cr.description]
        out = {}
        for raw in self.env.cr.fetchall():
            row = dict(zip(cols, raw))
            if row['pv_identity_hash'] == h:
                out[row['pv_month']] = row['pv_outcome']
        return out

    def _python_outcomes(self, h):
        history = svc.load_history(self.config, 'hum_id', 'H1', None)
        ev = svc.evaluate(self.config, h, history.get(h, []))
        return {r.month: ev.outcome(r.month) for r in ev.rows}

    # ── Mark ─────────────────────────────────────────────────────────────

    def test_mark_saves_record_and_event(self):
        self._insert('H1', 'BCS', JUN, 0)
        res = self._call('mark', self.alice, note='Appt booked', expected_date='2026-06-18',
                         evidence='appt')
        rec = self._records()
        self.assertEqual(len(rec), 1)
        self.assertEqual((rec.cycle_no, rec.state, rec.revision, rec.attempt_no),
                         (1, 'active', 1, 1))
        self.assertEqual((rec.first_applies_from, rec.applies_from, rec.attempt_months),
                         ('202606', '202606', '202606'))
        self.assertEqual(rec.owner_id, self.alice)
        self.assertEqual(rec.note, 'Appt booked')
        self.assertEqual(str(rec.expected_date), '2026-06-18')
        self.assertEqual(rec.publish_state, 'none')          # PG type: nothing to publish
        self.assertEqual(rec.published_revision, 1)
        ev = self._events()
        self.assertEqual(ev.mapped('action'), ['mark'])
        self.assertEqual(ev.actor_name, 'Alice')
        self.assertEqual(res['identity_revision'], 1)
        self.assertEqual(res['outcome'], 'projected')
        self.assertEqual(res['covering_cycle_no'], 1)
        self.assertFalse(res['can_mark'])
        cyc = res['cycles']['1']
        self.assertTrue(cyc['can_edit'] and cyc['can_undo'])
        self.assertFalse(cyc['can_reproject'])
        self.assertEqual(res['history'][0]['action'], 'mark')
        self.assertEqual(res['history'][0]['user'], 'Alice')

    def test_mark_preconditions(self):
        self._insert('H1', 'BCS', JUN, 1)
        self._err('mark', self.alice, 'already_compliant')
        self._insert('H1', 'COL', JUN, 0, eligible=0)
        self._err('mark', self.alice, 'not_eligible', identity_hash=self.h2)
        self._insert('H1', 'COL', JUL, 0)
        h3 = pid.identity_hash(['H1', 'LDL', 2026])
        self._insert('H1', 'LDL', JUN, 0)
        self._insert('H1', 'LDL', JUL, 0)
        exc = self._err('mark', self.alice, 'not_latest_month', identity_hash=h3, snapshot=JUN)
        self.assertEqual(exc.extra.get('latest_month'), '202607')
        self.config.allow_historical_mark = True
        res = self._call('mark', self.alice, identity_hash=h3, snapshot=JUN)
        self.assertEqual(res['outcome'], 'projected')
        self.config.allow_historical_mark = False
        self._err('mark', self.alice, 'row_not_found', identity_hash=self.h2, snapshot=SEP)
        self._err('mark', self.alice, 'missing_snapshot', snapshot='')
        self._err('mark', self.alice, 'bad_identity', identity_hash='xyz')
        self._err('mark', self.alice, 'type_not_found', type_key='nope')
        self._err('mark', self.alice, 'section_not_found', section_id='other')
        self._err('mark', self.alice, 'bad_evidence', identity_hash=self.h2, snapshot=JUL,
                  evidence='unknown')
        self._err('mark', self.alice, 'bad_date', identity_hash=self.h2, snapshot=JUL,
                  expected_date='18/06/2026')

    def test_mark_twice_is_already_active(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        exc = self._err('mark', self.bob, 'already_active', expected_revision=1)
        self.assertEqual(exc.extra.get('cycle_no'), 1)
        self.assertEqual(len(self._records()), 1)

    def test_replay_same_request_id(self):
        self._insert('H1', 'BCS', JUN, 0)
        rid = uuid.uuid4().hex
        first = self._call('mark', self.alice, request_id=rid, note='x')
        again = self._call('mark', self.alice, request_id=rid, note='x')
        self.assertEqual(first, again)
        self.assertEqual(len(self._records()), 1)
        self.assertEqual(len(self._events()), 1)
        # same id, different content → conflict, nothing written
        self._err('mark', self.alice, 'request_conflict', request_id=rid, note='y')
        self.assertEqual(len(self._events()), 1)
        self._err('mark', self.alice, 'missing_request_id', request_id='')

    def test_stale_revision_conflict(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        exc = self._err('edit', self.bob, 'stale_revision', cycle_no=1, expected_revision=0,
                        note='late')
        self.assertEqual(exc.extra['conflict']['revision'], 1)
        self.assertEqual(exc.extra['conflict']['actor_name'], 'Alice')
        self.assertIn('Alice updated this measure', exc.message)
        self.assertFalse(self._records().note)

    # ── Edit / Re-project / Undo ─────────────────────────────────────────

    def test_edit_keeps_months_and_advances_revision(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice, note='first')
        res = self._call('edit', self.bob, cycle_no=1, expected_revision=1, note='second',
                         expected_date='2026-06-30')
        rec = self._records()
        self.assertEqual((rec.revision, rec.note, str(rec.expected_date), rec.attempt_months),
                         (2, 'second', '2026-06-30', '202606'))
        self.assertEqual(rec.owner_id, self.alice)              # ownership unchanged
        self.assertEqual([e['action'] for e in res['history']], ['edit', 'mark'])
        self.assertEqual([e['user'] for e in res['history']], ['Bob', 'Alice'])
        before = json.loads(self._events()[-1].before_json)
        self.assertEqual(before['note'], 'first')
        # clearing the date stays cleared
        self._call('edit', self.bob, cycle_no=1, expected_revision=2, note='second',
                   expected_date='')
        self.assertFalse(self._records().expected_date)

    def test_missed_reproject_matched_sequence(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        self._insert('H1', 'BCS', JUL, 0)                       # July: not matched
        self.assertEqual(self._python_outcomes(self.h1), {'202606': 'projected',
                                                          '202607': 'missed'})
        # re-project must target the latest month and the covering cycle
        self._err('reproject', self.bob, 'not_reprojectable', cycle_no=1,
                  expected_revision=1, snapshot=JUN)
        res = self._call('reproject', self.bob, cycle_no=1, expected_revision=1,
                         snapshot=JUL, note='call again')
        rec = self._records()
        self.assertEqual((rec.attempt_no, rec.applies_from, rec.attempt_months, rec.revision),
                         (2, '202607', '202606,202607', 2))
        self.assertEqual(res['outcome'], 'projected')
        self._insert('H1', 'BCS', AUG, 1)                       # August: matched
        self._insert('H1', 'BCS', SEP, 1)
        self.assertEqual(self._python_outcomes(self.h1), {
            '202606': 'projected', '202607': 'projected', '202608': 'matched', '202609': ''})
        self.assertEqual(self._view_outcomes(self.h1), self._python_outcomes(self.h1))
        # after the match: edit yes, undo/re-project no, mark again only when non-compliant
        self._call('edit', self.alice, cycle_no=1, expected_revision=2, snapshot=JUN,
                   note='closed')
        self._err('undo', self.alice, 'not_undoable', cycle_no=1, expected_revision=3,
                  snapshot=JUL)
        self._err('mark', self.alice, 'already_compliant', expected_revision=3, snapshot=SEP)

    def test_scenario_2_matches_without_reproject(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        self._insert('H1', 'BCS', JUL, 0)
        self._insert('H1', 'BCS', AUG, 1)
        self._insert('H1', 'BCS', SEP, 1)
        expected = {'202606': 'projected', '202607': 'missed', '202608': 'matched', '202609': ''}
        self.assertEqual(self._python_outcomes(self.h1), expected)
        self.assertEqual(self._view_outcomes(self.h1), expected)

    def test_undo_then_mark_again_continues_revision(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        self._call('undo', self.bob, cycle_no=1, expected_revision=1)
        rec = self._records()
        self.assertEqual((rec.state, rec.undone_month, rec.revision, rec.undone_by_id),
                         ('undone', '202606', 2, self.bob))
        self._insert('H1', 'BCS', JUL, 1)                       # compliant later: no match
        self.assertEqual(self._python_outcomes(self.h1), {'202606': '', '202607': ''})
        self.assertEqual(self._view_outcomes(self.h1), {'202606': '', '202607': ''})
        self._insert('H1', 'BCS', AUG, 0)
        # Mark again needs the identity-wide revision and continues the sequence
        self._err('mark', self.alice, 'stale_revision', snapshot=AUG, expected_revision=0)
        res = self._call('mark', self.alice, snapshot=AUG, expected_revision=2)
        recs = self._records()
        self.assertEqual(recs.mapped('cycle_no'), [1, 2])
        self.assertEqual(recs.mapped('revision'), [2, 3])
        self.assertEqual(res['identity_revision'], 3)
        self.assertEqual([e['action'] for e in res['history']], ['mark', 'undo', 'mark'])

    def test_second_cycle_preserves_first_cycle_months(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        for ym, c in ((JUL, 1), (AUG, 1), (SEP, 1), (OCT, 0)):
            self._insert('H1', 'BCS', ym, c)
        res = self._call('mark', self.bob, snapshot=OCT, expected_revision=1)
        self.assertEqual(res['covering_cycle_no'], 2)
        expected = {'202606': 'projected', '202607': 'matched', '202608': '', '202609': '',
                    '202610': 'projected'}
        self.assertEqual(self._python_outcomes(self.h1), expected)
        self.assertEqual(self._view_outcomes(self.h1), expected)
        # editing July targets cycle 1 and never touches cycle 2
        self._err('edit', self.alice, 'cycle_mismatch', cycle_no=2, expected_revision=2,
                  snapshot=JUL, note='wrong cycle')
        self._call('edit', self.alice, cycle_no=1, expected_revision=2, snapshot=JUL,
                   note='july note')
        recs = self._records()
        self.assertEqual(recs.filtered(lambda r: r.cycle_no == 1).note, 'july note')
        self.assertFalse(recs.filtered(lambda r: r.cycle_no == 2).note)
        self.assertEqual(recs.mapped('revision'), [3, 2])
        # an admin change to cycle 1 invalidates a stale expected_revision on cycle 2
        self._err('edit', self.bob, 'stale_revision', cycle_no=2, expected_revision=2,
                  snapshot=OCT, note='x')

    def test_ambiguous_row_and_view_row_count(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._insert('H1', 'BCS', JUN, 0)                       # duplicated source row
        self._err('mark', self.alice, 'ambiguous_row')
        self._insert('H1', '', JUL, 0)                          # identity-less row
        self.env.flush_all()
        self.env.cr.execute(self.config._render_view_select_postgres())
        self.assertEqual(len(self.env.cr.fetchall()), 3)       # every source row survives

    # ── Admin actions ────────────────────────────────────────────────────

    def test_admin_void_needs_reason_and_removes_every_month(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        self._insert('H1', 'BCS', JUL, 1)
        rec = self._records()
        with self.assertRaises(UserError):
            svc.admin_void(self.env, self.env.user, rec, '   ')
        svc.admin_void(self.env, self.env.user, rec, 'Entered on the wrong patient')
        self.assertEqual((rec.state, rec.undone_month, rec.revision), ('undone', '202606', 2))
        self.assertEqual(self._python_outcomes(self.h1), {'202606': '', '202607': ''})
        self.assertEqual(self._view_outcomes(self.h1), {'202606': '', '202607': ''})
        last = self._events()[-1]
        self.assertEqual((last.action, last.reason), ('admin_void', 'Entered on the wrong patient'))
        lines = svc.history_lines(self.config, self.h1)
        self.assertEqual(lines[0]['action'], 'admin_void')
        self.assertEqual(lines[0]['reason'], 'Entered on the wrong patient')

    def test_admin_undo_keeps_earlier_match(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        self._insert('H1', 'BCS', JUL, 1)
        self._insert('H1', 'BCS', AUG, 1)
        rec = self._records()
        svc.admin_undo(self.env, self.env.user, rec)
        self.assertEqual((rec.state, rec.undone_month), ('undone', '202608'))
        self.assertEqual(self._python_outcomes(self.h1),
                         {'202606': 'projected', '202607': 'matched', '202608': ''})

    # ── History and immutability ─────────────────────────────────────────

    def test_history_lines_limit_and_exclusions(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        for rev, note in ((1, 'a'), (2, 'b'), (3, 'c')):
            self._call('edit', self.alice, cycle_no=1, expected_revision=rev, note=note)
        rec = self._records()
        self.env['dashboard.projection.event'].create({
            'projection_id': rec.id, 'config_id': self.config.id, 'identity_hash': self.h1,
            'cycle_no': 1, 'action': 'republish', 'actor_id': self.env.user.id,
            'actor_name': 'cron', 'at': '2026-09-08 00:00:00', 'revision': 999})
        lines = svc.history_lines(self.config, self.h1)
        self.assertEqual(len(lines), 3)
        self.assertEqual([l['action'] for l in lines], ['edit', 'edit', 'edit'])
        self.assertEqual(len(self._events()), 5)               # everything retained

    def test_events_and_records_are_immutable(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._call('mark', self.alice)
        event = self._events()[0]
        with self.assertRaises(UserError):
            event.write({'before_json': 'tampered'})
        with self.assertRaises(UserError):
            event.unlink()
        with self.assertRaises(UserError):
            self._records().unlink()
        event.write({'publish_state': 'published'})            # outbox bookkeeping allowed
        with self.assertRaises(UserError):
            self.config.write({'snapshot_column_id': self.col['measurement_year'].id})

    def test_owner_policy(self):
        self.config.undo_policy = 'owner_or_admin'
        self._insert('H1', 'BCS', JUN, 0)
        res = self._call('mark', self.alice)
        self.assertTrue(res['cycles']['1']['can_edit'])
        self._err('edit', self.bob, 'not_owner', cycle_no=1, expected_revision=1, note='x')
        self._call('edit', self.alice, cycle_no=1, expected_revision=1, note='mine')
        self.config.undo_policy = 'anyone_allowed'

    # ── Drawer overlay ───────────────────────────────────────────────────

    def test_drawer_overlay_rows_and_flags(self):
        self._insert('H1', 'BCS', JUN, 0)
        self._insert('H1', 'COL', JUN, 1)
        self._call('mark', self.alice, note='hi')               # June marked (latest month)
        self._insert('H1', 'COL', JUL, 1)
        self._insert('H1', 'BCS', JUL, 0)                       # July: not matched
        ctx = {'sql_params': {'month': JUL}, 'filter_values_by_name': {}}
        out = self.widget._execute_drawer_detail('H1', ctx, user=self.bob)
        sec = out['sections']['measures']
        rows = {r['measure_cat']: r for r in sec['rows']}
        bcs, col = rows['BCS'], rows['COL']
        self.assertEqual(bcs['__pv_identity_hash'], self.h1)
        self.assertEqual((bcs['__pv_month'], bcs['__pv_outcome'], bcs['__pv_cycle_no']),
                         ('202607', 'missed', 1))
        self.assertFalse(bcs['__pv_source_positive'])
        self.assertTrue(bcs['__pv_can_reproject'] and bcs['__pv_can_edit'] and bcs['__pv_can_undo'])
        self.assertFalse(bcs['__pv_can_mark'])
        self.assertTrue(col['__pv_source_positive'])
        self.assertEqual(col['__pv_outcome'], '')
        self.assertFalse(col['__pv_can_mark'])                  # compliant: nothing to mark
        ident = sec['projections']['quality_compliance'][self.h1]
        self.assertEqual(ident['identity_revision'], 1)
        self.assertEqual(ident['latest_month'], '202607')
        self.assertEqual(ident['cycles']['1']['note'], 'hi')
        self.assertEqual(ident['history'][0]['action'], 'mark')
        meta = sec['projection_meta']
        self.assertTrue(meta['can_act'])
        self.assertEqual(meta['month_filter_param'], 'month')
        self.assertEqual(meta['latest_snapshot'], '202607')
        self.assertEqual(meta['styles']['missed']['color'], '#d97706')
        # a section without the block is untouched; a widget consumer flag is set
        self.assertTrue(self.widget._is_projection_consumer())
        # without a user: read-only (no capabilities)
        out2 = self.widget._execute_drawer_detail('H1', ctx)
        self.assertFalse(out2['sections']['measures']['projection_meta']['can_act'])
        self.assertFalse(out2['sections']['measures']['rows'][0]['__pv_can_edit'])

    def test_public_meta(self):
        meta = self.config.get_public_meta()
        self.assertEqual(meta['labels']['mark'], 'Mark Projected Compliant')
        self.assertEqual(meta['styles']['missed']['label'], 'Not matched in {month} data')
        self.assertEqual([o['value'] for o in meta['capture']['evidence_options']],
                         ['appt', 'chart'])
        self.assertEqual(meta['history_shown'], 3)
