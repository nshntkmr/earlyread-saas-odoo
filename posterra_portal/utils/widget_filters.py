# -*- coding: utf-8 -*-
"""Widget-level filter value injection.

Pure helpers (no Odoo imports) shared by the portal initial render and every
widget API endpoint. A widget can declare N filters of its own
(``dashboard.widget.filter``); their values reach the widget's SQL through the
same ``%(param)s`` / ``[[ ... ]]`` contract page filters use, but are scoped to
ONE widget: the client sends them as ``_wf_<param>=<value>`` request params
and this module merges them into a COPY of that widget's ``portal_ctx``.

Modes (``options_mode`` on the filter record):

* ``static`` / ``schema`` — the widget's own dimension. The value is bound
  under the filter's ``param_name``. Blank (or absent) = "All": the param is
  bound as ``''`` (single) / ``('__all__',)`` (multi) so a placeholder that
  sits outside ``[[ ]]`` never raises, while ``[[ ]]`` clauses drop as usual.
* ``mirror`` — a local override of a page filter. The value is bound under
  the PAGE filter's param name and replaces the page value for this widget
  only. Blank = inherit: the page value is left untouched.

Only params DECLARED on the widget are ever read from the request — a caller
cannot smuggle arbitrary params through the ``_wf_`` prefix.
"""

from .sql_params import build_sql_params

WF_PREFIX = '_wf_'
# Upper bound on a single widget-filter value (a multi-select CSV included).
# Mirrors the spirit of AUTO_SELECT_ALL_MAX_CHARS — nothing legitimate is
# longer, and it keeps a hostile client from shipping megabytes into SQL binds.
WF_MAX_VALUE_LEN = 4000


def parse_widget_filter_kw(kw, declared):
    """Read ``_wf_<param>`` request params for the DECLARED widget filters.

    Args:
        kw: request params dict (query string / form).
        declared: list of dicts from ``dashboard.widget.get_widget_filter_declarations()``
            — each carries ``param_name`` (the RUNTIME key: the page filter's
            param for mirrors), ``mode`` and ``is_multiselect``.

    Returns:
        {runtime_param: raw_string_value} — only for declared params that are
        present in ``kw``. Absent params are simply not in the dict, so the
        caller can distinguish "not sent" from "sent blank" if it needs to.
    """
    values = {}
    if not kw or not declared:
        return values
    for d in declared:
        param = d.get('param_name') or ''
        if not param:
            continue
        raw = kw.get(WF_PREFIX + param)
        if raw is None:
            continue
        if not isinstance(raw, str):
            raw = str(raw)
        raw = raw.strip()
        if len(raw) > WF_MAX_VALUE_LEN:
            raw = raw[:WF_MAX_VALUE_LEN]
        values[param] = raw
    return values


def apply_widget_filter_values(portal_ctx, declared, values):
    """Return a COPY of ``portal_ctx`` with widget-filter values bound.

    The input ctx is never mutated: portal.py shares one ctx (or one scoped
    bundle) across every widget on a tab, so binding in place would leak one
    widget's local filter into its neighbours.

    Args:
        portal_ctx: dict with ``sql_params`` and ``filter_values_by_name``.
        declared: see ``parse_widget_filter_kw``.
        values: {runtime_param: raw_string} — typically the parsed request
            params, or the filters' ``default_value``s on initial render.
    """
    if not declared:
        return portal_ctx
    ctx = dict(portal_ctx)
    sql_params = dict(ctx.get('sql_params') or {})
    fvbn = dict(ctx.get('filter_values_by_name') or {})

    for d in declared:
        param = d.get('param_name') or ''
        if not param:
            continue
        raw = (values.get(param) if values else None)
        raw = (raw or '').strip() if isinstance(raw, str) else (raw or '')
        mode = d.get('mode') or 'static'
        if mode == 'mirror' and raw == '':
            # Inherit: the page's own value for this param stays as-is.
            continue
        multi = {param} if d.get('is_multiselect') else set()
        sql_params.update(build_sql_params({param: raw}, multi))
        fvbn[param] = raw

    ctx['sql_params'] = sql_params
    ctx['filter_values_by_name'] = fvbn
    return ctx


def default_values(declared):
    """{runtime_param: default_value} for the initial (server-side) render."""
    out = {}
    for d in declared or []:
        param = d.get('param_name') or ''
        if param:
            out[param] = (d.get('default_value') or '').strip()
    return out
