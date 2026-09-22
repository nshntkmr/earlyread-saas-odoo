# -*- coding: utf-8 -*-
"""Page PDF export (plan v5) — tag ``posterra_pdf_export``.

Covers the database-level bounding helpers, the PostgreSQL / ClickHouse
``execute_bounded`` implementations (ClickHouse through a fake client), the
print mirror against the shared fixture, the shared scope resolver, the
context plumbing into the widget SQL paths, the export route end-to-end
(render service patched), audit-log lifecycle and configuration sync.

Never run against the live DB. Run on a scratch DB:
    odoo-bin -d <test_db> -u posterra_portal,dashboard_builder --test-enable \\
             --test-tags /posterra_portal:posterra_pdf_export --stop-after-init
"""

import base64
import hashlib
import hmac
import html as html_lib
import json
import os
import re
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import psycopg2

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged

from ..services.pdf_export import cell_format
from ..utils.query_executors import bounded
from ..utils.query_executors.clickhouse import ClickHouseExecutor
from ..utils.query_executors.postgres_local import PostgresLocalExecutor

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'pdf_cell_format.json')
RENDER_PATH = 'odoo.addons.posterra_portal.controllers.pdf_export_api.render_pdf'


def _text(markup):
    return html_lib.unescape(re.sub(r'<[^>]+>', '', str(markup)))


# ─────────────────────────────────────────────────────────────────────────
@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestBoundedSql(TransactionCase):

    def test_no_limit_no_sort_returns_sql_unchanged(self):
        sql = 'SELECT 1 ;'
        self.assertEqual(bounded.wrap_bounded(sql), sql)

    def test_limit_asks_one_extra_row(self):
        out = bounded.wrap_bounded('SELECT 1', max_rows=500)
        self.assertTrue(out.endswith('LIMIT 501'))
        self.assertIn('AS _pv_bounded', out)

    def test_trailing_semicolons_and_comments(self):
        for sql in ('SELECT 1;', 'SELECT 1 ;  ', 'SELECT 1; -- done', 'SELECT 1 /* c */ ;;',
                    'SELECT 1; /* a ; b */'):
            out = bounded.wrap_bounded(sql, max_rows=5)
            masked = bounded.mask_sql(out)
            self.assertNotIn(';', masked, sql)

    def test_semicolon_inside_literal_kept(self):
        out = bounded.wrap_bounded("SELECT ';' AS s", max_rows=5)
        self.assertIn("';'", out)

    def test_trailing_line_comment_does_not_eat_the_paren(self):
        out = bounded.wrap_bounded('SELECT 1 AS a -- trailing', max_rows=5)
        self.assertIn('-- trailing\n) AS _pv_bounded', out)

    def test_middle_semicolon_left_in_place(self):
        out = bounded.wrap_bounded('SELECT 1; SELECT 2', max_rows=5)
        self.assertIn('SELECT 1; SELECT 2', out)

    def test_clickhouse_format_rejected(self):
        with self.assertRaises(bounded.BoundedSqlError):
            bounded.wrap_bounded('SELECT 1 FORMAT JSON', max_rows=5, dialect='clickhouse')

    def test_order_by_nulls_and_quoting(self):
        order = [('Compliance Rate %', 'desc'), ('name', 'asc')]
        pg = bounded.build_order_clause(order, 'postgres')
        self.assertEqual(pg, 'ORDER BY "Compliance Rate %%" DESC NULLS LAST, "name" ASC NULLS FIRST')
        ch = bounded.build_order_clause(order, 'clickhouse')
        self.assertEqual(ch, 'ORDER BY "Compliance Rate %" DESC NULLS LAST, "name" ASC NULLS FIRST')

    def test_bad_identifiers_skipped(self):
        self.assertEqual(bounded.build_order_clause([('a"b', 'asc'), ('x`', 'desc')], 'postgres'), '')

    def test_order_from_column_defs(self):
        cols = [{'field': 'a', 'sort': 'asc'}, {'field': 'b', 'sort': 'desc', 'sortIndex': 0},
                {'field': 'c'}, {'field': 'd', 'sort': 'bogus'}]
        self.assertEqual(bounded.order_by_from_column_defs(cols), [('b', 'desc'), ('a', 'asc')])

    def test_error_classifiers(self):
        self.assertTrue(bounded.is_unknown_column_error(SimpleNamespace(pgcode='42703')))
        self.assertTrue(bounded.is_unknown_column_error(Exception('Code: 47. DB::Exception')))
        self.assertTrue(bounded.is_timeout_error(SimpleNamespace(pgcode='57014')))
        self.assertTrue(bounded.is_timeout_error(Exception('Code: 159. TIMEOUT_EXCEEDED')))


# ─────────────────────────────────────────────────────────────────────────
@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestPostgresBounded(TransactionCase):

    SQL = ("SELECT g AS n, CASE WHEN g %% 5 = 0 THEN NULL ELSE g END AS m "
           "FROM generate_series(1, %(total)s) g ORDER BY g")

    def setUp(self):
        super().setUp()
        self.ex = PostgresLocalExecutor(self.env)

    def _timeout(self):
        self.env.cr.execute('SHOW statement_timeout')
        return self.env.cr.fetchone()[0]

    def test_cap_and_more_available(self):
        res = self.ex.execute_bounded(self.SQL, {'total': 30}, max_rows=10)
        self.assertEqual(len(res.rows), 10)
        self.assertTrue(res.more_available)
        self.assertEqual([r[0] for r in res.rows], list(range(1, 11)))   # inner ORDER BY kept
        exact = self.ex.execute_bounded(self.SQL, {'total': 10}, max_rows=10)
        self.assertFalse(exact.more_available)

    def test_sort_applied_before_truncation(self):
        res = self.ex.execute_bounded(self.SQL, {'total': 30}, max_rows=3, order_by=[('n', 'desc')])
        self.assertEqual([r[0] for r in res.rows], [30, 29, 28])
        self.assertTrue(res.sort_applied)
        # AG Grid: null is the smallest value → ASC puts NULLs first
        res = self.ex.execute_bounded(self.SQL, {'total': 30}, max_rows=3, order_by=[('m', 'asc')])
        self.assertEqual([r[1] for r in res.rows], [None, None, None])

    def test_unknown_sort_column_retries_without_sort(self):
        res = self.ex.execute_bounded(self.SQL, {'total': 5}, max_rows=3, order_by=[('missing', 'asc')])
        self.assertFalse(res.sort_applied)
        self.assertEqual(len(res.rows), 3)

    def test_timeout_restored_on_success_and_failure(self):
        before = self._timeout()
        self.ex.execute_bounded('SELECT pg_sleep(0.01)', {}, timeout_s=5)
        self.assertEqual(self._timeout(), before)
        with self.assertRaises(psycopg2.errors.QueryCanceled):
            self.ex.execute_bounded('SELECT pg_sleep(2)', {}, timeout_s=0.2)
        self.assertEqual(self._timeout(), before)
        self.env.cr.execute('SELECT 1')   # transaction still usable

    def test_execute_unchanged(self):
        cols, rows = self.ex.execute(self.SQL, {'total': 30})
        self.assertEqual(len(rows), 30)
        self.assertEqual(cols, ['n', 'm'])

    def test_base_and_snowflake_refuse(self):
        from ..utils.query_executors.base import BaseQueryExecutor
        from ..utils.query_executors.snowflake import SnowflakeExecutor
        for cls in (BaseQueryExecutor, SnowflakeExecutor):
            with self.assertRaises(NotImplementedError):
                cls(self.env).execute_bounded('SELECT 1', {}, max_rows=1)


# ─────────────────────────────────────────────────────────────────────────
class _FakeResult:
    def __init__(self, cols, rows):
        self.column_names, self.result_rows = cols, rows


class _FakeClient:
    def __init__(self, fail_first_with=None):
        self.calls = []
        self.fail_first_with = fail_first_with

    def query(self, sql, parameters=None, settings=None):
        self.calls.append({'sql': sql, 'parameters': parameters, 'settings': settings})
        if self.fail_first_with and len(self.calls) == 1:
            raise Exception(self.fail_first_with)
        return _FakeResult(['n'], [(i,) for i in range(4)])


@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestClickHouseBounded(TransactionCase):

    def setUp(self):
        super().setUp()
        self.conn = SimpleNamespace(id=424242, name='fake-ch', query_timeout_seconds=30,
                                    requires_tenant_filter=True)
        self.ex = ClickHouseExecutor(self.env, self.conn)
        self.ex.get_tenant_id = lambda: 'tenant-a'

    def _run(self, client, **kw):
        with patch('odoo.addons.posterra_portal.utils.query_executors.clickhouse._get_client',
                   return_value=client):
            return self.ex.execute_bounded('SELECT n FROM t WHERE x = %(x)s', {'x': 1}, **kw)

    def test_wrap_settings_and_cap(self):
        client = _FakeClient()
        res = self._run(client, max_rows=3, timeout_s=7.2, order_by=[('n', 'desc')])
        call = client.calls[0]
        self.assertIn('LIMIT 4', call['sql'])
        self.assertIn('ORDER BY "n" DESC NULLS LAST', call['sql'])
        self.assertIn('{x:Int64}', call['sql'])
        self.assertEqual(call['settings']['SQL_tenant_id'], 'tenant-a')
        self.assertEqual(call['settings']['max_execution_time'], 8)     # ceil(7.2), ≤ connection 30
        self.assertEqual((len(res.rows), res.more_available, res.sort_applied), (3, True, True))

    def test_unknown_identifier_retry(self):
        client = _FakeClient(fail_first_with='Code: 47. DB::Exception: Unknown identifier')
        res = self._run(client, max_rows=10, order_by=[('gone', 'asc')])
        self.assertEqual(len(client.calls), 2)
        self.assertNotIn('ORDER BY', client.calls[1]['sql'])
        self.assertFalse(res.sort_applied)

    def test_execute_keeps_tenant_rule(self):
        client = _FakeClient()
        with patch('odoo.addons.posterra_portal.utils.query_executors.clickhouse._get_client',
                   return_value=client):
            self.ex.execute('SELECT n FROM t', {})
        s = client.calls[0]['settings']
        self.assertEqual(s['SQL_tenant_id'], 'tenant-a')
        self.assertEqual(s['max_execution_time'], 30)
        self.assertNotIn('LIMIT', client.calls[0]['sql'])


# ─────────────────────────────────────────────────────────────────────────
@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestCellFormat(TransactionCase):

    def test_fixture(self):
        with open(FIXTURE, encoding='utf-8') as fh:
            cases = json.load(fh)['cases']
        self.assertGreaterEqual(len(cases), 30)
        for case in cases:
            with self.subTest(case['name']):
                html, _align, _style = cell_format.render_cell(case['col'], case['row'])
                self.assertEqual(_text(html), case['text'])

    def test_rule_colors_and_safety(self):
        col = {'field': 'v', 'cellClassRules': {'cell-good': 'x >= 70', 'cell-bad': 'x < 50'}}
        self.assertIn('#10b981', cell_format.render_cell(col, {'v': 80})[2])
        self.assertIn('#ef4444', cell_format.render_cell(col, {'v': 10})[2])
        self.assertEqual(cell_format.render_cell(col, {'v': 60})[2], '')
        self.assertFalse(cell_format.eval_rule('constructor.constructor("x")() || true', 1))
        bad = {'field': 'v', 'cellRenderer': 'badge',
               'cellRendererParams': {'colorMap': {'X': 'red;background:url(//evil)'}}}
        self.assertNotIn('evil', str(cell_format.render_cell(bad, {'v': 'X'})[0]))


# ─────────────────────────────────────────────────────────────────────────
@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestPdfCharts(TransactionCase):

    def test_embed_json_cannot_close_the_script(self):
        from ..services.pdf_export.charts import embed_json
        out = embed_json({'label': '</script><img src=x onerror=alert(1)>', 'amp': 'a&b'})
        self.assertNotIn('<', out)
        self.assertNotIn('>', out)
        self.assertNotIn('&', out)
        self.assertEqual(json.loads(out)['label'], '</script><img src=x onerror=alert(1)>')

    def test_printable_option_is_static(self):
        from ..services.pdf_export.charts import printable_option
        src = {'series': [{'type': 'line', 'data': [1, 2]}], 'toolbox': {'show': True},
               'dataZoom': [{'type': 'slider', 'start': 10}, {'type': 'inside'}]}
        out = printable_option(src)
        self.assertFalse(out['animation'])
        self.assertEqual(out['series'][0]['progressive'], 0)      # one synchronous frame
        self.assertFalse(out['series'][0]['animation'])
        self.assertFalse(out['toolbox']['show'])
        self.assertFalse(out['dataZoom'][0]['show'])
        self.assertEqual(out['dataZoom'][0]['start'], 10)          # selected range kept
        self.assertNotIn('show', out['dataZoom'][1])
        self.assertNotIn('animation', src)                         # input untouched
        self.assertNotIn('progressive', src['series'][0])
        single = printable_option({'series': {'type': 'gauge', 'data': [{'value': 5}]}})
        self.assertEqual(single['series']['progressive'], 0)       # object-form series too

    def test_scripts_only_when_there_are_charts(self):
        from ..services.pdf_export.charts import chart_scripts
        self.assertEqual(str(chart_scripts([])), '')               # chart-free PDFs carry no script
        full = str(chart_scripts([{'id': 'pvc1', 'option': {'series': []}, 'width': 300, 'height': 200}]))
        self.assertIn('data:text/javascript;base64,', full)
        self.assertIn("d.textContent='';", full)                  # placeholder cleared before drawing
        self.assertNotIn('__pvChartsReady', full)                  # nothing for the renderer to wait on
        self.assertEqual(full.count('</script>'), 3)

    def test_chart_option_sources(self):
        from ..services.pdf_export.charts import chart_option
        self.assertEqual(chart_option({'echart_json': '{"series": [1]}'}), {'series': [1]})
        self.assertEqual(chart_option({'echart_option': {'series': [2]}}), {'series': [2]})
        self.assertIsNone(chart_option({'type': 'gauge', 'rows': []}))   # custom gauge style
        self.assertIsNone(chart_option({'echart_json': 'not json'}))

    def test_chart_width_fits_the_print_grid(self):
        from ..services.pdf_export.document import card_inner_width_px, content_width_px
        full = content_width_px('letter', 'landscape')
        self.assertAlmostEqual(full, 979.2, places=1)
        self.assertEqual(card_inner_width_px(full, '12'), int(full) - 18)
        half = card_inner_width_px(full, '6')
        self.assertLess(half * 2 + 7 + 36, full + 2)

    def test_render_sends_no_wait_condition(self):
        # Charts draw before the load event; a wait condition would make every
        # export time out on a renderer that runs without JavaScript.
        from ..services.pdf_export.render_client import paper_form
        form = paper_form('letter', 'landscape')
        self.assertFalse([k for k in form if k.lower().startswith('wait')])

    def test_mini_gauge_size_is_clamped(self):
        from ..services.pdf_export.document import _mini_gauge_size
        self.assertEqual(_mini_gauge_size({}), 64)
        self.assertEqual(_mini_gauge_size({'mini_gauge_size': 90}), 90)
        self.assertEqual(_mini_gauge_size({'mini_gauge_size': 5000}), 120)
        self.assertEqual(_mini_gauge_size({'mini_gauge_size': 'x'}), 64)

    def test_vendored_echarts_matches_the_portal_version(self):
        from ..services.pdf_export.charts import ECHARTS_VERSION, echarts_script_src
        module = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(module, 'static', 'lib', 'echarts', 'VERSION'), encoding='ascii') as fh:
            self.assertEqual(fh.read().strip(), ECHARTS_VERSION)
        self.assertTrue(echarts_script_src().startswith('data:text/javascript;base64,'))
        pkg = os.path.join(module, 'static', 'src', 'react', 'node_modules', 'echarts', 'package.json')
        if os.path.exists(pkg):        # dev checkouts only (node_modules is not in the image)
            with open(pkg, encoding='utf-8') as fh:
                self.assertEqual(json.load(fh)['version'], ECHARTS_VERSION)


# ─────────────────────────────────────────────────────────────────────────
class _PdfFixture:
    """Shared records: app, page with 2 tabs, PG-backed widgets."""

    @classmethod
    def _setup_records(cls):
        env = cls.env
        cls.app = env['saas.app'].sudo().create({
            'name': 'PDF App', 'app_key': 'pdf-app', 'access_mode': 'group',
            'access_group_xmlid': 'base.group_user',
        })
        nav = env['dashboard.nav.section'].sudo().create({'name': 'PDF Nav', 'key': 'pdf_nav'})
        cls.page = env['dashboard.page'].sudo().create({
            'name': 'Scorecard', 'key': 'pdf_scorecard', 'app_id': cls.app.id,
            'nav_section_id': nav.id, 'pdf_export_enabled': True, 'pdf_row_limit': 10,
            'pdf_title_template': '{app_name} — {page_name} — {tab_name}',
        })
        Tab = env['dashboard.page.tab'].sudo()
        cls.tab = Tab.create({'name': 'Main', 'key': 'main', 'page_id': cls.page.id, 'sequence': 1})
        cls.tab2 = Tab.create({'name': 'Other', 'key': 'other', 'page_id': cls.page.id, 'sequence': 2})
        W = env['dashboard.widget'].sudo()
        base = {'page_id': cls.page.id, 'tab_id': cls.tab.id, 'query_type': 'sql'}
        cls.kpi = W.create(dict(base, name='Compliance Rate', chart_type='kpi', sequence=10,
                                query_sql='SELECT 53.3 AS v', x_column='v'))
        cls.table = W.create(dict(base, name='Measures', chart_type='table', sequence=20,
                                  query_sql=("SELECT g AS n, 'Measure ' || g AS label "
                                             "FROM generate_series(1, 30) g ORDER BY g"),
                                  table_column_config=json.dumps([
                                      {'field': 'n', 'headerName': 'N', 'sort': 'desc'},
                                      {'field': 'label', 'headerName': 'Label'},
                                      {'field': 'hidden', 'headerName': 'Hidden', 'hide': True}])))
        cls.chart = W.create(dict(base, name='Trend', chart_type='bar', sequence=30,
                                  query_sql=("SELECT 'Jan' AS x, 2 AS y UNION ALL "
                                             "SELECT 'Feb', 5 UNION ALL SELECT '</script><b>x', 3"),
                                  x_column='x', y_columns='y'))
        cls.gauge_kpi = W.create(dict(base, name='Gauge KPI', chart_type='kpi', sequence=32,
                                      query_sql='SELECT 42 AS v, 80 AS target', x_column='v',
                                      visual_config=json.dumps({'kpi_style': 'mini_gauge'})))
        cls.spark_kpi = W.create(dict(base, name='Spark KPI', chart_type='kpi', sequence=33,
                                      query_sql="SELECT 7 AS v, '1,3,2,5' AS sparkline_data",
                                      x_column='v', visual_config=json.dumps({'kpi_style': 'sparkline'})))
        cls.gauge_breakdown = W.create(dict(base, name='Gauge Breakdown', chart_type='gauge_kpi', sequence=34,
                                            query_sql="SELECT 64 AS v, 12 AS open_gaps, 'Behind plan' AS note",
                                            x_column='v', gauge_sub_kpi_columns='open_gaps',
                                            gauge_sub_kpi_labels='Open Gaps', gauge_alert_column='note'))
        cls.map_widget = W.create(dict(base, name='Region Map', chart_type='map', sequence=35,
                                       query_sql='SELECT 1 AS x', x_column='x'))
        cls.excluded = W.create(dict(base, name='Not Printed', chart_type='kpi', sequence=40,
                                     query_sql='SELECT 1 AS v', x_column='v', pdf_include=False))
        cls.other_tab = W.create(dict(base, name='Other Tab KPI', chart_type='kpi', sequence=50,
                                      tab_id=cls.tab2.id, query_sql='SELECT 2 AS v', x_column='v'))
        conn = env['dashboard.connection'].sudo().create({
            'name': 'SF Test', 'engine': 'snowflake', 'is_active': True,
            'requires_tenant_filter': False})
        sf_src = env['dashboard.schema.source'].sudo().create({
            'name': 'SF Src', 'table_name': 'SF_TABLE', 'is_active': True,
            'connection_id': conn.id, 'data_classification': 'non_phi'})
        cls.snowflake_widget = W.create(dict(base, name='Snowflake KPI', chart_type='kpi', sequence=60,
                                             query_sql='SELECT 1 AS v', x_column='v',
                                             schema_source_id=sf_src.id))


# ─────────────────────────────────────────────────────────────────────────
@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestScopeAndPlumbing(TransactionCase, _PdfFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_records()

    def test_resolver_non_strict_matches_data_route(self):
        from ..controllers.widget_api import InvalidScopeOption, _resolve_widget_scope
        w = self.table
        w.write({'scope_mode': 'independent', 'scope_query_mode': 'query', 'scope_param_name': 'metric'})
        Opt = self.env['dashboard.widget.scope.option'].sudo()
        opt = Opt.create({'widget_id': w.id, 'label': 'A', 'value': 'a', 'sequence': 1,
                          'query_sql': 'SELECT 1 AS n'})
        foreign = Opt.create({'widget_id': self.kpi.id, 'label': 'F', 'value': 'f', 'sequence': 1,
                              'query_sql': 'SELECT 1 AS v'})
        # no id → default option
        self.assertEqual(_resolve_widget_scope(w, None, {}, strict=False)[0], opt)
        # foreign / junk id → silent fallback (widget SQL), binding still computed
        o, b = _resolve_widget_scope(w, str(foreign.id), {'metric': 'x'}, strict=False)
        self.assertIsNone(o)
        self.assertEqual(b, ('metric', 'x'))
        self.assertIsNone(_resolve_widget_scope(w, 'junk', {}, strict=False)[0])
        # strict: explicit invalid id raises; valid id resolves
        with self.assertRaises(InvalidScopeOption):
            _resolve_widget_scope(w, str(foreign.id), {}, strict=True)
        self.assertEqual(_resolve_widget_scope(w, str(opt.id), {}, strict=True)[0], opt)

    def test_parameter_mode_all_is_ignored(self):
        from ..controllers.widget_api import _resolve_widget_scope
        self.kpi.write({'scope_mode': 'independent', 'scope_param_name': 'region'})
        self.assertIsNone(_resolve_widget_scope(self.kpi, None, {'region': 'All'})[1])
        self.assertEqual(_resolve_widget_scope(self.kpi, None, {'region': 'TX'})[1], ('region', 'TX'))

    def test_limits_reach_executor_and_absent_key_is_unchanged(self):
        ctx = {'sql_params': {}, 'filter_values_by_name': {}, '_filter_defs': []}
        plain = self.table.get_portal_data(dict(ctx))
        again = self.table.get_portal_data(dict(ctx))
        self.assertEqual(json.dumps(plain, sort_keys=True, default=str),
                         json.dumps(again, sort_keys=True, default=str))
        self.assertEqual(plain['row_count'], 30)
        report = {}
        limited = self.table.with_context(
            pv_execution_limits={'max_rows': 5, 'timeout_s': 5, 'order_by': [('n', 'desc')]},
            pv_execution_report=report).get_portal_data(dict(ctx))
        self.assertEqual([r['n'] for r in limited['rowData']], [30, 29, 28, 27, 26])
        self.assertTrue(report['more_available'])
        self.assertTrue(report['sort_applied'])

    def test_page_config_key_only_when_enabled(self):
        from ..controllers.portal import _pdf_export_config
        cfg = _pdf_export_config(self.page)
        self.assertEqual(cfg['orientation'], 'landscape')
        self.assertTrue(cfg['keynote_enabled'])
        self.assertEqual((cfg['tab_restricted'], cfg['tab_keys']), (False, []))
        self.assertEqual(cfg['button'], {'bg_color': '', 'text_color': ''})

    def test_tab_restriction_rule(self):
        from ..controllers.portal import _pdf_export_config
        self.assertTrue(self.page.pdf_tab_allowed(self.tab))
        self.page.write({'pdf_tab_ids': [(6, 0, [self.tab2.id])]})
        self.assertFalse(self.page.pdf_tab_allowed(self.tab))
        self.assertTrue(self.page.pdf_tab_allowed(self.tab2))
        self.assertTrue(self.page.pdf_tab_allowed(self.env['dashboard.page.tab']))   # page without tabs
        cfg = _pdf_export_config(self.page)
        self.assertEqual((cfg['tab_restricted'], cfg['tab_keys']), (True, ['other']))
        # every selected tab inactive → restricted with no tab (never "all tabs")
        self.tab2.write({'is_active': False})
        cfg = _pdf_export_config(self.page)
        self.assertEqual((cfg['tab_restricted'], cfg['tab_keys']), (True, []))

    def test_tab_restriction_rejects_foreign_tabs(self):
        from odoo.exceptions import ValidationError
        nav = self.env['dashboard.nav.section'].sudo().create({'name': 'N2', 'key': 'pdf_nav2'})
        other_page = self.env['dashboard.page'].sudo().create({
            'name': 'Other', 'key': 'pdf_other_page', 'app_id': self.app.id, 'nav_section_id': nav.id})
        foreign = self.env['dashboard.page.tab'].sudo().create(
            {'name': 'F', 'key': 'f', 'page_id': other_page.id})
        with self.assertRaises(ValidationError):
            self.page.write({'pdf_tab_ids': [(4, foreign.id)]})

    def test_button_colors_validated(self):
        from odoo.exceptions import ValidationError
        from ..controllers.portal import _pdf_export_config
        self.page.write({'pdf_button_bg_color': '#0b6e4f', 'pdf_button_text_color': 'white'})
        self.assertEqual(_pdf_export_config(self.page)['button'],
                         {'bg_color': '#0b6e4f', 'text_color': 'white'})
        for bad in ('red;background:url(x)', 'expression(alert(1))', '#12'):
            with self.assertRaises(ValidationError):
                self.page.write({'pdf_button_bg_color': bad})

    def test_page_limits_constraint(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.page.write({'pdf_row_limit': 5001})
        with self.assertRaises(ValidationError):
            self.page.write({'pdf_max_columns': 25})


# ─────────────────────────────────────────────────────────────────────────
class _RouteBase(_PdfFixture):
    SECRET = 'pdf-export-test-secret'

    @classmethod
    def _setup_route(cls):
        cls.env['ir.config_parameter'].sudo().set_param('posterra_portal.jwt_secret', cls.SECRET)
        cls._setup_records()
        Users = cls.env['res.users'].sudo()
        group_internal = cls.env.ref('base.group_user')
        cls.member = Users.create({'name': 'PDF Member', 'login': 'pdf.member@test.local',
                                   'email': 'pdf.member@test.local'})
        cls.outsider = Users.create({'name': 'PDF Outsider', 'login': 'pdf.outsider@test.local',
                                     'email': 'pdf.outsider@test.local'})
        group_internal.sudo().write({'user_ids': [(4, cls.member.id), (4, cls.outsider.id)]})
        cls.other_app = cls.env['saas.app'].sudo().create({
            'name': 'Other App', 'app_key': 'pdf-other', 'access_mode': 'group',
            'access_group_xmlid': 'base.group_user'})
        cls.member.partner_id.sudo().write(
            {'portal_app_ids': [(4, cls.app.id), (4, cls.other_app.id)]})

    def _token(self, user, app=None):
        def b64(b):
            return base64.urlsafe_b64encode(b).rstrip(b'=').decode()
        now = int(time.time())
        h = b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
        p = b64(json.dumps({'type': 'access', 'user_id': user.id, 'app_id': (app or self.app).id,
                            'iat': now, 'exp': now + 600}, separators=(',', ':')).encode())
        s = b64(hmac.new(self.SECRET.encode(), f'{h}.{p}'.encode(), hashlib.sha256).digest())
        return f'{h}.{p}.{s}'

    def _export(self, body=None, user=None, app=None, page=None):
        body = {'tab_key': 'main', 'filters': {}} if body is None else body
        return self.url_open(
            f'/api/v1/page/{(page or self.page).id}/export/pdf', data=json.dumps(body),
            headers={'Content-Type': 'application/json',
                     'Authorization': f'Bearer {self._token(user or self.member, app)}'})

    def _render_capture(self):
        captured = {}

        def fake(env, html, footer, **kw):
            captured.update(html=html, footer=footer, kw=kw)
            return b'%PDF-1.7 fake'
        return captured, patch(RENDER_PATH, side_effect=fake)


@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestPdfExportReadonlyCursor(HttpCase, _RouteBase):
    """The route runs on a READ-ONLY request cursor (the harness issues
    ``SET TRANSACTION READ ONLY``). Only the two audit entry points — which
    open an autonomous cursor in production — are replaced, so a 200 proves
    the collection, locks, timeouts and QWeb render never write on the
    request cursor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_route()

    def test_export_succeeds_without_writing_on_the_request_cursor(self):
        Log = type(self.env['dashboard.pdf.export.log'])
        events = []
        captured, render_patch = self._render_capture()
        with render_patch, \
                patch.dict(os.environ, {'POSTERRA_PDF_FINGERPRINT_KEY': 'k' * 32}), \
                patch.object(Log, 'log_started', lambda self, vals: events.append('started') or 1), \
                patch.object(Log, 'log_terminal',
                             lambda self, sid, ev, vals=None: events.append(ev) or 2):
            resp = self._export()
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertEqual(events, ['started', 'completed'])
        self.assertIn('Measures', captured['html'])


@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestPdfExportRoute(HttpCase, _RouteBase):
    """Full path including the autonomous-cursor audit writes. The harness's
    read-only simulation is off here because it refuses to open a read/write
    TEST cursor from a read-only one (production opens a separate real
    connection); TestPdfExportReadonlyCursor covers the read-only guarantee."""

    _registry_readonly_enabled = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_route()

    def test_happy_path_pdf_and_dataset(self):
        captured, p = self._render_capture()
        with p:
            resp = self._export({'tab_key': 'main', 'filters': {},
                                 'keynote': 'Focus on outreach', 'orientation': 'portrait'})
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertEqual(resp.headers['Content-Type'], 'application/pdf')
        self.assertIn('no-store', resp.headers['Cache-Control'])
        self.assertEqual(resp.headers.get('Vary'), 'Authorization')
        self.assertTrue(resp.content.startswith(b'%PDF'))
        html = captured['html']
        self.assertTrue(html.startswith('<!DOCTYPE html>'))
        self.assertIn('PDF App — Scorecard — Main', html)
        self.assertIn('Compliance Rate', html)
        self.assertIn('Focus on outreach', html)
        self.assertIn('Showing first 10 rows; more rows are available', html)
        self.assertLess(html.index('>30<'), html.index('>29<'))       # configured sort, before cap
        self.assertNotIn('>Hidden<', html)                              # hidden column dropped
        # charts: drawn in the render service from the server option
        self.assertIn('>Trend<', html)
        self.assertIn('id="pv-chart-data"', html)
        self.assertIn('data:text/javascript;base64,', html)
        self.assertEqual(html.count('</script>'), 3)                    # data value never closes a script
        self.assertIn('\\u003c/script\\u003e', html)
        marker = '<script type="application/json" id="pv-chart-data">'
        start = html.index(marker) + len(marker)
        specs = json.loads(html[start:html.index('</script>', start)])
        # Trend, mini gauge KPI, sparkline KPI, gauge + KPI breakdown
        self.assertEqual([s['id'] for s in specs], ['pvc1', 'pvc2', 'pvc3', 'pvc4'])
        trend, gauge, spark, breakdown = specs
        self.assertEqual([p['type'] for p in trend['option']['series']], ['bar'])
        self.assertEqual((gauge['width'], gauge['height']), (64, 64))
        self.assertEqual(gauge['option']['series'][0]['type'], 'gauge')
        self.assertEqual(spark['height'], 40)
        self.assertEqual(breakdown['option']['series'][0]['type'], 'gauge')
        self.assertTrue(all(s['progressive'] == 0 for spec in specs for s in spec['option']['series']))
        self.assertEqual(html.count('Chart not drawn'), 4)              # placeholder per chart box
        tiles = html[html.index('class="gauge-subs"'):]
        self.assertIn('Open Gaps', tiles[:600])
        self.assertIn('12%', tiles[:600])
        self.assertIn('Behind plan', html)                              # gauge alert line
        # mini gauge prints like the portal: ring + text, no duplicate CSS bar
        self.assertIn('class="kpi-split"', html)
        split = html[html.index('class="kpi-split"'):]
        self.assertIn('Gauge KPI', split[:1500])
        self.assertIn('48pp below benchmark', split[:1500])
        self.assertEqual(html.count('class="kpi-prog"'), 0)
        self.assertIn('1 widget of a type the PDF cannot print yet was not included: Region Map', html)
        self.assertIn('Snowflake KPI', html)                            # skipped notice
        self.assertNotIn('Not Printed', html)                           # pdf_include=False
        self.assertNotIn('Other Tab KPI', html)                         # other tab
        self.assertEqual(captured['kw']['orientation'], 'portrait')
        Log = self.env['dashboard.pdf.export.log'].sudo()
        started = Log.search([('event_type', '=', 'started'), ('page_id', '=', self.page.id)])
        self.assertEqual(len(started), 1)
        done = Log.search([('started_id', '=', started.id)])
        self.assertEqual(done.event_type, 'completed')
        self.assertTrue(done.keynote_used)
        self.assertNotIn('outreach', json.dumps(done.read()[0], default=str))

    def test_filter_values_never_logged(self):
        captured, p = self._render_capture()
        with p:
            resp = self._export({'tab_key': 'main', 'filters': {'region': 'SECRET-VALUE'}})
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        row = self.env['dashboard.pdf.export.log'].sudo().search([('event_type', '=', 'started')], limit=1)
        self.assertEqual(row.filter_params, 'region')
        self.assertNotIn('SECRET-VALUE', json.dumps(row.read()[0], default=str))
        self.assertEqual(len(row.input_fingerprint), 64)

    def test_permission_matrix(self):
        captured, p = self._render_capture()
        with p:
            self.assertEqual(self._export(user=self.outsider).status_code, 401)      # no app access
            self.assertEqual(self._export(app=self.other_app).status_code, 403)      # page of another app
            self.assertEqual(self._export({'tab_key': 'nope', 'filters': {}}).status_code, 400)
            self.assertEqual(self._export({'tab_key': 'main', 'filters': {},
                                           'keynote': 'x' * 2001}).status_code, 400)
            self.page.sudo().write({'group_ids': [(6, 0, [self.env.ref('base.group_system').id])]})
            self.assertEqual(self._export().status_code, 403)                       # page groups
            self.page.sudo().write({'group_ids': [(5, 0, 0)], 'pdf_export_enabled': False})
            self.assertEqual(self._export().status_code, 403)                       # disabled
        self.assertFalse(captured)

    def test_export_only_from_selected_tabs(self):
        self.page.sudo().write({'pdf_tab_ids': [(6, 0, [self.tab2.id])]})
        _captured, p = self._render_capture()
        with p:
            refused = self._export({'tab_key': 'main', 'filters': {}})
            allowed = self._export({'tab_key': 'other', 'filters': {}})
        self.assertEqual(refused.status_code, 403)
        self.assertIn('not enabled for this tab', refused.json()['error'])
        self.assertEqual(allowed.status_code, 200, allowed.text[:300])

    def test_invalid_scope_option_is_400(self):
        self.table.write({'scope_mode': 'independent', 'scope_query_mode': 'query'})
        _captured, p = self._render_capture()
        with p:
            resp = self._export({'tab_key': 'main', 'filters': {},
                                 'scope_options': {str(self.table.id): 999999}})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 'invalid_scope_option')

    def test_busy_when_another_export_holds_the_global_lock(self):
        from odoo.sql_db import db_connect
        other = db_connect(self.env.cr.dbname).cursor()
        try:
            other.execute('SELECT pg_advisory_lock(hashtext(%s))', ('posterra_pdf_export:global',))
            _captured, p = self._render_capture()
            with p:
                resp = self._export()
            self.assertEqual(resp.status_code, 429)
            self.assertIn('Another PDF export', resp.json()['error'])
        finally:
            other.execute('SELECT pg_advisory_unlock_all()')
            other.close()

    def test_render_failures_map_to_friendly_errors(self):
        from ..services.pdf_export.render_client import RenderError
        for code, status in (('render_busy', 429), ('render_unavailable', 503), ('render_timeout', 504)):
            with patch(RENDER_PATH, side_effect=RenderError(code)):
                resp = self._export()
            self.assertEqual(resp.status_code, status, code)
            self.assertEqual(resp.json()['code'], code)
        failed = self.env['dashboard.pdf.export.log'].sudo().search([('event_type', '=', 'failed')])
        self.assertEqual(sorted(failed.mapped('error_code')),
                         ['render_busy', 'render_timeout', 'render_unavailable'])

    def test_audit_append_only_retention_and_reconcile(self):
        Log = self.env['dashboard.pdf.export.log'].sudo()
        sid = Log.log_started({'user_id': self.member.id, 'app_id': self.app.id, 'page_id': self.page.id})
        rec = Log.browse(sid)
        with self.assertRaises(AccessError):
            rec.write({'error_code': 'x'})
        with self.assertRaises(AccessError):
            rec.unlink()
        from odoo.service.model import get_public_method
        for name in ('_gc_expired_pdf_export_logs', '_append_event', '_cron_reconcile'):
            with self.assertRaises(AccessError):
                get_public_method(Log, name)
        # one terminal event per export
        self.assertTrue(Log.log_terminal(sid, 'completed', {}))
        self.assertIsNone(Log.log_terminal(sid, 'failed', {}))
        # reconciler: an old started event without outcome → completion_unknown, once
        orphan = Log.log_started({'page_id': self.page.id})
        # create_date is naive UTC (Odoo convention) — backdate in UTC, not
        # the session time zone.
        self.env.cr.execute("UPDATE dashboard_pdf_export_log "
                            "SET create_date = (now() AT TIME ZONE 'UTC') - interval '30 minutes' "
                            "WHERE id = %s", (orphan,))
        Log._cron_reconcile()
        Log._cron_reconcile()
        closed = Log.search([('started_id', '=', orphan)])
        self.assertEqual(closed.mapped('event_type'), ['completion_unknown'])
        # retention purges old exports together with their terminal events
        self.env.cr.execute("UPDATE dashboard_pdf_export_log SET create_date = now() - interval '500 days' "
                            "WHERE id IN %s", ((sid, orphan),))
        Log._gc_expired_pdf_export_logs()
        self.assertFalse(Log.search([('id', 'in', [sid, orphan])]))
        self.assertFalse(Log.search([('started_id', 'in', [sid, orphan])]))


# ─────────────────────────────────────────────────────────────────────────
@tagged('post_install', '-at_install', 'posterra_pdf_export')
class TestPdfLayoutSync(HttpCase):

    def test_library_update_never_overwrites_instance_layout(self):
        env = self.env
        app = env['saas.app'].sudo().create({'name': 'Sync App', 'app_key': 'pdf-sync',
                                             'access_mode': 'group', 'access_group_xmlid': 'base.group_user'})
        nav = env['dashboard.nav.section'].sudo().create({'name': 'Sync', 'key': 'pdf_sync'})
        page = env['dashboard.page'].sudo().create({'name': 'Sync', 'key': 'pdf_sync', 'app_id': app.id,
                                                    'nav_section_id': nav.id})
        defn = env['dashboard.widget.definition'].sudo().create({
            'name': 'Def', 'chart_type': 'kpi', 'query_sql': 'SELECT 1 AS v', 'x_column': 'v',
            'pdf_include': True, 'pdf_col_span': '6'})
        from odoo.addons.dashboard_builder.controllers.builder_api import _build_widget_vals_from_definition
        vals = _build_widget_vals_from_definition(defn, {})
        self.assertEqual((vals['pdf_include'], vals['pdf_col_span']), (True, '6'))
        inst = env['dashboard.widget'].sudo().create({
            'name': 'Inst', 'page_id': page.id, 'definition_id': defn.id, 'chart_type': 'kpi',
            'query_type': 'sql', 'query_sql': 'SELECT 1 AS v', 'x_column': 'v',
            'pdf_include': False, 'pdf_col_span': '12'})
        self.authenticate('admin', 'admin')
        resp = self.url_open(f'/dashboard/designer/api/library/{defn.id}',
                             data=json.dumps({'pdf_include': False, 'pdf_col_span': '4',
                                              'pdf_page_break_before': True}),
                             headers={'Content-Type': 'application/json'}, method='PUT')
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        defn.invalidate_recordset()
        inst.invalidate_recordset()
        self.assertEqual((defn.pdf_include, defn.pdf_col_span, defn.pdf_page_break_before), (False, '4', True))
        self.assertEqual((inst.pdf_include, inst.pdf_col_span, inst.pdf_page_break_before), (False, '12', False))
        detail = self.url_open(f'/dashboard/designer/api/library/{defn.id}').json()
        payload = detail.get('definition', detail)
        self.assertEqual(payload.get('pdf_col_span'), '4')

    def test_page_template_round_trip(self):
        env = self.env
        app = env['saas.app'].sudo().create({'name': 'Tpl App', 'app_key': 'pdf-tpl',
                                             'access_mode': 'group', 'access_group_xmlid': 'base.group_user'})
        nav = env['dashboard.nav.section'].sudo().create({'name': 'Tpl', 'key': 'pdf_tpl'})
        page = env['dashboard.page'].sudo().create({
            'name': 'Tpl', 'key': 'pdf_tpl', 'app_id': app.id, 'nav_section_id': nav.id,
            'pdf_export_enabled': True, 'pdf_orientation': 'portrait', 'pdf_row_limit': 250,
            'pdf_max_columns': 12, 'pdf_title_template': '{page_name} report', 'pdf_keynote_enabled': False,
            'pdf_button_bg_color': '#0b6e4f', 'pdf_button_text_color': '#ffffff'})
        Tab = env['dashboard.page.tab'].sudo()
        Tab.create({'name': 'A', 'key': 'tab_a', 'page_id': page.id, 'sequence': 1})
        tab_b = Tab.create({'name': 'B', 'key': 'tab_b', 'page_id': page.id, 'sequence': 2})
        page.write({'pdf_tab_ids': [(6, 0, [tab_b.id])]})
        env['dashboard.widget'].sudo().create({
            'name': 'W', 'page_id': page.id, 'chart_type': 'kpi', 'query_type': 'sql',
            'query_sql': 'SELECT 1 AS v', 'x_column': 'v',
            'pdf_include': False, 'pdf_page_break_before': True, 'pdf_col_span': '8'})
        Template = env['dashboard.page.template'].sudo()
        cfg = Template.serialize_page(page)
        tpl = Template.create({'name': 'T', 'page_config': json.dumps(cfg, default=str)})
        new_page = tpl.create_page_from_template(app.id, nav.id, name_override='Tpl copy',
                                                 key_override='pdf_tpl_copy')
        new_page = new_page if hasattr(new_page, 'pdf_export_enabled') else env['dashboard.page'].browse(new_page)
        self.assertEqual((new_page.pdf_export_enabled, new_page.pdf_orientation, new_page.pdf_row_limit,
                          new_page.pdf_max_columns, new_page.pdf_title_template, new_page.pdf_keynote_enabled),
                         (True, 'portrait', 250, 12, '{page_name} report', False))
        self.assertEqual((new_page.pdf_button_bg_color, new_page.pdf_button_text_color), ('#0b6e4f', '#ffffff'))
        self.assertEqual(new_page.pdf_tab_ids.mapped('key'), ['tab_b'])
        self.assertEqual(new_page.pdf_tab_ids.page_id, new_page)          # re-linked to the NEW tabs
        # a template listing a tab key it does not define fails instead of widening to all tabs
        from odoo.exceptions import ValidationError
        bad = dict(cfg, page=dict(cfg['page'], pdf_tab_keys=['nope']))
        bad_tpl = Template.create({'name': 'T2', 'page_config': json.dumps(bad, default=str)})
        with self.assertRaises(ValidationError):
            bad_tpl.create_page_from_template(app.id, nav.id, name_override='Bad', key_override='pdf_tpl_bad')
        w = new_page.widget_ids
        self.assertEqual((w.pdf_include, w.pdf_page_break_before, w.pdf_col_span), (False, True, '8'))
