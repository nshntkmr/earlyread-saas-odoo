# -*- coding: utf-8 -*-
"""Drawer overlay for projection-enabled ``measure_cards`` sections (spec §6).

Called by ``dashboard.widget._execute_drawer_detail`` for a section whose
``card.projection`` block names a Projection Type. It adds, per row:

    __pv_identity_hash, __pv_month, __pv_source_positive, __pv_cycle_no,
    __pv_outcome, __pv_can_mark, __pv_can_edit, __pv_can_reproject, __pv_can_undo

and, per section:

    projections: {"<type_key>": {"<identity_hash>": {identity_revision,
                  latest_month, cycles: {"<cycle_no>": {...}}, history: [...]}}}
    projection_meta: labels, colours, capture, poll_seconds, can_act,
                     latest_snapshot, latest_filter_value, month_filter_param

Everything is computed server-side (the client renders from flags and
never derives permissions from colours). Sections without the block are
untouched; any failure here is isolated into ``projection_meta.error``.
"""

import logging

from . import projection_service as svc
from ..utils import projection_identity as pid

_logger = logging.getLogger(__name__)


def latest_source_month(config, widget, month_filter_param):
    """``(latest_month, filter_value)`` of the type's source, where
    ``filter_value`` is the value of the page filter named by
    ``month_filter_param`` on the latest row (empty when unknown)."""
    from ..utils.query_executors import get_executor
    from ..utils.sql_idents import IDENT_RE
    month = config._render_month_expr()
    select = ['%s AS s' % month]
    filter_col = ''
    if month_filter_param:
        pf = widget.page_id.filter_ids.filtered(
            lambda f: f.param_name == month_filter_param and f.is_active)[:1]
        col = pf.schema_column_id.column_name if pf and pf.schema_column_id else ''
        if col and IDENT_RE.match(col) and col in {c.column_name for c in config.source_id.column_ids}:
            filter_col = col
            select.append('%s AS v' % pid.normalized_column_expr(col, config.engine))
    sql = 'SELECT %s FROM %s ORDER BY s DESC LIMIT 1' % (
        ', '.join(select), config._quoted_source())
    try:
        _cols, rows = get_executor(config.env, config.source_id).execute(sql, {})
    except Exception as exc:  # noqa: BLE001
        _logger.debug('projection overlay: latest month query failed: %s', exc)
        return '', ''
    if not rows:
        return '', ''
    row = rows[0]
    return pid.normalize_component(row[0]), (pid.normalize_component(row[1]) if filter_col else '')


def apply_overlay(widget, section_cfg, section_result, portal_ctx, user=None, providers=None):
    """Mutate ``section_result`` in place (see module docstring)."""
    block = ((section_cfg.get('card') or {}).get('projection')) or {}
    if not block or section_cfg.get('type') != 'measure_cards':
        return
    app = widget.page_id.app_id
    env = widget.env
    try:
        config = svc.find_config(env, app, block.get('type_key'))
    except svc.ProjectionError as exc:
        section_result['projection_meta'] = {'error': exc.message}
        return
    meta = config.get_public_meta()
    meta['month_filter_param'] = block.get('month_filter_param') or ''

    # Who may act: read access is the drawer's own; acting needs the groups
    # and (provider scope) a provider list.
    can_act = False
    scope_values = None
    if user is not None:
        try:
            scope_values = svc.authorize(config, user, app, providers)
            can_act = True
        except svc.ProjectionError as exc:
            if exc.code == 'no_scope' and config.scope_mode == 'provider':
                section_result['projection_meta'] = dict(meta, error=exc.message, can_act=False)
                return
    meta['can_act'] = can_act

    rows = section_result.get('rows') or []
    aliases = svc.block_identity_aliases(config, block)
    snap_alias = block.get('snapshot_alias') or config.snapshot_column_id.column_name
    member_col = block.get('member_key_column') or ''
    status_col = (section_cfg.get('card') or {}).get('status_column') or ''
    allow_hist = bool(config.allow_historical_mark)

    history = {}
    if rows and member_col and member_col in rows[0]:
        history = svc.load_history(config, member_col, rows[0].get(member_col), scope_values)

    evaluations = {}
    projections = {}
    for row in rows:
        h = pid.identity_hash_or_none([row.get(alias) for _, alias in aliases])
        month = pid.normalize_component(row.get(snap_alias))
        row['__pv_identity_hash'] = h or ''
        row['__pv_month'] = month
        row['__pv_source_positive'] = bool(config.value_is_positive(row.get(status_col)))
        row['__pv_cycle_no'] = 0
        row['__pv_outcome'] = ''
        for flag in ('__pv_can_mark', '__pv_can_edit', '__pv_can_reproject', '__pv_can_undo'):
            row[flag] = False
        if not h:
            continue
        ev = evaluations.get(h)
        if ev is None:
            ev = evaluations[h] = svc.evaluate(config, h, history.get(h, []))
        cycle = ev.covering(month)
        record = cycle.record if cycle else None
        policy_ok = svc._policy_allows(config, user, record) if (user is not None and record) else False
        row['__pv_cycle_no'] = cycle.cycle_no if cycle else 0
        row['__pv_outcome'] = ev.outcome(month)
        row['__pv_can_mark'] = bool(can_act and ev.can_mark(month, allow_hist))
        row['__pv_can_edit'] = bool(can_act and policy_ok and ev.can_edit(cycle, month))
        row['__pv_can_reproject'] = bool(
            can_act and policy_ok and ev.can_reproject(cycle, month, allow_hist))
        row['__pv_can_undo'] = bool(can_act and policy_ok and ev.can_undo(cycle, month))
        if h not in projections:
            cycles = {}
            for c in ev.cycles:
                data = c.record.to_public_dict()
                data['match_month'] = ev.match_month(c) or ''
                cycles[str(c.cycle_no)] = data
            projections[h] = {
                'identity_revision': ev.identity_revision,
                'latest_month': ev.latest_month,
                'cycles': cycles,
                'history': svc.history_lines(config, h),
            }

    latest_snapshot, latest_filter_value = latest_source_month(
        config, widget, meta['month_filter_param'])
    meta['latest_snapshot'] = latest_snapshot
    meta['latest_filter_value'] = latest_filter_value
    section_result['projections'] = {config.key: projections}
    section_result['projection_meta'] = meta
