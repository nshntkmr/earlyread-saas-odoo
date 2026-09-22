# -*- coding: utf-8 -*-
"""Charts in the page PDF (user decision 2026-09-21: option 1 — draw charts
inside the render service from the SERVER's chart options).

The portal's ``EChartWidget`` passes the server's ``echart_option`` to
``echarts.setOption`` unchanged, so drawing the same option with the same
ECharts version in the PDF reproduces the on-screen chart from server data
(never from browser images).

* The library is the vendored copy ``static/lib/echarts/echarts.min.js`` —
  the SAME version the portal bundle resolves (``node_modules`` is not in the
  production image). It is loaded through a ``data:`` URI: no network, and no
  chance of library text breaking out of an inline ``<script>``.
* Chart options are embedded as JSON with ``<``, ``>``, ``&`` escaped, so a
  data value can never close the script element.
* The render service therefore runs WITH JavaScript; every network
  sub-request, private IP and local file outside the request directory stays
  blocked (containment re-verified with JavaScript on).
* Drawing is synchronous: animation and progressive rendering are switched
  off, and the scripts sit at the end of the body, so every chart is drawn
  before the page's load event — the render service needs no wait condition.
  (Verified with a 5,000-point line chart.) Each chart box starts with a
  "Chart not drawn" placeholder that the script clears: a renderer running
  WITHOUT JavaScript still produces the PDF, and the boxes say why they are
  empty instead of the export failing.
"""

import base64
import copy
import json
import os

from markupsafe import Markup

ECHARTS_VERSION = '5.6.0'
# chart_type values whose display payload is a plain ECharts option
# (``echart_json``). Gauges only when their style produces one (the bullet /
# RAG / percentile styles are custom React widgets → "not included").
# ``gauge_kpi`` also prints its sub-KPI tiles and alert line (GaugeKPI.jsx).
# Keep in sync with the Designer's PdfExportOptions.jsx PRINTED_TYPES.
PRINTABLE_CHART_TYPES = frozenset({
    'bar', 'line', 'pie', 'donut', 'radar', 'scatter', 'heatmap', 'sankey', 'gauge', 'gauge_kpi'})
# KPI variants that carry a small ECharts drawing inside the card (the
# ``progress`` variant's bar is printed with CSS instead — no script needed).
KPI_MINI_CHART_VARIANTS = frozenset({'sparkline', 'mini_gauge'})

_LIB_REL = ('static', 'lib', 'echarts', 'echarts.min.js')
_LIB_CACHE = {}


def echarts_script_src():
    """``data:`` URI of the vendored ECharts build (cached per process)."""
    if 'src' not in _LIB_CACHE:
        module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(module_dir, *_LIB_REL), 'rb') as fh:
            data = fh.read()
        _LIB_CACHE['src'] = 'data:text/javascript;base64,' + base64.b64encode(data).decode('ascii')
    return _LIB_CACHE['src']


def chart_option(payload):
    """The ECharts option of a display payload, or None."""
    if not isinstance(payload, dict):
        return None
    raw = payload.get('echart_json')
    if isinstance(raw, str) and raw.strip():
        try:
            option = json.loads(raw)
        except (ValueError, TypeError):
            return None
        return option if isinstance(option, dict) and option else None
    option = payload.get('echart_option')
    return option if isinstance(option, dict) and option else None


def printable_option(option):
    """Copy of ``option`` for a static page: no animation, no progressive
    (multi-frame) rendering, and controls that only make sense on screen
    (toolbox, sliders) hidden. The data range a slider selects is kept."""
    opt = copy.deepcopy(option)
    opt['animation'] = False
    series = opt.get('series')
    for s in (series if isinstance(series, list) else [series] if isinstance(series, dict) else []):
        if isinstance(s, dict):
            s['progressive'] = 0
            s['animation'] = False
    for key in ('toolbox',):
        if key in opt:
            items = opt[key] if isinstance(opt[key], list) else [opt[key]]
            for item in items:
                if isinstance(item, dict):
                    item['show'] = False
    zooms = opt.get('dataZoom')
    for z in (zooms if isinstance(zooms, list) else [zooms] if isinstance(zooms, dict) else []):
        if isinstance(z, dict) and z.get('type', 'slider') == 'slider':
            z['show'] = False
    return opt


def embed_json(value):
    """JSON safe to place inside a ``<script type="application/json">``."""
    text = json.dumps(value, separators=(',', ':'), default=str, ensure_ascii=False)
    return (text.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
            .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))


CHART_PLACEHOLDER = 'Chart not drawn'

_INIT_SCRIPT = (
    "(function(){"
    "try{"
    "var el=document.getElementById('pv-chart-data');"
    "if(!el||!window.echarts){return;}"
    "var specs=JSON.parse(el.textContent||'[]');"
    "specs.forEach(function(s){"
    "var d=document.getElementById(s.id);"
    "if(!d){return;}"
    "try{"
    "d.textContent='';d.className=d.className.replace('pv-chart-pending','');"
    "var c=window.echarts.init(d,null,{renderer:'svg',width:s.width,height:s.height});"
    "c.setOption(s.option);"
    "}catch(e){d.textContent='Chart unavailable';d.className+=' pv-chart-error';}"
    "});"
    "}catch(e){}"
    "})();"
)


def chart_scripts(specs):
    """Script block placed at the end of the PDF body: the vendored library,
    the chart specs and the synchronous drawing script. Empty when the page
    has no charts (such PDFs carry no script at all)."""
    if not specs:
        return Markup('')
    return Markup(
        '<script src="%s"></script>'
        '<script type="application/json" id="pv-chart-data">%s</script>'
        '<script>%s</script>'
    ) % (echarts_script_src(), Markup(embed_json(specs)), Markup(_INIT_SCRIPT))
