# -*- coding: utf-8 -*-
"""Generate the golden normalization fixtures (Python side = authoritative).

Run:  python dashboard_builder/schemas/generate_golden_fixtures.py
Then: node posterra_portal/static/src/react/scripts/test_normalizer_parity.mjs

Each fixture = {name, widget, input, canonical}. The JS suite re-normalizes
``input`` with the grid-utils normalizer and asserts STRUCTURAL equality with
``canonical`` — the contract that keeps the two normalizers identical.
Partially-populated inputs are the point: they exercise default-filling.
"""

import importlib.util
import json
import pathlib
import sys
import types

_SERVICES = pathlib.Path(__file__).resolve().parents[1] / 'services'
_PKG = '_gf_services'


def _load(name):
    full = '%s.%s' % (_PKG, name)
    if _PKG not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(_SERVICES)]
        sys.modules[_PKG] = pkg
    spec = importlib.util.spec_from_file_location(full, _SERVICES / ('%s.py' % name))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


norm = _load('widget_config_normalizer')

# ── Non-normative EXAMPLES double as fixture inputs ─────────────────────────
# (The canonical defaults ship empty; the fully-populated shapes live here.)

FIXTURES = [
    # attribute_grid
    ('ag_empty', 'attribute_grid', {}),
    ('ag_version_only', 'attribute_grid', {'version': 1}),
    ('ag_single_record_full_field', 'attribute_grid', {
        'version': 1, 'columns': 3, 'density': 'compact',
        'default_style_key': 'info',
        'styles': {'brand': {'foreground': '#123456', 'background': '#abcdef'}},
        'leading_visual': {'mode': 'initials', 'source_column': 'NAME'},
        'fields': [{
            'key': 'timeline', 'label': 'Timeline', 'value_column': 'TL',
            'icon': {'mode': 'static', 'key': 'clock'},
            'span': 2, 'layout': 'inline', 'emphasis': 'strong',
            'divider_before': True,
            'format': {'type': 'date'},
            'link': {'type': 'internal', 'template': '/member?eid={EID}',
                     'new_tab': True},
            'style_key': 'brand',
        }],
    }),
    ('ag_attribute_rows', 'attribute_grid', {
        'version': 1, 'data_shape': 'attribute_rows', 'columns': 2,
        'row_mapping': {'label_column': 'LABEL', 'value_column': 'VALUE',
                        'icon_key_column': 'IC'},
        'row_icon': {'allowed_keys': ['clock', 'users'],
                     'fallback_key': 'info-circle'},
        'row_default_format': {'null_text': 'n/a'},
        'row_link': {'type': 'tel', 'template': '{link_value}'},
    }),
    ('ag_unknown_keys_dropped', 'attribute_grid', {
        'version': 1, 'bogus': True, 'columns': 8,
        'fields': [{'key': 'a', 'label': 'A', 'value_column': 'X',
                    'mystery': 1}],
    }),
    # metric_list
    ('ml_empty', 'metric_list', {}),
    ('ml_minimal_mapping', 'metric_list', {
        'version': 1,
        'mapping': {'label_column': 'METRIC', 'value_column': 'VALUE'},
    }),
    ('ml_risk_acuity_style', 'metric_list', {
        'version': 1,
        'mapping': {'key_column': 'K', 'label_column': 'L', 'value_column': 'V',
                    'detail_column': 'D', 'scale_min_column': 'SMIN',
                    'scale_max_column': 'SMAX', 'direction_column': 'DIR'},
        'value_format': {'decimals': 3},
        'detail_label': 'Drivers',
        'default_direction': 'neutral',
        'metric_settings': [
            {'metric_key': 'unplanned_admission', 'direction': 'lower_is_better'},
            {'metric_key': 'high_cost', 'direction': 'lower_is_better'},
        ],
        'status_rules': [
            {'key': 'sepsis_amber', 'applies_to': ['sepsis'],
             'match_values': [], 'label': 'Moderate',
             'color': '#d97706', 'background': '#fef3c7',
             'range': {'max': 0.5}},
            {'key': 'hc_red', 'applies_to': ['high_cost'], 'label': 'Elevated',
             'color': '#dc2626', 'background': '#fee2e2',
             'range': {'min': 5, 'min_inclusive': False, 'max': None}},
            {'key': 'named', 'match_values': ['Low', 'low risk'],
             'label': 'Low', 'color': '#16a34a', 'background': '#dcfce7',
             'range': None},
        ],
        'legend': {'mode': 'semantic'},
    }),
    ('ml_per_row_formatting', 'metric_list', {
        'version': 1,
        'mapping': {'label_column': 'M', 'value_column': 'V',
                    'format_type_column': 'FT', 'decimals_column': 'DEC',
                    'display_multiplier_column': 'MULT',
                    'prefix_column': 'PRE', 'suffix_column': 'SUF'},
        'progress': {'height': 8},
        'max_items': 50,
    }),
    ('ml_unknown_keys_dropped', 'metric_list', {
        'version': 1, 'legacy_junk': [1, 2],
        'mapping': {'label_column': 'a', 'value_column': 'b', 'ghost_col': 'x'},
    }),
]


def main():
    out = []
    for name, widget, config in FIXTURES:
        canonical = (norm.normalize_attribute_grid(config)
                     if widget == 'attribute_grid'
                     else norm.normalize_metric_list(config))
        out.append({'name': name, 'widget': widget,
                    'input': config, 'canonical': canonical})
    target = pathlib.Path(__file__).resolve().parent / 'golden_fixtures' / 'normalization.v1.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2, sort_keys=True) + '\n',
                      encoding='utf-8')
    print('Wrote %d fixtures -> %s' % (len(out), target))


if __name__ == '__main__':
    main()
