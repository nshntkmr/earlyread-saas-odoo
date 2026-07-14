# -*- coding: utf-8 -*-
"""Unit tests for the ``key_takeaways`` multi-row widget formatter.

Covers ``dashboard.widget._build_key_takeaways_data`` (the portal payload),
its parity with the designer preview formatter
(``dashboard_builder.services.preview_formatter``), the page-template
``row_span`` round-trip, and that existing widgets (insight_panel single-row,
table/kpi/bar dispatch) are unaffected.

Run:
    odoo-bin --test-enable -i posterra_portal \\
             --test-tags posterra_key_takeaways --stop-after-init -d <test_db>
"""

import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'posterra_key_takeaways')
class TestKeyTakeawaysFormatter(TransactionCase):
    """The formatter is read-only and never writes / uses self.id, so an
    in-memory ``.new()`` record is sufficient and keeps the tests fast."""

    def _widget(self, **vals):
        base = {'chart_type': 'key_takeaways', 'name': 'KT', 'query_type': 'sql'}
        base.update(vals)
        return self.env['dashboard.widget'].new(base)

    # ── 1. Happy path: N valid rows → N items in SQL order ────────────────

    def test_four_rows_produce_four_items_in_order(self):
        w = self._widget(x_column='takeaway_text', series_column='severity',
                         visual_config='{"max_items": 4}')
        cols = ['takeaway_text', 'severity']
        rows = [
            ['Professional spend is the largest driver', 'warning'],
            ['Outpatient facility spend adds 1.2 points', 'warning'],
            ['Inpatient and SNF are improving', 'positive'],
            ['Emergency Room utilization is rising fastest', 'critical'],
        ]
        out = w._build_key_takeaways_data(cols, rows)
        self.assertEqual(out['type'], 'key_takeaways')
        self.assertEqual(len(out['items']), 4)
        # Order preserved
        self.assertEqual([i['text'] for i in out['items']],
                         [r[0] for r in rows])
        # Severity-derived icon + css
        self.assertEqual(out['items'][0], {
            'text': 'Professional spend is the largest driver',
            'severity': 'warning',
            'icon_class': 'fa fa-exclamation-circle',
            'status_css': 'status-warning',
        })
        self.assertEqual(out['items'][2]['icon_class'], 'fa fa-check-circle')
        self.assertEqual(out['items'][3]['status_css'], 'status-critical')

    # ── 2. Blank / None text rows are skipped ─────────────────────────────

    def test_blank_text_rows_skipped(self):
        w = self._widget(x_column='t', series_column='sev')
        cols = ['t', 'sev']
        rows = [
            ['Real takeaway', 'info'],
            ['', 'warning'],          # blank → skipped
            ['   ', 'warning'],       # whitespace-only → skipped
            [None, 'critical'],       # None → skipped
            ['Second real', 'positive'],
        ]
        out = w._build_key_takeaways_data(cols, rows)
        self.assertEqual([i['text'] for i in out['items']],
                         ['Real takeaway', 'Second real'])

    # ── 3. Unknown / missing severity → neutral ───────────────────────────

    def test_unknown_and_missing_severity_become_neutral(self):
        w = self._widget(x_column='t', series_column='sev')
        cols = ['t', 'sev']
        rows = [
            ['Unknown sev', 'banana'],   # unknown token
            ['Empty sev', ''],           # blank severity
            ['Null sev', None],          # null severity
        ]
        out = w._build_key_takeaways_data(cols, rows)
        for item in out['items']:
            self.assertEqual(item['severity'], 'neutral')
            self.assertEqual(item['icon_class'], 'fa fa-circle-o')
            self.assertEqual(item['status_css'], 'status-neutral')

    def test_no_series_column_configured_all_neutral(self):
        w = self._widget(x_column='t')  # series_column unset
        out = w._build_key_takeaways_data(['t'], [['Only text']])
        self.assertEqual(out['items'][0]['severity'], 'neutral')

    # ── 4. Severity matching is case-insensitive ──────────────────────────

    def test_severity_case_insensitive(self):
        w = self._widget(x_column='t', series_column='sev')
        cols = ['t', 'sev']
        rows = [['a', 'WARNING'], ['b', 'Warning'], ['c', 'warning'],
                ['d', '  Critical  ']]
        out = w._build_key_takeaways_data(cols, rows)
        self.assertEqual([i['severity'] for i in out['items']],
                         ['warning', 'warning', 'warning', 'critical'])

    # ── 5. max_items default 4, clamp 1–10, defensive parse ───────────────

    def _five_rows(self):
        return ['t'], [['r1'], ['r2'], ['r3'], ['r4'], ['r5']]

    def test_max_items_default_four_when_absent(self):
        cols, rows = self._five_rows()
        w = self._widget(x_column='t')  # no visual_config
        self.assertEqual(len(w._build_key_takeaways_data(cols, rows)['items']), 4)

    def test_max_items_blank_none_malformed_default_four(self):
        cols, rows = self._five_rows()
        for vc in ('{"max_items": ""}', '{"max_items": null}',
                   '{"max_items": "abc"}', 'not json at all', '{}'):
            w = self._widget(x_column='t', visual_config=vc)
            self.assertEqual(
                len(w._build_key_takeaways_data(cols, rows)['items']), 4,
                f'visual_config={vc!r} should default max_items to 4')

    def test_max_items_zero_clamps_to_one(self):
        cols, rows = self._five_rows()
        w = self._widget(x_column='t', visual_config='{"max_items": 0}')
        self.assertEqual(len(w._build_key_takeaways_data(cols, rows)['items']), 1)

    def test_max_items_above_ten_clamps_to_ten(self):
        cols = ['t']
        rows = [[f'r{i}'] for i in range(20)]
        w = self._widget(x_column='t', visual_config='{"max_items": 99}')
        self.assertEqual(len(w._build_key_takeaways_data(cols, rows)['items']), 10)

    def test_max_items_valid_value_is_hard_cap(self):
        cols, rows = self._five_rows()
        w = self._widget(x_column='t', visual_config='{"max_items": 2}')
        self.assertEqual(len(w._build_key_takeaways_data(cols, rows)['items']), 2)

    # ── 6. Empty results → safe empty payload ─────────────────────────────

    def test_empty_rows_returns_empty_items(self):
        w = self._widget(x_column='t', series_column='sev')
        self.assertEqual(w._build_key_takeaways_data(['t', 'sev'], []),
                         {'type': 'key_takeaways', 'items': []})

    # ── 6b. Stale / absent column mappings + short rows ───────────────────

    def test_stale_x_column_falls_back_to_first_column(self):
        # x_column names a column not in the result → fall back to first column
        w = self._widget(x_column='does_not_exist', series_column='sev')
        out = w._build_key_takeaways_data(['headline', 'sev'],
                                          [['Fallback works', 'info']])
        self.assertEqual(out['items'][0]['text'], 'Fallback works')
        self.assertEqual(out['items'][0]['severity'], 'info')

    def test_no_columns_returns_empty(self):
        w = self._widget(x_column='t')
        self.assertEqual(w._build_key_takeaways_data([], [[1, 2]]),
                         {'type': 'key_takeaways', 'items': []})

    def test_stale_series_column_all_neutral(self):
        w = self._widget(x_column='t', series_column='missing_sev')
        out = w._build_key_takeaways_data(['t', 'sev'], [['txt', 'warning']])
        # severity column is absent from the mapping → neutral
        self.assertEqual(out['items'][0]['severity'], 'neutral')

    def test_short_rows_handled_without_indexerror(self):
        # severity_idx in range of cols but row is short → treated as neutral;
        # text_idx out of range on a short row → skipped, no IndexError.
        w = self._widget(x_column='t', series_column='sev')
        cols = ['t', 'sev']
        rows = [['has text only'], ['full text', 'warning'], []]
        out = w._build_key_takeaways_data(cols, rows)
        self.assertEqual([i['text'] for i in out['items']],
                         ['has text only', 'full text'])
        self.assertEqual(out['items'][0]['severity'], 'neutral')   # missing cell
        self.assertEqual(out['items'][1]['severity'], 'warning')

    # ── 7. Designer preview ↔ portal payload parity ───────────────────────

    def test_preview_and_portal_payloads_match(self):
        try:
            from odoo.addons.dashboard_builder.services.preview_formatter import (
                format_preview,
            )
        except ImportError:
            self.skipTest('dashboard_builder not installed')

        cols = ['takeaway_text', 'severity']
        rows = [
            ['Professional spend is the largest driver', 'warning'],
            ['Blank should be skipped', ''],
            ['', 'critical'],     # blank text skipped in BOTH
            ['ER utilization rising', 'CRITICAL'],
            ['Doing great', 'positive'],
        ]
        vc = {'max_items': 4}
        w = self._widget(x_column='takeaway_text', series_column='severity',
                         visual_config=json.dumps(vc))
        portal = w._build_key_takeaways_data(cols, rows)
        preview = format_preview(
            'key_takeaways', cols, rows,
            {'x_column': 'takeaway_text', 'series_column': 'severity'}, vc,
        )
        self.assertEqual(preview, portal,
                         'designer preview payload must match portal exactly')


@tagged('post_install', '-at_install', 'posterra_key_takeaways')
class TestKeyTakeawaysPortability(TransactionCase):
    """Definition/page-template round-trips must preserve the data + layout
    fields, including the newly-serialized top-level ``row_span``."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.app = cls.env['saas.app'].sudo().create({
            'name': 'KT Test App', 'app_key': 'ktapp',
            'access_mode': 'hha_provider', 'is_active': True,
        })
        cls.nav = cls.env['dashboard.nav.section'].sudo().create({
            'name': 'KT Nav', 'key': 'kt_nav',
        })
        cls.page = cls.env['dashboard.page'].sudo().create({
            'name': 'KT Page', 'key': 'kt_page',
            'app_id': cls.app.id, 'nav_section_id': cls.nav.id,
            'portal_type': 'hha',
        })
        cls.widget = cls.env['dashboard.widget'].sudo().create({
            'page_id': cls.page.id,
            'name': 'Key Takeaways',
            'chart_type': 'key_takeaways',
            'query_type': 'sql',
            'query_sql': 'SELECT 1 AS takeaway_text, 2 AS severity',
            'x_column': 'takeaway_text',
            'series_column': 'severity',
            'visual_config': '{"max_items": 3}',
            'col_span': '6',
            'row_span': 2,
            'chart_height': 380,
        })

    def test_page_template_round_trip_preserves_fields(self):
        Template = self.env['dashboard.page.template'].sudo()
        cfg = Template.serialize_page(self.page)

        # Serialize captures the data + layout fields (incl. the row_span fix)
        wcfg = next(w for w in cfg['widgets'] if w['chart_type'] == 'key_takeaways')
        self.assertEqual(wcfg['x_column'], 'takeaway_text')
        self.assertEqual(wcfg['series_column'], 'severity')
        self.assertEqual(wcfg['visual_config'], '{"max_items": 3}')
        self.assertEqual(wcfg['col_span'], '6')
        self.assertEqual(wcfg['row_span'], 2)
        self.assertEqual(wcfg['chart_height'], 380)

        # Deserialize: create a new page from the serialized config and assert
        # every field survived the round-trip.
        template = Template.create({
            'name': 'KT Round Trip', 'page_config': json.dumps(cfg),
        })
        new_page = template.create_page_from_template(
            self.app.id, self.nav.id,
            name_override='KT Page Copy', key_override='kt_page_copy',
        )
        new_w = new_page.widget_ids.filtered(
            lambda x: x.chart_type == 'key_takeaways')
        self.assertEqual(len(new_w), 1)
        self.assertEqual(new_w.x_column, 'takeaway_text')
        self.assertEqual(new_w.series_column, 'severity')
        self.assertEqual(new_w.visual_config, '{"max_items": 3}')
        self.assertEqual(new_w.col_span, '6')
        self.assertEqual(new_w.row_span, 2)
        self.assertEqual(new_w.chart_height, 380)


@tagged('post_install', '-at_install', 'posterra_key_takeaways')
class TestExistingWidgetRegression(TransactionCase):
    """The new chart_type + dispatch branch must not disturb neighbors."""

    def _widget(self, **vals):
        base = {'name': 'W', 'query_type': 'sql'}
        base.update(vals)
        return self.env['dashboard.widget'].new(base)

    def test_insight_panel_still_single_row(self):
        # insight_panel reads ONLY rows[0] — unchanged by key_takeaways work.
        w = self._widget(chart_type='insight_panel')
        cols = ['classification', 'metric1']
        rows = [['warning', '10'], ['up', '20']]
        out = w._build_insight_data(cols, rows, {})
        self.assertEqual(out['type'], 'insight_panel')
        # Reflects rows[0] (warning), not rows[1] (up)
        self.assertEqual(out['status_css'], 'status-warning')

    def test_dispatch_routes_each_type_correctly(self):
        ctx = {'filter_values_by_name': {}, 'sql_params': {}}

        # key_takeaways → multi-row list
        kt = self._widget(chart_type='key_takeaways', x_column='t',
                          series_column='sev')
        kt_out = kt._dispatch_chart_builder(
            ['t', 'sev'], [['a', 'warning'], ['b', 'positive']], ctx)
        self.assertEqual(kt_out['type'], 'key_takeaways')
        self.assertEqual(len(kt_out['items']), 2)

        # table → AG Grid shape (unchanged)
        tbl = self._widget(chart_type='table')
        tbl_out = tbl._dispatch_chart_builder(['a', 'b'], [[1, 2]], ctx)
        self.assertIn('columnDefs', tbl_out)
        self.assertIn('rowData', tbl_out)

        # insight_panel → its own type (unchanged)
        ip = self._widget(chart_type='insight_panel')
        ip_out = ip._dispatch_chart_builder(
            ['classification'], [['up']], ctx)
        self.assertEqual(ip_out['type'], 'insight_panel')

        # bar (default else branch) → ECharts JSON (unchanged)
        bar = self._widget(chart_type='bar', x_column='cat', y_columns='val')
        bar_out = bar._dispatch_chart_builder(
            ['cat', 'val'], [['A', 1], ['B', 2]], ctx)
        self.assertIn('echart_json', bar_out)


@tagged('post_install', '-at_install', 'posterra_key_takeaways')
class TestAlbersChoroplethDispatch(TransactionCase):
    """The standalone ``albers_choropleth`` chart type must dispatch to the
    SVG-Albers choropleth builder — NOT fall through to the ECharts branch."""

    def _widget(self, **vals):
        base = {
            'chart_type': 'albers_choropleth',
            'name': 'Geo',
            'query_type': 'sql',
            'visual_config': json.dumps({
                'choropleth_join_column': 'region',
                'choropleth_metric_column': 'value',
            }),
        }
        base.update(vals)
        return self.env['dashboard.widget'].new(base)

    def test_build_returns_choropleth_payload(self):
        w = self._widget()
        cols = ['region', 'value', 'STATE_NAME']
        rows = [['CA', 100, 'California'], ['NY', 50, 'New York']]
        out = w._build_albers_choropleth(cols, rows)
        # Tagged as the standalone type, not 'map'
        self.assertEqual(out['type'], 'albers_choropleth')
        # Choropleth payload shape (not an ECharts option)
        self.assertIn('choropleth_data', out)
        self.assertIn('geo_level', out)
        self.assertIn('join_property', out)
        self.assertNotIn('echart_json', out)
        # Region → numeric metric mapping
        self.assertEqual(out['choropleth_data'], {'CA': 100.0, 'NY': 50.0})
        # Default state level → STUSPS join; renderer forced to SVG Albers
        self.assertEqual(out['geo_level'], 'state')
        self.assertEqual(out['join_property'], 'STUSPS')
        self.assertEqual(out['map_config'].get('choropleth_renderer'),
                         'svg_albers_usa')

    def test_dispatch_routes_to_choropleth_not_echarts(self):
        w = self._widget()
        cols = ['region', 'value']
        rows = [['CA', 100], ['NY', 50]]
        out = w._dispatch_chart_builder(cols, rows, {})
        self.assertEqual(out['type'], 'albers_choropleth')
        self.assertIn('choropleth_data', out)
        self.assertNotIn('echart_json', out)

    def test_all_zero_opt_in_round_trips_without_collapsing_zero_to_null(self):
        """The backend must preserve both the opt-in flag and genuine zeros.

        The client decides whether the complete zero-only selection uses the
        no-data fill; keeping zeros numeric preserves tooltip/display semantics
        and keeps mixed zero/non-zero selections on the normal scale.
        """
        w = self._widget(visual_config=json.dumps({
            'choropleth_join_column': 'region',
            'choropleth_metric_column': 'value',
            'choropleth_all_zero_as_no_data': True,
        }))
        out = w._build_albers_choropleth(
            ['region', 'value'], [['CA', 0], ['NY', 0]])
        self.assertIs(out['map_config']['choropleth_all_zero_as_no_data'], True)
        self.assertEqual(out['choropleth_data'], {'CA': 0.0, 'NY': 0.0})

    def test_existing_config_does_not_enable_all_zero_behavior(self):
        """Absent flag remains absent/false so prior maps render identically."""
        out = self._widget()._build_albers_choropleth(
            ['region', 'value'], [['CA', 0], ['NY', 0]])
        self.assertFalse(
            out['map_config'].get('choropleth_all_zero_as_no_data', False))
        self.assertEqual(out['choropleth_data'], {'CA': 0.0, 'NY': 0.0})

    def test_builder_exposes_all_zero_flag_as_opt_in(self):
        try:
            from odoo.addons.dashboard_builder.services.chart_flags import (
                get_flags_for_chart,
            )
        except ImportError:
            self.skipTest('dashboard_builder not installed')
        matches = [
            flag for flag in get_flags_for_chart('albers_choropleth')
            if flag.get('flag') == 'choropleth_all_zero_as_no_data'
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['type'], 'boolean')
        self.assertIs(matches[0]['default'], False)

    def test_preview_formatter_returns_empty_no_fallthrough(self):
        try:
            from odoo.addons.dashboard_builder.services.preview_formatter import (
                format_preview,
            )
        except ImportError:
            self.skipTest('dashboard_builder not installed')
        # Maps/choropleths render client-side → empty preview payload (NOT the
        # raw-data fallback), same contract as the existing 'map' type.
        out = format_preview('albers_choropleth', ['region', 'value'],
                             [['CA', 100]], {}, {})
        self.assertEqual(out, {})
