# -*- coding: utf-8 -*-
"""Projection identity encoding (spec §3.1) — identical in Python, Postgres
and ClickHouse.

A projection is *about* an identity: the ordered list of source columns
configured on the Projection Type (e.g. ``HUM_ID, MEASURE_CAT,
MEASUREMENT_YEAR``). Every engine must derive the same key from the same
row, so the encoding is normative:

1. Each component is converted to text and trimmed of exactly U+0020, U+0009,
   U+000D and U+000A at both ends. NULL becomes ``''``.
2. A component that is empty after trimming makes the row un-projectable
   (Python raises :class:`IdentityIncomplete`; SQL yields ``''``/NULL).
3. Components are encoded as ``<utf8_byte_length>:<value>`` and concatenated.
4. The MD5 of the UTF-8 bytes, lowercase hex, is the ``identity_hash``.

The length prefix makes the encoding injective (``ab|c`` vs ``a|bc`` can
never collide), so no delimiter character can appear in a value and break
the key. ``render_identity_expr`` emits the equivalent SQL expression for
the Projection Type form (the admin pastes it into the reporting view) and
for the service's history query.
"""

import hashlib

from .sql_idents import IDENT_RE

TRIM_CHARS = ' \t\r\n'

# The same four characters as SQL literals. Both Postgres (E'...') and
# ClickHouse string literals understand C-style escapes.
_PG_TRIM_LITERAL = "E' \\t\\r\\n'"
_CH_TRIM_LITERAL = "' \\t\\r\\n'"


class IdentityIncomplete(ValueError):
    """A required identity component is NULL or empty after trimming."""


def normalize_component(value):
    """Return the normalized text form of one identity component."""
    if value is None:
        return ''
    if isinstance(value, bool):
        value = int(value)
    return str(value).strip(TRIM_CHARS)


def encode_components(values):
    """Return the length-prefixed encoding of ``values`` (all required)."""
    parts = []
    for value in values:
        n = normalize_component(value)
        if n == '':
            raise IdentityIncomplete('identity incomplete')
        parts.append('%d:%s' % (len(n.encode('utf-8')), n))
    return ''.join(parts)


def identity_hash(values):
    """Lowercase-hex MD5 of the encoded components."""
    return hashlib.md5(encode_components(values).encode('utf-8')).hexdigest()


def identity_hash_or_none(values):
    """Like :func:`identity_hash` but ``None`` for an incomplete identity."""
    try:
        return identity_hash(values)
    except IdentityIncomplete:
        return None


def _quoted(column, table_alias=None):
    if not column or not IDENT_RE.match(column):
        raise ValueError('invalid identifier %r' % (column,))
    q = '"%s"' % column
    return '%s.%s' % (table_alias, q) if table_alias else q


def normalized_column_expr(column, engine, table_alias=None):
    """SQL expression for the trimmed text form of one column."""
    q = _quoted(column, table_alias)
    if engine == 'clickhouse':
        return "trim(BOTH %s FROM ifNull(toString(%s), ''))" % (_CH_TRIM_LITERAL, q)
    return "btrim(coalesce(%s::text, ''), %s)" % (q, _PG_TRIM_LITERAL)


def render_identity_expr(columns, engine, table_alias=None):
    """SQL expression producing the identity hash of a source row.

    ClickHouse: ``''`` when any component is empty; Postgres: ``NULL``.
    """
    columns = list(columns or [])
    if not columns:
        raise ValueError('at least one identity column is required')
    norms = [normalized_column_expr(c, engine, table_alias) for c in columns]
    if engine == 'clickhouse':
        complete = ' AND '.join("%s != ''" % n for n in norms)
        parts = ', '.join(
            "toString(length(%s)), ':', %s" % (n, n) for n in norms)
        return "if(%s, lower(hex(MD5(concat(%s)))), '')" % (complete, parts)
    complete = ' AND '.join("%s <> ''" % n for n in norms)
    parts = ', '.join(
        "octet_length(%s)::text, ':', %s" % (n, n) for n in norms)
    return 'CASE WHEN %s THEN md5(concat(%s)) ELSE NULL END' % (complete, parts)


def render_in_list_expr(column, values, engine, table_alias=None):
    """``<normalized column> IN ('v1', 'v2')`` for a configured value list."""
    norm = normalized_column_expr(column, engine, table_alias)
    literals = ', '.join(
        "'%s'" % str(v).replace("'", "''") for v in values) or "''"
    return '%s IN (%s)' % (norm, literals)


def parse_value_list(text, default='1'):
    """Comma-separated admin value list → list of trimmed strings."""
    raw = text if (text is not None and str(text).strip()) else default
    return [v.strip() for v in str(raw).split(',') if v.strip()]


def month_text_expr(column, engine, table_alias=None):
    """SQL expression giving the snapshot value as trimmed text."""
    return normalized_column_expr(column, engine, table_alias)
