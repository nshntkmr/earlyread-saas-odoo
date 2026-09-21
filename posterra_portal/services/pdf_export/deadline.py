# -*- coding: utf-8 -*-
"""Wall-clock budget for one PDF export (decision V6).

The total budget is split up front so the render always keeps its reserve:

    collect_budget = total - render_reserve - audit_reserve

Collection stops at ``collect_deadline`` (widgets not reached are listed as
"not loaded in time" in the PDF, which still renders). The render has its own
wall-clock check in ``render_client`` — ``requests``' read timeout is an
inactivity timeout, not a total one, so it is only a backstop.
"""

import time

from .limits import AUDIT_RESERVE_S, MIN_STEP_S, RENDER_RESERVE_S, WIDGET_TIMEOUT_MAX_S


class Deadline:

    def __init__(self, total_s, *, render_reserve_s=RENDER_RESERVE_S,
                 audit_reserve_s=AUDIT_RESERVE_S, clock=time.monotonic):
        self._clock = clock
        self.started = clock()
        self.total_s = float(total_s)
        self.render_reserve_s = float(render_reserve_s)
        self.audit_reserve_s = float(audit_reserve_s)
        self.end = self.started + self.total_s
        self.collect_end = self.end - self.render_reserve_s - self.audit_reserve_s

    def elapsed(self):
        return self._clock() - self.started

    def remaining(self):
        return self.end - self._clock()

    def collect_remaining(self):
        return self.collect_end - self._clock()

    def can_collect(self):
        """True when at least one more collection step fits."""
        return self.collect_remaining() >= MIN_STEP_S

    def step_timeout(self, cap=WIDGET_TIMEOUT_MAX_S):
        """Per-statement timeout for the next collection step, bounded by the
        remaining collect budget (never below the minimum step)."""
        return max(MIN_STEP_S, min(float(cap), self.collect_remaining()))

    def render_timeout(self):
        """Seconds the render may still use (its reserve, or less if the
        collection overran)."""
        return max(0.0, min(self.render_reserve_s,
                            self.remaining() - self.audit_reserve_s))
