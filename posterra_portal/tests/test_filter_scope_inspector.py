# -*- coding: utf-8 -*-
"""Offline tests for the pure parts of utils/filter_scope_inspector.py.

Runs standalone (``python posterra_portal/tests/test_filter_scope_inspector.py``)
and under the Odoo runner. Placeholder extraction + SQL-surface iteration are
pure; the ORM-touching helpers are covered by test_tab_scoped_filters.py.
"""

import importlib.util
import pathlib
import sys
import types
import unittest

_UTILS = pathlib.Path(__file__).resolve().parents[1] / 'utils'
_PKG = '_tsf_utils'


def _load(name):
    full = '%s.%s' % (_PKG, name)
    if full in sys.modules:
        return sys.modules[full]
    if _PKG not in sys.modules:
        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(_UTILS)]
        sys.modules[_PKG] = pkg
    spec = importlib.util.spec_from_file_location(full, _UTILS / ('%s.py' % name))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = _PKG
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


insp = _load('filter_scope_inspector')


class _Rec:
    """Duck-typed consumer record for iter_sql_surfaces."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestPlaceholders(unittest.TestCase):

    def test_extract_ordered_unique(self):
        sql = ("SELECT * FROM t WHERE a = %(year)s AND b = %(month)s "
               "AND a2 = %(year)s [[ AND c = %(hha_ccn)s ]]")
        self.assertEqual(insp.extract_placeholders(sql),
                         ['year', 'month', 'hha_ccn'])

    def test_system_and_map_keys_recognized(self):
        self.assertIn('selected_hha_ccn', insp.SYSTEM_KEYS)
        self.assertTrue(insp._MAP_KEY_RE.match('_map_level'))
        self.assertTrue(insp._MAP_KEY_RE.match('_drill_state_code'))
        self.assertFalse(insp._MAP_KEY_RE.match('encounter_year'))


class TestSqlSurfaces(unittest.TestCase):

    def test_top_level_surfaces(self):
        rec = _Rec(query_sql='SELECT %(a)s', download_sql='SELECT %(b)s',
                   annotation_query_sql='', ranked_detail_sql='SELECT %(c)s')
        surfaces = dict(insp.iter_sql_surfaces(rec))
        self.assertEqual(set(surfaces), {'query_sql', 'download_sql',
                                         'ranked_detail_sql'})

    def test_nested_detail_drawer_sections(self):
        rec = _Rec(query_sql='', detail_drawer_config="""
            {"enabled": true, "sections": [
                {"id": "s1", "source": "sql", "sql": "SELECT %(row_key)s"},
                {"id": "s2", "source": "master_row"},
                {"id": "s3", "sql": "SELECT %(encounter_year)s"}
            ]}""")
        surfaces = dict(insp.iter_sql_surfaces(rec))
        self.assertIn('detail_drawer_config.sections[s1]', surfaces)
        self.assertIn('detail_drawer_config.sections[s3]', surfaces)
        self.assertNotIn('detail_drawer_config.sections[s2]', surfaces)

    def test_nested_ranked_detail_config(self):
        rec = _Rec(ranked_detail_config="""
            {"detail_sql": "SELECT %(k)s",
             "tiles": [{"sql": "SELECT %(t1)s"}, {"label": "no-sql"}],
             "sub_list": {"sql": "SELECT %(t2)s"}}""")
        surfaces = dict(insp.iter_sql_surfaces(rec))
        self.assertIn('ranked_detail_config.detail_sql', surfaces)
        self.assertIn('ranked_detail_config.tiles[0]', surfaces)
        self.assertIn('ranked_detail_config.sub_list[0]', surfaces)

    def test_invalid_json_is_silently_skipped(self):
        rec = _Rec(ranked_detail_config='{not json', detail_drawer_config='[]')
        self.assertEqual(list(insp.iter_sql_surfaces(rec)), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
