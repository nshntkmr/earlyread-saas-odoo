# -*- coding: utf-8 -*-
"""Shared display formatting for attribute_grid / metric_list values.

Pure — no ORM, no locale guessing. Decimal-safe: numbers travel through
``decimal.Decimal(str(v))`` so float artifacts never reach the display string.
``bool`` is rejected as numeric BEFORE parsing (``isinstance(True, int)`` is
True in Python — a real silent-corruption path).
"""

import datetime
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_THOUSANDS_TYPES = ('integer', 'number', 'currency')


def parse_number(value):
    """Return Decimal or None. None/''/bool/non-finite/junk → None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    return d


def _group_thousands(digits):
    """'1234567.89' → '1,234,567.89' (sign-aware)."""
    sign = ''
    if digits.startswith('-'):
        sign, digits = '-', digits[1:]
    whole, dot, frac = digits.partition('.')
    parts = []
    while len(whole) > 3:
        parts.insert(0, whole[-3:])
        whole = whole[:-3]
    parts.insert(0, whole)
    return sign + ','.join(parts) + dot + frac


def _quantize(d, decimals):
    exp = Decimal(1).scaleb(-decimals) if decimals > 0 else Decimal(1)
    return d.quantize(exp, rounding=ROUND_HALF_UP)


def format_value(raw, fmt):
    """Format one value per an attr/metric ``format`` dict.

    Returns the display string. NULL handling is the CALLER's job (null_text
    differs per surface) — call only with a non-null raw value.
    """
    ftype = fmt.get('type') or 'text'
    if ftype in ('text', 'phone'):
        return str(raw).strip()
    if ftype in ('date', 'datetime'):
        return _format_temporal(raw, ftype)

    num = parse_number(raw)
    if num is None:
        # Non-numeric under a numeric format: show the raw text rather than
        # lying with a number (fail-soft, value preserved).
        return str(raw).strip()
    mult = fmt.get('display_multiplier', 1)
    if isinstance(mult, (int, float)) and not isinstance(mult, bool) \
            and math.isfinite(mult):
        num = num * Decimal(str(mult))
    decimals = fmt.get('decimals', 0)
    decimals = decimals if isinstance(decimals, int) \
        and not isinstance(decimals, bool) and 0 <= decimals <= 6 else 0
    if ftype == 'integer':
        decimals = 0
    digits = str(_quantize(num, decimals))
    if ftype in _THOUSANDS_TYPES:
        digits = _group_thousands(digits)
    prefix = fmt.get('prefix') or ''
    suffix = fmt.get('suffix') or ''
    if ftype == 'percent':
        # '%' is the semantic suffix and binds tightest: prefix + digits + '%'
        # + user suffix. The multiplier already ran — nothing is inferred.
        return '%s%s%%%s' % (prefix, digits, suffix)
    return '%s%s%s' % (prefix, digits, suffix)


_DATE_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')


def _format_temporal(raw, ftype):
    """YYYY-MM-DD / 'YYYY-MM-DD HH:MM'. Unparseable → raw string (fail-soft)."""
    if isinstance(raw, datetime.datetime):
        return raw.strftime('%Y-%m-%d %H:%M') if ftype == 'datetime' \
            else raw.strftime('%Y-%m-%d')
    if isinstance(raw, datetime.date):
        return raw.strftime('%Y-%m-%d') if ftype == 'date' \
            else raw.strftime('%Y-%m-%d 00:00')
    s = str(raw).strip()
    m = _DATE_RE.match(s)
    if not m:
        return s
    if ftype == 'date':
        return m.group(0)
    tm = re.match(r'^\d{4}-\d{2}-\d{2}[T ](\d{2}):(\d{2})', s)
    if tm:
        return '%s %s:%s' % (m.group(0), tm.group(1), tm.group(2))
    return '%s 00:00' % m.group(0)


def resolve_icon(key, icon_map, allowed_keys=None, fallback_key=''):
    """Registry-key → render dict. Unknown/disallowed → fallback → None.

    ``allowed_keys=None`` = static mode (no allow-list filtering);
    a list (even empty) = column mode filtering. ``icon_map`` includes
    inactive icons by design — archived glyphs keep rendering.
    """
    icon_map = icon_map or {}

    def _lookup(k):
        if not k or not isinstance(k, str):
            return None
        entry = icon_map.get(k.strip())
        if not entry:
            return None
        return {'key': k.strip(), 'fa_class': entry.get('fa_class', ''),
                'label': entry.get('label', '')}

    if key is not None and not isinstance(key, str):
        key = str(key)
    if key:
        key = key.strip()
    if key and (allowed_keys is None or key in allowed_keys):
        found = _lookup(key)
        if found:
            return found
    return _lookup(fallback_key)
