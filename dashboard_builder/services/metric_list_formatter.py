# -*- coding: utf-8 -*-
"""Pure, shared formatter for the ``metric_list`` widget.

SINGLE SOURCE OF TRUTH used by BOTH portal runtime
(``dashboard.widget._build_metric_list_data``) and designer preview
(``preview_formatter.format_preview``). No ORM / no I/O — the caller resolves
the icon registry into a plain ``icon_map`` dict.

Contract highlights (plan v5):
  • SQL row order preserved; ``max_items`` render-side truncation +
    ``METRIC_ROWS_CAP`` defensive cap.
  • Payload numbers: ``raw_value`` decimal STRING, ``progress_fraction``
    bounded float [0,1] or None, ``formatted_value`` display string.
  • Thresholds ALWAYS evaluate the raw value — never the display value.
  • 5-step status resolution: status_column vs scoped match_values → vs global
    match_values → scoped ranges → global ranges → neutral; an unrecognized
    status string falls THROUGH to numeric evaluation.
  • Per-row scale (both columns valid, min<max) else global; clamp=False +
    out-of-range → no bar + out_of_range flag (a zero/overflow bar is a lie).
  • Direction: Builder metric_settings → valid SQL direction_column → widget
    default; explicit ranges are never reinterpreted by direction.
  • legend.mode auto degrades to semantic unless every rule is global AND
    row display formatting is uniform.
"""

from decimal import Decimal

from . import widget_config_defaults as D
from .widget_config_normalizer import normalize_metric_list
from .widget_value_format import format_value, parse_number, resolve_icon

EMPTY_MARKER = '—'


def _error(code, message):
    return {'type': 'metric_list', 'error_code': code, 'error': message}


def _col_index(cols):
    idx = {}
    for i, c in enumerate(cols):
        if c in idx:
            return None, c
        idx[c] = i
    return idx, None


def _cell(row, idx, col):
    if not col or col not in idx:
        return None
    return row[idx[col]]


def _interval_contains(rng, value):
    lo, hi = rng['min'], rng['max']
    if lo is not None:
        if value < lo or (value == lo and not rng['min_inclusive']):
            return False
    if hi is not None:
        if value > hi or (value == hi and not rng['max_inclusive']):
            return False
    return True


def _resolve_status(cfg, metric_key, status_text, num_value):
    """The deterministic 5-step resolution. Returns (rule|None)."""
    rules = cfg['status_rules']
    scoped = [r for r in rules if metric_key and metric_key in r['applies_to']]
    global_ = [r for r in rules if not r['applies_to']]
    text = (status_text or '').strip().lower() if status_text is not None else ''
    if text:
        for pool in (scoped, global_):
            for r in pool:
                if any(text == str(mv).strip().lower()
                       for mv in r['match_values']):
                    return r
        # Unrecognized status string: fall through to numeric — only when
        # numeric also fails does the row land on neutral.
    if num_value is not None:
        fv = float(num_value)
        for pool in (scoped, global_):
            for r in pool:
                if r['range'] is not None and _interval_contains(r['range'], fv):
                    return r
    return None


def _resolve_direction(cfg, metric_key, row_direction):
    settings = {ms['metric_key']: ms['direction']
                for ms in cfg['metric_settings'] if ms.get('metric_key')}
    if metric_key and metric_key in settings:
        return settings[metric_key]
    if isinstance(row_direction, str) and row_direction.strip() in D.DIRECTIONS:
        return row_direction.strip()
    return cfg['default_direction']


def _row_format(cfg, idx, row):
    """Per-row display format: SQL columns override widget value_format,
    each field fail-soft independently."""
    base = cfg['value_format']
    mapping = cfg['mapping']
    fmt = dict(base)
    ftype = _cell(row, idx, mapping['format_type_column'])
    if isinstance(ftype, str) and ftype.strip() in D.METRIC_FORMAT_TYPES:
        fmt['type'] = ftype.strip()
    dec = _cell(row, idx, mapping['decimals_column'])
    dec_n = parse_number(dec)
    if dec_n is not None and 0 <= int(dec_n) <= 6 and int(dec_n) == dec_n:
        fmt['decimals'] = int(dec_n)
    mult = parse_number(_cell(row, idx, mapping['display_multiplier_column']))
    if mult is not None:
        fmt['display_multiplier'] = float(mult)
    for src, key in (('prefix_column', 'prefix'), ('suffix_column', 'suffix')):
        v = _cell(row, idx, mapping[src])
        if isinstance(v, str):
            fmt[key] = v
    return fmt


def _row_scale(cfg, idx, row):
    """(min, max, is_row_scale) — row override only when BOTH row values are
    valid and min < max; invalid row scale → (None, None, True) = no bar."""
    mapping = cfg['mapping']
    if mapping['scale_min_column'] and mapping['scale_max_column']:
        lo = parse_number(_cell(row, idx, mapping['scale_min_column']))
        hi = parse_number(_cell(row, idx, mapping['scale_max_column']))
        if lo is not None and hi is not None and lo < hi:
            return float(lo), float(hi), True
        return None, None, True
    return float(cfg['scale']['min']), float(cfg['scale']['max']), False


def _progress(cfg, value, lo, hi):
    """(fraction|None, out_of_range). Never emits <0 or >1."""
    if value is None or lo is None or hi is None:
        return None, False
    frac = (float(value) - lo) / (hi - lo)
    if 0.0 <= frac <= 1.0:
        return frac, False
    if cfg['scale']['clamp']:
        return (0.0 if frac < 0 else 1.0), False
    return None, True


def _legend_mode_resolved(cfg, uniform_formatting):
    mode = cfg['legend']['mode']
    if mode != 'auto':
        return mode
    all_global = all(not r['applies_to'] for r in cfg['status_rules'])
    return 'numeric' if (all_global and uniform_formatting) else 'semantic'


def _threshold_text(rule, fmt):
    """'< 40.0%'-style caption through the applicable value_format."""
    rng = rule['range']
    if rng is None:
        return ''
    lo, hi = rng['min'], rng['max']

    def _f(v):
        return format_value(v, fmt)

    if lo is None and hi is not None:
        return '%s %s' % ('≤' if rng['max_inclusive'] else '<', _f(hi))
    if hi is None and lo is not None:
        return '%s %s' % ('≥' if rng['min_inclusive'] else '>', _f(lo))
    if lo is not None and hi is not None:
        return '%s–%s' % (_f(lo), _f(hi))
    return ''


def format_metric_list(cols, rows, config, icon_map=None):
    """Return the render-ready ``metric_list`` payload."""
    cfg = normalize_metric_list(config or {})
    cols = list(cols or [])
    rows = list(rows or [])

    if not rows:
        return {'type': 'metric_list', 'empty': True,
                'empty_text': cfg['empty_text']}
    idx, dup = _col_index(cols)
    if idx is None:
        return _error('DUPLICATE_ALIAS', 'Duplicate result column alias: %s' % dup)
    mapping = cfg['mapping']
    for required in ('label_column', 'value_column'):
        col = mapping.get(required)
        if not col:
            return _error('BAD_CONFIG', 'mapping.%s is not configured' % required)
        if col not in idx:
            return _error('MISSING_COLUMN',
                          'Configured column not in result: %s' % col)

    rows = rows[:D.METRIC_ROWS_CAP][:cfg['max_items']]
    uniform = not any(mapping[c] for c in (
        'format_type_column', 'decimals_column', 'display_multiplier_column',
        'prefix_column', 'suffix_column'))

    items = []
    for i, row in enumerate(rows):
        raw_key = _cell(row, idx, mapping['key_column'])
        metric_key = str(raw_key).strip() if raw_key not in (None, '') \
            else 'row-%d' % i
        label_v = _cell(row, idx, mapping['label_column'])
        label = '' if label_v is None else str(label_v)
        raw = _cell(row, idx, mapping['value_column'])
        num = parse_number(raw)
        fmt = _row_format(cfg, idx, row)
        lo, hi, _row_scaled = _row_scale(cfg, idx, row)
        fraction, out_of_range = _progress(cfg, num, lo, hi)
        status_text = _cell(row, idx, mapping['status_column'])
        rule = _resolve_status(
            cfg, metric_key,
            str(status_text) if status_text is not None else None, num)
        direction = _resolve_direction(
            cfg, metric_key, _cell(row, idx, mapping['direction_column']))
        detail_v = _cell(row, idx, mapping['detail_column'])
        icon = resolve_icon(
            _cell(row, idx, mapping['icon_column']), icon_map,
            allowed_keys=cfg['icon']['allowed_keys'],
            fallback_key=cfg['icon']['fallback_key'],
        ) if mapping['icon_column'] else None

        item = {
            'key': metric_key,
            'label': label,
            'raw_value': None if num is None else str(num),
            'formatted_value': EMPTY_MARKER if num is None
                               else format_value(num, fmt),
            'progress_fraction': fraction,
            'direction': direction,
            'detail': None if detail_v in (None, '') else str(detail_v),
            'icon': icon,
        }
        if out_of_range:
            item['out_of_range'] = True
        if rule is not None:
            item['status'] = {'key': rule['key'], 'label': rule['label'],
                              'color': rule['color'],
                              'background': rule['background']}
        else:
            item['status'] = None
        if cfg['legend']['mode'] == 'per_metric':
            scoped = [r for r in cfg['status_rules']
                      if (metric_key in r['applies_to']) or not r['applies_to']]
            item['thresholds'] = [
                {'key': r['key'], 'label': r['label'], 'color': r['color'],
                 'text': _threshold_text(r, fmt)}
                for r in scoped if r['show_in_legend'] and r['range'] is not None]
        items.append(item)

    mode = _legend_mode_resolved(cfg, uniform)
    legend = {'mode': mode, 'position': cfg['legend']['position'], 'entries': []}
    if mode in ('numeric', 'semantic'):
        for r in cfg['status_rules']:
            if not r['show_in_legend']:
                continue
            entry = {'key': r['key'], 'label': r['label'],
                     'color': r['color'], 'background': r['background']}
            if mode == 'numeric' and cfg['legend']['include_threshold_text']:
                entry['text'] = _threshold_text(r, cfg['value_format'])
            legend['entries'].append(entry)

    return {
        'type': 'metric_list',
        'items': items,
        'legend': legend,
        'detail_label': cfg['detail_label'],
        'progress': {'show': cfg['progress']['show'],
                     'height': cfg['progress']['height'],
                     'track_color': cfg['progress']['track_color']},
        'neutral': dict(D.NEUTRAL_STATUS),
        'empty_text': cfg['empty_text'],
    }
