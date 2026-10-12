# -*- coding: utf-8 -*-
"""Offline contract tests for the shared ``record_header`` formatter.

Pure — no DB, no Odoo registry. Runs standalone
(``python dashboard_builder/tests/test_record_header_formatter.py``) and under
the Odoo test runner alike: the service is loaded by file path so neither run
needs ``odoo`` importable.

Locks two things:
  • the CLASSIC payload (title / avatar / footer fields, fail-closed rules)
    is byte-identical when ``header_layout`` is absent or 'classic';
  • the SCORECARD layout adds subtitle / stats / chips from their own
    columns with the same fail-closed rule for a configured-but-missing
    column, thousands-separator number formatting and CSV/JSON chips.
"""

import importlib.util
import pathlib
import unittest

_SERVICES = pathlib.Path(__file__).resolve().parents[1] / 'services'


def _load():
    spec = importlib.util.spec_from_file_location(
        '_rh_formatter', _SERVICES / 'record_header_formatter.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fmt = _load()
F = fmt.format_record_header

COLS = ['PROVIDER_NAME', 'SUBTITLE', 'MARKET_COUNT', 'PCP_COUNT',
        'MEMBER_COUNT', 'PLAN_COUNT', 'MARKET_LIST', 'RATE', 'PROVIDER_SUMMARY']
ROW = ('Upperline Healthcare PC', 'Provider group', 9, 1106, 2781.0, 8,
       'FL, IL, IN', 65.66, 'Operates in 9 markets')


class TestClassicUnchanged(unittest.TestCase):

    def _classic(self, extra=None):
        cfg = {'x_column': 'PROVIDER_NAME', 'y_columns': 'PROVIDER_SUMMARY',
               'label_overrides': {'PROVIDER_SUMMARY': 'Summary'}}
        cfg.update(extra or {})
        return F(COLS, [ROW], cfg)

    def test_classic_payload_shape(self):
        out = self._classic()
        self.assertEqual(out, {
            'type': 'record_header',
            'title': 'Upperline Healthcare PC',
            'avatar': {'mode': 'initials', 'text': 'UP', 'color': fmt.DEFAULT_AVATAR_COLOR},
            'fields': [{'key': 'PROVIDER_SUMMARY', 'label': 'Summary',
                        'value': 'Operates in 9 markets'}],
        })

    def test_explicit_classic_layout_is_identical(self):
        self.assertEqual(self._classic(), self._classic({'header_layout': 'classic'}))

    def test_scorecard_keys_ignored_in_classic(self):
        out = self._classic({'stats': [{'column': 'NOPE'}], 'chips_column': 'NOPE',
                             'subtitle_column': 'NOPE'})
        self.assertNotIn('error', out)
        self.assertNotIn('stats', out)

    def test_fail_closed_rules(self):
        self.assertEqual(F(COLS, [], {})['empty'], True)
        self.assertIn('error', F(COLS, [ROW, ROW], {}))
        self.assertIn('error', F(COLS, [ROW], {'x_column': 'MISSING'}))
        self.assertIn('error', F(COLS, [ROW], {'y_columns': 'MISSING'}))
        self.assertIn('error', F(['A', 'A'], [(1, 2)], {}))


class TestScorecard(unittest.TestCase):

    CFG = {
        'header_layout': 'scorecard',
        'x_column': 'PROVIDER_NAME',
        'subtitle_column': 'SUBTITLE',
        'stats': [
            {'column': 'MARKET_COUNT', 'label': 'Markets', 'icon': 'fa-map-marker'},
            {'column': 'PCP_COUNT', 'label': 'PCPs', 'format': 'number'},
            {'column': 'MEMBER_COUNT', 'label': 'Members'},
            {'column': 'RATE', 'label': 'Rate', 'format': 'percent'},
            {'column': '', 'label': 'skipped'},
        ],
        'chips_column': 'MARKET_LIST', 'chips_label': 'Markets',
        'avatar_shape': 'circle',
    }

    def test_payload(self):
        out = F(COLS, [ROW], self.CFG)
        self.assertEqual(out['layout'], 'scorecard')
        self.assertEqual(out['title'], 'Upperline Healthcare PC')
        self.assertEqual(out['subtitle'], 'Provider group')
        self.assertEqual(out['avatar']['shape'], 'circle')
        self.assertEqual(out['fields'], [])          # no y_columns → no footer
        self.assertEqual([s['value'] for s in out['stats']],
                         ['9', '1,106', '2,781', '65.7%'])
        self.assertEqual(out['stats'][0]['icon'], 'fa-map-marker')
        self.assertEqual(out['stats'][0]['label'], 'Markets')
        self.assertEqual(out['chips'], ['FL', 'IL', 'IN'])
        self.assertEqual(out['chips_label'], 'Markets')

    def test_stat_label_falls_back_to_override_then_column(self):
        cfg = dict(self.CFG, stats=[{'column': 'PLAN_COUNT'}],
                   label_overrides={'PLAN_COUNT': 'Plans'})
        self.assertEqual(F(COLS, [ROW], cfg)['stats'][0]['label'], 'Plans')
        cfg = dict(self.CFG, stats=[{'column': 'PLAN_COUNT'}])
        self.assertEqual(F(COLS, [ROW], cfg)['stats'][0]['label'], 'PLAN_COUNT')

    def test_stats_as_json_string(self):
        cfg = dict(self.CFG, stats='[{"column": "PLAN_COUNT", "label": "Plans"}]')
        self.assertEqual(F(COLS, [ROW], cfg)['stats'][0]['value'], '8')
        cfg = dict(self.CFG, stats='not json')
        self.assertEqual(F(COLS, [ROW], cfg)['stats'], [])

    def test_missing_columns_fail_closed(self):
        self.assertIn('error', F(COLS, [ROW], dict(self.CFG, subtitle_column='NOPE')))
        self.assertIn('error', F(COLS, [ROW], dict(self.CFG, stats=[{'column': 'NOPE'}])))
        self.assertIn('error', F(COLS, [ROW], dict(self.CFG, chips_column='NOPE')))

    def test_chips_json_and_blank(self):
        row = ROW[:6] + ('["KY", " OH ", ""]', 65.66, 'x')
        self.assertEqual(F(COLS, [row], self.CFG)['chips'], ['KY', 'OH'])
        row = ROW[:6] + (None, 65.66, 'x')
        self.assertEqual(F(COLS, [row], self.CFG)['chips'], [])
        self.assertEqual(F(COLS, [ROW], dict(self.CFG, chips_column=''))['chips'], [])

    def test_stat_null_and_text(self):
        row = ROW[:2] + (None, 'n/a', 2781.0, 8, 'FL', 65.66, 'x')
        out = F(COLS, [row], self.CFG)
        self.assertEqual(out['stats'][0]['value'], '')
        self.assertEqual(out['stats'][1]['value'], 'n/a')   # non-numeric under number → text

    def test_tile_colors_default_and_override(self):
        cfg = dict(self.CFG, stat_icon_color='#0f6e56', stat_bg='#eee',
                   stats=[{'column': 'PLAN_COUNT'},
                          {'column': 'PCP_COUNT', 'icon_color': '#2563eb', 'value_color': '#111'}])
        st = F(COLS, [ROW], cfg)['stats']
        self.assertEqual(st[0]['icon_color'], '#0f6e56')
        self.assertEqual(st[0]['bg'], '#eee')
        self.assertNotIn('label_color', st[0])           # blank → omitted
        self.assertEqual(st[1]['icon_color'], '#2563eb')  # per-tile override wins
        self.assertEqual(st[1]['value_color'], '#111')
        self.assertEqual(st[1]['bg'], '#eee')

    def test_trend_arrow(self):
        cols = COLS + ['PCP_PRIOR', 'RATE_PRIOR']
        row = ROW + (1100, 66.4)
        cfg = dict(self.CFG, stats=[
            {'column': 'PCP_COUNT', 'prior_column': 'PCP_PRIOR'},
            {'column': 'RATE', 'format': 'percent', 'prior_column': 'RATE_PRIOR'},
            {'column': 'PCP_COUNT', 'prior_column': 'PCP_PRIOR', 'higher_is_better': False},
            {'column': 'PLAN_COUNT'},
        ])
        st = F(cols, [row], cfg)['stats']
        self.assertEqual(st[0]['trend'], {'dir': 'up', 'status': 'good', 'delta': '+6'})
        self.assertEqual(st[1]['trend'], {'dir': 'down', 'status': 'bad', 'delta': '-0.7 pts'})
        self.assertEqual(st[2]['trend']['status'], 'bad')   # up but lower is better
        self.assertNotIn('trend', st[3])
        # equal → flat/neutral; NULL prior → no trend; missing prior column → error
        row2 = ROW + (1106, None)
        st2 = F(cols, [row2], cfg)['stats']
        self.assertEqual(st2[0]['trend'], {'dir': 'flat', 'status': 'neutral', 'delta': ''})
        self.assertNotIn('trend', st2[1])
        self.assertIn('error', F(COLS, [ROW], dict(self.CFG, stats=[{'column': 'PCP_COUNT', 'prior_column': 'NOPE'}])))

    def test_scorecard_keeps_classic_fail_closed(self):
        self.assertEqual(F(COLS, [], self.CFG)['empty'], True)
        self.assertIn('error', F(COLS, [ROW, ROW], self.CFG))


class TestScorecardPrototypeKeys(unittest.TestCase):
    """Opt-in identity/tile extras (title status, subtitle items, badges,
    tile caption/status, panel style, empty text). The first test locks the
    contract that matters most: a scorecard that sets none of them gets the
    exact payload it got before they existed."""

    COLS2 = COLS + ['RATE_MONTH', 'RATE_STATUS', 'RATE_TONE', 'ELIG',
                    'ELIG_TONE', 'MBI', 'EID', 'GENDER']
    ROW2 = ROW + ('Aug 2026', 'Below 85%', 'success', 'Currently eligible',
                  'SUCCESS', '1EG4-TE5-MK72', '', 'Male')
    BASE = TestScorecard.CFG
    NEUTRAL = fmt.TONE_COLORS['neutral']
    SUCCESS = fmt.TONE_COLORS['success']

    def _row(self, **cells):
        row = list(self.ROW2)
        for col, val in cells.items():
            row[self.COLS2.index(col)] = val
        return tuple(row)

    def test_absent_keys_leave_payload_identical(self):
        plain = F(self.COLS2, [self.ROW2], self.BASE)
        blanks = dict(self.BASE, stats_style='', badges=[], subtitle_items=[],
                      title_status_column='', title_status_tone_column='',
                      empty_text='')
        self.assertEqual(plain, F(self.COLS2, [self.ROW2], blanks))
        for key in ('stats_style', 'badges', 'subtitle_items', 'title_status',
                    'empty_text'):
            self.assertNotIn(key, plain)
        for st in plain['stats']:
            self.assertNotIn('caption', st)
            self.assertNotIn('status', st)
        # 'tiles' is the default and must not leak a key either.
        self.assertNotIn('stats_style',
                         F(self.COLS2, [self.ROW2], dict(self.BASE, stats_style='tiles')))

    def test_panel_style(self):
        out = F(self.COLS2, [self.ROW2], dict(self.BASE, stats_style='panel'))
        self.assertEqual(out['stats_style'], 'panel')

    def test_tile_caption_and_status(self):
        cfg = dict(self.BASE, stats=[
            {'column': 'RATE', 'format': 'percent', 'caption_column': 'RATE_MONTH',
             'status_column': 'RATE_STATUS', 'status_tone_column': 'RATE_TONE',
             'color_value_by_status': True},
            {'column': 'PLAN_COUNT', 'status_column': 'RATE_STATUS'},  # no tone → neutral
        ])
        st = F(self.COLS2, [self.ROW2], cfg)['stats']
        self.assertEqual(st[0]['caption'], 'Aug 2026')
        self.assertEqual(st[0]['status'], {'text': 'Below 85%',
                                           'color': self.SUCCESS['color'],
                                           'background': self.SUCCESS['background']})
        self.assertEqual(st[0]['value_color'], self.SUCCESS['color'])
        self.assertEqual(st[1]['status']['color'], self.NEUTRAL['color'])
        self.assertNotIn('value_color', st[1])
        # Blank caption/status text → no key; unknown tone → neutral colours.
        st = F(self.COLS2, [self._row(RATE_MONTH='', RATE_STATUS=None)], cfg)['stats']
        self.assertNotIn('caption', st[0])
        self.assertNotIn('status', st[0])
        self.assertNotIn('value_color', st[0])
        st = F(self.COLS2, [self._row(RATE_TONE='bogus')], cfg)['stats']
        self.assertEqual(st[0]['status']['background'], self.NEUTRAL['background'])
        # Configured-but-missing columns fail closed like every other column.
        for bad in ({'caption_column': 'NOPE'}, {'status_column': 'NOPE'},
                    {'status_column': 'RATE_STATUS', 'status_tone_column': 'NOPE'}):
            spec = dict({'column': 'RATE'}, **bad)
            self.assertIn('error', F(self.COLS2, [self.ROW2], dict(self.BASE, stats=[spec])))

    def test_title_status(self):
        cfg = dict(self.BASE, title_status_column='ELIG', title_status_tone_column='ELIG_TONE')
        out = F(self.COLS2, [self.ROW2], cfg)
        # tone words are case-insensitive ('SUCCESS' in the row)
        self.assertEqual(out['title_status'], {'text': 'Currently eligible',
                                               'color': self.SUCCESS['color'],
                                               'background': self.SUCCESS['background']})
        out = F(self.COLS2, [self.ROW2], dict(self.BASE, title_status_column='ELIG'))
        self.assertEqual(out['title_status']['color'], self.NEUTRAL['color'])
        self.assertNotIn('title_status', F(self.COLS2, [self._row(ELIG='')], cfg))
        self.assertIn('error', F(self.COLS2, [self.ROW2], dict(self.BASE, title_status_column='NOPE')))
        self.assertIn('error', F(self.COLS2, [self.ROW2],
                                 dict(self.BASE, title_status_column='ELIG',
                                      title_status_tone_column='NOPE')))

    def test_badges(self):
        cfg = dict(self.BASE, badges=[
            {'column': 'MBI', 'label': 'MBI', 'copy': True},
            {'column': 'EID', 'label': 'EID', 'copy': 'true'},   # blank value → hidden
            {'column': 'PROVIDER_NAME'},                          # label: spec → override → column
            {'column': ''},
        ], label_overrides={'PROVIDER_NAME': 'Provider'})
        self.assertEqual(F(self.COLS2, [self.ROW2], cfg)['badges'], [
            {'key': 'MBI', 'label': 'MBI', 'value': '1EG4-TE5-MK72', 'copy': True},
            {'key': 'PROVIDER_NAME', 'label': 'Provider',
             'value': 'Upperline Healthcare PC', 'copy': False},
        ])
        self.assertEqual(F(self.COLS2, [self.ROW2], dict(self.BASE, badges=[{'column': 'PLAN_COUNT'}]))['badges'],
                         [{'key': 'PLAN_COUNT', 'label': 'PLAN_COUNT', 'value': '8', 'copy': False}])
        # JSON-string form (visual_config round-trip) and fail-closed column.
        self.assertEqual(F(self.COLS2, [self.ROW2], dict(self.BASE, badges='[{"column": "MBI"}]'))['badges'][0]['value'],
                         '1EG4-TE5-MK72')
        self.assertIn('error', F(self.COLS2, [self.ROW2], dict(self.BASE, badges=[{'column': 'NOPE'}])))

    def test_subtitle_items(self):
        cfg = dict(self.BASE, subtitle_items=[
            {'column': 'GENDER', 'icon': 'fa-user'},
            {'column': 'EID', 'icon': 'fa-id-card'},   # blank value → skipped
            {'column': ''},
        ])
        out = F(self.COLS2, [self.ROW2], cfg)
        self.assertEqual(out['subtitle_items'], [{'icon': 'fa-user', 'value': 'Male'}])
        self.assertEqual(out['subtitle'], 'Provider group')   # plain subtitle still emitted
        self.assertIn('error', F(self.COLS2, [self.ROW2], dict(self.BASE, subtitle_items=[{'column': 'NOPE'}])))

    def test_empty_text(self):
        self.assertEqual(F(COLS, [], self.BASE), {'type': 'record_header', 'empty': True})
        self.assertEqual(F(COLS, [], dict(self.BASE, empty_text=' Find a member to begin ')),
                         {'type': 'record_header', 'empty': True,
                          'empty_text': 'Find a member to begin'})
        # Generic: the classic layout gets the placeholder too.
        self.assertEqual(F(COLS, [], {'empty_text': 'x'})['empty_text'], 'x')
        self.assertEqual(F(COLS, [], {}), {'type': 'record_header', 'empty': True})


if __name__ == '__main__':
    unittest.main()
