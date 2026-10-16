# -*- coding: utf-8 -*-
"""Attribute Grid field placement for the page PDF.

Line-for-line copy of the shared ``static/src/shared/grid-utils/placement.js``
(``effectiveColumns`` + ``resolvePlacement``), which the portal and the
Designer preview run against the real container width. The PDF runs it
against the card's printed width, so a field lands in the same column as on
a screen of that width. The fixture ``tests/fixtures/pdf_placement.json`` is
asserted against this module by the Python suite (tag ``posterra_pdf_export``)
and against ``placement.js`` by
``static/src/react/scripts/test_pdf_placement_parity.mjs`` — change both
sides together.

Like the portal, the print template applies only the resolved COLUMN and
span (``grid-column: col / span n``) and keeps the items in SQL order; the
browser's grid auto-placement then decides the rows the same way on paper as
on screen.
"""

import math


def _js_int(value):
    """``value | 0`` for the values the formatter emits (int / float / None)."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and math.isfinite(value):
        return int(value)
    return 0


def _is_integer(value):
    """``Number.isInteger`` — bools are not numbers in JavaScript."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value) and value.is_integer()


def _truthy_number(value):
    """The number when JavaScript would treat it as truthy (0 / NaN / None /
    non-numbers → None), for ``value || 1``."""
    if isinstance(value, bool):
        return 1 if value else None
    if isinstance(value, (int, float)) and value == value and value != 0:
        return value
    return None


def effective_columns(container_width, configured_columns):
    """Container-width steps (px) → effective column ceiling. Wide keeps the
    configured count; medium ≤ 4; narrow ≤ 2; small = 1."""
    try:
        cfg = int(configured_columns or 1)
    except (TypeError, ValueError):
        cfg = 1
    cfg = max(1, min(cfg, 8))
    if not container_width or container_width >= 900:
        return cfg
    if container_width >= 560:
        return min(cfg, 4)
    if container_width >= 360:
        return min(cfg, 2)
    return 1


def resolve_placement(items, columns):
    """``[{**item, 'resolved': {'row', 'col', 'span'}}]`` in the ORIGINAL order."""
    items = list(items or [])
    cols = max(1, _js_int(columns))

    def _row_order(item):
        p = (item or {}).get('placement') if isinstance(item, dict) else None
        r = (p or {}).get('row_order')
        return math.inf if r is None else r

    indexed = sorted(enumerate(items), key=lambda pair: (_row_order(pair[1]), pair[0]))

    occupied = set()

    def is_free(row, col, span):
        for c in range(col, col + span):
            if c > cols or (row, c) in occupied:
                return False
        return True

    def claim(row, col, span):
        for c in range(col, col + span):
            occupied.add((row, c))

    def find_free(span, start_row):
        row = start_row
        while True:
            col = 1
            while col + span - 1 <= cols:
                if is_free(row, col, span):
                    return row, col
                col += 1
            row += 1

    cursor_row = 1
    resolved = [None] * len(items)
    for i, item in indexed:
        p = (item.get('placement') if isinstance(item, dict) else None) or {}
        # Math.max(1, Math.min(p.column_span || 1, cols)); the formatter
        # only ever emits integer spans.
        span = int(max(1, min(_truthy_number(p.get('column_span')) or 1, cols)))
        placed = None
        start = p.get('column_start')
        if _is_integer(start) and start >= 1 and start + span - 1 <= cols:
            start = int(start)
            for row in range(cursor_row, cursor_row + len(items) + 1):
                if is_free(row, start, span):
                    placed = (row, start)
                    break
        if placed is None:
            placed = find_free(span, 1)
        claim(placed[0], placed[1], span)
        cursor_row = max(cursor_row, placed[0])
        resolved[i] = {'row': placed[0], 'col': placed[1], 'span': span}
    return [dict(item, resolved=resolved[i]) for i, item in enumerate(items)]
