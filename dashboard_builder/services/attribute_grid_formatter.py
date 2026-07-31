# -*- coding: utf-8 -*-
"""Pure, shared formatter for the ``attribute_grid`` widget.

SINGLE SOURCE OF TRUTH used by BOTH portal runtime
(``dashboard.widget._build_attribute_grid_data``) and designer preview
(``preview_formatter.format_preview``). No ORM / no I/O.

Two data shapes (plan v5):
  • ``single_record`` — fail-closed: 0 rows → empty; >1 rows → MULTIPLE_ROWS;
    duplicate alias / missing configured column → error. Layout comes from the
    configured ``fields`` list.
  • ``attribute_rows`` — one SQL row per displayed attribute; 0..N rows with a
    defensive cap; missing REQUIRED mapped columns → MISSING_COLUMN; invalid
    metadata on one item degrades that item only (fail-soft).

Placement: this formatter only VALIDATES/NORMALIZES ``row_order`` /
``column_start`` / ``column_span`` into safe metadata (invalid → None /
clamped). Final positions are computed by the shared JS placement function in
``grid-utils`` against the real container width — Python cannot know it.

Links are built server-side via ``widget_link_safety`` (admin-controlled
contents, per-part encoding, post-substitution scheme validation).
"""

from . import widget_config_defaults as D
from . import widget_link_safety as links
from .widget_config_normalizer import normalize_attribute_grid
from .widget_value_format import format_value, parse_number, resolve_icon


def _error(code, message):
    return {'type': 'attribute_grid', 'error_code': code, 'error': message}


def _col_index(cols):
    idx = {}
    for i, c in enumerate(cols):
        if c in idx:
            return None, c
        idx[c] = i
    return idx, None


def _style(cfg, style_key):
    """Token → {foreground, background} | None. Unknown token falls back to
    default_style_key, then widget default (None = component default)."""
    styles = cfg['styles']
    for candidate in (style_key, cfg['default_style_key']):
        if candidate and isinstance(candidate, str) \
                and candidate.strip() in styles:
            s = styles[candidate.strip()]
            return {'key': candidate.strip(),
                    'foreground': s['foreground'],
                    'background': s['background']}
    return None


def _initials(text):
    parts = [p for p in str(text or '').split() if p]
    if not parts:
        return ''
    letters = parts[0][:1] if len(parts) == 1 else (parts[0][:1] + parts[-1][:1])
    return letters.upper()[:2]


def _leading_visual(cfg, row_values, icon_map):
    lv = cfg['leading_visual']
    if lv['mode'] == 'none':
        return None
    out = {'mode': lv['mode'], 'foreground': lv['foreground'],
           'background': lv['background']}
    if lv['mode'] == 'icon':
        icon = resolve_icon(lv['icon_key'], icon_map)
        if icon is None:
            return None
        out['icon'] = icon
    elif lv['mode'] == 'initials':
        src = lv['source_column']
        out['text'] = _initials(row_values.get(src, '')) if src else ''
        if not out['text']:
            return None
    return out


def _format_cell(raw, fmt):
    """NULL → null_text; 0/False/'' are REAL values and format normally."""
    if raw is None:
        return fmt.get('null_text') or ''
    if isinstance(raw, bool):
        return 'True' if raw else 'False'
    return format_value(raw, fmt)


# ═══════════════════════════════════════════════════════════════════════════════
# single_record
# ═══════════════════════════════════════════════════════════════════════════════

def _format_single_record(cfg, cols, rows, icon_map):
    if len(rows) > 1:
        return _error('MULTIPLE_ROWS', 'Query returned multiple rows for a '
                                       'single-record grid')
    if not cols:
        return _error('MISSING_COLUMN', 'Query returned no columns')
    idx, dup = _col_index(cols)
    if idx is None:
        return _error('DUPLICATE_ALIAS', 'Duplicate result column alias: %s' % dup)
    row = rows[0]
    row_values = {c: row[i] for c, i in idx.items()}

    # Fail closed on any configured column missing from the result.
    referenced = set()
    for f in cfg['fields']:
        referenced.add(f['value_column'])
        if f['icon']['mode'] == 'column' and f['icon']['column']:
            referenced.add(f['icon']['column'])
    if cfg['leading_visual']['mode'] == 'initials' \
            and cfg['leading_visual']['source_column']:
        referenced.add(cfg['leading_visual']['source_column'])
    missing = sorted(c for c in referenced if c and c not in idx)
    if missing:
        return _error('MISSING_COLUMN',
                      'Configured column(s) not in result: %s'
                      % ', '.join(missing))

    items = []
    for f in cfg['fields']:
        raw = row_values.get(f['value_column'])
        icon = None
        ic = f['icon']
        if ic['mode'] == 'static':
            icon = resolve_icon(ic['key'], icon_map,
                                fallback_key=ic['fallback_key'])
        elif ic['mode'] == 'column':
            icon = resolve_icon(row_values.get(ic['column']), icon_map,
                                allowed_keys=ic['allowed_keys'],
                                fallback_key=ic['fallback_key'])
        link = links.build_link(
            f['link']['type'], f['link']['template'], row_values,
            new_tab=f['link']['new_tab']) if raw is not None else None
        items.append({
            'key': f['key'],
            'label': f['label'],
            'value': _format_cell(raw, f['format']),
            'is_null': raw is None,
            'icon': icon,
            'style': _style(cfg, f['style_key']),
            'layout': f['layout'] if f['layout'] != 'inherit'
                      else cfg['default_layout'],
            'emphasis': f['emphasis'],
            'divider_before': f['divider_before'],
            'placement': {'row_order': None, 'column_start': None,
                          'column_span': min(max(f['span'], 1), cfg['columns'])},
            'link': link,
        })
    return items, row_values


# ═══════════════════════════════════════════════════════════════════════════════
# attribute_rows
# ═══════════════════════════════════════════════════════════════════════════════

def _truthy(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() not in ('', '0', 'false', 'f', 'no', 'n')


def _int_or_none(v, lo=None, hi=None):
    n = parse_number(v)
    if n is None or n != int(n):
        return None
    n = int(n)
    if lo is not None and n < lo:
        return None
    if hi is not None and n > hi:
        return None
    return n


def _format_attribute_rows(cfg, cols, rows, icon_map):
    idx, dup = _col_index(cols)
    if idx is None:
        return _error('DUPLICATE_ALIAS', 'Duplicate result column alias: %s' % dup)
    rm = cfg['row_mapping']
    for required in ('label_column', 'value_column'):
        col = rm.get(required)
        if not col:
            return _error('BAD_CONFIG',
                          'row_mapping.%s is not configured' % required)
        if col not in idx:
            return _error('MISSING_COLUMN',
                          'Configured column not in result: %s' % col)

    def cell(row, role):
        col = rm.get(role)
        if not col or col not in idx:
            return None  # optional mapping absent from result → unmapped
        return row[idx[col]]

    items = []
    for i, row in enumerate(rows[:D.ATTRIBUTE_ROWS_CAP]):
        if rm['is_visible_column'] and rm['is_visible_column'] in idx \
                and not _truthy(cell(row, 'is_visible_column')):
            continue
        raw_key = cell(row, 'item_key_column')
        key = str(raw_key).strip() if raw_key not in (None, '') else 'row-%d' % i
        label_v = cell(row, 'label_column')
        raw = cell(row, 'value_column')

        # Per-row format: SQL metadata overrides row_default_format, each
        # component independently fail-soft.
        fmt = dict(cfg['row_default_format'])
        ftype = cell(row, 'format_type_column')
        if isinstance(ftype, str) and ftype.strip() in D.ATTR_FORMAT_TYPES:
            fmt['type'] = ftype.strip()
        dec = _int_or_none(cell(row, 'decimals_column'), 0, 6)
        if dec is not None:
            fmt['decimals'] = dec
        mult = parse_number(cell(row, 'display_multiplier_column'))
        if mult is not None:
            fmt['display_multiplier'] = float(mult)
        for role, fkey in (('prefix_column', 'prefix'),
                           ('suffix_column', 'suffix'),
                           ('null_text_column', 'null_text')):
            v = cell(row, role)
            if isinstance(v, str):
                fmt[fkey] = v

        layout = cell(row, 'layout_column')
        layout = layout.strip() if isinstance(layout, str) \
            and layout.strip() in D.LAYOUTS else cfg['default_layout']
        emphasis = cell(row, 'emphasis_column')
        emphasis = emphasis.strip() if isinstance(emphasis, str) \
            and emphasis.strip() in D.EMPHASES else 'normal'

        icon = resolve_icon(
            cell(row, 'icon_key_column'), icon_map,
            allowed_keys=cfg['row_icon']['allowed_keys'],
            fallback_key=cfg['row_icon']['fallback_key'],
        ) if rm['icon_key_column'] else None

        # Link: only when link_value is non-null. Type from allow-listed
        # link_type_column, else row_link.type. Placeholders resolve against
        # this row's mapped role values + {value}/{link_value}.
        link = None
        link_value = cell(row, 'link_value_column')
        if link_value is not None:
            ltype = cell(row, 'link_type_column')
            ltype = ltype.strip() if isinstance(ltype, str) \
                and ltype.strip() in D.LINK_TYPES else cfg['row_link']['type']
            template = cfg['row_link']['template'] or '{link_value}'
            values = {role.replace('_column', ''): cell(row, role)
                      for role in rm if rm.get(role)}
            values['value'] = raw
            values['link_value'] = link_value
            link = links.build_link(ltype, template, values,
                                    new_tab=cfg['row_link']['new_tab'])

        secondary = cell(row, 'secondary_value_column')
        items.append({
            'key': key,
            'label': '' if label_v is None else str(label_v),
            'value': _format_cell(raw, fmt),
            'is_null': raw is None,
            'secondary_value': None if secondary in (None, '')
                               else str(secondary),
            'icon': icon,
            'style': _style(cfg, cell(row, 'style_key_column')),
            'layout': layout,
            'emphasis': emphasis,
            'divider_before': _truthy(cell(row, 'divider_before_column')),
            'placement': {
                'row_order': _int_or_none(cell(row, 'row_order_column')),
                'column_start': _int_or_none(cell(row, 'column_start_column'),
                                             1, cfg['columns']),
                'column_span': _int_or_none(cell(row, 'column_span_column'),
                                            1, cfg['columns']) or 1,
            },
            'link': link,
        })
    return items, {}


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

def format_attribute_grid(cols, rows, config, icon_map=None):
    """Return the render-ready ``attribute_grid`` payload."""
    cfg = normalize_attribute_grid(config or {})
    cols = list(cols or [])
    rows = list(rows or [])

    if not rows:
        return {'type': 'attribute_grid', 'empty': True,
                'empty_text': cfg['empty_text']}

    if cfg['data_shape'] == 'attribute_rows':
        result = _format_attribute_rows(cfg, cols, rows, icon_map)
    else:
        result = _format_single_record(cfg, cols, rows, icon_map)
    if isinstance(result, dict):   # error payload
        return result
    items, row_values = result

    return {
        'type': 'attribute_grid',
        'data_shape': cfg['data_shape'],
        'columns': cfg['columns'],
        'density': cfg['density'],
        'leading_visual': _leading_visual(cfg, row_values, icon_map),
        'items': items,
        'empty_text': cfg['empty_text'],
    }
