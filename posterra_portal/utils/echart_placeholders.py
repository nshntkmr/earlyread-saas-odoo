# -*- coding: utf-8 -*-
"""Filter-value placeholders in a widget's chart styling.

``%(PARAM)s`` tokens are replaced with the APPLIED page-filter values
(``portal_ctx['filter_values_by_name']``) in two static JSON surfaces of
``dashboard.widget``:

  • ``echart_override`` — resolved on the raw text, before ``json.loads``
    (``resolve_echart_placeholders``);
  • ``visual_config.series_styles`` — resolved on the parsed string values
    (``resolve_placeholders_deep``), because series keys such as ``markArea``
    can only reach the generated series through series_styles: a ``series``
    list in the override would replace the SQL-built series.

Example — a band behind the month the user picked on a month × category
heatmap, in visual_config::

    {"series_styles": {"*": {"markArea": {"itemStyle": {"color": "rgba(29,95,191,0.14)"},
        "data": [[{"xAxis": "%(SERVICE_YEAR)s-%(SERVICE_MONTH)s"},
                  {"xAxis": "%(SERVICE_YEAR)s-%(SERVICE_MONTH)s"}]]}}}}

Rules, all deliberately narrow:
  • Only the exact ``%(NAME)s`` form is a token. A lone ``%`` (``"left": "98%"``)
    is never touched, so every existing override and style is byte-identical.
  • Only names present in ``values`` are replaced. An unknown name stays as
    typed — the Designer preview has no filter values, so a band whose
    category does not exist simply does not draw there; nothing breaks.
  • In the raw override text the value is inserted JSON-string-safe (quotes,
    backslashes and control characters escaped), so a filter value can never
    break out of the string literal the admin typed it into. Multi-select
    values travel as the CSV text the filter bar holds.
  • Pure: no ORM, no I/O.
"""

import json
import re

_TOKEN_RE = re.compile(r'%\((\w+)\)s')


def _value_text(value):
    if value is None:
        return ''
    if isinstance(value, (list, tuple, set)):
        return ','.join(str(v) for v in value)
    return str(value)


def resolve_echart_placeholders(text, values):
    """Return ``text`` with every ``%(NAME)s`` whose NAME is a key of ``values``
    replaced by that value, escaped for a JSON string context. Text without a
    token, or no values, comes back unchanged (same object)."""
    if not text or not values or '%(' not in text:
        return text

    def _sub(match):
        name = match.group(1)
        if name not in values:
            return match.group(0)
        return json.dumps(_value_text(values[name]), ensure_ascii=False)[1:-1]

    return _TOKEN_RE.sub(_sub, text)


def resolve_placeholders_deep(obj, values):
    """Return a copy of a parsed JSON structure (dict / list / scalars) with
    the tokens in its string leaves replaced by the plain filter values. With
    no values, or no token anywhere, the SAME object is returned."""
    if not values or not _has_token(obj):
        return obj
    return _walk(obj, values)


def _has_token(obj):
    if isinstance(obj, str):
        return '%(' in obj
    if isinstance(obj, dict):
        return any(_has_token(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return any(_has_token(v) for v in obj)
    return False


def _walk(obj, values):
    if isinstance(obj, str):
        if '%(' not in obj:
            return obj
        return _TOKEN_RE.sub(
            lambda m: _value_text(values[m.group(1)]) if m.group(1) in values
            else m.group(0), obj)
    if isinstance(obj, dict):
        return {k: _walk(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(v, values) for v in obj]
    return obj
