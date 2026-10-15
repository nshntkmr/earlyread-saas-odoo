# -*- coding: utf-8 -*-
"""Offline contract tests for the shared heatmap empty-cell option.

Pure — no DB, no Odoo registry. Runs standalone
(``python dashboard_builder/tests/test_heatmap_cells.py``); the service is
loaded by file path so the run does not need ``odoo`` importable.

Locks two things:
  • OFF (the default) changes nothing: ``cell_value`` is exactly the
    historical ``value or 0`` and ``value_range`` is the historical
    min/max with the (0, 1) defaults;
  • ON, only a SQL NULL becomes an empty (None) cell — 0, '' and False still
    draw as 0 — and the visualMap range ignores the empty cells.
"""

import importlib.util
import pathlib
import unittest
from decimal import Decimal

_SERVICES = pathlib.Path(__file__).resolve().parents[1] / 'services'


def _load():
    spec = importlib.util.spec_from_file_location(
        '_heatmap_cells', _SERVICES / 'heatmap_cells.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hc = _load()


class TestFlagReader(unittest.TestCase):

    def test_off_unless_set_true(self):
        for vc in ({}, None, 'x', [], {'heatmap_blank_null': False},
                   {'heatmap_blank_null': 0}, {'heatmap_blank_null': ''}):
            self.assertFalse(hc.blank_null_on(vc), vc)

    def test_on(self):
        self.assertTrue(hc.blank_null_on({'heatmap_blank_null': True}))
        self.assertTrue(hc.blank_null_on({'heatmap_blank_null': 1}))
        self.assertEqual(hc.BLANK_NULL_FLAG, 'heatmap_blank_null')


class TestCellValue(unittest.TestCase):

    def test_off_is_the_historical_or_zero(self):
        for raw in (None, 0, '', False, 5, Decimal('2.5'), 'text', -1):
            self.assertEqual(hc.cell_value(raw, False), raw or 0, raw)

    def test_on_blanks_only_null(self):
        self.assertIsNone(hc.cell_value(None, True))
        for raw in (0, '', False):
            self.assertEqual(hc.cell_value(raw, True), 0, raw)
        self.assertEqual(hc.cell_value(5, True), 5)
        self.assertEqual(hc.cell_value(Decimal('2.5'), True), Decimal('2.5'))


class TestValueRange(unittest.TestCase):

    def test_historical_defaults_and_minmax(self):
        self.assertEqual(hc.value_range([]), (0, 1))
        data = [[0, 0, 3], [1, 0, 0], [0, 1, 7]]
        self.assertEqual(hc.value_range(data), (0, 7))
        self.assertEqual(hc.value_range(data),
                         (min(d[2] for d in data), max(d[2] for d in data)))

    def test_empty_cells_are_ignored(self):
        self.assertEqual(hc.value_range([[0, 0, None], [1, 0, 4], [2, 0, 2]]), (2, 4))
        self.assertEqual(hc.value_range([[0, 0, None], [1, 0, None]]), (0, 1))


if __name__ == '__main__':
    unittest.main()
