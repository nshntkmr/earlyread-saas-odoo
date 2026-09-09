# -*- coding: utf-8 -*-
"""The monthly outcome rule (spec §3.2) on the timelines from the accepted
plan — pure Python, no database.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_projections --stop-after-init -d <test_db>
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.posterra_portal.utils.projection_outcomes import (
    Cycle, Evaluation, Row, OUTCOME_INELIGIBLE, OUTCOME_MATCHED, OUTCOME_MISSED,
    OUTCOME_NONE, OUTCOME_PROJECTED,
)

JUN, JUL, AUG, SEP, OCT, NOV = '202606', '202607', '202608', '202609', '202610', '202611'


def rows(**months):
    """rows(JUN=0, JUL=1) → non-compliant June, compliant July (all eligible)."""
    out = []
    for name, compliant in months.items():
        month = globals()[name]
        out.append(Row(month, True, bool(compliant)))
    return out


def outcomes(ev, *months):
    return [ev.outcome(m) for m in months]


@tagged('post_install', '-at_install', 'posterra_projections')
class TestProjectionOutcomes(TransactionCase):

    def test_scenario_1_matched_next_month(self):
        cycles = [Cycle(1, 'active', JUN, [JUN])]
        ev = Evaluation(cycles, rows(JUN=0, JUL=1, AUG=1, SEP=1))
        self.assertEqual(outcomes(ev, JUN, JUL, AUG, SEP),
                         [OUTCOME_PROJECTED, OUTCOME_MATCHED, OUTCOME_NONE, OUTCOME_NONE])
        self.assertEqual(ev.matches, {1: JUL})

    def test_scenario_2_missed_then_matched_without_reproject(self):
        cycles = [Cycle(1, 'active', JUN, [JUN])]
        ev = Evaluation(cycles, rows(JUN=0, JUL=0, AUG=1, SEP=1))
        self.assertEqual(outcomes(ev, JUN, JUL, AUG, SEP),
                         [OUTCOME_PROJECTED, OUTCOME_MISSED, OUTCOME_MATCHED, OUTCOME_NONE])

    def test_scenario_2_with_reproject_in_july(self):
        cycles = [Cycle(1, 'active', JUN, [JUN, JUL], applies_from=JUL)]
        ev = Evaluation(cycles, rows(JUN=0, JUL=0, AUG=1, SEP=1))
        self.assertEqual(outcomes(ev, JUN, JUL, AUG, SEP),
                         [OUTCOME_PROJECTED, OUTCOME_PROJECTED, OUTCOME_MATCHED, OUTCOME_NONE])

    def test_several_reprojections_before_match(self):
        cycles = [Cycle(1, 'active', JUN, [JUN, JUL], applies_from=JUL)]
        ev = Evaluation(cycles, rows(JUN=0, JUL=0, AUG=0, SEP=1, OCT=1))
        self.assertEqual(outcomes(ev, JUN, JUL, AUG, SEP, OCT),
                         [OUTCOME_PROJECTED, OUTCOME_PROJECTED, OUTCOME_MISSED,
                          OUTCOME_MATCHED, OUTCOME_NONE])

    def test_same_month_correction_counts_once(self):
        cycles = [Cycle(1, 'active', JUN, [JUN])]
        ev = Evaluation(cycles, rows(JUN=1, JUL=1))
        self.assertEqual(outcomes(ev, JUN, JUL), [OUTCOME_MATCHED, OUTCOME_NONE])

    def test_second_cycle_preserves_first(self):
        cycles = [Cycle(1, 'active', JUN, [JUN]), Cycle(2, 'active', OCT, [OCT])]
        ev = Evaluation(cycles, rows(JUN=0, JUL=1, AUG=1, SEP=1, OCT=0, NOV=1))
        self.assertEqual(outcomes(ev, JUN, JUL, AUG, SEP, OCT, NOV),
                         [OUTCOME_PROJECTED, OUTCOME_MATCHED, OUTCOME_NONE, OUTCOME_NONE,
                          OUTCOME_PROJECTED, OUTCOME_MATCHED])
        self.assertEqual(ev.covering(SEP).cycle_no, 1)
        self.assertEqual(ev.covering(OCT).cycle_no, 2)

    def test_undo_before_match_cancels_from_effective_month(self):
        cycles = [Cycle(1, 'undone', JUN, [JUN], undone_month=JUN)]
        ev = Evaluation(cycles, rows(JUN=0, JUL=1))
        self.assertEqual(outcomes(ev, JUN, JUL), [OUTCOME_NONE, OUTCOME_NONE])
        self.assertEqual(ev.matches, {})
        # undone in July after a June miss: June keeps Projected
        cycles = [Cycle(1, 'undone', JUN, [JUN], undone_month=JUL)]
        ev = Evaluation(cycles, rows(JUN=0, JUL=0, AUG=1))
        self.assertEqual(outcomes(ev, JUN, JUL, AUG),
                         [OUTCOME_PROJECTED, OUTCOME_NONE, OUTCOME_NONE])

    def test_admin_void_removes_every_month(self):
        cycles = [Cycle(1, 'undone', JUN, [JUN], undone_month=JUN)]
        ev = Evaluation(cycles, rows(JUN=0, JUL=1, AUG=1))
        self.assertEqual(outcomes(ev, JUN, JUL, AUG), [OUTCOME_NONE] * 3)

    def test_missing_month_is_not_a_failure(self):
        cycles = [Cycle(1, 'active', JUN, [JUN])]
        ev = Evaluation(cycles, rows(JUN=0, AUG=1))     # no July row
        self.assertEqual(outcomes(ev, JUN, JUL, AUG),
                         [OUTCOME_PROJECTED, OUTCOME_NONE, OUTCOME_MATCHED])

    def test_ineligible_month_neither_matches_nor_fails(self):
        cycles = [Cycle(1, 'active', JUN, [JUN])]
        r = rows(JUN=0, JUL=1, AUG=1)
        r[1].eligible = False                            # July ineligible (though "compliant")
        ev = Evaluation(cycles, r)
        self.assertEqual(outcomes(ev, JUN, JUL, AUG),
                         [OUTCOME_PROJECTED, OUTCOME_INELIGIBLE, OUTCOME_MATCHED])

    def test_no_cycle_shows_nothing_but_can_mark(self):
        ev = Evaluation([], rows(JUN=0, JUL=0))
        self.assertEqual(outcomes(ev, JUN, JUL), [OUTCOME_NONE, OUTCOME_NONE])
        self.assertTrue(ev.can_mark(JUL))
        self.assertFalse(ev.can_mark(JUN))               # not the latest month
        self.assertTrue(ev.can_mark(JUN, allow_historical=True))

    def test_capability_flags(self):
        c1 = Cycle(1, 'active', JUN, [JUN])
        ev = Evaluation([c1], rows(JUN=0, JUL=0))
        self.assertTrue(ev.can_edit(c1, JUN))
        self.assertTrue(ev.can_undo(c1, JUL))
        self.assertTrue(ev.can_reproject(c1, JUL))
        self.assertFalse(ev.can_reproject(c1, JUN))       # June is Projected, not missed
        self.assertFalse(ev.can_mark(JUL))                # cycle still open
        # after a match: edit yes, undo/reproject no, mark again only later
        ev = Evaluation([c1], rows(JUN=0, JUL=1, AUG=0))
        self.assertTrue(ev.can_edit(c1, JUN))
        self.assertFalse(ev.can_undo(c1, JUN))
        self.assertFalse(ev.can_reproject(c1, AUG))
        self.assertTrue(ev.can_mark(AUG))
        self.assertFalse(ev.can_mark(JUL))

    def test_identity_revision_is_max_over_cycles(self):
        class R:  # stand-in for the record
            def __init__(self, revision):
                self.revision = revision
        cycles = [Cycle(1, 'active', JUN, [JUN], record=R(3)),
                  Cycle(2, 'active', OCT, [OCT], record=R(5))]
        ev = Evaluation(cycles, rows(JUN=0, OCT=0))
        self.assertEqual(ev.identity_revision, 5)
        self.assertEqual(Evaluation([], []).identity_revision, 0)
