# -*- coding: utf-8 -*-
"""Projection cycles and the monthly outcome rule (spec §3.2).

Pure Python, no Odoo imports — the same rule the rendered reporting view
implements in SQL, used by the drawer overlay and by the service's
preconditions. Months are compared as text and must sort chronologically
(``YYYYMM``); the Projection Type validates that at save time.

A *cycle* is one saved expectation: it starts with Mark in month ``F``
(``first_applies_from``), may gain Re-project attempts (``attempt_months``,
``F`` included) and ends when a month's data confirms compliance (the match
month ``C``) or when a user undoes it (from ``undone_month`` onward).
"""

OUTCOME_NONE = ''
OUTCOME_INELIGIBLE = 'ineligible'
OUTCOME_MATCHED = 'matched'
OUTCOME_PROJECTED = 'projected'
OUTCOME_MISSED = 'missed'

STATE_ACTIVE = 'active'
STATE_UNDONE = 'undone'


class Cycle(object):
    __slots__ = ('cycle_no', 'state', 'first_applies_from', 'applies_from',
                 'attempt_months', 'undone_month', 'record')

    def __init__(self, cycle_no, state, first_applies_from, attempt_months,
                 undone_month='', applies_from=None, record=None):
        self.cycle_no = int(cycle_no)
        self.state = state or STATE_ACTIVE
        self.first_applies_from = str(first_applies_from or '')
        self.applies_from = str(applies_from or self.first_applies_from)
        self.attempt_months = [str(m) for m in (attempt_months or []) if str(m)]
        self.undone_month = str(undone_month or '')
        self.record = record

    @property
    def is_active(self):
        return self.state == STATE_ACTIVE


class Row(object):
    __slots__ = ('month', 'eligible', 'compliant')

    def __init__(self, month, eligible, compliant):
        self.month = str(month or '')
        self.eligible = bool(eligible)
        self.compliant = bool(compliant)


def covering_cycle(cycles, month):
    """The cycle covering ``month``: greatest ``F <= month``, ties by the
    higher cycle number. ``None`` when no cycle has started by then."""
    best = None
    for c in cycles:
        if not c.first_applies_from or c.first_applies_from > month:
            continue
        if best is None or (c.first_applies_from, c.cycle_no) > (
                best.first_applies_from, best.cycle_no):
            best = c
    return best


def compute_matches(cycles, rows):
    """{cycle_no: match_month} — the earliest eligible compliant month each
    cycle covers (before ``undone_month`` for undone cycles)."""
    matches = {}
    for row in rows:
        if not (row.eligible and row.compliant):
            continue
        c = covering_cycle(cycles, row.month)
        if c is None:
            continue
        if c.state == STATE_UNDONE and c.undone_month and row.month >= c.undone_month:
            continue
        cur = matches.get(c.cycle_no)
        if cur is None or row.month < cur:
            matches[c.cycle_no] = row.month
    return matches


def outcome_for(row, cycles, matches):
    """Outcome of one source row (spec §3.2 table, first match wins)."""
    if not row.eligible:
        return OUTCOME_INELIGIBLE
    c = covering_cycle(cycles, row.month)
    if c is None:
        return OUTCOME_NONE
    if c.state == STATE_UNDONE and c.undone_month and row.month >= c.undone_month:
        return OUTCOME_NONE
    match = matches.get(c.cycle_no)
    if match is not None:
        if row.month == match:
            return OUTCOME_MATCHED
        if row.month > match:
            return OUTCOME_NONE
    if row.month in c.attempt_months:
        return OUTCOME_PROJECTED
    return OUTCOME_MISSED


class Evaluation(object):
    """Everything the drawer and the service need for one identity."""

    def __init__(self, cycles, rows):
        self.cycles = sorted(cycles, key=lambda c: c.cycle_no)
        self.rows = list(rows)
        self.matches = compute_matches(self.cycles, self.rows)
        self.latest_month = max((r.month for r in self.rows), default='')

    @property
    def latest_cycle(self):
        return self.cycles[-1] if self.cycles else None

    @property
    def identity_revision(self):
        return max((int(getattr(c.record, 'revision', 0) or 0)
                    for c in self.cycles), default=0)

    def row_for(self, month):
        for r in self.rows:
            if r.month == month:
                return r
        return None

    def outcome(self, month):
        row = self.row_for(month)
        if row is None:
            return OUTCOME_NONE
        return outcome_for(row, self.cycles, self.matches)

    def covering(self, month):
        return covering_cycle(self.cycles, month)

    def match_month(self, cycle):
        return self.matches.get(cycle.cycle_no) if cycle else None

    def open_cycle(self, month):
        """The cycle that still blocks a new Mark as seen from ``month``:
        the latest cycle when it is active and either unmatched or matched
        in a month not before ``month``."""
        latest = self.latest_cycle
        if latest is None or not latest.is_active:
            return None
        match = self.matches.get(latest.cycle_no)
        if match is None or month <= match:
            return latest
        return None

    # ── Capability flags (server-side only; the client renders from them) ──

    def can_mark(self, month, allow_historical=False):
        row = self.row_for(month)
        if row is None or not row.eligible or row.compliant:
            return False
        if not allow_historical and month != self.latest_month:
            return False
        return self.open_cycle(month) is None

    def can_edit(self, cycle, month):
        return (cycle is not None and cycle.is_active
                and self.covering(month) is cycle)

    def can_reproject(self, cycle, month, allow_historical=False):
        if cycle is None or cycle is not self.latest_cycle or not cycle.is_active:
            return False
        if self.matches.get(cycle.cycle_no) is not None:
            return False
        if not allow_historical and month != self.latest_month:
            return False
        return self.outcome(month) == OUTCOME_MISSED

    def can_undo(self, cycle, month):
        if cycle is None or cycle is not self.latest_cycle or not cycle.is_active:
            return False
        if self.matches.get(cycle.cycle_no) is not None:
            return False
        return self.covering(month) is cycle
