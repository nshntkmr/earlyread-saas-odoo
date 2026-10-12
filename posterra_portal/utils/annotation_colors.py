# -*- coding: utf-8 -*-
"""Header-badge colour resolution for SQL-driven ``annotation_color``.

``dashboard.widget.annotation_color`` is normally one fixed hex. When the
admin writes a ``%(column)s`` template instead (same convention as
``annotation_text``), ``_interpolate_annotations`` substitutes the column
value and passes it through :func:`resolve_badge_colour`, which is the ONLY
place a SQL-sourced value becomes CSS: a valid hex passes (3-digit expanded to
6 so React's ``<hex>1f`` tint suffix stays valid), a tone word maps to the
platform palette (the attribute_grid / metric_list DEFAULT_STYLES colours),
anything else — including an unresolved template — becomes ``''``, i.e. the
classic grey badge. Pure: no ORM, no I/O.
"""

import re

_HEX_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

# Tone words a SQL column may return. ``neutral`` → '' = the classic grey.
TONE_HEX = {
    'success': '#059669',
    'warning': '#d97706',
    'danger':  '#dc2626',
    'info':    '#087ad8',
    'neutral': '',
}


def resolve_badge_colour(value):
    """SQL-sourced badge colour → validated hex or '' (classic grey)."""
    text = str(value or '').strip()
    if _HEX_RE.match(text):
        if len(text) == 4:  # #abc → #aabbcc
            return '#' + ''.join(ch * 2 for ch in text[1:])
        return text
    return TONE_HEX.get(text.lower(), '')
