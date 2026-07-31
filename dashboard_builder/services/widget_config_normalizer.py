# -*- coding: utf-8 -*-
"""Normalize raw attribute_grid / metric_list configs to canonical v1 form.

Pure — no ORM, no I/O. The JS mirror is
``grid-utils/configNormalizer.js``; both are asserted structurally identical by
the golden fixtures (``dashboard_builder/schemas/golden_fixtures/``).

Contract: unknown keys are dropped; known scalar keys keep the user value when
present (whatever its type — the VALIDATOR judges types, the normalizer only
shapes); known dict keys merge recursively; list keys are replaced wholesale
with each item normalized against its item defaults. ``styles`` is special:
user keys merge INTO the seeded defaults (custom palette keys are additive).
``range`` is special: ``None`` stays ``None`` (status-only rule); an object is
normalized against RANGE_DEFAULTS.
"""

import copy

from . import widget_config_defaults as D


def _merge_known(defaults, raw):
    """Recursive merge of ``raw`` into a deep copy of ``defaults``.

    Only keys present in ``defaults`` survive. Dict-valued defaults merge
    recursively; everything else takes the raw value verbatim when supplied.
    """
    out = copy.deepcopy(defaults)
    if not isinstance(raw, dict):
        return out
    for key, dflt in defaults.items():
        if key not in raw:
            continue
        val = raw[key]
        if isinstance(dflt, dict) and isinstance(val, dict):
            out[key] = _merge_known(dflt, val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def _normalize_list(items, item_defaults, item_fn=None):
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        norm = _merge_known(item_defaults, item if isinstance(item, dict) else {})
        if item_fn is not None:
            norm = item_fn(norm, item)
        out.append(norm)
    return out


def normalize_attribute_grid(raw):
    raw = raw if isinstance(raw, dict) else {}
    cfg = _merge_known(D.ATTRIBUTE_GRID_DEFAULTS, raw)
    # styles: additive merge — custom keys join the seeded four.
    styles = copy.deepcopy(D.DEFAULT_STYLES)
    if isinstance(raw.get('styles'), dict):
        for k, v in raw['styles'].items():
            if isinstance(v, dict):
                styles[k] = {
                    'foreground': v.get('foreground', ''),
                    'background': v.get('background', ''),
                }
    cfg['styles'] = styles
    cfg['fields'] = _normalize_list(raw.get('fields'), D.FIELD_ITEM_DEFAULTS)
    return cfg


def _normalize_rule(norm, raw_item):
    # range: None (status-only) vs object; both-null-object rejection is the
    # validator's job — the normalizer only shapes.
    raw_range = raw_item.get('range') if isinstance(raw_item, dict) else None
    if raw_range is None:
        norm['range'] = None
    else:
        norm['range'] = _merge_known(
            D.RANGE_DEFAULTS, raw_range if isinstance(raw_range, dict) else {})
    if not isinstance(norm.get('applies_to'), list):
        norm['applies_to'] = []
    if not isinstance(norm.get('match_values'), list):
        norm['match_values'] = []
    return norm


def normalize_metric_list(raw):
    raw = raw if isinstance(raw, dict) else {}
    cfg = _merge_known(D.METRIC_LIST_DEFAULTS, raw)
    cfg['status_rules'] = _normalize_list(
        raw.get('status_rules'), D.STATUS_RULE_DEFAULTS, _normalize_rule)
    cfg['metric_settings'] = _normalize_list(
        raw.get('metric_settings'), D.METRIC_SETTING_DEFAULTS)
    if not isinstance(cfg['icon'].get('allowed_keys'), list):
        cfg['icon']['allowed_keys'] = []
    return cfg
