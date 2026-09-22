# -*- coding: utf-8 -*-
"""Client for the Gotenberg render service (own Deployment + Service).

POSTs ``index.html`` (+ ``footer.html``) to ``/forms/chromium/convert/html``
and returns the PDF bytes. Gotenberg 8.37 behaviour verified in phase 0:
429 when its queue is full (queue size counts the in-flight conversion), 503
on its own ``--api-timeout``, 413 over ``--api-body-limit``, 401 without
basic-auth credentials.

The wall-clock budget is enforced here: ``requests``' read timeout measures
socket inactivity, not total time, so the elapsed time is checked after the
call as well (``RenderError('render_timeout')``).
"""

import logging
import time

import requests

from .limits import CONNECT_TIMEOUT_S, MAX_HTML_BYTES, render_settings

_logger = logging.getLogger(__name__)

PAPER_SIZES_IN = {'letter': (8.5, 11.0), 'a4': (8.27, 11.69)}
MARGIN_LEFT_IN = MARGIN_RIGHT_IN = 0.4   # document.py sizes charts from these
# No wait condition is sent: charts are drawn synchronously before the page's
# load event (see charts.py), so a renderer without JavaScript still prints
# the page (chart boxes then show their placeholder) instead of timing out.


class RenderError(Exception):
    """``code`` is a stable, user-safe error code (never the upstream body)."""

    def __init__(self, code, status=None):
        super().__init__(code)
        self.code = code
        self.status = status


def paper_form(paper, orientation):
    w, h = PAPER_SIZES_IN.get(paper or 'letter', PAPER_SIZES_IN['letter'])
    if orientation == 'landscape':
        w, h = h, w
    return {
        'paperWidth': f'{w}', 'paperHeight': f'{h}',
        'marginTop': '0.45', 'marginBottom': '0.6',
        'marginLeft': f'{MARGIN_LEFT_IN}', 'marginRight': f'{MARGIN_RIGHT_IN}',
        'printBackground': 'true', 'preferCssPageSize': 'false',
        'generateDocumentOutline': 'false',
    }


def render_pdf(env, html, footer_html, *, paper, orientation, timeout_s,
               clock=time.monotonic, session=None):
    """Return PDF bytes or raise ``RenderError``."""
    body = html.encode('utf-8')
    footer = footer_html.encode('utf-8')
    if len(body) + len(footer) > MAX_HTML_BYTES:
        raise RenderError('size_limit', 413)
    if timeout_s < 1.0:
        raise RenderError('render_timeout', 504)
    url, auth = render_settings(env)
    files = [
        ('files', ('index.html', body, 'text/html')),
        ('files', ('footer.html', footer, 'text/html')),
    ]
    started = clock()
    http = session or requests
    try:
        resp = http.post(
            f'{url}/forms/chromium/convert/html',
            files=files, data=paper_form(paper, orientation), auth=auth,
            timeout=(CONNECT_TIMEOUT_S, timeout_s))
    except requests.exceptions.ConnectTimeout:
        raise RenderError('render_unavailable', 503)
    except requests.exceptions.ReadTimeout:
        raise RenderError('render_timeout', 504)
    except requests.exceptions.RequestException as exc:
        _logger.warning('PDF render service unreachable: %s', type(exc).__name__)
        raise RenderError('render_unavailable', 503)
    elapsed = clock() - started
    status = resp.status_code
    if status == 200 and resp.content[:5] == b'%PDF-':
        if elapsed > timeout_s + 0.5:
            # Finished, but past the budget the gateway allows — fail closed
            # rather than return after the caller's deadline.
            raise RenderError('render_timeout', 504)
        return resp.content
    code = {
        429: 'render_busy',
        503: 'render_timeout',
        413: 'size_limit',
        401: 'render_auth',
        403: 'render_auth',
    }.get(status, 'render_failed')
    _logger.warning('PDF render failed: status=%s code=%s', status, code)
    raise RenderError(code, status)
