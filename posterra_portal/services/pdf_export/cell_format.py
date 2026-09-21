# -*- coding: utf-8 -*-
"""Print mirror of the AG Grid cell formatters + renderers (decision V5).

Source of truth (keep in sync; ``tests/fixtures/pdf_cell_format.json`` pins
the outputs and ``static/src/react/scripts/test_pdf_cell_format_parity.mjs``
checks the JavaScript formatters against the same fixture):

  * ``static/src/shared/grid-utils/formatters.js``  — VALUE_FORMATTERS
  * ``static/src/shared/grid-utils/renderers.jsx``  — CELL_RENDERERS

Rules mirrored exactly:

  * A cell renderer takes precedence over the value formatter (AG Grid), and
    each renderer reads the RAW value — except ``expandableCount``, which
    shows the formatted value when a formatter exists.
  * ``multiply`` has OPPOSITE defaults: the ``percentage`` formatter and the
    ``pctColored`` renderer multiply by 100 unless ``multiply === false``;
    ``barInline`` multiplies only when ``multiply === true``.
  * JavaScript number semantics: ``Number('') === 0`` (a blank cell under the
    ``number`` formatter shows "0", as on screen), ``toFixed`` rounds ties
    away from zero on the exact binary value, ``toLocaleString('en-US')``
    groups thousands with at most 3 fraction digits by default.
  * Conditional formatting (``cellClassRules``) is admin-typed JavaScript;
    only simple comparisons joined by ``&&`` / ``||`` are evaluated — any
    other expression is ignored (never executed).

Every admin-supplied colour passes ``safe_color`` before it reaches a style
attribute; every value is HTML-escaped.
"""

import datetime
import json
import math
import re
from decimal import ROUND_HALF_UP, Decimal

from markupsafe import Markup, escape

NAN = float('nan')

# ── JavaScript value semantics ────────────────────────────────────────────

_JS_NUM_RE = re.compile(r'^[+-]?(?:\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)$')


def client_value(v):
    """The value the browser grid sees for a Python cell value.

    ``_build_table_data`` maps None → '' and the API serialises with
    ``json.dumps(..., default=str)``: Decimal/date/datetime become strings.
    """
    if v is None:
        return ''
    if isinstance(v, (bool, int, float, str, list, dict)):
        return v
    return str(v)


def js_number(v):
    """``Number(v)``."""
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return 0.0
        if _JS_NUM_RE.match(s):
            return float(s)
        if re.match(r'^0[xX][0-9a-fA-F]+$', s):
            return float(int(s, 16))
        if s in ('Infinity', '+Infinity'):
            return math.inf
        if s == '-Infinity':
            return -math.inf
        return NAN
    return NAN


def is_nan(x):
    return isinstance(x, float) and math.isnan(x)


def js_str(v):
    """``String(v)`` for display (None/'' → '')."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v):
            return 'NaN'
        if math.isinf(v):
            return 'Infinity' if v > 0 else '-Infinity'
        if v == 0:
            return '0'
        if v.is_integer() and abs(v) < 1e21:
            return str(int(v))
        r = repr(v)
        if 'e' in r:
            if 1e-6 <= abs(v) < 1e21:
                return format(Decimal(r), 'f')
            mant, exp = r.split('e')
            e = int(exp)
            return f"{mant}e{'+' if e > 0 else '-'}{abs(e)}"
        return r
    if isinstance(v, (list, dict)):
        return json.dumps(v, separators=(',', ':'))
    return str(v)


def js_to_fixed(x, digits):
    """``Number.prototype.toFixed`` (ties away from zero on the exact value)."""
    if is_nan(x):
        return 'NaN'
    if math.isinf(x) or abs(x) >= 1e21:
        return js_str(x)
    if x == 0:
        x = 0.0  # JS: (-0).toFixed(1) === "0.0"
    q = Decimal(x).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return format(q, 'f')


def js_locale(x, min_frac=0, max_frac=3):
    """``Number(x).toLocaleString('en-US', {min/maxFractionDigits})``."""
    if is_nan(x):
        return 'NaN'
    if math.isinf(x):
        return '∞' if x > 0 else '-∞'
    negative = x < 0 or (x == 0 and math.copysign(1.0, x) < 0)
    q = abs(Decimal(x)).quantize(Decimal(1).scaleb(-max_frac), rounding=ROUND_HALF_UP)
    text = format(q, 'f')
    int_part, _, frac = text.partition('.')
    frac = frac.rstrip('0')
    if len(frac) < min_frac:
        frac = frac + '0' * (min_frac - len(frac))
    body = f'{int(int_part):,}' + (('.' + frac) if frac else '')
    return ('-' if negative else '') + body


# ── Safe CSS values ────────────────────────────────────────────────────────

_COLOR_RE = re.compile(
    r'^(#[0-9a-fA-F]{3,8}|[a-zA-Z]{3,20}|rgba?\(\s*[\d.]+%?\s*,\s*[\d.]+%?\s*,\s*[\d.]+%?'
    r'(\s*,\s*[\d.]+%?)?\s*\))$')


def safe_color(c, default=''):
    c = (c or '').strip() if isinstance(c, str) else ''
    return c if c and _COLOR_RE.match(c) else default


def _num_attr(x):
    return f'{x:.2f}'.rstrip('0').rstrip('.') or '0'


# ── Value formatters (formatters.js) ──────────────────────────────────────

def _fmt_number(v, col):
    n = js_number(v)
    return js_str(v) if is_nan(n) else js_locale(n, 0, 3)


def _fmt_currency(v, col):
    n = js_number(v)
    return js_str(v) if is_nan(n) else '$' + js_locale(n, 0, 0)


def _fmt_percentage(v, col):
    n = js_number(v)
    if is_nan(n):
        return js_str(v)
    multiply = (col.get('cellRendererParams') or {}).get('multiply') is not False
    return js_to_fixed(n * 100 if multiply else n, 1) + '%'


def _fmt_decimal(v, col):
    n = js_number(v)
    return js_str(v) if is_nan(n) else js_to_fixed(n, 2)


def _fmt_date(v, col):
    """``new Date(v).toLocaleDateString()`` (en-US). The date part is printed
    as written (no browser time-zone shift)."""
    if v in (None, '', 0, False):
        return ''
    s = js_str(v)
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
    if not m:
        return s
    try:
        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return s
    return f'{d.month}/{d.day}/{d.year}'


VALUE_FORMATTERS = {
    'number': _fmt_number,
    'currency': _fmt_currency,
    'percentage': _fmt_percentage,
    'decimal': _fmt_decimal,
    'date': _fmt_date,
}


# ── Conditional formatting (cellClassRules) — restricted evaluator ────────

RULE_CLASS_COLORS = {
    'cell-good': ('#10b981', True),
    'cell-bad': ('#ef4444', True),
    'cell-warn': ('#f59e0b', True),
    'cell-muted': ('#9ca3af', False),
}
BADGE_CLASS_COLORS = {
    'cell-good': '#059669', 'cell-warn': '#d97706', 'cell-bad': '#dc2626',
    'cell-info': '#3b82f6', 'cell-muted': '#6b7280',
}

_TOKEN_RE = re.compile(
    r'\s*(?:(?P<num>\d+(?:\.\d+)?|\.\d+)'
    r'|(?P<str>"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
    r'|(?P<op>===|!==|==|!=|>=|<=|>|<|&&|\|\||\(|\)|-)'
    r'|(?P<name>[A-Za-z_][A-Za-z0-9_]*))')


class _RuleError(Exception):
    pass


def _tokenize(expr):
    pos, out = 0, []
    expr = expr or ''
    while pos < len(expr):
        if expr[pos:].strip() == '':
            break
        m = _TOKEN_RE.match(expr, pos)
        if not m or m.end() == pos:
            raise _RuleError(expr)
        pos = m.end()
        if m.group('num') is not None:
            out.append(('lit', float(m.group('num'))))
        elif m.group('str') is not None:
            raw = m.group('str')[1:-1]
            out.append(('lit', re.sub(r'\\(.)', r'\1', raw)))
        elif m.group('op') is not None:
            out.append(('op', m.group('op')))
        else:
            name = m.group('name')
            if name == 'x':
                out.append(('x', None))
            elif name == 'true':
                out.append(('lit', True))
            elif name == 'false':
                out.append(('lit', False))
            elif name == 'null':
                out.append(('lit', None))
            else:
                raise _RuleError(name)   # identifiers other than x are refused
    return out


def _js_type(v):
    if v is None:
        return 'null'
    if isinstance(v, bool):
        return 'boolean'
    if isinstance(v, (int, float)):
        return 'number'
    return 'string'


def _loose_eq(a, b):
    ta, tb = _js_type(a), _js_type(b)
    if ta == tb:
        return a == b
    if 'null' in (ta, tb):
        return False
    na, nb = js_number(a), js_number(b)
    return not (is_nan(na) or is_nan(nb)) and na == nb


def _compare(op, a, b):
    if op == '===':
        return _js_type(a) == _js_type(b) and a == b
    if op == '!==':
        return not (_js_type(a) == _js_type(b) and a == b)
    if op == '==':
        return _loose_eq(a, b)
    if op == '!=':
        return not _loose_eq(a, b)
    if isinstance(a, str) and isinstance(b, str):
        pa, pb = a, b
    else:
        pa, pb = js_number(a), js_number(b)
        if is_nan(pa) or is_nan(pb):
            return False
    return {'>': pa > pb, '<': pa < pb, '>=': pa >= pb, '<=': pa <= pb}[op]


def eval_rule(expr, x):
    """Evaluate a simple admin rule like ``x >= 70 && x < 85``. Unsupported
    syntax → False (the rule is ignored, never executed)."""
    try:
        tokens = _tokenize(expr)
    except _RuleError:
        return False
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else (None, None)

    def take():
        tok = peek()
        pos[0] += 1
        return tok

    def atom():
        kind, val = take()
        if kind == 'op' and val == '(':
            v = or_expr()
            if take() != ('op', ')'):
                raise _RuleError('paren')
            return v
        if kind == 'op' and val == '-':
            k2, v2 = take()
            if k2 != 'lit' or not isinstance(v2, float):
                raise _RuleError('neg')
            return -v2
        if kind == 'x':
            return x
        if kind == 'lit':
            return val
        raise _RuleError('atom')

    def cmp_expr():
        left = atom()
        kind, val = peek()
        if kind == 'op' and val in ('===', '!==', '==', '!=', '>=', '<=', '>', '<'):
            take()
            return _compare(val, left, atom())
        return bool(left) if not isinstance(left, str) else left != ''

    def and_expr():
        v = cmp_expr()
        while peek() == ('op', '&&'):
            take()
            rhs = cmp_expr()
            v = v and rhs
        return v

    def or_expr():
        v = and_expr()
        while peek() == ('op', '||'):
            take()
            rhs = and_expr()
            v = v or rhs
        return v

    try:
        result = or_expr()
        if pos[0] != len(tokens):
            return False
        return bool(result)
    except (_RuleError, TypeError, KeyError, IndexError):
        return False


def matched_rule_classes(col, value):
    rules = col.get('cellClassRules')
    if not isinstance(rules, dict):
        return []
    return [cls for cls, expr in rules.items()
            if isinstance(expr, str) and eval_rule(expr, value)]


# ── Renderers (renderers.jsx) ─────────────────────────────────────────────

def _star_rating(v, p, row, col, formatted):
    n = js_number(v)
    if is_nan(n) or v is None or v == '':
        return Markup('')
    text = js_str(n) if float(n).is_integer() else js_to_fixed(n, 1)
    return Markup('<span class="pv-star">★ %s</span>') % text


def _pct_colored(v, p, row, col, formatted):
    n = js_number(v)
    if is_nan(n):
        return escape(js_str(v))
    pct = n * 100 if p.get('multiply') is not False else n
    good_above = p.get('goodAbove') if p.get('goodAbove') is not None else 70
    bad_below = p.get('badBelow') if p.get('badBelow') is not None else 50
    try:
        good_above, bad_below = float(good_above), float(bad_below)
    except (TypeError, ValueError):
        good_above, bad_below = 70.0, 50.0
    if pct >= good_above:
        color = safe_color(p.get('goodColor'), '#10b981')
    elif pct < bad_below:
        color = safe_color(p.get('badColor'), '#ef4444')
    else:
        color = '#f59e0b'
    return Markup('<span style="color:%s;font-weight:600">%s%%</span>') % (color, js_to_fixed(pct, 1))


def _badge(v, p, row, col, formatted):
    if v is None or v == '':
        return Markup('')
    bg = safe_color((p.get('colorMap') or {}).get(js_str(v)) if isinstance(p.get('colorMap'), dict) else '')
    if not bg:
        rules = col.get('cellClassRules')
        if isinstance(rules, dict):
            for cls, expr in rules.items():
                color = BADGE_CLASS_COLORS.get(cls)
                if color and isinstance(expr, str) and eval_rule(expr, v):
                    bg = color
                    break
    bg = bg or safe_color(p.get('defaultColor'), '#6b7280')
    return Markup('<span class="pv-badge" style="background:%s">%s</span>') % (bg, js_str(v))


def _svg(w, h, inner):
    return Markup('<svg width="%s" height="%s" viewBox="0 0 %s %s" class="pv-svg">%s</svg>') % (
        _num_attr(w), _num_attr(h), _num_attr(w), _num_attr(h), Markup(inner))


def _parse_series(raw):
    values = raw
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except ValueError:
            values = [js_number(s) for s in values.split(',')]
    if not isinstance(values, list) or len(values) < 2:
        return None
    nums = [js_number(x) for x in values]
    nums = [n for n in nums if not is_nan(n)]
    return nums if len(nums) >= 2 else None


def _dim(value, default):
    n = js_number(value) if value not in (None, '', 0, False) else NAN
    return default if is_nan(n) or n <= 0 else n


def _sparkline(v, p, row, col, formatted):
    raw = v
    if raw is None or raw == '':
        return Markup('')
    variant = p.get('variant') or 'line'
    w, h = _dim(p.get('width'), 60), _dim(p.get('height'), 20)
    if variant == 'bullet':
        data = raw
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                return escape(js_str(raw))
        data = data if isinstance(data, dict) else {}
        val = js_number(data.get('value', 0))
        tgt = js_number(data.get('target', 0))
        mx = js_number(data.get('max', 100))
        if any(is_nan(q) or math.isinf(q) for q in (val, tgt, mx)) or mx <= 0:
            return Markup('')
        color = p.get('color')
        bar = safe_color(color) if color and color != 'auto' else ('#10b981' if val >= tgt else '#f59e0b')
        bar = bar or '#10b981'
        tcolor = safe_color(p.get('targetColor'), '#0f172a')
        track = safe_color(p.get('trackColor'), '#e2e8f0')
        vw = max(0.0, min(1.0, val / mx)) * w
        tx = max(0.0, min(1.0, tgt / mx)) * w
        inner = (f'<rect x="0" y="{_num_attr(h / 2 - 3)}" width="{_num_attr(w)}" height="6" fill="{track}"/>'
                 f'<rect x="0" y="{_num_attr(h / 2 - 3)}" width="{_num_attr(vw)}" height="6" fill="{bar}"/>'
                 f'<line x1="{_num_attr(tx)}" y1="1" x2="{_num_attr(tx)}" y2="{_num_attr(h - 1)}" '
                 f'stroke="{tcolor}" stroke-width="1.5"/>')
        return _svg(w, h, inner)
    nums = _parse_series(raw)
    if not nums:
        return escape(js_str(raw))
    trend_up = nums[-1] >= nums[0]
    color = p.get('color')
    color = safe_color(color) if color and color != 'auto' else ('#10b981' if trend_up else '#ef4444')
    color = color or '#10b981'
    n = len(nums)
    if variant == 'winloss':
        parts = [f'<line x1="0" y1="{_num_attr(h / 2)}" x2="{_num_attr(w)}" y2="{_num_attr(h / 2)}" '
                 f'stroke="#cbd5e1" stroke-width="0.5"/>']
        for i, val in enumerate(nums):
            x = (i / (n - 1)) * w
            c = '#10b981' if val > 0 else ('#ef4444' if val < 0 else '#94a3b8')
            top = 2 if val > 0 else (h / 2 if val < 0 else h / 2 - 1)
            th = (h / 2 - 2) if val != 0 else 2
            parts.append(f'<rect x="{_num_attr(x - 2)}" y="{_num_attr(top)}" width="3" '
                         f'height="{_num_attr(th)}" fill="{c}"/>')
        return _svg(w, h, ''.join(parts))
    lo, hi = min(nums), max(nums)
    rng = (hi - lo) or 1
    if variant == 'bar':
        bw = max(1.0, (w / n) - 1)
        parts = []
        for i, val in enumerate(nums):
            bh = ((val - lo) / rng) * (h - 2)
            parts.append(f'<rect x="{_num_attr((i / n) * w)}" y="{_num_attr(h - bh - 1)}" '
                         f'width="{_num_attr(bw)}" height="{_num_attr(bh)}" fill="{color}"/>')
        return _svg(w, h, ''.join(parts))
    pts = ' '.join(f'{_num_attr((i / (n - 1)) * w)},{_num_attr(h - ((val - lo) / rng) * (h - 2) - 1)}'
                   for i, val in enumerate(nums))
    line = f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/>'
    if variant == 'area':
        area = f'<polygon points="0,{_num_attr(h)} {pts} {_num_attr(w)},{_num_attr(h)}" fill="{color}" opacity="0.2"/>'
        return _svg(w, h, area + line)
    return _svg(w, h, line)


_BAR_SCALES = {'none': ('', 1.0), 'thousands': ('K', 1e3), 'millions': ('M', 1e6), 'billions': ('B', 1e9)}


def bar_inline_label(value, p):
    """``formatBarInlineValue``."""
    fmt = p.get('format') or 'number'
    if fmt == 'raw':
        return js_str(value)
    scale_suffix, divisor = _BAR_SCALES.get(p.get('scale') or 'none', _BAR_SCALES['none'])
    scaled = value / divisor
    dec = p.get('decimals')
    if dec is not None and dec != '':
        dn = js_number(dec)
        decimals = int(max(0, min(6, 0 if is_nan(dn) else dn)))
    elif fmt in ('percent', 'pp'):
        decimals = 1
    elif fmt == 'currency' and scale_suffix:
        decimals = 1
    else:
        decimals = 0 if float(scaled).is_integer() else 1
    sign = '+' if ((p.get('showSign') is True or fmt == 'pp') and scaled > 0) else ''
    prefix = p['prefix'] if p.get('prefix') is not None else ('$' if fmt == 'currency' else '')
    suffix = p['suffix'] if p.get('suffix') is not None else ('%' if fmt == 'percent' else (' pp' if fmt == 'pp' else ''))
    return f'{sign}{prefix}{js_locale(scaled, decimals, decimals)}{scale_suffix}{suffix}'


def _bar_inline(v, p, row, col, formatted):
    n = js_number(v)
    if is_nan(n):
        return escape(js_str(v))
    val = n * 100 if p.get('multiply') is True else n
    mx = js_number(p.get('max')) if p.get('max') not in (None, '', 0, False) else 100.0
    if is_nan(mx) or mx == 0:
        mx = 100.0
    pct = min(max((val / mx) * 100, 0.0), 100.0)
    color = safe_color(p.get('color'), '#3b82f6')
    position = p.get('valuePosition') or 'right'
    label = '' if position == 'hidden' else bar_inline_label(val, p)
    bar = Markup('<span class="pv-bar"><span style="width:%s%%;background:%s"></span></span>') % (_num_attr(pct), color)
    lab = Markup('<span class="pv-bar-label">%s</span>') % label if label != '' else Markup('')
    inner = (lab + bar) if position == 'left' else (bar + lab)
    return Markup('<span class="pv-barinline">%s</span>') % inner


def _composite(v, p, row, col, formatted):
    lines = p.get('lines') or []
    if not isinstance(lines, list) or not lines:
        return escape(js_str(v))
    out = []
    if v is not None and v != '':
        out.append(Markup('<div class="pv-comp-main">%s</div>') % js_str(v))
    for line in lines:
        if not isinstance(line, dict):
            continue
        parts = [js_str(row.get(f)) for f in (line.get('fields') or [])
                 if row.get(f) is not None and row.get(f) != '']
        if not parts:
            continue
        text = (line.get('separator') or ' ').join(parts)
        if line.get('prefix'):
            text = str(line['prefix']) + text
        if line.get('suffix'):
            text = text + str(line['suffix'])
        style = []
        if line.get('bold'):
            style.append('font-weight:600')
        if line.get('muted'):
            style.append('color:#6b7280;font-size:0.85em')
        if line.get('small'):
            style.append('font-size:0.8em')
        if safe_color(line.get('color')):
            style.append('color:' + safe_color(line.get('color')))
        link = Markup(' <span class="pv-muted">↗</span>') if (
            line.get('linkField') and row.get(line.get('linkField'))) else Markup('')
        out.append(Markup('<div style="%s">%s%s</div>') % (';'.join(style), text, link))
    return Markup('').join(out)


def _dual_value(v, p, row, col, formatted):
    if v is None or v == '':
        return Markup('')
    primary = js_locale(float(v)) if isinstance(v, (int, float)) and not isinstance(v, bool) else js_str(v)
    field = p.get('secondaryField')
    sraw = row.get(field) if field else None
    fmt = p.get('secondaryFormat') or 'pct'
    secondary = None
    if sraw is not None and sraw != '':
        sv = js_number(sraw)
        if not is_nan(sv):
            if fmt == 'pct':
                d = p.get('secondaryDecimals')
                d = 0 if d is None else d
                dn = js_number(d)
                secondary = js_to_fixed(sv * 100 if p.get('secondaryMultiply') is not False else sv,
                                        int(0 if is_nan(dn) else dn)) + '%'
            elif fmt == 'number':
                secondary = js_locale(sv)
            else:
                secondary = js_str(sraw)
        else:
            secondary = js_str(sraw)
    color, arrow = '#6b7280', ''
    if p.get('coloredDelta') is True and sraw is not None and sraw != '':
        sn = js_number(sraw)
        if not is_nan(sn):
            if sn > 0:
                color, arrow = '#059669', '▲ '
            elif sn < 0:
                color, arrow = '#dc2626', '▼ '
    sec_html = (Markup(' <span style="color:%s;font-size:0.9em">%s%s</span>') % (color, arrow, secondary)
                if secondary is not None else Markup(''))
    return Markup('<strong>%s</strong>%s') % (primary, sec_html)


def _inline_chart(v, p, row, col, formatted):
    raw = v
    if raw is None or raw == '':
        return Markup('')
    kind = p.get('type') or 'bar'
    w, h = (150, 40) if p.get('size') == 'medium' else (80, 32)
    color = safe_color(p.get('color'), '#0d9488')
    if kind == 'kpi':
        kpi = raw
        if isinstance(kpi, str):
            try:
                kpi = json.loads(kpi)
            except ValueError:
                kpi = {'value': raw}
        if isinstance(kpi, dict):
            value, label = kpi.get('value'), kpi.get('label')
            kcolor = safe_color(kpi.get('color'), color)
        else:
            value, label, kcolor = kpi, None, color
        lab = Markup('<div class="pv-muted" style="font-size:0.8em">%s</div>') % js_str(label) if label else Markup('')
        return Markup('<div style="color:%s;font-weight:600">%s</div>%s') % (
            kcolor, js_str(value) if value is not None else '', lab)
    nums = _parse_series(raw)
    if not nums:
        return escape(js_str(raw))
    n, lo, hi = len(nums), min(nums), max(nums)
    rng = (hi - lo) or 1
    if kind == 'bar':
        bw = max(1.0, (w / n) - 1)
        parts = []
        for i, val in enumerate(nums):
            bh = ((val - lo) / rng) * (h - 4)
            parts.append(f'<rect x="{_num_attr((i / n) * w)}" y="{_num_attr(h - bh - 2)}" '
                         f'width="{_num_attr(bw)}" height="{_num_attr(bh)}" fill="{color}"/>')
        return _svg(w, h, ''.join(parts))
    pts = ' '.join(f'{_num_attr((i / (n - 1)) * w)},{_num_attr(h - ((val - lo) / rng) * (h - 4) - 2)}'
                   for i, val in enumerate(nums))
    return _svg(w, h, f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/>')


_STRIP_COLORS = {'compliant': '#16a34a', 'nonCompliant': '#dc2626', 'na': '#e5e7eb'}
_STRIP_SIZES = {'sm': 12, 'md': 16, 'lg': 20}


def _strip_items(raw):
    items = raw
    if isinstance(items, str):
        s = items.strip()
        if not s:
            return []
        try:
            items = json.loads(s)
        except ValueError:
            return []
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append({'label': it.get('label') if it.get('label') is not None else '',
                        'status': it.get('status') if it.get('status') is not None else 'na'})
        else:
            out.append({'label': '', 'status': 'na'})
    return out


def _compliance_strip(v, p, row, col, formatted):
    raw = row.get(p.get('itemsField')) if p.get('itemsField') else v
    items = _strip_items(raw)
    if not items:
        return Markup('<span class="pv-muted">—</span>')
    colors = dict(_STRIP_COLORS)
    if isinstance(p.get('colors'), dict):
        for k, c in p['colors'].items():
            if safe_color(c):
                colors[k] = safe_color(c)
    size = p.get('size') or 'sm'
    px = size if isinstance(size, (int, float)) and not isinstance(size, bool) else _STRIP_SIZES.get(size, 12)
    out = []
    for it in items:
        status = it['status'] if it['status'] in colors else 'na'
        if p.get('showLabels'):
            font = p.get('fontSize') if isinstance(p.get('fontSize'), (int, float)) else (
                px if isinstance(size, (int, float)) else 11)
            out.append(Markup('<span class="pv-pill" style="background:%s;font-size:%spx">%s</span>') % (
                colors[status], _num_attr(font), js_str(it['label'])))
        else:
            out.append(Markup('<span class="pv-dot" style="background:%s;width:%spx;height:%spx"></span>') % (
                colors[status], _num_attr(px * 0.75), _num_attr(px * 0.75)))
    return Markup('<span class="pv-strip">%s</span>') % Markup('').join(out)


def _expandable_count(v, p, row, col, formatted):
    display = formatted if formatted is not None else ('' if v is None else js_str(v))
    return escape(display)


CELL_RENDERERS = {
    'starRating': _star_rating,
    'pctColored': _pct_colored,
    'badge': _badge,
    'sparkline': _sparkline,
    'barInline': _bar_inline,
    'composite': _composite,
    'dualValue': _dual_value,
    'inlineChart': _inline_chart,
    'complianceStrip': _compliance_strip,
    'expandableCount': _expandable_count,
}

_NUMERIC_TEXT_RE = re.compile(r'^[\s$+\-−(]*[\d.,]+\s*(%|pts|pp|[KMB])?\)?$')
_SAFE_CELL_STYLE = {'color': 'color', 'backgroundColor': 'background', 'fontWeight': 'font-weight'}


def render_cell(col, row):
    """``(Markup html, css_class, style)`` for one printed cell.

    ``row`` holds CLIENT values (see ``client_value``) keyed by field.
    """
    field = col.get('field')
    value = row.get(field, '') if field else ''
    fmt_key = col.get('valueFormatter')
    formatter = VALUE_FORMATTERS.get(fmt_key) if isinstance(fmt_key, str) else None
    formatted = formatter(value, col) if formatter else None
    p = col.get('cellRendererParams') if isinstance(col.get('cellRendererParams'), dict) else {}
    renderer = CELL_RENDERERS.get(col.get('cellRenderer')) if isinstance(col.get('cellRenderer'), str) else None
    if renderer:
        html = renderer(value, p, row, col, formatted)
        text_for_align = formatted if formatted is not None else js_str(value)
    else:
        text_for_align = formatted if formatted is not None else js_str(value)
        html = escape(text_for_align)
    styles = []
    for cls in matched_rule_classes(col, value):
        color = RULE_CLASS_COLORS.get(cls)
        if color:
            styles.append(f'color:{color[0]}' + (';font-weight:600' if color[1] else ''))
            break
    cell_style = col.get('cellStyle')
    if isinstance(cell_style, dict):
        for key, css in _SAFE_CELL_STYLE.items():
            val = cell_style.get(key)
            if key == 'fontWeight' and isinstance(val, (str, int)) and re.match(r'^(bold|normal|[1-9]00)$', str(val)):
                styles.append(f'{css}:{val}')
            elif key != 'fontWeight' and safe_color(val):
                styles.append(f'{css}:{safe_color(val)}')
    align = 'num' if (renderer in (None, _expandable_count, _pct_colored, _star_rating)
                      and _NUMERIC_TEXT_RE.match(text_for_align or '')) else ''
    return html, align, ';'.join(styles)


def printable_columns(column_defs, max_columns):
    """Visible columns (``hide`` excluded) capped at ``max_columns``.
    Returns ``(columns, total_visible)``."""
    cols = [c for c in (column_defs or []) if isinstance(c, dict) and not c.get('hide')
            and (c.get('field') or c.get('colId'))]
    return cols[:max_columns], len(cols)


def header_label(col):
    name = col.get('headerName')
    if isinstance(name, str) and name.strip():
        return name
    return str(col.get('field') or col.get('colId') or '')
