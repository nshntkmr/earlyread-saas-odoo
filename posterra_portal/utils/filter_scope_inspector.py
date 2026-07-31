# -*- coding: utf-8 -*-
"""Shared effective-filter / placeholder inspector (Phase T).

ONE implementation used by: filter/dependency/scope_filter_id validators, the
tab unlink guard, the filter unlink guard, and Builder/template preflight.
Per-consumer copies would drift — don't add any.

Placeholder algorithm (non-regression rule): tab compatibility applies ONLY
when an extracted ``%(name)s`` placeholder matches a configured page-filter
runtime key (``param_name or field_name`` of an active filter on the page).
Everything else — trusted system keys (``selected_hha_id``/``selected_hha_ccn``),
the consumer's configured ``scope_param_name``, validated map params
(``_map_level``/``_drill_state_*``), ``row_key`` (detail/drawer SQL only) —
keeps its existing consumer-specific validation. ``_scope_value`` is an API
transport key, never an SQL placeholder.

Consumer scoping table (binding, plan v8):
  page-level section / badge / page_summary widget / global widget → global
  filters only; tab widget / tab section → global + SAME-tab filters.
"""

import re

_PLACEHOLDER_RE = re.compile(r'%\((\w+)\)s')

# Trusted system keys injected into every bundle AFTER partitioning —
# never subject to tab compatibility.
SYSTEM_KEYS = frozenset({'selected_hha_id', 'selected_hha_ccn'})
_MAP_KEY_RE = re.compile(r'^(_map_level|_drill_state_\w+)$')


def runtime_key(flt):
    """The active runtime key a filter owns in URL/state/SQL params."""
    return flt.param_name or flt.field_name or ''


def extract_placeholders(sql):
    """Ordered unique ``%(name)s`` names in one SQL text."""
    seen, out = set(), []
    for m in _PLACEHOLDER_RE.finditer(sql or ''):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def iter_sql_surfaces(record):
    """Yield (surface_name, sql_text) for EVERY executable SQL surface of a
    widget/section/badge/scope-option/composite-item record — top-level
    fields AND the nested-JSON locations (ranked_detail_config SQL,
    detail_drawer_config section SQL, legacy ranked_detail_sql)."""
    import json as _json

    def _get(field):
        return getattr(record, field, '') or ''

    for field in ('query_sql', 'download_sql', 'annotation_query_sql',
                  'ranked_detail_sql'):
        sql = _get(field)
        if sql:
            yield field, sql

    for cfg_field, sql_keys in (
            ('ranked_detail_config', ('detail_sql', 'sql')),
            ('detail_drawer_config', None)):
        raw = _get(cfg_field)
        if not raw:
            continue
        try:
            cfg = _json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            continue
        if not isinstance(cfg, dict):
            continue
        if cfg_field == 'detail_drawer_config':
            for section in cfg.get('sections') or []:
                if isinstance(section, dict) and section.get('sql'):
                    yield ('detail_drawer_config.sections[%s]'
                           % section.get('id', '?'), section['sql'])
        else:
            for key in sql_keys:
                if cfg.get(key):
                    yield '%s.%s' % (cfg_field, key), cfg[key]
            # sub-list / tile SQL blocks, when present
            for key in ('tiles', 'sub_list'):
                block = cfg.get(key)
                items = block if isinstance(block, list) else (
                    [block] if isinstance(block, dict) else [])
                for i, item in enumerate(items):
                    if isinstance(item, dict) and item.get('sql'):
                        yield '%s.%s[%d]' % (cfg_field, key, i), item['sql']


def effective_filters(env, page, tab):
    """Recordset of active filters a consumer at (page, tab) may reference:
    page-wide always; same-tab when ``tab`` is set."""
    Filter = env['dashboard.page.filter'].sudo()
    domain = [('page_id', '=', page.id), ('is_active', '=', True)]
    records = Filter.search(domain)
    return records.filtered(
        lambda f: not f.tab_id or (tab and f.tab_id.id == tab.id))


def foreign_tab_keys(env, page, tab):
    """{runtime_key: filter} for active filters OUTSIDE the consumer's scope
    (i.e. scoped to a DIFFERENT tab). These are the only keys tab
    compatibility rejects."""
    Filter = env['dashboard.page.filter'].sudo()
    records = Filter.search([('page_id', '=', page.id),
                             ('is_active', '=', True),
                             ('tab_id', '!=', False)])
    out = {}
    for f in records:
        if tab and f.tab_id.id == tab.id:
            continue
        key = runtime_key(f)
        if key:
            out[key] = f
    return out


def check_sql_surfaces(env, record, page, tab, consumer_label):
    """Return a list of error strings for foreign-tab placeholders across
    every executable SQL surface of ``record``. Non-filter placeholders are
    left to existing consumer-specific validation (never rejected here)."""
    foreign = foreign_tab_keys(env, page, tab)
    if not foreign:
        return []
    errors = []
    for surface, sql in iter_sql_surfaces(record):
        for name in extract_placeholders(sql):
            if name in SYSTEM_KEYS or _MAP_KEY_RE.match(name) \
                    or name == 'row_key':
                continue
            if name in foreign:
                flt = foreign[name]
                errors.append(
                    "%s: %s references %%(%s)s, a filter scoped to tab '%s' "
                    "— a %s can only use page-wide%s filters."
                    % (consumer_label, surface, name, flt.tab_id.name,
                       consumer_label.split(' ')[0],
                       (' or same-tab' if tab else '')))
    return errors


def filter_references(env, flt):
    """Human-readable list of consumers referencing ``flt`` (scope_filter_id
    or any SQL surface placeholder). Used by the filter unlink guard."""
    key = runtime_key(flt)
    hits = []
    scan = [('dashboard.widget', 'widget'),
            ('dashboard.page.section', 'section')]
    if 'dashboard.page.badge' in env:
        scan.append(('dashboard.page.badge', 'badge'))
    for model, label in scan:
        Model = env[model].sudo()
        if 'scope_filter_id' in Model._fields:
            for rec in Model.search([('scope_filter_id', '=', flt.id)]):
                hits.append('%s "%s" (scope filter)'
                            % (label, rec.display_name))
        if key:
            domain = [('page_id', '=', flt.page_id.id)] \
                if 'page_id' in Model._fields else []
            for rec in Model.search(domain):
                for surface, sql in iter_sql_surfaces(rec):
                    if key in extract_placeholders(sql):
                        hits.append('%s "%s" (%s uses %%(%s)s)'
                                    % (label, rec.display_name, surface, key))
                        break
    return hits
