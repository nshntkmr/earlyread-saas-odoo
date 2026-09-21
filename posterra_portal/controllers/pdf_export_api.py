# -*- coding: utf-8 -*-
"""POST /api/v1/page/<page_id>/export/pdf — page PDF export (plan v5).

Order of checks (fail → JSON error, no PDF):
  1. JWT → user + app (``_get_api_user`` — also re-checks app access)
  2. page belongs to the app, is active, has ``pdf_export_enabled``
  3. ``page.group_ids`` (if set) — dashboard admins bypass like page load
  4. the requested tab is an active tab of the page
  5. body validation (sizes, types, keynote length)
  6. one active export cluster-wide + one per user (advisory xact locks on
     the read-only request cursor; busy → 429 with a friendly message)
  7. ``started`` audit event (fail-closed → 503)
Then collection under the time budget, render through the Gotenberg
service, and a terminal audit event in ``finally``.

The route is ``readonly=True``: it never writes on the request cursor.
Audit rows use an autonomous cursor (``dashboard.pdf.export.log``).
"""

import hashlib
import hmac
import json
import logging
import time

from odoo import http
from odoo.http import content_disposition, request

from .auth_api import _get_request_json, _json_response
from .portal import _is_dashboard_admin
from .widget_api import InvalidScopeOption, _get_api_user
from ..services.pdf_export import limits as L
from ..services.pdf_export.collector import Collector, select_widgets
from ..services.pdf_export.deadline import Deadline
from ..services.pdf_export.document import (build_view, filename_for, footer_html,
                                            render_html, utcnow)
from ..services.pdf_export.render_client import RenderError, render_pdf

_logger = logging.getLogger(__name__)

MESSAGES = {
    'busy_global': 'Another PDF export is being generated right now. Please try again in a moment.',
    'busy_user': 'Your previous PDF export is still being generated. Please wait for it to finish.',
    'render_busy': 'The PDF service is busy right now. Please try again in a moment.',
    'render_unavailable': 'The PDF service is not available right now. Please try again later.',
    'render_timeout': 'The PDF took too long to generate. Try fewer rows or a narrower filter.',
    'render_auth': 'The PDF service rejected the request. Please contact your administrator.',
    'render_failed': 'The PDF could not be generated. Please try again.',
    'size_limit': 'This report is too large to print. Lower the PDF row limit or narrow the filters.',
    'audit_unavailable': 'PDF export is temporarily unavailable. Please try again later.',
    'invalid_scope_option': 'A widget view selected on screen is no longer available. '
                            'Reload the page and try again.',
    'internal_error': 'The PDF could not be generated. Please try again.',
}
STATUS = {'busy_global': 429, 'busy_user': 429, 'render_busy': 429, 'render_unavailable': 503,
          'render_timeout': 504, 'render_auth': 502, 'render_failed': 502, 'size_limit': 413,
          'audit_unavailable': 503, 'invalid_scope_option': 400, 'internal_error': 500}


def _error(status, message, code=None):
    return _json_response({'error': message, 'code': code or '', 'status': status}, status=status)


def _coded_error(code):
    return _error(STATUS.get(code, 500), MESSAGES.get(code, MESSAGES['internal_error']), code)


def _str_value(v, max_len=4000):
    if v is None:
        return ''
    if isinstance(v, (list, tuple)):
        v = ','.join(str(x) for x in v if x is not None)
    return str(v)[:max_len]


def _int_keyed(obj, cast):
    out = {}
    if not isinstance(obj, dict):
        return out
    for k, v in list(obj.items())[:L.MAX_WIDGET_PARAM_ENTRIES]:
        try:
            key = int(k)
        except (TypeError, ValueError):
            continue
        val = cast(v)
        if val not in (None, '', {}):
            out[key] = val
    return out


def _positive_int(v):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _wf_dict(v):
    if not isinstance(v, dict):
        return {}
    return {str(k)[:120]: _str_value(val, 1000) for k, val in list(v.items())[:50]
            if str(k).startswith('_wf_')}


def parse_body(body, page):
    """Validate the JSON body. Returns (data, error_message)."""
    if not isinstance(body, dict):
        return None, 'Invalid request body.'
    filters = body.get('filters') or {}
    if not isinstance(filters, dict) or len(filters) > 200:
        return None, 'Invalid filters.'
    keynote = body.get('keynote') or ''
    if not isinstance(keynote, str):
        return None, 'Invalid keynote.'
    keynote = keynote.strip()
    if len(keynote) > L.KEYNOTE_MAX_CHARS:
        return None, f'The keynote is too long (maximum {L.KEYNOTE_MAX_CHARS:,} characters).'
    orientation = body.get('orientation') or page.pdf_orientation or 'landscape'
    if orientation not in ('landscape', 'portrait'):
        orientation = page.pdf_orientation or 'landscape'
    return {
        'tab_key': str(body.get('tab_key') or '')[:120],
        'filters': {str(k)[:120]: _str_value(v) for k, v in filters.items()},
        'scope_options': _int_keyed(body.get('scope_options'), _positive_int),
        'scope_values': _int_keyed(body.get('scope_values'), lambda v: _str_value(v, 500)),
        'widget_filters': _int_keyed(body.get('widget_filters'), _wf_dict),
        'keynote': keynote if page.pdf_keynote_enabled else '',
        'orientation': orientation,
    }, None


def _user_in_page_groups(user, page):
    if not page.group_ids:
        return True
    groups = getattr(user, 'all_group_ids', None)
    if groups is None:
        groups = getattr(user, 'group_ids', None) or user.groups_id
    return bool(groups & page.group_ids)


def _try_lock(cr, name):
    cr.execute('SELECT pg_try_advisory_xact_lock(hashtext(%s))', (f'{L.LOCK_NAMESPACE}:{name}',))
    return bool(cr.fetchone()[0])


def input_fingerprint(env, page, data, widgets):
    key, version = L.fingerprint_key(env)
    canon = {
        'page_id': page.id, 'tab_key': data['tab_key'],
        'filters': data['filters'],
        'scope_options': {str(k): v for k, v in sorted(data['scope_options'].items())},
        'scope_values': {str(k): v for k, v in sorted(data['scope_values'].items())},
        'widget_filters': {str(k): v for k, v in sorted(data['widget_filters'].items())},
        'orientation': data['orientation'], 'keynote_present': bool(data['keynote']),
        'config': {'page': str(page.write_date or ''),
                   'widgets': str(max(widgets.mapped('write_date')) if widgets else '')},
    }
    msg = json.dumps(canon, sort_keys=True, separators=(',', ':'), default=str).encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest(), version


def _pdf_response(pdf, filename, incomplete):
    headers = [
        ('Content-Type', 'application/pdf'),
        ('Content-Disposition', content_disposition(filename)),
        ('Content-Length', str(len(pdf))),
        ('Cache-Control', 'private, no-store, no-cache, must-revalidate'),
        ('Pragma', 'no-cache'),
        ('Vary', 'Authorization'),
        ('X-Content-Type-Options', 'nosniff'),
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Headers', 'Authorization, Content-Type'),
        ('Access-Control-Allow-Methods', 'POST, OPTIONS'),
        ('Access-Control-Expose-Headers', 'Content-Disposition, X-PDF-Incomplete'),
    ]
    if incomplete:
        headers.append(('X-PDF-Incomplete', '1'))
    return request.make_response(pdf, headers=headers)


class PosterraPdfExportAPI(http.Controller):

    @http.route('/api/v1/page/<int:page_id>/export/pdf', type='http', auth='none',
                methods=['POST', 'OPTIONS'], csrf=False, readonly=True)
    def api_page_export_pdf(self, page_id, **kw):
        if request.httprequest.method == 'OPTIONS':
            return _json_response({})
        started_at = time.monotonic()
        env = request.env
        try:
            user, app = _get_api_user()
        except ValueError as exc:
            return _error(401, str(exc))

        length = request.httprequest.content_length or 0
        if length > L.MAX_REQUEST_BYTES:
            return _error(413, 'The export request is too large.')

        page = env['dashboard.page'].sudo().browse(page_id)
        if not page.exists():
            return _error(404, 'Page not found.')
        if page.app_id.id != app.id:
            return _error(403, 'Page does not belong to your app.')
        if not page.is_active or not page.pdf_export_enabled:
            return _error(403, 'PDF export is not enabled for this page.')
        if not _is_dashboard_admin(user) and not _user_in_page_groups(user, page):
            return _error(403, 'You do not have access to this page.')

        data, problem = parse_body(_get_request_json(), page)
        if problem:
            return _error(400, problem)
        tabs = page.tab_ids.filtered(lambda t: t.is_active).sorted(lambda t: (t.sequence, t.id))
        tab = env['dashboard.page.tab']
        if tabs:
            tab = tabs.filtered(lambda t: t.key == data['tab_key'])[:1]
            if not tab:
                return _error(400, 'Unknown or inactive tab.')
            if not page.pdf_tab_allowed(tab):
                return _error(403, 'PDF export is not enabled for this tab.')

        cr = env.cr
        if not _try_lock(cr, f'user:{user.id}'):
            return _coded_error('busy_user')
        if not _try_lock(cr, 'global'):
            return _coded_error('busy_global')

        Log = env['dashboard.pdf.export.log'].sudo()
        deadline = Deadline(L.total_budget_s(env))
        widgets = select_widgets(page, tab or None)
        fingerprint, key_version = input_fingerprint(env, page, data, widgets)
        base_vals = {
            'user_id': user.id, 'app_id': app.id, 'page_id': page.id,
            'tab_key': tab.key if tab else '', 'orientation': data['orientation'],
            'input_fingerprint': fingerprint, 'fingerprint_key_version': key_version,
            'filter_params': ','.join(sorted(k for k, v in data['filters'].items() if v))[:2000],
            'widget_ids': ','.join(str(i) for i in widgets.ids)[:2000],
            'keynote_used': bool(data['keynote']),
        }
        try:
            started_id = Log.log_started(base_vals)
        except Exception as exc:
            _logger.error('PDF export: started audit event failed (%s); refusing export',
                          type(exc).__name__)
            return _coded_error('audit_unavailable')

        outcome = {'event': 'failed', 'vals': {'error_code': 'internal_error'}}
        response = None
        previous_timeout = None
        try:
            cr.execute('SHOW statement_timeout')
            previous_timeout = cr.fetchone()[0]
            collect_ms_budget = max(1000, int(deadline.collect_remaining() * 1000))
            cr.execute('SET LOCAL statement_timeout = %s', (f'{collect_ms_budget}ms',))
            try:
                dataset = Collector(env, page, tab or None, user, app, data, deadline).collect()
            finally:
                try:
                    cr.execute('SET LOCAL statement_timeout = %s', (previous_timeout,))
                except Exception:
                    # Transaction already aborted by a timeout outside a
                    # savepoint: the export fails below; nothing to restore.
                    pass
            generated_at = utcnow()
            view = build_view(env, page=page, tab=tab or None, app=app, user=user, dataset=dataset,
                              keynote=data['keynote'], orientation=data['orientation'],
                              paper=page.pdf_paper or 'letter', generated_at=generated_at)
            html = render_html(env, view)
            render_started = time.monotonic()
            pdf = render_pdf(env, html, footer_html(page, app), paper=page.pdf_paper or 'letter',
                             orientation=data['orientation'], timeout_s=deadline.render_timeout())
            render_ms = int((time.monotonic() - render_started) * 1000)
            notices = dataset['notices']
            incomplete = bool(notices['failed'] or notices['not_loaded'])
            outcome = {'event': 'completed', 'vals': {
                'bytes': len(pdf), 'collect_ms': dataset['collect_ms'], 'render_ms': render_ms,
                'notices_json': json.dumps({k: [i['widget_id'] for i in v] for k, v in notices.items()}),
                'row_totals_json': json.dumps({str(b['widget_id']): [b.get('row_shown'), bool(b.get('more_available'))]
                                               for b in dataset['blocks'] if b.get('kind') == 'table'}),
                'scope_option_ids': ','.join(str(b['scope_option_id']) for b in dataset['blocks']
                                             if b.get('scope_option_id'))[:2000],
                'error_code': 'incomplete' if incomplete else '',
            }}
            response = _pdf_response(pdf, filename_for(page, tab or None, generated_at), incomplete)
        except InvalidScopeOption:
            outcome['vals']['error_code'] = 'invalid_scope_option'
            response = _coded_error('invalid_scope_option')
        except RenderError as exc:
            outcome['vals']['error_code'] = exc.code
            response = _coded_error(exc.code)
        except Exception as exc:
            _logger.exception('PDF export failed (page=%s): %s', page.id, type(exc).__name__)
            outcome['vals']['error_code'] = 'internal_error'
            response = _coded_error('internal_error')
        finally:
            outcome['vals']['duration_ms'] = int((time.monotonic() - started_at) * 1000)
            try:
                Log.log_terminal(started_id, outcome['event'], dict(base_vals, **outcome['vals']))
            except Exception as exc:
                # The PDF (or error) is still returned; the reconciler records
                # completion_unknown for this export later.
                _logger.error('PDF export: terminal audit event failed for started id %s (%s): '
                              'terminal_log_failed', started_id, type(exc).__name__)
        return response
