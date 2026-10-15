# -*- coding: utf-8 -*-
"""Filter-value placeholders in chart styling + heatmap empty cells.

  • ``utils.echart_placeholders`` — pure: only the exact ``%(NAME)s`` form is
    a token, unknown names stay as typed, a plain ``%`` is never touched,
    values are JSON-string-safe in the raw override text;
  • ``dashboard.widget._build_echart_option`` — resolves tokens in
    ``echart_override`` AND ``visual_config.series_styles`` from the applied
    filter values, through every caller (dispatch, scope-option path, direct);
    no token / no context → byte-identical option;
  • heatmap ``heatmap_blank_null`` — off: the historical ``or 0``; on: a SQL
    NULL is an undrawn ``null`` cell, visualMap range ignores it, and the
    Designer preview builds the same cells.

Run:
    odoo-bin --test-enable -u posterra_portal \\
             --test-tags posterra_echart_placeholders --stop-after-init -d <test_db>
"""

import json

from odoo.tests import TransactionCase, tagged

from odoo.addons.posterra_portal.utils.echart_placeholders import (
    resolve_echart_placeholders, resolve_placeholders_deep,
)
from odoo.addons.dashboard_builder.services import preview_formatter

BAND = ('{"series_styles": {"*": {"markArea": {"data": [[{"xAxis": '
        '"%(SERVICE_YEAR)s-%(SERVICE_MONTH)s"}, {"xAxis": '
        '"%(SERVICE_YEAR)s-%(SERVICE_MONTH)s"}]]}}}}')


@tagged('posterra_echart_placeholders', 'post_install', '-at_install')
class TestPlaceholderHelpers(TransactionCase):

    def test_raw_text_replaces_known_names_only(self):
        text = '{"xAxis": {"name": "%(SERVICE_MONTH)s"}, "grid": {"left": "98%"}, '\
               '"note": "%(UNKNOWN)s"}'
        out = resolve_echart_placeholders(text, {'SERVICE_MONTH': '03'})
        self.assertEqual(json.loads(out), {'xAxis': {'name': '03'},
                                           'grid': {'left': '98%'},
                                           'note': '%(UNKNOWN)s'})

    def test_raw_text_value_is_json_string_safe(self):
        text = '{"a": "%(V)s"}'
        for value in ('He said "hi"', 'back\\slash', 'line\nbreak', 'tab\tx'):
            out = resolve_echart_placeholders(text, {'V': value})
            self.assertEqual(json.loads(out), {'a': value}, value)

    def test_raw_text_none_and_csv_values(self):
        text = '{"a": "%(A)s", "b": "%(B)s"}'
        out = resolve_echart_placeholders(text, {'A': None, 'B': ['TX', 'CA']})
        self.assertEqual(json.loads(out), {'a': '', 'b': 'TX,CA'})

    def test_raw_text_untouched_without_token_or_values(self):
        plain = '{"grid": {"left": "98%"}, "fmt": "{c}%"}'
        self.assertIs(resolve_echart_placeholders(plain, {'X': '1'}), plain)
        tokened = '{"a": "%(X)s"}'
        self.assertIs(resolve_echart_placeholders(tokened, None), tokened)
        self.assertIs(resolve_echart_placeholders(tokened, {}), tokened)
        self.assertEqual(resolve_echart_placeholders('', {'X': '1'}), '')

    def test_deep_replaces_string_leaves_only(self):
        styles = {'*': {'markArea': {'data': [[{'xAxis': '%(Y)s-%(M)s'},
                                               {'xAxis': '%(Y)s-%(M)s'}]],
                                     'itemStyle': {'opacity': 0.5}},
                        'label': {'formatter': '{c}%', 'width': 98}}}
        out = resolve_placeholders_deep(styles, {'Y': '2026', 'M': '03'})
        self.assertEqual(out['*']['markArea']['data'],
                         [[{'xAxis': '2026-03'}, {'xAxis': '2026-03'}]])
        self.assertEqual(out['*']['markArea']['itemStyle'], {'opacity': 0.5})
        self.assertEqual(out['*']['label'], {'formatter': '{c}%', 'width': 98})
        # the input is never mutated
        self.assertEqual(styles['*']['markArea']['data'][0][0]['xAxis'], '%(Y)s-%(M)s')

    def test_deep_same_object_without_token_or_values(self):
        styles = {'*': {'label': {'formatter': '{c}%'}}}
        self.assertIs(resolve_placeholders_deep(styles, {'Y': '1'}), styles)
        tokened = {'*': {'markArea': {'data': [[{'xAxis': '%(Y)s'}]]}}}
        self.assertIs(resolve_placeholders_deep(tokened, None), tokened)
        # unknown names stay as typed
        self.assertEqual(resolve_placeholders_deep(tokened, {'Z': '1'}), tokened)


@tagged('posterra_echart_placeholders', 'post_install', '-at_install')
class TestWidgetOption(TransactionCase):
    """``_build_echart_option`` is read-only, so in-memory ``.new()`` records
    are enough and keep the tests fast."""

    COLS = ['MONTH', 'ENCOUNTERS']
    ROWS = [['2026-01', 3], ['2026-02', 5], ['2026-03', 2]]

    def _bar(self, **vals):
        base = {'chart_type': 'bar', 'name': 'B', 'query_type': 'sql',
                'x_column': 'MONTH', 'y_columns': 'ENCOUNTERS'}
        base.update(vals)
        return self.env['dashboard.widget'].new(base)

    def test_override_resolves_from_filter_values(self):
        w = self._bar(echart_override='{"xAxis": {"name": "%(SERVICE_MONTH)s"}}')
        opt = w._build_echart_option(self.COLS, self.ROWS,
                                     filter_values={'SERVICE_MONTH': '03'})
        self.assertEqual(opt['xAxis']['name'], '03')
        # no context → as typed (Designer preview, legacy callers)
        opt = w._build_echart_option(self.COLS, self.ROWS)
        self.assertEqual(opt['xAxis']['name'], '%(SERVICE_MONTH)s')

    def test_series_styles_band_resolves_and_keeps_data(self):
        w = self._bar(visual_config=BAND)
        opt = w._build_echart_option(
            self.COLS, self.ROWS,
            filter_values={'SERVICE_YEAR': '2026', 'SERVICE_MONTH': '02'})
        series = opt['series'][0]
        self.assertEqual(series['markArea']['data'],
                         [[{'xAxis': '2026-02'}, {'xAxis': '2026-02'}]])
        self.assertEqual(series['data'], [3, 5, 2])      # SQL data untouched
        # blank month → the band names a category that does not exist and
        # simply does not draw; the option still builds
        opt = w._build_echart_option(
            self.COLS, self.ROWS,
            filter_values={'SERVICE_YEAR': '2026', 'SERVICE_MONTH': ''})
        self.assertEqual(opt['series'][0]['markArea']['data'][0][0]['xAxis'], '2026-')

    def test_byte_identical_without_tokens(self):
        w = self._bar(visual_config='{"series_styles": {"*": {"label": {"formatter": "{c}%"}}}}',
                      echart_override='{"grid": {"left": "98%"}, "tooltip": {"show": false}}')
        with_ctx = w._build_echart_option(
            self.COLS, self.ROWS, filter_values={'SERVICE_MONTH': '03', 'X': 'y'})
        without = w._build_echart_option(self.COLS, self.ROWS)
        self.assertEqual(json.dumps(with_ctx, default=str, sort_keys=True),
                         json.dumps(without, default=str, sort_keys=True))
        self.assertEqual(with_ctx['grid']['left'], '98%')
        self.assertEqual(with_ctx['series'][0]['label']['formatter'], '{c}%')

    def test_dispatch_and_scope_paths_pass_the_context(self):
        w = self._bar(echart_override='{"xAxis": {"name": "%(SERVICE_MONTH)s"}}')
        ctx = {'sql_params': {'SERVICE_MONTH': '04'},
               'filter_values_by_name': {'SERVICE_MONTH': '04'}}
        out = w._dispatch_chart_builder(self.COLS, self.ROWS, ctx)
        self.assertEqual(json.loads(out['echart_json'])['xAxis']['name'], '04')
        out = w._format_scope_result(self.COLS, self.ROWS, ctx)
        self.assertEqual(json.loads(out['echart_json'])['xAxis']['name'], '04')
        # the scope path without a context (its historical signature) still works
        out = w._format_scope_result(self.COLS, self.ROWS)
        self.assertEqual(json.loads(out['echart_json'])['xAxis']['name'],
                         '%(SERVICE_MONTH)s')


@tagged('posterra_echart_placeholders', 'post_install', '-at_install')
class TestHeatmapBlankCells(TransactionCase):

    COLS = ['MONTH', 'CLAIM_TYPE', 'ENCOUNTERS']
    ROWS = [['2026-01', 'Office visit', 3], ['2026-02', 'Office visit', None],
            ['2026-01', 'Emergency room', None], ['2026-02', 'Emergency room', 1]]
    CONFIG = {'x_column': 'MONTH', 'y_columns': 'CLAIM_TYPE, ENCOUNTERS'}

    def _heat(self, **vals):
        base = {'chart_type': 'heatmap', 'name': 'H', 'query_type': 'sql',
                'x_column': 'MONTH', 'y_columns': 'CLAIM_TYPE, ENCOUNTERS'}
        base.update(vals)
        return self.env['dashboard.widget'].new(base)

    def _cells(self, option):
        return sorted(option['series'][0]['data'], key=lambda d: (d[0], d[1]))

    def test_off_is_the_historical_zero(self):
        for vc in (False, '{}', '{"heatmap_blank_null": false}', '{not json'):
            opt = self._heat(visual_config=vc)._build_echart_option(self.COLS, self.ROWS)
            self.assertEqual(self._cells(opt), [[0, 0, 0], [0, 1, 3], [1, 0, 1], [1, 1, 0]], vc)
            self.assertEqual((opt['visualMap']['min'], opt['visualMap']['max']), (0, 3), vc)

    def test_on_leaves_null_cells_empty(self):
        opt = self._heat(visual_config='{"heatmap_blank_null": true}')\
            ._build_echart_option(self.COLS, self.ROWS)
        self.assertEqual(self._cells(opt),
                         [[0, 0, None], [0, 1, 3], [1, 0, 1], [1, 1, None]])
        self.assertEqual((opt['visualMap']['min'], opt['visualMap']['max']), (1, 3))
        # JSON null travels to ECharts (an undrawn cell), never 0
        self.assertIn('null', json.dumps(opt['series'][0]['data']))

    def test_designer_preview_builds_the_same_cells(self):
        for flag in (False, True):
            vc = {'heatmap_blank_null': flag}
            portal = self._heat(visual_config=json.dumps(vc))\
                ._build_echart_option(self.COLS, self.ROWS)
            preview = preview_formatter.format_preview(
                'heatmap', self.COLS, self.ROWS, config=self.CONFIG,
                visual_config=vc)['echart_option']
            self.assertEqual(self._cells(preview), self._cells(portal), flag)
            self.assertEqual(preview['visualMap']['min'], portal['visualMap']['min'])
            self.assertEqual(preview['visualMap']['max'], portal['visualMap']['max'])


@tagged('posterra_echart_placeholders', 'post_install', '-at_install')
class TestHeatmapLabelColumn(TransactionCase):
    """"Cell Label Column": the 4th element of every cell is the label text,
    the series prints it and visualMap keeps colouring by the value."""

    COLS = ['MONTH', 'CLAIM_TYPE', 'VALUE', 'LABEL']
    ROWS = [['2026-01', 'Office visit', 3, '3'],
            ['2026-02', 'Office visit', None, ''],      # blank cell
            ['Total', 'Office visit', -1, '7'],         # totals cell: out of range, label prints
            ['2026-01', 'All claim types', -1, '3']]
    CONFIG = {'x_column': 'MONTH', 'y_columns': 'CLAIM_TYPE, VALUE'}

    def _heat(self, vc):
        return self.env['dashboard.widget'].new({
            'chart_type': 'heatmap', 'name': 'H', 'query_type': 'sql',
            'x_column': 'MONTH', 'y_columns': 'CLAIM_TYPE, VALUE',
            'visual_config': json.dumps(vc)})

    def test_label_dimension_formatter_and_value_mapping(self):
        vc = {'heatmap_blank_null': True, 'heatmap_label_column': 'LABEL'}
        opt = self._heat(vc)._build_echart_option(self.COLS, self.ROWS)
        series = opt['series'][0]
        points = sorted(series['data'], key=lambda d: (d[0], d[1]))
        # x sorted: '2026-01' < '2026-02' < 'Total'; y sorted: 'All claim types' < 'Office visit'
        self.assertEqual(points, [[0, 0, -1, '3'], [0, 1, 3, '3'],
                                  [1, 1, None, ''], [2, 1, -1, '7']])
        self.assertEqual(series['label'], {'show': True, 'formatter': '{@[3]}'})
        self.assertEqual(opt['visualMap']['dimension'], 2)
        # the range still comes from the values (the -1 totals included, so a
        # widget override sets min: 0 to push them out of range)
        self.assertEqual((opt['visualMap']['min'], opt['visualMap']['max']), (-1, 3))

    def test_unset_or_missing_column_is_byte_identical(self):
        base = self._heat({'heatmap_blank_null': True})._build_echart_option(self.COLS, self.ROWS)
        for vc in ({'heatmap_blank_null': True, 'heatmap_label_column': ''},
                   {'heatmap_blank_null': True, 'heatmap_label_column': 'NOT_IN_RESULT'}):
            opt = self._heat(vc)._build_echart_option(self.COLS, self.ROWS)
            self.assertEqual(json.dumps(opt, default=str, sort_keys=True),
                             json.dumps(base, default=str, sort_keys=True), vc)
        self.assertEqual(len(base['series'][0]['data'][0]), 3)
        self.assertNotIn('formatter', base['series'][0]['label'])
        self.assertNotIn('dimension', base['visualMap'])

    def test_designer_preview_parity(self):
        vc = {'heatmap_blank_null': True, 'heatmap_label_column': 'LABEL'}
        portal = self._heat(vc)._build_echart_option(self.COLS, self.ROWS)
        preview = preview_formatter.format_preview(
            'heatmap', self.COLS, self.ROWS, config=self.CONFIG,
            visual_config=vc)['echart_option']
        self.assertEqual(sorted(preview['series'][0]['data']),
                         sorted(portal['series'][0]['data']))
        self.assertEqual(preview['series'][0]['label'], portal['series'][0]['label'])
        self.assertEqual(preview['visualMap']['dimension'], portal['visualMap']['dimension'])
