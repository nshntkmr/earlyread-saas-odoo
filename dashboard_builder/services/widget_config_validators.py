# -*- coding: utf-8 -*-
"""Save-time validation for attribute_grid_config / metric_list_config.

Pure — no ORM. The mixin's ``@api.constrains`` parses the stored JSON, calls
``validate_attribute_grid_config`` / ``validate_metric_list_config`` on the
raw dict, and raises ``ValidationError`` with the joined error list.

Shape-specific: only the ACTIVE data shape's surface is validated. Scope-aware:
numeric-band overlap and match_values duplication are rejected only across
rules whose effective scopes intersect (globals among themselves); a scoped
rule may overlap a global one — scoped wins at evaluation.
"""

import math
import re

from . import widget_config_defaults as D
from . import widget_link_safety as links
from .widget_config_normalizer import (
    normalize_attribute_grid,
    normalize_metric_list,
)

_KEY_RE = re.compile(D.KEY_PATTERN)
_STYLE_KEY_RE = re.compile(D.STYLE_KEY_PATTERN)
_ICON_KEY_RE = re.compile(D.ICON_KEY_PATTERN)
_COLOR_RE = re.compile(D.COLOR_PATTERN)


def _is_num(v):
    """Finite real number; bool is explicitly NOT a number here."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) \
        and math.isfinite(v)


def _is_int(v, lo=None, hi=None):
    if not isinstance(v, int) or isinstance(v, bool):
        return False
    if lo is not None and v < lo:
        return False
    if hi is not None and v > hi:
        return False
    return True


def _str_ok(v, max_len):
    return isinstance(v, str) and len(v) <= max_len


def _check_color(errors, value, where):
    if not isinstance(value, str) or not _COLOR_RE.match(value):
        errors.append('%s: invalid color %r — expected #RGB/#RGBA/#RRGGBB/'
                      '#RRGGBBAA hex.' % (where, value))


def _check_format(errors, fmt, allowed_types, where):
    if fmt.get('type') not in allowed_types:
        errors.append('%s: format type must be one of %s.'
                      % (where, ', '.join(allowed_types)))
    if not _is_int(fmt.get('decimals'), D.DECIMALS_MIN, D.DECIMALS_MAX):
        errors.append('%s: decimals must be an integer %d–%d.'
                      % (where, D.DECIMALS_MIN, D.DECIMALS_MAX))
    if not _is_num(fmt.get('display_multiplier')):
        errors.append('%s: display_multiplier must be a finite number.' % where)
    for k in ('prefix', 'suffix'):
        if not _str_ok(fmt.get(k, ''), D.TEXT_MAX):
            errors.append('%s: %s too long (max %d).' % (where, k, D.TEXT_MAX))
    if 'null_text' in fmt and not _str_ok(fmt.get('null_text', ''), D.TEXT_MAX):
        errors.append('%s: null_text too long (max %d).' % (where, D.TEXT_MAX))


def _check_link(errors, link, where):
    ltype = link.get('type')
    if ltype not in D.LINK_TYPES:
        errors.append('%s: link type must be one of %s.'
                      % (where, ', '.join(D.LINK_TYPES)))
        return
    template = link.get('template') or ''
    if not _str_ok(template, D.TEMPLATE_MAX):
        errors.append('%s: link template too long (max %d).'
                      % (where, D.TEMPLATE_MAX))
        return
    if ltype != 'none':
        if not template:
            errors.append('%s: link type %r requires a template.' % (where, ltype))
        elif links.template_statically_unsafe(ltype, template):
            errors.append('%s: link template is unsafe for type %r '
                          '(scheme/shape check failed).' % (where, ltype))
    if not isinstance(link.get('new_tab', False), bool):
        errors.append('%s: new_tab must be boolean.' % where)


def _check_icon_keys(errors, keys, where):
    for k in keys:
        if not isinstance(k, str) or not _ICON_KEY_RE.match(k):
            errors.append('%s: invalid icon key %r.' % (where, k))


# ═══════════════════════════════════════════════════════════════════════════════
# Attribute Grid
# ═══════════════════════════════════════════════════════════════════════════════

def validate_attribute_grid_config(raw):
    """Return a list of error strings (empty = valid)."""
    errors = []
    if not isinstance(raw, dict):
        return ['attribute_grid_config must be a JSON object.']
    if raw.get('version') != D.VERSION:
        errors.append('attribute_grid_config requires "version": %d.' % D.VERSION)
    cfg = normalize_attribute_grid(raw)

    shape = cfg['data_shape']
    if shape not in D.DATA_SHAPES:
        errors.append('data_shape must be one of %s.' % ', '.join(D.DATA_SHAPES))
        return errors

    if not _is_int(cfg['columns'], D.COLUMNS_MIN, D.COLUMNS_MAX):
        errors.append('columns must be an integer %d–%d.'
                      % (D.COLUMNS_MIN, D.COLUMNS_MAX))
    if cfg['density'] not in D.DENSITIES:
        errors.append('density must be one of %s.' % ', '.join(D.DENSITIES))
    if cfg['default_layout'] not in D.LAYOUTS:
        errors.append('default_layout must be one of %s.' % ', '.join(D.LAYOUTS))
    if not _str_ok(cfg['empty_text'], D.TEXT_MAX):
        errors.append('empty_text too long (max %d).' % D.TEXT_MAX)

    # styles palette
    for skey, sval in cfg['styles'].items():
        if not isinstance(skey, str) or not _STYLE_KEY_RE.match(skey):
            errors.append('styles: invalid style key %r.' % skey)
            continue
        _check_color(errors, sval.get('foreground'), 'styles.%s.foreground' % skey)
        _check_color(errors, sval.get('background'), 'styles.%s.background' % skey)
    dsk = cfg['default_style_key']
    if dsk and dsk not in cfg['styles']:
        errors.append('default_style_key %r is not defined in styles.' % dsk)

    # leading visual (enum deliberately distinct from field icon.mode)
    lv = cfg['leading_visual']
    if lv['mode'] not in D.LEADING_VISUAL_MODES:
        errors.append('leading_visual.mode must be one of %s.'
                      % ', '.join(D.LEADING_VISUAL_MODES))
    elif lv['mode'] == 'icon' and not lv['icon_key']:
        errors.append('leading_visual mode "icon" requires icon_key.')
    elif lv['mode'] == 'initials' and not lv['source_column']:
        errors.append('leading_visual mode "initials" requires source_column.')
    if lv['icon_key']:
        _check_icon_keys(errors, [lv['icon_key']], 'leading_visual.icon_key')
    _check_color(errors, lv['foreground'], 'leading_visual.foreground')
    _check_color(errors, lv['background'], 'leading_visual.background')

    if shape == 'single_record':
        _validate_single_record_fields(errors, cfg)
    else:
        _validate_attribute_rows(errors, cfg, raw)
    return errors


def _validate_single_record_fields(errors, cfg):
    fields = cfg['fields']
    if not (D.FIELDS_MIN <= len(fields) <= D.FIELDS_MAX):
        errors.append('single_record requires %d–%d configured fields.'
                      % (D.FIELDS_MIN, D.FIELDS_MAX))
        if not fields:
            return
    seen = set()
    columns = cfg['columns'] if _is_int(cfg['columns'], 1, 8) else 8
    for i, f in enumerate(fields):
        where = 'fields[%d]' % i
        key = f.get('key')
        if not isinstance(key, str) or not _KEY_RE.match(key):
            errors.append('%s: key must match %s.' % (where, D.KEY_PATTERN))
        elif key in seen:
            errors.append('%s: duplicate field key %r.' % (where, key))
        else:
            seen.add(key)
        if not _str_ok(f.get('label') or '', D.LABEL_MAX) or not f.get('label'):
            errors.append('%s: label is required (max %d chars).'
                          % (where, D.LABEL_MAX))
        if not f.get('value_column'):
            errors.append('%s: value_column is required.' % where)
        icon = f['icon']
        if icon['mode'] not in D.FIELD_ICON_MODES:
            errors.append('%s: icon.mode must be one of %s.'
                          % (where, ', '.join(D.FIELD_ICON_MODES)))
        elif icon['mode'] == 'static' and not icon['key']:
            errors.append('%s: icon mode "static" requires key.' % where)
        elif icon['mode'] == 'column':
            if not icon['column']:
                errors.append('%s: icon mode "column" requires column.' % where)
            if not icon['allowed_keys']:
                errors.append('%s: icon mode "column" requires non-empty '
                              'allowed_keys (export discovery depends on it).'
                              % where)
        _check_icon_keys(
            errors,
            [k for k in ([icon['key'], icon['fallback_key']]
                         + list(icon['allowed_keys'])) if k],
            where + '.icon')
        if not _is_int(f.get('span'), 1, columns):
            errors.append('%s: span must be an integer 1–%d.' % (where, columns))
        if f.get('layout') not in D.FIELD_LAYOUTS:
            errors.append('%s: layout must be one of %s.'
                          % (where, ', '.join(D.FIELD_LAYOUTS)))
        if f.get('emphasis') not in D.EMPHASES:
            errors.append('%s: emphasis must be one of %s.'
                          % (where, ', '.join(D.EMPHASES)))
        if not isinstance(f.get('divider_before'), bool):
            errors.append('%s: divider_before must be boolean.' % where)
        _check_format(errors, f['format'], D.ATTR_FORMAT_TYPES, where + '.format')
        _check_link(errors, f['link'], where + '.link')
        sk = f.get('style_key') or ''
        if sk and sk not in cfg['styles']:
            errors.append('%s: style_key %r is not defined in styles.'
                          % (where, sk))


def _validate_attribute_rows(errors, cfg, raw):
    # The inactive shape's surface (fields) is never validated — but a
    # non-empty fields list alongside attribute_rows is a config smell the
    # admin should fix explicitly.
    if raw.get('fields'):
        errors.append('attribute_rows: fields must be empty '
                      '(layout comes from SQL rows).')
    rm = cfg['row_mapping']
    for required in ('label_column', 'value_column'):
        if not rm.get(required):
            errors.append('attribute_rows: row_mapping.%s is required.'
                          % required)
    for k, v in rm.items():
        if not isinstance(v, str):
            errors.append('row_mapping.%s must be a string alias.' % k)
    if rm.get('icon_key_column') and not cfg['row_icon']['allowed_keys']:
        errors.append('row_mapping.icon_key_column requires non-empty '
                      'row_icon.allowed_keys (export discovery depends on it).')
    _check_icon_keys(
        errors,
        [k for k in ([cfg['row_icon']['fallback_key']]
                     + list(cfg['row_icon']['allowed_keys'])) if k],
        'row_icon')
    _check_format(errors, cfg['row_default_format'], D.ATTR_FORMAT_TYPES,
                  'row_default_format')
    _check_link(errors, cfg['row_link'], 'row_link')


# ═══════════════════════════════════════════════════════════════════════════════
# Metric List
# ═══════════════════════════════════════════════════════════════════════════════

def _interval(rule_range):
    """(start, start_inc, end, end_inc) with None = ±infinity."""
    return (rule_range['min'], bool(rule_range['min_inclusive']),
            rule_range['max'], bool(rule_range['max_inclusive']))


def _intervals_overlap(a, b):
    """True when two (start, s_inc, end, e_inc) intervals share any point."""
    a_start, a_si, a_end, a_ei = a
    b_start, b_si, b_end, b_ei = b
    lo_a = -math.inf if a_start is None else a_start
    hi_a = math.inf if a_end is None else a_end
    lo_b = -math.inf if b_start is None else b_start
    hi_b = math.inf if b_end is None else b_end
    if hi_a < lo_b or hi_b < lo_a:
        return False
    if hi_a == lo_b:
        return a_ei and b_si
    if hi_b == lo_a:
        return b_ei and a_si
    return True


def _check_rule_set(errors, rules, scope_name):
    """Pairwise overlap + case-insensitive match_values dup within one
    effective scope (a metric key, or the global set)."""
    ranged = [(r['key'], _interval(r['range'])) for r in rules
              if r['range'] is not None]
    for i in range(len(ranged)):
        for j in range(i + 1, len(ranged)):
            if _intervals_overlap(ranged[i][1], ranged[j][1]):
                errors.append(
                    'status_rules %r and %r have overlapping numeric ranges '
                    'for scope %s (after inclusivity).'
                    % (ranged[i][0], ranged[j][0], scope_name))
    seen = {}
    for r in rules:
        for mv in r['match_values']:
            if not isinstance(mv, str):
                continue
            low = mv.strip().lower()
            if low in seen and seen[low] != r['key']:
                errors.append(
                    'match value %r is claimed by rules %r and %r within '
                    'scope %s.' % (mv, seen[low], r['key'], scope_name))
            else:
                seen[low] = r['key']


def validate_metric_list_config(raw):
    """Return a list of error strings (empty = valid)."""
    errors = []
    if not isinstance(raw, dict):
        return ['metric_list_config must be a JSON object.']
    if raw.get('version') != D.VERSION:
        errors.append('metric_list_config requires "version": %d.' % D.VERSION)
    cfg = normalize_metric_list(raw)

    mapping = cfg['mapping']
    for required in ('label_column', 'value_column'):
        if not mapping.get(required):
            errors.append('mapping.%s is required.' % required)
    for k, v in mapping.items():
        if not isinstance(v, str):
            errors.append('mapping.%s must be a string alias.' % k)
    has_min = bool(mapping.get('scale_min_column'))
    has_max = bool(mapping.get('scale_max_column'))
    if has_min != has_max:
        errors.append('Per-row scale requires BOTH scale_min_column and '
                      'scale_max_column (or neither).')
    if mapping.get('icon_column') and not cfg['icon']['allowed_keys']:
        errors.append('mapping.icon_column requires non-empty '
                      'icon.allowed_keys (export discovery depends on it).')
    _check_icon_keys(
        errors,
        [k for k in ([cfg['icon']['fallback_key']]
                     + list(cfg['icon']['allowed_keys'])) if k],
        'icon')

    scale = cfg['scale']
    if not _is_num(scale.get('min')) or not _is_num(scale.get('max')):
        errors.append('scale.min and scale.max must be finite numbers.')
    elif scale['min'] >= scale['max']:
        errors.append('scale.min must be < scale.max.')
    if not isinstance(scale.get('clamp'), bool):
        errors.append('scale.clamp must be boolean.')

    _check_format(errors, cfg['value_format'], D.METRIC_FORMAT_TYPES,
                  'value_format')

    progress = cfg['progress']
    if not isinstance(progress.get('show'), bool):
        errors.append('progress.show must be boolean.')
    if not _is_int(progress.get('height'), D.PROGRESS_HEIGHT_MIN,
                   D.PROGRESS_HEIGHT_MAX):
        errors.append('progress.height must be an integer %d–%d.'
                      % (D.PROGRESS_HEIGHT_MIN, D.PROGRESS_HEIGHT_MAX))
    _check_color(errors, progress.get('track_color'), 'progress.track_color')

    if not _str_ok(cfg['detail_label'], D.TEXT_MAX):
        errors.append('detail_label too long (max %d).' % D.TEXT_MAX)
    if not _str_ok(cfg['empty_text'], D.TEXT_MAX):
        errors.append('empty_text too long (max %d).' % D.TEXT_MAX)
    if not _is_int(cfg['max_items'], D.MAX_ITEMS_MIN, D.MAX_ITEMS_MAX):
        errors.append('max_items must be an integer %d–%d.'
                      % (D.MAX_ITEMS_MIN, D.MAX_ITEMS_MAX))
    if cfg['default_direction'] not in D.DIRECTIONS:
        errors.append('default_direction must be one of %s.'
                      % ', '.join(D.DIRECTIONS))

    # metric_settings
    setting_keys = set()
    for i, ms in enumerate(cfg['metric_settings']):
        where = 'metric_settings[%d]' % i
        mk = ms.get('metric_key')
        if not isinstance(mk, str) or not mk.strip():
            errors.append('%s: metric_key is required.' % where)
        elif mk in setting_keys:
            errors.append('%s: duplicate metric_key %r.' % (where, mk))
        else:
            setting_keys.add(mk)
        if ms.get('direction') not in D.DIRECTIONS:
            errors.append('%s: direction must be one of %s.'
                          % (where, ', '.join(D.DIRECTIONS)))

    legend = cfg['legend']
    if legend['mode'] not in D.LEGEND_MODES:
        errors.append('legend.mode must be one of %s.' % ', '.join(D.LEGEND_MODES))
    if legend['position'] not in D.LEGEND_POSITIONS:
        errors.append('legend.position must be one of %s.'
                      % ', '.join(D.LEGEND_POSITIONS))
    if not isinstance(legend.get('include_threshold_text'), bool):
        errors.append('legend.include_threshold_text must be boolean.')

    # status_rules
    rule_keys = set()
    scoped_exists = False
    for i, r in enumerate(cfg['status_rules']):
        where = 'status_rules[%d]' % i
        rk = r.get('key')
        if not isinstance(rk, str) or not rk.strip():
            errors.append('%s: key is required.' % where)
        elif rk in rule_keys:
            errors.append('%s: duplicate rule key %r.' % (where, rk))
        else:
            rule_keys.add(rk)
        for a in r['applies_to']:
            if not isinstance(a, str) or not a.strip():
                errors.append('%s: applies_to entries must be non-empty '
                              'strings.' % where)
        if r['applies_to']:
            scoped_exists = True
        for mv in r['match_values']:
            if not isinstance(mv, str) or not mv.strip():
                errors.append('%s: match_values entries must be non-empty '
                              'strings.' % where)
        if not _str_ok(r.get('label') or '', D.LABEL_MAX):
            errors.append('%s: label too long (max %d).' % (where, D.LABEL_MAX))
        _check_color(errors, r.get('color'), where + '.color')
        _check_color(errors, r.get('background'), where + '.background')
        if not isinstance(r.get('show_in_legend'), bool):
            errors.append('%s: show_in_legend must be boolean.' % where)
        rng = r['range']
        if rng is not None:
            for bound in ('min', 'max'):
                v = rng.get(bound)
                if v is not None and not _is_num(v):
                    errors.append('%s: range.%s must be null or a finite '
                                  'number.' % (where, bound))
            for flag in ('min_inclusive', 'max_inclusive'):
                if not isinstance(rng.get(flag), bool):
                    errors.append('%s: range.%s must be boolean.' % (where, flag))
            if rng.get('min') is None and rng.get('max') is None:
                errors.append('%s: a range object with both bounds null would '
                              'match every number — use "range": null for a '
                              'status-only rule.' % where)
            elif (_is_num(rng.get('min')) and _is_num(rng.get('max'))):
                if rng['min'] > rng['max']:
                    errors.append('%s: range.min must be <= range.max.' % where)
                elif rng['min'] == rng['max'] and not (
                        rng.get('min_inclusive') and rng.get('max_inclusive')):
                    errors.append('%s: a single-point range requires both '
                                  'bounds inclusive.' % where)
        if not r['match_values'] and rng is None:
            errors.append('%s: a rule needs at least one match_value or a '
                          'usable numeric range.' % where)

    if (scoped_exists or cfg['metric_settings']) and not mapping.get('key_column'):
        errors.append('mapping.key_column is required when any rule has '
                      'applies_to or metric_settings is non-empty (scoped '
                      'behavior must not depend on row-index fallback keys).')

    # Scope-aware overlap + match_values checks: per effective metric key
    # across INTERSECTING scopes, and among globals.
    valid_rules = [r for r in cfg['status_rules']
                   if isinstance(r.get('key'), str) and r['key'].strip()]
    global_rules = [r for r in valid_rules if not r['applies_to']]
    _check_rule_set(errors, global_rules, 'global')
    all_keys = set()
    for r in valid_rules:
        all_keys.update(a for a in r['applies_to']
                        if isinstance(a, str) and a.strip())
    for key in sorted(all_keys):
        scoped = [r for r in valid_rules if key in r['applies_to']]
        _check_rule_set(errors, scoped, repr(key))

    return errors
