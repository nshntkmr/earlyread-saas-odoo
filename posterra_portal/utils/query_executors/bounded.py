# -*- coding: utf-8 -*-
"""Database-level row bounding for opt-in callers (the PDF export).

``execute()`` on every executor is untouched. Callers that need a bounded
result (a hard row cap enforced by the DATABASE, not by slicing a fully
fetched result) call ``executor.execute_bounded(...)``, which uses the helpers
here to wrap the already-validated widget SQL:

    SELECT * FROM (
    <original sql, trailing ';' removed>
    ) AS _pv_bounded
    [ORDER BY "col" ASC NULLS FIRST, ...]
    LIMIT <max_rows + 1>

Why a wrap and not ``fetchmany``: a psycopg2 client-side cursor buffers the
whole result in the driver before the first ``fetchmany`` returns (measured:
112 MB for 500k rows vs 1.4 MB with the wrap), and ClickHouse's
``max_result_rows`` + ``break`` overshoots by a whole block (65,409 rows for a
2,001 cap). Row order inside the wrap was verified identical to the unwrapped
query on PostgreSQL and on ClickHouse 26.4 (phase-0 findings).

``max_rows + 1`` is requested so the caller learns whether more rows exist
without a COUNT. The configured AG Grid default sort (``sort``/``sortIndex``
on columnDefs) becomes the outer ``ORDER BY`` so truncation keeps the rows the
screen shows first. NULL placement mirrors AG Grid's default comparator
(null is the smallest value): ASC → NULLS FIRST, DESC → NULLS LAST.
"""

import re
from collections import namedtuple

WRAP_ALIAS = '_pv_bounded'

# ``execute_bounded`` result. Tuple-unpackable; ``sort_applied`` is False when
# the configured sort named a column the SQL no longer returns and the query
# was retried without it.
BoundedResult = namedtuple('BoundedResult', 'cols rows more_available sort_applied')
MAX_SORT_COLUMNS = 8

# Characters we refuse inside a sort identifier: quote characters of either
# dialect, escape characters and control characters. Anything else (spaces,
# '%', '#', unicode) is quoted normally.
_BAD_IDENT_CHARS = re.compile(r'["`\\\x00-\x1f]')
_TRAILING_FORMAT_RE = re.compile(r'\bFORMAT\s+[A-Za-z_][A-Za-z0-9_]*\s*$', re.IGNORECASE)


class BoundedSqlError(ValueError):
    """The SQL cannot be safely wrapped (user-safe message)."""


def mask_sql(sql):
    """Return ``sql`` with comments and quoted regions replaced by spaces.

    Offsets stay aligned with the original so callers can locate structural
    characters (a trailing ``;``) that are NOT inside a string, identifier,
    dollar-quoted body or comment. Handles ``--`` and ``/* */`` comments,
    single-quoted strings (``''`` and backslash escapes), double-quoted and
    backtick identifiers, and PostgreSQL dollar quoting (``$tag$...$tag$``).
    Unterminated regions are masked to the end (the database will reject
    such SQL anyway).
    """
    out = list(sql)
    i, n = 0, len(sql)

    def blank(a, b):
        for k in range(a, min(b, n)):
            if out[k] != '\n':
                out[k] = ' '

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ''
        if ch == '-' and nxt == '-':
            j = sql.find('\n', i)
            j = n if j == -1 else j
            blank(i, j)
            i = j
            continue
        if ch == '/' and nxt == '*':
            j = sql.find('*/', i + 2)
            j = n if j == -1 else j + 2
            blank(i, j)
            i = j
            continue
        if ch in ("'", '"', '`'):
            j = i + 1
            while j < n:
                if sql[j] == '\\' and ch == "'":
                    j += 2
                    continue
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:   # doubled quote escape
                        j += 2
                        continue
                    break
                j += 1
            j = min(j + 1, n)
            blank(i, j)
            i = j
            continue
        if ch == '$':
            m = re.match(r'\$([A-Za-z_][A-Za-z0-9_]*)?\$', sql[i:])
            if m:
                tag = m.group(0)
                j = sql.find(tag, i + len(tag))
                j = n if j == -1 else j + len(tag)
                blank(i, j)
                i = j
                continue
        i += 1
    return ''.join(out)


def strip_trailing_semicolons(sql):
    """Remove statement terminators that are followed only by whitespace or
    comments. A ``;`` in the middle (a second statement) is left in place so
    the wrapped query fails loudly instead of running something unexpected."""
    while True:
        masked = mask_sql(sql)
        stripped = masked.rstrip()
        if not stripped.endswith(';'):
            return sql
        pos = len(stripped) - 1
        sql = sql[:pos] + ' ' + sql[pos + 1:]


def quote_ident(name, dialect):
    """Quote a result-column name for the outer ORDER BY.

    PostgreSQL: double quotes, and a literal ``%`` is doubled because the
    query is always executed with a params mapping (psycopg2 %-formatting).
    ClickHouse: double quotes (no client-side %-formatting on that path).
    Returns None for names we refuse to quote (the sort is then skipped).
    """
    if not isinstance(name, str) or not name or _BAD_IDENT_CHARS.search(name):
        return None
    if dialect == 'postgres':
        return '"%s"' % name.replace('%', '%%')
    return '"%s"' % name


def order_by_from_column_defs(column_defs):
    """AG Grid default sort → ``[(field, 'asc'|'desc'), ...]``.

    Uses ``sort`` and ``sortIndex`` exactly like AG Grid's initial sort:
    columns with an explicit ``sortIndex`` first (ascending index), then the
    rest in column order. Hidden columns still sort (AG Grid does too).
    """
    if not isinstance(column_defs, list):
        return []
    picked = []
    for pos, col in enumerate(column_defs):
        if not isinstance(col, dict):
            continue
        direction = (col.get('sort') or '')
        if direction not in ('asc', 'desc'):
            continue
        field = col.get('field') or col.get('colId')
        if not field:
            continue
        idx = col.get('sortIndex')
        key = (0, int(idx), pos) if isinstance(idx, int) and not isinstance(idx, bool) else (1, 0, pos)
        picked.append((key, field, direction))
    picked.sort(key=lambda t: t[0])
    return [(field, direction) for _key, field, direction in picked][:MAX_SORT_COLUMNS]


def build_order_clause(order_by, dialect):
    """Render ``ORDER BY`` for the outer query, or '' when nothing usable."""
    parts = []
    for field, direction in order_by or []:
        ident = quote_ident(field, dialect)
        if not ident:
            continue
        if direction == 'desc':
            parts.append(f'{ident} DESC NULLS LAST')
        else:
            parts.append(f'{ident} ASC NULLS FIRST')
    return ('ORDER BY ' + ', '.join(parts)) if parts else ''


def wrap_bounded(sql, *, max_rows=None, order_by=None, dialect='postgres'):
    """Wrap validated SELECT/WITH ``sql`` with an outer ORDER BY and LIMIT.

    ``max_rows`` is the number of rows the caller will SHOW; the wrap asks the
    database for ``max_rows + 1``. With neither a limit nor a sort, ``sql`` is
    returned unchanged (timeout-only callers).
    """
    order_clause = build_order_clause(order_by, dialect)
    if max_rows is None and not order_clause:
        return sql
    body = strip_trailing_semicolons(sql).rstrip()
    masked_tail = mask_sql(body).rstrip()
    if dialect == 'clickhouse' and _TRAILING_FORMAT_RE.search(masked_tail):
        raise BoundedSqlError(
            'Widget SQL ends with a FORMAT clause, which cannot be bounded. '
            'Remove the FORMAT clause from the widget SQL.')
    parts = [f'SELECT * FROM (\n{body}\n) AS {WRAP_ALIAS}']
    if order_clause:
        parts.append(order_clause)
    if max_rows is not None:
        limit = int(max_rows) + 1
        if limit < 1:
            raise BoundedSqlError('max_rows must be >= 0')
        parts.append(f'LIMIT {limit}')
    return '\n'.join(parts)


def split_bounded_rows(rows, max_rows):
    """``(rows_to_show, more_available)`` for a result fetched with max+1."""
    if max_rows is None:
        return list(rows), False
    rows = list(rows)
    return rows[:max_rows], len(rows) > max_rows


def is_unknown_column_error(exc):
    """True when ``exc`` is the database rejecting an unknown column/identifier
    (PostgreSQL SQLSTATE 42703; ClickHouse code 47 UNKNOWN_IDENTIFIER). Used to
    retry once without the configured sort when the column config names a
    column the SQL no longer returns."""
    code = getattr(exc, 'pgcode', None)
    if code == '42703':
        return True
    text = str(exc)
    return 'Code: 47.' in text or 'UNKNOWN_IDENTIFIER' in text


def is_timeout_error(exc):
    """True for a statement timeout (PG SQLSTATE 57014 query_canceled) or a
    ClickHouse TIMEOUT_EXCEEDED (code 159)."""
    if getattr(exc, 'pgcode', None) == '57014':
        return True
    text = str(exc)
    return 'Code: 159.' in text or 'TIMEOUT_EXCEEDED' in text
