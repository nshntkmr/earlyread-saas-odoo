# -*- coding: utf-8 -*-
"""Offline contract tests for attribute_grid / metric_list (plan v5, group 1).

Pure — no DB, no Odoo registry. Runs standalone
(``python dashboard_builder/tests/test_widget_contracts.py``) and under the
Odoo test runner alike: services are loaded by file path into a synthetic
package so neither run needs ``odoo`` importable.
"""

import importlib.util
import pathlib
import sys
import types
import unittest
from decimal import Decimal

_SERVICES = pathlib.Path(__file__).resolve().parents[1] / 'services'
_PKG = '_wc_services'


def _load(name):
    full = '%s.%s' % (_PKG, name)
    if full in sys.modules:
        return sys.modules[full]
    if _PKG not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(_SERVICES)]
        sys.modules[_PKG] = pkg
    spec = importlib.util.spec_from_file_location(
        full, _SERVICES / ('%s.py' % name))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


D = _load('widget_config_defaults')
norm = _load('widget_config_normalizer')
val = _load('widget_config_validators')
links = _load('widget_link_safety')
vfmt = _load('widget_value_format')
agf = _load('attribute_grid_formatter')
mlf = _load('metric_list_formatter')

ICONS = {
    'clock': {'fa_class': 'fa-clock-o', 'label': 'Clock'},
    'user-md': {'fa_class': 'fa-user-md', 'label': 'Provider'},
    'archived-icon': {'fa_class': 'fa-archive', 'label': 'Archived'},
    'info-circle': {'fa_class': 'fa-info-circle', 'label': 'Info'},
}


def ml_cfg(**over):
    cfg = {'version': 1,
           'mapping': {'label_column': 'METRIC', 'value_column': 'VALUE'}}
    for k, v in over.items():
        if k == 'mapping':
            cfg['mapping'].update(v)
        else:
            cfg[k] = v
    return cfg


def ag_single(**over):
    cfg = {'version': 1, 'data_shape': 'single_record',
           'fields': [{'key': 'f1', 'label': 'One', 'value_column': 'A'}]}
    cfg.update(over)
    return cfg


def ag_rows(**over):
    cfg = {'version': 1, 'data_shape': 'attribute_rows',
           'row_mapping': {'label_column': 'LABEL', 'value_column': 'VALUE'}}
    for k, v in over.items():
        if k == 'row_mapping':
            cfg['row_mapping'].update(v)
        else:
            cfg[k] = v
    return cfg


# ═══════════════════════════════════════════════════════════════════════════════
class TestNormalizer(unittest.TestCase):

    def test_empty_configs_yield_canonical_defaults(self):
        ag = norm.normalize_attribute_grid({})
        self.assertEqual(ag['data_shape'], 'single_record')
        self.assertEqual(ag['fields'], [])
        self.assertEqual(ag['columns'], 2)
        self.assertIn('info', ag['styles'])
        ml = norm.normalize_metric_list({})
        self.assertEqual(ml['status_rules'], [])
        self.assertEqual(ml['default_direction'], 'neutral')
        self.assertEqual(ml['legend']['mode'], 'auto')
        self.assertNotIn('show', ml['legend'])

    def test_unknown_keys_dropped_and_custom_styles_additive(self):
        ag = norm.normalize_attribute_grid({
            'bogus': 1,
            'styles': {'brand': {'foreground': '#123456',
                                 'background': '#654321'}},
        })
        self.assertNotIn('bogus', ag)
        self.assertIn('brand', ag['styles'])
        self.assertIn('success', ag['styles'])  # seeded keys survive

    def test_rule_range_null_vs_object(self):
        ml = norm.normalize_metric_list({'status_rules': [
            {'key': 'a', 'match_values': ['x']},
            {'key': 'b', 'range': {'max': 0.4}},
        ]})
        self.assertIsNone(ml['status_rules'][0]['range'])
        rng = ml['status_rules'][1]['range']
        self.assertEqual(rng['max'], 0.4)
        self.assertTrue(rng['min_inclusive'])
        self.assertFalse(rng['max_inclusive'])


# ═══════════════════════════════════════════════════════════════════════════════
class TestMetricListValidator(unittest.TestCase):

    def assertValid(self, cfg):
        self.assertEqual(val.validate_metric_list_config(cfg), [])

    def assertInvalid(self, cfg, fragment):
        errors = val.validate_metric_list_config(cfg)
        self.assertTrue(any(fragment in e for e in errors),
                        'expected %r in %r' % (fragment, errors))

    def test_minimal_valid(self):
        self.assertValid(ml_cfg())

    def test_version_and_required_mappings(self):
        self.assertInvalid({'mapping': {'label_column': 'a',
                                        'value_column': 'b'}}, 'version')
        self.assertInvalid({'version': 1, 'mapping': {'value_column': 'b'}},
                           'label_column')

    def test_scale_columns_both_or_neither(self):
        self.assertInvalid(ml_cfg(mapping={'scale_min_column': 'MIN'}),
                           'BOTH scale_min_column')
        self.assertValid(ml_cfg(mapping={'scale_min_column': 'MIN',
                                         'scale_max_column': 'MAX'}))

    def test_icon_column_requires_allowed_keys(self):
        self.assertInvalid(ml_cfg(mapping={'icon_column': 'IC'}),
                           'allowed_keys')
        self.assertValid(ml_cfg(mapping={'icon_column': 'IC'},
                                icon={'allowed_keys': ['clock'],
                                      'fallback_key': ''}))

    def test_scale_sanity_and_nonfinite(self):
        self.assertInvalid(ml_cfg(scale={'min': 1, 'max': 1}), 'scale.min')
        self.assertInvalid(ml_cfg(scale={'min': float('inf'), 'max': 1}),
                           'finite')
        self.assertInvalid(ml_cfg(scale={'min': True, 'max': 1}), 'finite')

    def test_range_rules(self):
        both_null = ml_cfg(status_rules=[{'key': 'r', 'range': {}}])
        self.assertInvalid(both_null, 'both bounds null')
        status_only = ml_cfg(status_rules=[
            {'key': 'r', 'match_values': ['low'], 'range': None}])
        self.assertValid(status_only)
        point = ml_cfg(status_rules=[
            {'key': 'r', 'range': {'min': 1, 'max': 1,
                                   'min_inclusive': True,
                                   'max_inclusive': False}}])
        self.assertInvalid(point, 'single-point')
        empty_rule = ml_cfg(status_rules=[{'key': 'r'}])
        self.assertInvalid(empty_rule, 'at least one match_value')

    def test_half_open_bands_tile_without_overlap(self):
        cfg = ml_cfg(status_rules=[
            {'key': 'lo', 'range': {'min': 0, 'max': 0.4}},
            {'key': 'mid', 'range': {'min': 0.4, 'max': 0.6}},
        ])
        self.assertValid(cfg)

    def test_touching_inclusive_bounds_overlap(self):
        cfg = ml_cfg(status_rules=[
            {'key': 'lo', 'range': {'min': 0, 'max': 0.4,
                                    'max_inclusive': True}},
            {'key': 'mid', 'range': {'min': 0.4, 'max': 0.6}},
        ])
        self.assertInvalid(cfg, 'overlapping')

    def test_intersecting_scopes_checked_per_key(self):
        cfg = ml_cfg(
            mapping={'key_column': 'K'},
            status_rules=[
                {'key': 'a', 'applies_to': ['sepsis', 'high_cost'],
                 'range': {'min': 0, 'max': 1}},
                {'key': 'b', 'applies_to': ['sepsis'],
                 'range': {'min': 0.5, 'max': 2}},
            ])
        self.assertInvalid(cfg, "'sepsis'")
        ok = ml_cfg(
            mapping={'key_column': 'K'},
            status_rules=[
                {'key': 'a', 'applies_to': ['sepsis', 'high_cost'],
                 'range': {'min': 0, 'max': 1}},
                {'key': 'b', 'applies_to': ['sepsis'],
                 'range': {'min': 1, 'max': 2}},
            ])
        self.assertValid(ok)

    def test_scoped_vs_global_overlap_is_legal(self):
        cfg = ml_cfg(
            mapping={'key_column': 'K'},
            status_rules=[
                {'key': 'g', 'range': {'min': 0, 'max': 1}},
                {'key': 's', 'applies_to': ['hc'],
                 'range': {'min': 0, 'max': 1}},
            ])
        self.assertValid(cfg)

    def test_match_values_scope_aware(self):
        within = ml_cfg(status_rules=[
            {'key': 'a', 'match_values': ['Low']},
            {'key': 'b', 'match_values': ['low']},
        ])
        self.assertInvalid(within, 'claimed by rules')
        across = ml_cfg(
            mapping={'key_column': 'K'},
            status_rules=[
                {'key': 'a', 'applies_to': ['sepsis'], 'match_values': ['low']},
                {'key': 'b', 'applies_to': ['cost'], 'match_values': ['low']},
            ])
        self.assertValid(across)

    def test_key_column_required_for_scoped_and_settings(self):
        self.assertInvalid(
            ml_cfg(status_rules=[{'key': 'a', 'applies_to': ['x'],
                                  'match_values': ['low']}]),
            'key_column')
        self.assertInvalid(
            ml_cfg(metric_settings=[{'metric_key': 'x',
                                     'direction': 'neutral'}]),
            'key_column')

    def test_metric_settings_validation(self):
        dup = ml_cfg(mapping={'key_column': 'K'}, metric_settings=[
            {'metric_key': 'x', 'direction': 'neutral'},
            {'metric_key': 'x', 'direction': 'manual'},
        ])
        self.assertInvalid(dup, 'duplicate metric_key')
        bad = ml_cfg(mapping={'key_column': 'K'}, metric_settings=[
            {'metric_key': 'x', 'direction': 'up'}])
        self.assertInvalid(bad, 'direction')

    def test_bounds_and_enums(self):
        self.assertInvalid(ml_cfg(max_items=0), 'max_items')
        self.assertInvalid(ml_cfg(progress={'show': True, 'height': 1,
                                            'track_color': '#eee'}),
                           'progress.height')
        self.assertInvalid(ml_cfg(legend={'mode': 'fancy'}), 'legend.mode')
        self.assertInvalid(ml_cfg(default_direction='sideways'),
                           'default_direction')


# ═══════════════════════════════════════════════════════════════════════════════
class TestAttributeGridValidator(unittest.TestCase):

    def assertValid(self, cfg):
        self.assertEqual(val.validate_attribute_grid_config(cfg), [])

    def assertInvalid(self, cfg, fragment):
        errors = val.validate_attribute_grid_config(cfg)
        self.assertTrue(any(fragment in e for e in errors),
                        'expected %r in %r' % (fragment, errors))

    def test_minimal_shapes(self):
        self.assertValid(ag_single())
        self.assertValid(ag_rows())

    def test_single_record_requires_fields(self):
        self.assertInvalid({'version': 1, 'data_shape': 'single_record'},
                           'configured fields')

    def test_attribute_rows_rejects_fields(self):
        cfg = ag_rows()
        cfg['fields'] = [{'key': 'x', 'label': 'X', 'value_column': 'A'}]
        self.assertInvalid(cfg, 'fields must be empty')

    def test_inactive_shape_not_validated(self):
        # Broken row_mapping alongside single_record must not fail.
        cfg = ag_single()
        cfg['row_mapping'] = {'label_column': ''}
        self.assertValid(cfg)

    def test_field_rules(self):
        dup = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X'},
            {'key': 'a', 'label': 'B', 'value_column': 'Y'},
        ])
        self.assertInvalid(dup, 'duplicate field key')
        bad_key = ag_single(fields=[
            {'key': 'Bad-Key', 'label': 'A', 'value_column': 'X'}])
        self.assertInvalid(bad_key, 'key must match')
        span = ag_single(columns=2, fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X', 'span': 3}])
        self.assertInvalid(span, 'span')

    def test_color_regex_rejects_5_and_7_digit(self):
        cfg = ag_single(styles={'info': {'foreground': '#12345',
                                         'background': '#e7f1fb'}})
        self.assertInvalid(cfg, 'invalid color')
        cfg7 = ag_single(styles={'info': {'foreground': '#1234567',
                                          'background': '#e7f1fb'}})
        self.assertInvalid(cfg7, 'invalid color')
        ok = ag_single(styles={'info': {'foreground': '#1234',
                                        'background': '#e7f1fb88'}})
        self.assertValid(ok)

    def test_icon_modes(self):
        static_no_key = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'icon': {'mode': 'static'}}])
        self.assertInvalid(static_no_key, 'requires key')
        col_no_allow = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'icon': {'mode': 'column', 'column': 'IC'}}])
        self.assertInvalid(col_no_allow, 'allowed_keys')

    def test_link_templates(self):
        js = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'link': {'type': 'url', 'template': 'javascript:alert(1)'}}])
        self.assertInvalid(js, 'unsafe')
        http_remote = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'link': {'type': 'url', 'template': 'http://evil.example/{X}'}}])
        self.assertInvalid(http_remote, 'unsafe')
        https_ok = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'link': {'type': 'url',
                      'template': 'https://x.example/m?id={X}'}}])
        self.assertValid(https_ok)
        proto_rel = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'link': {'type': 'internal', 'template': '//evil.example'}}])
        self.assertInvalid(proto_rel, 'unsafe')

    def test_attribute_rows_icon_requires_allowed(self):
        cfg = ag_rows(row_mapping={'icon_key_column': 'IC'})
        self.assertInvalid(cfg, 'allowed_keys')
        ok = ag_rows(row_mapping={'icon_key_column': 'IC'},
                     row_icon={'allowed_keys': ['clock'], 'fallback_key': ''})
        self.assertValid(ok)

    def test_style_key_references(self):
        cfg = ag_single(default_style_key='nope')
        self.assertInvalid(cfg, 'default_style_key')
        field_ref = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'style_key': 'ghost'}])
        self.assertInvalid(field_ref, 'style_key')

    def test_leading_visual(self):
        cfg = ag_single(leading_visual={'mode': 'icon'})
        self.assertInvalid(cfg, 'requires icon_key')
        cfg2 = ag_single(leading_visual={'mode': 'initials'})
        self.assertInvalid(cfg2, 'requires source_column')


# ═══════════════════════════════════════════════════════════════════════════════
class TestLinkSafety(unittest.TestCase):

    def test_scheme_rules(self):
        self.assertIsNotNone(links.build_link(
            'url', 'https://x.example/a', {}))
        self.assertIsNotNone(links.build_link(
            'url', 'http://localhost:8069/a', {}))
        self.assertIsNotNone(links.build_link(
            'url', 'http://posterra.localhost:8069/a', {}))
        self.assertIsNone(links.build_link('url', 'http://evil.example/a', {}))
        self.assertIsNone(links.build_link('url', 'javascript:alert(1)', {}))

    def test_post_substitution_scheme_rejected(self):
        self.assertIsNone(links.build_link(
            'internal', '{v}', {'v': 'javascript:alert(1)'}))

    def test_missing_placeholder_disables(self):
        self.assertIsNone(links.build_link(
            'url', 'https://x.example/{missing}', {'other': 1}))
        self.assertIsNone(links.build_link(
            'url', 'https://x.example/{v}', {'v': None}))

    def test_query_encoding(self):
        link = links.build_link(
            'url', 'https://x.example/p?q={v}', {'v': 'a b&c'})
        self.assertEqual(link['href'], 'https://x.example/p?q=a%20b%26c')

    def test_tel_and_mailto(self):
        tel = links.build_link('tel', '{p}', {'p': '(602) 555-0148'})
        self.assertEqual(tel['href'], 'tel:6025550148')
        self.assertIsNone(links.build_link('tel', '{p}', {'p': 'CALL-ME-x'}))
        mail = links.build_link('mailto', '{m}', {'m': 'a@b.example'})
        self.assertEqual(mail['href'], 'mailto:a@b.example')
        self.assertIsNone(links.build_link('mailto', '{m}', {'m': 'a b@c.d'}))

    def test_new_tab_rel(self):
        link = links.build_link('url', 'https://x.example', {}, new_tab=True)
        self.assertEqual(link['rel'], 'noopener noreferrer')

    def test_internal_shapes(self):
        self.assertIsNotNone(links.build_link('internal', '/member?eid={e}',
                                              {'e': 'E123'}))
        self.assertIsNone(links.build_link('internal', '//evil.example', {}))


# ═══════════════════════════════════════════════════════════════════════════════
class TestValueFormat(unittest.TestCase):

    def test_number_semantics_table(self):
        # The three canonical rows from the plan.
        f = vfmt.format_value
        self.assertEqual(
            f(Decimal('0.356'), {'type': 'decimal', 'decimals': 3,
                                 'display_multiplier': 1}), '0.356')
        self.assertEqual(
            f(Decimal('0.356'), {'type': 'percent', 'decimals': 1,
                                 'display_multiplier': 100}), '35.6%')
        self.assertEqual(
            f(Decimal('35.6'), {'type': 'percent', 'decimals': 1,
                                'display_multiplier': 1}), '35.6%')

    def test_bool_is_not_numeric(self):
        self.assertIsNone(vfmt.parse_number(True))
        self.assertIsNone(vfmt.parse_number(False))

    def test_nonfinite_rejected(self):
        self.assertIsNone(vfmt.parse_number(float('nan')))
        self.assertIsNone(vfmt.parse_number(float('inf')))
        self.assertIsNone(vfmt.parse_number('Infinity'))

    def test_thousands(self):
        self.assertEqual(
            vfmt.format_value(1234567, {'type': 'integer'}), '1,234,567')
        self.assertEqual(
            vfmt.format_value('-1234.5', {'type': 'currency', 'decimals': 2,
                                          'prefix': '$'}), '$-1,234.50')

    def test_temporal(self):
        self.assertEqual(vfmt.format_value('2021-01-15T10:30:00',
                                           {'type': 'date'}), '2021-01-15')
        self.assertEqual(vfmt.format_value('2021-01-15 10:30:00',
                                           {'type': 'datetime'}),
                         '2021-01-15 10:30')

    def test_icon_resolution(self):
        r = vfmt.resolve_icon('clock', ICONS)
        self.assertEqual(r['fa_class'], 'fa-clock-o')
        # column mode: disallowed key → fallback
        r2 = vfmt.resolve_icon('clock', ICONS, allowed_keys=['user-md'],
                               fallback_key='info-circle')
        self.assertEqual(r2['key'], 'info-circle')
        # unknown key, no fallback → None
        self.assertIsNone(vfmt.resolve_icon('ghost', ICONS, allowed_keys=[]))
        # archived icons stay renderable — the map simply includes them
        self.assertIsNotNone(vfmt.resolve_icon('archived-icon', ICONS))


# ═══════════════════════════════════════════════════════════════════════════════
class TestMetricListFormatter(unittest.TestCase):

    RISK_CFG = {
        'version': 1,
        'mapping': {'key_column': 'K', 'label_column': 'L',
                    'value_column': 'V', 'detail_column': 'D',
                    'scale_min_column': 'SMIN', 'scale_max_column': 'SMAX'},
        'value_format': {'type': 'decimal', 'decimals': 3,
                         'display_multiplier': 1},
        'detail_label': 'Drivers',
        'status_rules': [
            {'key': 'sepsis_amber', 'applies_to': ['sepsis'],
             'label': 'Moderate', 'color': '#d97706', 'background': '#fef3c7',
             'range': {'min': None, 'max': 0.5, 'max_inclusive': False}},
            {'key': 'hc_red', 'applies_to': ['high_cost'],
             'label': 'Elevated', 'color': '#dc2626', 'background': '#fee2e2',
             'range': {'min': 5, 'min_inclusive': False, 'max': None}},
        ],
    }
    COLS = ['K', 'L', 'V', 'D', 'SMIN', 'SMAX']

    def _row(self, key, value, smin=0, smax=1, label='Metric', detail=None):
        return [key, label, value, detail, smin, smax]

    def test_empty(self):
        out = mlf.format_metric_list(self.COLS, [], self.RISK_CFG)
        self.assertTrue(out['empty'])

    def test_sepsis_boundary_exactly_half_open(self):
        rows = [self._row('sepsis', 0.49), self._row('sepsis', 0.5),
                self._row('sepsis', 0.51)]
        out = mlf.format_metric_list(self.COLS, rows, self.RISK_CFG)
        st = [i['status'] for i in out['items']]
        self.assertEqual(st[0]['key'], 'sepsis_amber')   # 0.49 < 0.5
        self.assertIsNone(st[1])                          # 0.5 excluded
        self.assertIsNone(st[2])                          # only one band configured

    def test_high_cost_gt5_on_row_scale(self):
        rows = [self._row('high_cost', 5.0, 0, 10),
                self._row('high_cost', 5.01, 0, 10)]
        out = mlf.format_metric_list(self.COLS, rows, self.RISK_CFG)
        self.assertIsNone(out['items'][0]['status'])          # 5.0 NOT red
        self.assertEqual(out['items'][1]['status']['key'], 'hc_red')
        self.assertAlmostEqual(out['items'][1]['progress_fraction'], 0.501)

    def test_status_column_precedence_and_fallthrough(self):
        cfg = dict(self.RISK_CFG)
        cfg = {**cfg, 'mapping': {**cfg['mapping'], 'status_column': 'S'},
               'status_rules': cfg['status_rules'] + [
                   {'key': 'named', 'match_values': ['special'],
                    'label': 'Special', 'color': '#16a34a',
                    'background': '#dcfce7', 'range': None}]}
        cols = self.COLS + ['S']
        recognized = [['sepsis', 'M', 0.9, None, 0, 1, 'special']]
        out = mlf.format_metric_list(cols, recognized, cfg)
        self.assertEqual(out['items'][0]['status']['key'], 'named')
        unrecognized = [['sepsis', 'M', 0.4, None, 0, 1, 'garbage']]
        out2 = mlf.format_metric_list(cols, unrecognized, cfg)
        # unknown status string falls THROUGH to numeric → amber band
        self.assertEqual(out2['items'][0]['status']['key'], 'sepsis_amber')

    def test_clamp_false_out_of_range(self):
        cfg = {**ml_cfg(mapping={'key_column': 'K'}),
               'scale': {'min': 0, 'max': 1, 'clamp': False}}
        cols = ['K', 'METRIC', 'VALUE']
        out = mlf.format_metric_list(cols, [['m', 'M', 1.5]], cfg)
        item = out['items'][0]
        self.assertIsNone(item['progress_fraction'])
        self.assertTrue(item['out_of_range'])

    def test_invalid_row_scale_no_bar(self):
        rows = [self._row('sepsis', 0.3, 5, 5)]   # min == max → invalid
        out = mlf.format_metric_list(self.COLS, rows, self.RISK_CFG)
        self.assertIsNone(out['items'][0]['progress_fraction'])

    def test_null_and_bool_values(self):
        rows = [self._row('sepsis', None), self._row('sepsis', True)]
        out = mlf.format_metric_list(self.COLS, rows, self.RISK_CFG)
        for item in out['items']:
            self.assertIsNone(item['raw_value'])
            self.assertEqual(item['formatted_value'], mlf.EMPTY_MARKER)
            self.assertIsNone(item['progress_fraction'])

    def test_key_fallback_and_order_and_max_items(self):
        cfg = {**ml_cfg(), 'max_items': 2}
        cols = ['METRIC', 'VALUE']
        rows = [['a', 0.1], ['b', 0.2], ['c', 0.3]]
        out = mlf.format_metric_list(cols, rows, cfg)
        self.assertEqual([i['key'] for i in out['items']], ['row-0', 'row-1'])
        self.assertEqual([i['label'] for i in out['items']], ['a', 'b'])

    def test_direction_priority(self):
        cfg = ml_cfg(mapping={'key_column': 'K', 'direction_column': 'DIR'},
                     default_direction='neutral',
                     metric_settings=[{'metric_key': 'a',
                                       'direction': 'lower_is_better'}])
        cols = ['K', 'METRIC', 'VALUE', 'DIR']
        rows = [
            ['a', 'A', 0.1, 'higher_is_better'],   # setting wins over SQL
            ['b', 'B', 0.2, 'higher_is_better'],   # SQL wins over default
            ['c', 'C', 0.3, 'bogus'],              # invalid SQL → default
        ]
        out = mlf.format_metric_list(cols, rows, cfg)
        self.assertEqual([i['direction'] for i in out['items']],
                         ['lower_is_better', 'higher_is_better', 'neutral'])

    def test_mixed_per_row_formatting_thresholds_on_raw(self):
        cfg = ml_cfg(
            mapping={'key_column': 'K', 'format_type_column': 'FT',
                     'decimals_column': 'DEC',
                     'display_multiplier_column': 'MULT',
                     'scale_min_column': 'SMIN', 'scale_max_column': 'SMAX'},
            status_rules=[{'key': 'hot', 'applies_to': ['pct'],
                           'label': 'Hot', 'color': '#dc2626',
                           'background': '#fee2e2',
                           'range': {'min': 0.3, 'max': None}}])
        cols = ['K', 'METRIC', 'VALUE', 'FT', 'DEC', 'MULT', 'SMIN', 'SMAX']
        rows = [
            ['pct', 'Rate', 0.356, 'percent', 1, 100, 0, 1],
            ['plain', 'Cost', 6.14, 'decimal', 2, 1, 0, 10],
        ]
        out = mlf.format_metric_list(cols, rows, cfg)
        self.assertEqual(out['items'][0]['formatted_value'], '35.6%')
        self.assertEqual(out['items'][1]['formatted_value'], '6.14')
        # threshold matched on RAW 0.356, not display 35.6
        self.assertEqual(out['items'][0]['status']['key'], 'hot')
        self.assertEqual(out['items'][0]['raw_value'], '0.356')

    def test_legend_auto_degrades_with_scoped_rules(self):
        out = mlf.format_metric_list(self.COLS, [self._row('sepsis', 0.2)],
                                     self.RISK_CFG)
        self.assertEqual(out['legend']['mode'], 'semantic')
        global_cfg = ml_cfg(status_rules=[
            {'key': 'lo', 'label': 'Low', 'color': '#16a34a',
             'background': '#dcfce7', 'range': {'min': None, 'max': 0.4}}])
        out2 = mlf.format_metric_list(['METRIC', 'VALUE'], [['a', 0.1]],
                                      global_cfg)
        self.assertEqual(out2['legend']['mode'], 'numeric')
        self.assertEqual(out2['legend']['entries'][0]['text'], '< 0.400')

    def test_error_payload_shapes(self):
        dup = mlf.format_metric_list(['A', 'A'], [[1, 2]], ml_cfg())
        self.assertEqual(dup['error_code'], 'DUPLICATE_ALIAS')
        missing = mlf.format_metric_list(['X'], [[1]], ml_cfg())
        self.assertEqual(missing['error_code'], 'MISSING_COLUMN')
        self.assertNotIn('METRIC', missing.get('error', '') and '')


# ═══════════════════════════════════════════════════════════════════════════════
class TestAttributeGridFormatter(unittest.TestCase):

    def test_single_record_cardinality(self):
        cfg = ag_single()
        self.assertTrue(agf.format_attribute_grid(['A'], [], cfg)['empty'])
        two = agf.format_attribute_grid(['A'], [[1], [2]], cfg)
        self.assertEqual(two['error_code'], 'MULTIPLE_ROWS')
        dup = agf.format_attribute_grid(['A', 'A'], [[1, 2]], cfg)
        self.assertEqual(dup['error_code'], 'DUPLICATE_ALIAS')
        missing = agf.format_attribute_grid(['B'], [[1]], cfg)
        self.assertEqual(missing['error_code'], 'MISSING_COLUMN')

    def test_falsy_values_preserved(self):
        cfg = ag_single(fields=[
            {'key': 'zero', 'label': 'Z', 'value_column': 'Z'},
            {'key': 'flag', 'label': 'F', 'value_column': 'F'},
            {'key': 'blank', 'label': 'B', 'value_column': 'B'},
            {'key': 'null', 'label': 'N', 'value_column': 'N',
             'format': {'type': 'text', 'null_text': 'n/a'}},
        ])
        out = agf.format_attribute_grid(['Z', 'F', 'B', 'N'],
                                        [[0, False, '', None]], cfg)
        vals = {i['key']: i for i in out['items']}
        self.assertEqual(vals['zero']['value'], '0')
        self.assertEqual(vals['flag']['value'], 'False')
        self.assertEqual(vals['blank']['value'], '')
        self.assertEqual(vals['null']['value'], 'n/a')
        self.assertTrue(vals['null']['is_null'])
        self.assertFalse(vals['zero']['is_null'])

    def test_static_icon_and_style(self):
        cfg = ag_single(fields=[
            {'key': 'a', 'label': 'A', 'value_column': 'X',
             'icon': {'mode': 'static', 'key': 'clock'},
             'style_key': 'success'}])
        out = agf.format_attribute_grid(['X'], [['v']], cfg, icon_map=ICONS)
        item = out['items'][0]
        self.assertEqual(item['icon']['fa_class'], 'fa-clock-o')
        self.assertEqual(item['style']['foreground'], '#059669')

    def test_unknown_style_token_falls_back(self):
        cfg = ag_rows(default_style_key='info',
                      row_mapping={'style_key_column': 'STYLE'})
        cols = ['LABEL', 'VALUE', 'STYLE']
        out = agf.format_attribute_grid(cols, [['A', 'v', 'ghost']], cfg)
        self.assertEqual(out['items'][0]['style']['key'], 'info')

    def test_attribute_rows_basics(self):
        cfg = ag_rows(row_mapping={
            'item_key_column': 'K', 'icon_key_column': 'IC',
            'is_visible_column': 'VIS', 'row_order_column': 'ORD',
            'column_start_column': 'CS', 'column_span_column': 'SPAN',
            'layout_column': 'LAY', 'divider_before_column': 'DIV'},
            row_icon={'allowed_keys': ['clock'], 'fallback_key': ''},
            columns=2)
        cols = ['K', 'LABEL', 'VALUE', 'IC', 'VIS', 'ORD', 'CS', 'SPAN',
                'LAY', 'DIV']
        rows = [
            ['t', 'Timeline', 'Jan 2021', 'clock', 1, 1, 1, 1, 'stacked', 0],
            ['h', 'Hidden', 'x', None, 0, 2, None, None, None, 0],
            ['addr', 'Address', '4827 E Rd', 'ghost', 1, 3, 99, 7,
             'weird', 'yes'],
        ]
        out = agf.format_attribute_grid(cols, rows, cfg, icon_map=ICONS)
        keys = [i['key'] for i in out['items']]
        self.assertEqual(keys, ['t', 'addr'])            # hidden row dropped
        addr = out['items'][1]
        self.assertIsNone(addr['icon'])                  # ghost not allowed
        self.assertIsNone(addr['placement']['column_start'])  # 99 invalid
        self.assertEqual(addr['placement']['column_span'], 1)  # 7 > columns → default
        self.assertEqual(addr['layout'], 'stacked')      # 'weird' → default
        self.assertTrue(addr['divider_before'])          # 'yes' truthy

    def test_attribute_rows_link_gating(self):
        cfg = ag_rows(row_mapping={
            'link_value_column': 'LV', 'link_type_column': 'LT'},
            row_link={'type': 'none', 'template': '{link_value}',
                      'new_tab': False})
        cols = ['LABEL', 'VALUE', 'LV', 'LT']
        rows = [
            ['Phone', '(602) 555-0148', '(602) 555-0148', 'tel'],
            ['Plain', 'text', None, 'tel'],           # null link_value → no link
            ['Evil', 'x', 'javascript:alert(1)', 'internal'],
        ]
        out = agf.format_attribute_grid(cols, rows, cfg)
        self.assertEqual(out['items'][0]['link']['href'], 'tel:6025550148')
        self.assertIsNone(out['items'][1]['link'])
        self.assertIsNone(out['items'][2]['link'])

    def test_leading_visual_initials(self):
        cfg = ag_single(
            leading_visual={'mode': 'initials', 'source_column': 'NAME'},
            fields=[{'key': 'n', 'label': 'N', 'value_column': 'NAME'}])
        out = agf.format_attribute_grid(
            ['NAME'], [['Marcus Halloran']], cfg)
        self.assertEqual(out['leading_visual']['text'], 'MH')

    def test_row_cap(self):
        cfg = ag_rows()
        cols = ['LABEL', 'VALUE']
        rows = [['L%d' % i, i] for i in range(D.ATTRIBUTE_ROWS_CAP + 50)]
        out = agf.format_attribute_grid(cols, rows, cfg)
        self.assertEqual(len(out['items']), D.ATTRIBUTE_ROWS_CAP)


if __name__ == '__main__':
    unittest.main(verbosity=2)
