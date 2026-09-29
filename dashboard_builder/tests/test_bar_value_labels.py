# -*- coding: utf-8 -*-
"""Offline contract tests for the shared bar value-label options.

Pure — no DB, no Odoo registry. Runs standalone
(``python dashboard_builder/tests/test_bar_value_labels.py``); the service is
loaded by file path so the run does not need ``odoo`` importable.

Locks two things:
  • OFF (the default) changes nothing: ``series_value`` is exactly the
    historical ``value or 0`` and the flag readers stay off for blank text,
    line charts, labels off and horizontal bars;
  • ON, a SQL NULL prints the configured text on the label AND in the tooltip,
    a real 0 prints 0, and every other point prints what today's chart prints
    (raw label, comma tooltip), while clicks keep the plain number.
"""

import importlib.util
import pathlib
import unittest
from decimal import Decimal

_SERVICES = pathlib.Path(__file__).resolve().parents[1] / 'services'


def _load():
    spec = importlib.util.spec_from_file_location(
        '_bar_value_labels', _SERVICES / 'bar_value_labels.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bvl = _load()
CATS = ['Q1\n2023', 'Q2\n2023', 'Q3\n2023', 'Q4\n2023']


def _series(**named):
    return [{'name': n, 'type': 'bar', 'data': list(d), 'label': {'show': True, 'position': 'top'}}
            for n, d in named.items()]


class TestOffByDefault(unittest.TestCase):

    def test_series_value_matches_historical_or_zero(self):
        for v in (None, 0, 0.0, '', False, 12, 3541.0, Decimal('238.50'), 'x'):
            self.assertEqual(bvl.series_value(v, False), v or 0)

    def test_null_label_off_cases(self):
        self.assertEqual(bvl.null_label_for('bar', {}, True), '')
        self.assertEqual(bvl.null_label_for('bar', {'null_label': ''}, True), '')
        self.assertEqual(bvl.null_label_for('bar', {'null_label': '   '}, True), '')
        self.assertEqual(bvl.null_label_for('bar', {'null_label': 11}, True), '')
        self.assertEqual(bvl.null_label_for('bar', {'null_label': '<11'}, False), '')
        self.assertEqual(bvl.null_label_for('line', {'null_label': '<11'}, True), '')
        self.assertEqual(bvl.null_label_for('bar', None, True), '')

    def test_null_label_on_is_trimmed(self):
        self.assertEqual(bvl.null_label_for('bar', {'null_label': ' <11 '}, True), '<11')

    def test_vertical_off_cases(self):
        self.assertFalse(bvl.vertical_labels_on('bar', {}, 'vertical'))
        self.assertFalse(bvl.vertical_labels_on('bar', {'label_direction': 'horizontal'}, 'vertical'))
        self.assertFalse(bvl.vertical_labels_on('bar', {'label_direction': 'vertical'}, 'horizontal'))
        self.assertFalse(bvl.vertical_labels_on('line', {'label_direction': 'vertical'}, 'vertical'))
        self.assertTrue(bvl.vertical_labels_on('bar', {'label_direction': 'vertical'}, 'vertical'))


class TestVerticalStyle(unittest.TestCase):

    def test_top_label_grows_upward(self):
        self.assertEqual(bvl.vertical_label_style('top'),
                         {'rotate': 90, 'align': 'left', 'verticalAlign': 'middle'})

    def test_inside_label_is_centred(self):
        self.assertEqual(bvl.vertical_label_style('inside'),
                         {'rotate': 90, 'align': 'center', 'verticalAlign': 'middle'})


class TestHiddenValueLabels(unittest.TestCase):

    def _apply(self, series, **kw):
        bvl.apply_null_labels(series, CATS, '<11', **kw)
        return series

    def test_null_zero_and_values(self):
        s = self._apply(_series(FFS=[None, 0, 12, 12422], MCO=[138, 178, 238, 5492]))
        ffs = s[0]['data']
        # [category index, bar value, label text, tooltip text]
        self.assertEqual(ffs[0]['value'], [0, 0, '<11', '<11'])      # suppressed
        self.assertEqual(ffs[1]['value'], [1, 0, '0', '0'])          # real zero
        self.assertEqual(ffs[2]['value'], [2, 12, '12', '12'])
        self.assertEqual(ffs[3]['value'], [3, 12422, '12422', '12,422'])  # raw label, comma tooltip
        self.assertEqual([p['name'] for p in ffs], CATS)
        self.assertEqual([p['clickValue'] for p in ffs], [0, 0, 12, 12422])

    def test_series_wiring(self):
        s = self._apply(_series(FFS=[None, 1, 2, 3]))[0]
        self.assertEqual(s['encode'], {'x': 'pv_cat', 'y': 'pv_val', 'tooltip': 'pv_tip'})
        self.assertEqual([d['name'] for d in s['dimensions']], ['pv_cat', 'pv_val', 'pv_label', 'pv_tip'])
        self.assertEqual(s['label'], {'show': True, 'position': 'top', 'formatter': '{@pv_label}'})

    def test_horizontal_swaps_axes(self):
        s = self._apply(_series(FFS=[None, 1, 2, 3]), horizontal=True)[0]
        self.assertEqual(s['encode'], {'y': 'pv_cat', 'x': 'pv_val', 'tooltip': 'pv_tip'})

    def test_other_label_keys_survive(self):
        series = _series(FFS=[None, 1, 2, 3])
        series[0]['label'].update(bvl.vertical_label_style('top'))
        s = self._apply(series)[0]
        self.assertEqual(s['label']['rotate'], 90)
        self.assertEqual(s['label']['formatter'], '{@pv_label}')

    def test_comma_format(self):
        s = self._apply(_series(FFS=[None, 3745, 3541.5, 12422]), number_format='comma')[0]
        self.assertEqual([p['value'][2] for p in s['data']], ['<11', '3,745', '3,541.50', '12,422'])

    def test_percent_values(self):
        s = self._apply(_series(FFS=[None, 42.9, 50.0, 0]), percent=True)[0]
        self.assertEqual([p['value'][2] for p in s['data']], ['<11', '42.9%', '50%', '0%'])

    def test_share_of_total(self):
        s = self._apply(_series(FFS=[None, 25, 75, 0]), pct_of_total=True)[0]
        self.assertEqual([p['value'][2] for p in s['data']], ['<11', '25 (25.0%)', '75 (75.0%)', '0 (0.0%)'])

    def test_decimal_and_float_print_like_today(self):
        # json.dumps(default=str) sends a Decimal as its string → raw label "238.50";
        # the tooltip parses it to a number → "238.5". A float 3541.0 prints "3541".
        s = self._apply(_series(FFS=[Decimal('238.50'), 3541.0, 1234567.25, -4200]))[0]
        self.assertEqual([p['value'][2] for p in s['data']], ['238.50', '3541', '1234567.25', '-4200'])
        self.assertEqual([p['value'][3] for p in s['data']], ['238.5', '3,541', '1,234,567.25', '-4,200'])


if __name__ == '__main__':
    unittest.main()
