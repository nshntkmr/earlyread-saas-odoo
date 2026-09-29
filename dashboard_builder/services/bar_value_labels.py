# -*- coding: utf-8 -*-
"""Opt-in value-label options for BAR charts.

SINGLE SOURCE OF TRUTH used by BOTH:
  • posterra_portal ``dashboard.widget._build_echart_option`` (portal runtime;
    the PDF export draws the same option)
  • dashboard_builder ``preview_formatter._build_echart_preview`` (designer preview)

Two visual_config flags, both OFF by default. While they are off nothing here
touches the ECharts option, so every existing bar chart is byte-identical:

  ``null_label``       "Label for Hidden Values", e.g. ``<11``. A SQL NULL
                       prints this text on the bar label AND in the hover
                       tooltip instead of ``0``; the bar itself stays empty.
                       The SQL decides what is hidden: return NULL for a
                       suppressed cell and 0 for a real zero.
  ``label_direction``  ``vertical`` turns value labels upright so the labels of
                       side-by-side bars cannot overlap (vertical bars only).

No ORM / no I/O.

How the text reaches the tooltip with JSON only (a chart option cannot carry JS
formatter functions): every point becomes
``{name, value: [index, number, label_text, tooltip_text], clickValue}``. The
series declares those four dimensions, ``encode.tooltip`` points the axis
tooltip at the tooltip text and ``label.formatter`` reads ``{@pv_label}``.
``clickValue`` is the plain number the point held before; WidgetGrid prefers it
for click actions, so clicks send exactly what they sent before.
"""

import math
import re
from decimal import Decimal, InvalidOperation

NULL_LABEL_FLAG = 'null_label'
LABEL_DIRECTION_FLAG = 'label_direction'

_DIMENSIONS = (
    {'name': 'pv_cat', 'type': 'number'},     # category index on the category axis
    {'name': 'pv_val', 'type': 'number'},     # bar value (0 for a hidden point)
    {'name': 'pv_label', 'type': 'ordinal'},  # value-label text
    {'name': 'pv_tip', 'type': 'ordinal'},    # tooltip text
)
_COMMAS_RE = re.compile(r'(\d{1,3})(?=(?:\d{3})+(?!\d))')


# ── Flag readers ──────────────────────────────────────────────────────────────

def null_label_for(chart_type, vc, show_labels):
    """The configured hidden-value text, or '' when the option is off."""
    if chart_type != 'bar' or not show_labels or not isinstance(vc, dict):
        return ''
    text = vc.get(NULL_LABEL_FLAG)
    return text.strip() if isinstance(text, str) else ''


def vertical_labels_on(chart_type, vc, orientation):
    """True when value labels should be drawn upright (vertical bars only)."""
    return (chart_type == 'bar' and isinstance(vc, dict)
            and vc.get(LABEL_DIRECTION_FLAG) == 'vertical'
            and orientation != 'horizontal')


def vertical_label_style(position):
    """Label keys that turn a value label upright. A label above the bar grows
    upward from the bar end; a label inside a bar is centred in it."""
    if str(position or '').startswith('inside'):
        return {'rotate': 90, 'align': 'center', 'verticalAlign': 'middle'}
    return {'rotate': 90, 'align': 'left', 'verticalAlign': 'middle'}


def series_value(value, keep_null):
    """A series value as the builders store it. Historically every falsy SQL
    value became 0 (``value or 0``); while the hidden-value label is active a
    SQL NULL stays None so it can be labelled."""
    if keep_null and value is None:
        return None
    return value or 0


# ── Text as the chart prints it today ─────────────────────────────────────────

def _js_text(value):
    """``value`` as ECharts prints a raw value after ``json.dumps(default=str)``
    (a Decimal travels as its string, so it prints as that string)."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    return str(value)


def _as_number(value):
    """ECharts ``numericToNumber``: the number a raw value stands for, or None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value if not isinstance(value, float) or math.isfinite(value) else None
    try:
        num = float(Decimal(str(value).strip()))
    except (InvalidOperation, ValueError):
        return None
    return num if math.isfinite(num) else None


def _tooltip_text(value):
    """The axis tooltip's default text for a value (ECharts ``addCommas``)."""
    num = _as_number(value)
    if num is None:
        if isinstance(value, bool):
            return _js_text(value)
        text = str(value).strip() if value is not None else ''
        return text or '-'
    int_part, dot, frac = _js_text(num).partition('.')
    return _COMMAS_RE.sub(r'\1,', int_part) + dot + frac


def _comma_text(value):
    """Comma number format (same rule as the pie's pre-formatted labels)."""
    num = _as_number(value)
    if num is None:
        return str(value)
    return f'{num:,.0f}' if num == int(num) else f'{num:,.2f}'


# ── Hidden-value labels ───────────────────────────────────────────────────────

def apply_null_labels(series_list, categories, null_label, number_format='auto',
                      percent=False, pct_of_total=False, horizontal=False):
    """Rewrite bar series so the label and the tooltip print display text.

    A None value (SQL NULL) prints ``null_label``; any other value prints the
    text today's chart shows for it:
      ``percent``       the values are percentages → ``42.9%``
      ``pct_of_total``  share of the grand total  → ``2484 (42.9%)``
      ``number_format`` ``comma`` → ``12,422``; anything else → raw ``12422``
    The tooltip keeps its usual comma form (``12,422``).
    """
    grand_total = 0
    if pct_of_total and not percent:
        for s in series_list:
            grand_total += sum(v or 0 for v in s.get('data', []))
    for s in series_list:
        points = []
        for i, raw in enumerate(s.get('data', [])):
            v = raw.get('value') if isinstance(raw, dict) else raw
            shown = 0 if v is None else v
            if v is None:
                label = tip = null_label
            else:
                if percent:
                    label = f'{_js_text(v)}%'
                elif pct_of_total:
                    if grand_total > 0:
                        pct = round((v or 0) / grand_total * 100, 1)
                        label = f'{_js_text(v)} ({pct}%)'
                    else:
                        label = _js_text(v)
                elif number_format == 'comma':
                    label = _comma_text(v)
                else:
                    label = _js_text(v)
                tip = _tooltip_text(v)
            points.append({
                'name': categories[i] if i < len(categories) else '',
                'value': [i, shown, label, tip],
                'clickValue': shown,
            })
        s['data'] = points
        s['dimensions'] = [dict(d) for d in _DIMENSIONS]
        s['encode'] = ({'y': 'pv_cat', 'x': 'pv_val', 'tooltip': 'pv_tip'} if horizontal
                       else {'x': 'pv_cat', 'y': 'pv_val', 'tooltip': 'pv_tip'})
        label_cfg = dict(s.get('label') or {})
        label_cfg['formatter'] = '{@pv_label}'
        s['label'] = label_cfg
