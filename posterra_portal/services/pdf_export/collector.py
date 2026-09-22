# -*- coding: utf-8 -*-
"""Build ONE immutable report dataset for the current tab (plan v5 §3–§4).

Every block comes from the SAME display paths the dashboard uses:
``_build_portal_ctx`` (filters, provider scope, tab scoping), the widget's
own filters, the shared ``_resolve_widget_scope`` (strict), then
``execute_option_sql`` / ``get_portal_data`` — with
``pv_execution_limits`` in the context so tables are bounded in the
database, the configured default sort is applied before truncation and
every statement gets a per-step timeout. Never ``download_sql`` /
``get_download_data``.

The dataset is freshly collected at export time (not a historical snapshot).
Templates and (later) AI commentary read only this dict; no section queries
on its own. Request-bound (uses ``odoo.http.request`` through the widget API
helpers); call it from the export controller only.
"""

import copy
import json
import logging
import time

from .cell_format import client_value, header_label, printable_columns, render_cell
from .charts import (KPI_MINI_CHART_VARIANTS, PRINTABLE_CHART_TYPES, chart_option,
                     printable_option)
from .limits import clamp_column_limit, clamp_row_limit

_logger = logging.getLogger(__name__)

# chart_type → printed block kind: headers, KPIs, tables and standard ECharts
# charts (drawn in the render service from the server's chart option).
V1_KINDS = {
    'record_header': 'record_header',
    'kpi': 'kpi',
    'status_kpi': 'kpi',
    'table': 'table',
    **{ct: 'chart' for ct in PRINTABLE_CHART_TYPES},
}
UNSUPPORTED_ENGINES = ('snowflake',)   # decision V1: skipped, never queried


def _engine(source):
    conn = source.connection_id if source else None
    return (conn.engine or '') if conn else 'postgres_local'


def _is_timeout_message(msg):
    text = (msg or '').lower()
    return ('statement timeout' in text or 'canceling statement' in text
            or 'timeout_exceeded' in text or 'timeout exceeded' in text)


def effective_column_defs(widget, option):
    """Column config the display path will use — mirrors
    ``execute_option_sql`` (option → first sibling with config) and
    ``_build_table_data`` (widget-level)."""
    raw = ''
    if option:
        raw = option.table_column_config or ''
        if not raw:
            for sibling in (widget.scope_option_ids - option).sorted('sequence'):
                if sibling.table_column_config:
                    raw = sibling.table_column_config
                    break
    if not raw:
        raw = widget.table_column_config or ''
    try:
        cols = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        cols = []
    return cols if isinstance(cols, list) else []


def split_total_rows(rows, visual_config):
    """``(body_rows, total_rows)`` — mirror of ``splitTotalRows`` in the
    portal's DataTable.jsx: a row is a total row when
    ``str(row[column]) == str(value)`` on the RAW row value (hidden columns
    included), never on rendered text. Unset / blank → all rows are body."""
    vc = visual_config if isinstance(visual_config, dict) else {}
    col = vc.get('tableTotalRowColumn')
    val = vc.get('tableTotalRowValue')
    col = col.strip() if isinstance(col, str) else ''
    if not col or val is None or val == '':
        return list(rows or []), []
    want = str(val)
    body, totals = [], []
    for r in rows or []:
        v = r.get(col) if isinstance(r, dict) else None
        (totals if (v is not None and str(v) == want) else body).append(r)
    return body, totals


def select_widgets(page, tab):
    """Widgets printed for this tab, in screen order: page-summary grid first,
    then the tab-content grid (tab widgets + page-wide widgets)."""
    active = page.widget_ids.filtered(lambda w: w.is_active)
    key = lambda w: (w.sequence, w.id)
    summary = active.filtered(lambda w: w.render_region == 'page_summary').sorted(key)
    content = active.filtered(
        lambda w: w.render_region != 'page_summary'
        and (not w.tab_id or (tab and w.tab_id.id == tab.id))).sorted(key)
    return summary + content


class Collector:
    """One export's collection pass. ``request_data`` is the validated JSON
    body; ``deadline`` a ``Deadline``."""

    def __init__(self, env, page, tab, user, app, request_data, deadline):
        self.env = env
        self.page = page
        self.tab = tab
        self.user = user
        self.app = app
        self.req = request_data
        self.deadline = deadline
        self.row_limit = clamp_row_limit(page.pdf_row_limit)
        self.col_limit = clamp_column_limit(page.pdf_max_columns)
        self._ctx_memo = {}
        self.notices = {'omitted': [], 'skipped_engine': [], 'failed': [],
                        'not_loaded': [], 'sort_not_applied': []}

    # ── context ────────────────────────────────────────────────────────
    def _widget_kw(self, w):
        kw = dict(self.req['filters'])
        opt_id = self.req['scope_options'].get(w.id)
        if opt_id:
            kw['_scope_option_id'] = str(opt_id)
        scope_val = self.req['scope_values'].get(w.id)
        if scope_val and w.scope_mode in ('dependent', 'independent'):
            pname = ''
            if w.scope_mode == 'dependent' and w.scope_filter_id:
                pname = w.scope_filter_id.param_name or w.scope_filter_id.field_name or ''
            elif w.scope_mode == 'independent':
                pname = w.scope_param_name or ''
            if pname:
                kw[pname] = scope_val
        kw.update(self.req['widget_filters'].get(w.id) or {})
        return kw

    def _portal_ctx(self, w, kw):
        from ...controllers.widget_api import _build_portal_ctx
        region = 'summary' if w.render_region == 'page_summary' else (
            f'tab:{w.tab_id.id}' if w.tab_id else 'global')
        ctx_kw = {k: v for k, v in kw.items() if k != '_scope_option_id'}
        memo_key = (region, json.dumps(ctx_kw, sort_keys=True, default=str))
        if memo_key not in self._ctx_memo:
            self._ctx_memo[memo_key] = _build_portal_ctx(
                self.page, self.user, self.app, dict(ctx_kw), consumer=w)
        base = self._ctx_memo[memo_key]
        ctx = dict(base)                                  # never share mutable sql_params
        ctx['sql_params'] = dict(base.get('sql_params') or {})
        ctx['filter_values_by_name'] = dict(base.get('filter_values_by_name') or {})
        return ctx

    # ── one widget ─────────────────────────────────────────────────────
    def _collect_widget(self, w):
        from ...controllers.widget_api import _apply_widget_filters, _resolve_widget_scope
        kind = V1_KINDS.get(w.chart_type)
        base = {'widget_id': w.id, 'name': w.name or '', 'chart_type': w.chart_type,
                'kind': kind, 'col_span': w.pdf_col_span or w.col_span or '12',
                'page_break_before': bool(w.pdf_page_break_before)}
        if not kind:
            self.notices['omitted'].append({'widget_id': w.id, 'name': w.name, 'chart_type': w.chart_type})
            return None
        kw = self._widget_kw(w)
        option, binding = _resolve_widget_scope(
            w, kw.get('_scope_option_id'), kw, strict=True)
        source = (option.schema_source_id if option else None) or w.schema_source_id
        if _engine(source) in UNSUPPORTED_ENGINES:
            self.notices['skipped_engine'].append({'widget_id': w.id, 'name': w.name})
            return None
        if not self.deadline.can_collect():
            self.notices['not_loaded'].append({'widget_id': w.id, 'name': w.name})
            return None

        ctx = self._portal_ctx(w, kw)
        ctx = _apply_widget_filters(w, kw, ctx)
        if binding and not option:
            ctx['sql_params'][binding[0]] = binding[1]

        column_defs = effective_column_defs(w, option) if kind == 'table' else []
        from ...utils.query_executors.bounded import order_by_from_column_defs
        limits = {'timeout_s': self.deadline.step_timeout(),
                  'max_rows': self.row_limit if kind == 'table' else None,
                  'order_by': order_by_from_column_defs(column_defs) if kind == 'table' else None}
        report = {}
        target = (option or w).with_context(pv_execution_limits=limits,
                                            pv_execution_report=report)
        t0 = time.monotonic()
        data = target.execute_option_sql(ctx) if option else target.get_portal_data(ctx)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        if not isinstance(data, dict) or data.get('error'):
            reason = 'timeout' if isinstance(data, dict) and _is_timeout_message(data.get('error')) else 'error'
            _logger.warning('PDF export: widget %s failed (%s)', w.id, reason)
            self.notices['failed'].append({'widget_id': w.id, 'name': w.name, 'reason': reason})
            return dict(base, status='failed', reason=reason, elapsed_ms=elapsed_ms)
        block = dict(base, status='ok', elapsed_ms=elapsed_ms,
                     scope_option_id=option.id if option else None,
                     scope_value=binding[1] if (binding and not option) else None)
        if kind == 'table':
            block.update(self._table_block(data, report))
            if report.get('sort_requested') and not report.get('sort_applied'):
                self.notices['sort_not_applied'].append({'widget_id': w.id, 'name': w.name})
        elif kind == 'chart':
            option = chart_option(data)
            if not option:
                # e.g. a gauge style drawn by a custom React widget
                self.notices['omitted'].append({'widget_id': w.id, 'name': w.name,
                                                'chart_type': w.chart_type})
                return None
            block['option'] = printable_option(option)
            block['height'] = w.chart_height or 350
            if w.chart_type == 'gauge_kpi':
                # GaugeKPI.jsx shows sub-KPI tiles and an alert line under the ring
                block['sub_kpis'] = [
                    {'label': str(s.get('label') or ''), 'value': str(s.get('value') or ''),
                     'sub_label': str(s.get('sub_label') or '')}
                    for s in (data.get('sub_kpis') or []) if isinstance(s, dict)]
                block['alert_text'] = str(data.get('alert_text') or '')
        else:
            block['payload'] = data
            if kind == 'kpi' and (data.get('kpi_variant') or '') in KPI_MINI_CHART_VARIANTS:
                mini = chart_option(data)
                if mini:
                    block['mini_option'] = printable_option(mini)
        return block

    def _table_block(self, data, report):
        column_defs = data.get('columnDefs') or []
        rows = data.get('rowData') or []
        more = bool(report.get('more_available'))
        if len(rows) > self.row_limit:            # ORM tables / defence in depth
            rows, more = rows[:self.row_limit], True
        # Total row (visual_config.tableTotalRowColumn / tableTotalRowValue):
        # the portal grid pins matching rows to the bottom in bold; the PDF
        # prints them last, bold, after the body rows regardless of the sort.
        # Blank setting → every row is a body row (byte-identical output).
        body_rows, total_rows = split_total_rows(rows, data.get('visual_config'))
        cols, total_cols = printable_columns(column_defs, self.col_limit)

        def _print(row_list):
            printed = []
            for r in row_list:
                crow = {k: client_value(v) for k, v in r.items()}
                printed.append([render_cell(c, crow) for c in cols])
            return printed

        return {
            'columns': [{'label': header_label(c)} for c in cols],
            'rows': _print(body_rows),
            'total_rows': _print(total_rows),
            'row_shown': len(rows),
            'more_available': more,
            'columns_shown': len(cols),
            'columns_total': total_cols,
        }

    # ── labels / badges ────────────────────────────────────────────────
    def _providers(self):
        if self.app.access_mode != 'hha_provider':
            return None
        from ...controllers.portal import _get_providers_for_user
        return _get_providers_for_user(self.user)

    def filter_lines(self):
        """``[{label, value_label}]`` for visible filters applying to this
        tab that have a value. Labels resolved server-side (never trusted
        from the client); any failure prints the raw value."""
        out = []
        filters = self.page.filter_ids.filtered(
            lambda f: f.is_active and f.is_visible
            and (not f.tab_id or (self.tab and f.tab_id.id == self.tab.id))
        ).sorted(lambda f: (f.sequence, f.id))
        providers = None
        for f in filters:
            key = f.param_name or f.field_name
            raw = (self.req['filters'].get(key) or '').strip() if key else ''
            if not raw or raw.lower() == 'all':
                continue
            values = [v.strip() for v in raw.split(',') if v.strip()] if f.is_multiselect else [raw]
            labels = {}
            if self.deadline.can_collect():
                try:
                    if providers is None:
                        providers = self._providers() or self.env['hha.provider']
                    pids = providers.ids if (f.scope_to_user_hha and providers) else None
                    if f.ui_type == 'remote_autocomplete':
                        opts = f.hydrate_options(values, provider_ids=pids)
                    else:
                        opts = f.get_options(provider_ids=pids)
                    labels = {str(o.get('value')): str(o.get('label')) for o in (opts or [])}
                except Exception as exc:   # labels are cosmetic; never fail the export
                    _logger.info('PDF export: label lookup failed for filter %s: %s',
                                 f.id, type(exc).__name__)
            out.append({'param': key, 'label': f.label or key,
                        'value_label': ', '.join(labels.get(v, v) for v in values)})
        return out

    def badges(self):
        from ...controllers.widget_api import _build_portal_ctx
        badges = self.page.badge_ids.filtered(lambda b: b.is_active).sorted(lambda b: (b.sequence, b.id))
        if not badges or not self.deadline.can_collect():
            return []
        try:
            ctx = _build_portal_ctx(self.page, self.user, self.app,
                                    dict(self.req['filters']), consumer=self.page)
        except Exception as exc:
            _logger.info('PDF export: badge ctx failed: %s', type(exc).__name__)
            return []
        out = []
        for b in badges:
            source = getattr(b, 'schema_source_id', None)
            if _engine(source) in UNSUPPORTED_ENGINES or not self.deadline.can_collect():
                continue
            try:
                value = b.execute_badge_sql(copy.deepcopy(ctx))
            except Exception as exc:
                _logger.info('PDF export: badge %s failed: %s', b.id, type(exc).__name__)
                continue
            if value not in (None, ''):
                out.append({'value': str(value), 'color': b.text_color or ''})
        return out

    # ── all ────────────────────────────────────────────────────────────
    def collect(self):
        started = time.monotonic()
        blocks = []
        for w in select_widgets(self.page, self.tab):
            if not w.pdf_include:
                continue
            block = self._collect_widget(w)
            if block:
                blocks.append(block)
        filters = self.filter_lines()
        badges = self.badges()
        return {
            'blocks': blocks,
            'filters': filters,
            'badges': badges,
            'notices': self.notices,
            'row_limit': self.row_limit,
            'column_limit': self.col_limit,
            'collect_ms': int((time.monotonic() - started) * 1000),
        }
