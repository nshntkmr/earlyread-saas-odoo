# -*- coding: utf-8 -*-
"""Projection service — Mark / Edit / Re-project / Undo / admin Undo / Void.

Every mutation follows the same sequence (spec §3.3–3.5):

1. resolve the Projection Type, the widget's drawer section and its
   ``card.projection`` block;
2. authorize the JWT user (app membership, allowed groups, provider scope);
3. re-run the section SQL for the row key through the drawer's own scoped
   executor path and keep the single row whose identity hash **and**
   snapshot match the request (0 → 404, 2+ → 409 ambiguous);
4. load the member's monthly history from the source (identity, month,
   eligible, compliant) and evaluate the cycle rule;
5. take the per-identity advisory lock, answer idempotently for a replayed
   ``request_id``, check ``expected_revision`` against the identity-wide
   revision, check the action's preconditions;
6. write the cycle record and the append-only event in the same
   transaction; a residual unique violation (a concurrent commit this
   transaction could not see) is turned into ``ConcurrencyError`` so Odoo's
   standard retry re-runs the request.

Nothing here touches source data. The mirror publisher (Phase 3) reads the
events this module leaves in ``pending``.
"""

import hashlib
import json
import logging

import psycopg2

from odoo import fields
from odoo.exceptions import ConcurrencyError

from ..models.dashboard_projection import USER_FACING_ACTIONS
from ..utils import projection_identity as pid
from ..utils.projection_outcomes import Evaluation, Row

_logger = logging.getLogger(__name__)

NOTE_MAX_LEN = 2000
EVIDENCE_MAX_LEN = 120


class ProjectionError(Exception):
    """Domain error mapped to an HTTP status by the controller."""

    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra

    def to_dict(self):
        out = {'error': self.message, 'code': self.code, 'status': self.status}
        out.update(self.extra)
        return out


# ── Lookups ──────────────────────────────────────────────────────────────────

def find_config(env, app, type_key):
    cfg = env['dashboard.projection.config'].sudo().search([
        ('app_id', '=', app.id), ('key', '=', type_key or ''), ('is_active', '=', True),
    ], limit=1)
    if not cfg:
        raise ProjectionError(404, 'type_not_found',
                              'Projection Type %r is not configured for this app.' % (type_key,))
    return cfg


def load_block(widget, section_id):
    """Return ``(section, block)`` for the drawer section carrying the
    ``card.projection`` block, or raise."""
    cfg = widget._get_detail_drawer_config()
    if not cfg or not cfg.get('enabled'):
        raise ProjectionError(400, 'drawer_disabled', 'Widget has no enabled Detail Drawer.')
    for section in cfg.get('sections') or []:
        if not isinstance(section, dict) or section.get('id') != section_id:
            continue
        block = ((section.get('card') or {}).get('projection')) or {}
        if section.get('type') != 'measure_cards' or not block:
            raise ProjectionError(400, 'no_projection_block',
                                  'Section %r has no projection block.' % (section_id,))
        if section.get('source') != 'sql' or not (section.get('sql') or '').strip():
            raise ProjectionError(400, 'no_section_sql',
                                  'Section %r must be a SQL section.' % (section_id,))
        return section, block
    raise ProjectionError(404, 'section_not_found', 'Drawer section %r not found.' % (section_id,))


def block_identity_aliases(config, block):
    """Ordered list of ``(column_name, alias)`` for the identity columns."""
    mapping = block.get('identity') or {}
    out = []
    for name in config._identity_column_names():
        alias = mapping.get(name) or name
        out.append((name, alias))
    return out


# ── Authorization ────────────────────────────────────────────────────────────

def user_is_admin(user):
    try:
        return bool(user.has_group('posterra_portal.group_posterra_admin')
                    or user.has_group('base.group_system'))
    except Exception:  # noqa: BLE001 — fail closed
        return False


def authorize(config, user, app, providers=None):
    """Return the provider scope values (list) or ``None`` for app scope."""
    if config.app_id.id != app.id:
        raise ProjectionError(403, 'wrong_app', 'Projection Type belongs to another app.')
    if config.allowed_group_ids:
        user_groups = user.sudo().all_group_ids
        if not (user_groups & config.allowed_group_ids) and not user_is_admin(user):
            raise ProjectionError(403, 'not_allowed', 'You are not allowed to make projections.')
    if config.scope_mode != 'provider':
        return None
    field = config.scope_provider_field
    values = []
    for provider in (providers or []):
        val = getattr(provider, field, None)
        if val not in (None, False, ''):
            values.append(str(val))
    if not values:
        raise ProjectionError(403, 'no_scope', 'No provider scope for this user.')
    return values


def _policy_allows(config, user, cycle_record):
    if config.undo_policy != 'owner_or_admin':
        return True
    return bool(cycle_record and (cycle_record.owner_id.id == user.id or user_is_admin(user)))


# ── Source access ────────────────────────────────────────────────────────────

def _scoped_section_sql(sql, config, scope_values):
    if scope_values is None:
        return sql
    col = config.scope_column_id.column_name
    return 'SELECT * FROM (%s) pv_s WHERE pv_s."%s" IN %%(pv_scope)s' % (sql.strip().rstrip(';'), col)


def resolve_row(config, widget, section, block, row_key, identity_hash, snapshot,
                portal_ctx, scope_values=None):
    """The one authorized row whose identity hash and snapshot match."""
    ctx = dict(portal_ctx or {})
    ctx['sql_params'] = dict(ctx.get('sql_params') or {})
    if scope_values is not None:
        ctx['sql_params']['pv_scope'] = tuple(scope_values)
    sql = _scoped_section_sql(section['sql'], config, scope_values)
    try:
        cols, rows = widget._run_detail_query(sql, row_key, ctx)
    except Exception as exc:  # noqa: BLE001 — surface a clean message
        _logger.warning('projection: section SQL failed (widget %s): %s', widget.id, exc)
        raise ProjectionError(502, 'section_sql_error', 'The drawer section query failed.')
    aliases = block_identity_aliases(config, block)
    snap_alias = block.get('snapshot_alias') or config.snapshot_column_id.column_name
    want_snapshot = pid.normalize_component(snapshot)
    matches = []
    for raw in rows:
        row = dict(zip(cols, raw))
        h = pid.identity_hash_or_none([row.get(alias) for _, alias in aliases])
        if h != identity_hash:
            continue
        if pid.normalize_component(row.get(snap_alias)) != want_snapshot:
            continue
        matches.append(row)
    if not matches:
        raise ProjectionError(404, 'row_not_found',
                              'No row of this measure for the selected month is visible to you.')
    if len(matches) > 1:
        raise ProjectionError(409, 'ambiguous_row',
                              'More than one row matches this measure and month.')
    return matches[0]


def load_history(config, member_key_column, member_key_value, scope_values=None):
    """{identity_hash: [Row, ...]} for every month of the member."""
    from ..utils.query_executors import get_executor
    scope_col = config.scope_column_id.column_name if scope_values is not None else None
    sql = config.render_history_sql(member_key_column, scope_col)
    params = {'member_key': pid.normalize_component(member_key_value)}
    if scope_values is not None:
        params['pv_scope'] = tuple(scope_values)
    try:
        _cols, rows = get_executor(config.env, config.source_id).execute(sql, params)
    except Exception as exc:  # noqa: BLE001
        _logger.warning('projection: history query failed (type %s): %s', config.id, exc)
        raise ProjectionError(502, 'history_error', 'The monthly history could not be read.')
    out = {}
    for h, month, eligible, compliant in rows:
        if not h:
            continue
        out.setdefault(str(h), []).append(
            Row(pid.normalize_component(month), _as_bool(eligible), _as_bool(compliant)))
    return out


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 't', 'yes')
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return bool(value)


def cycles_for(config, identity_hash):
    return config.env['dashboard.projection'].sudo().search([
        ('config_id', '=', config.id), ('identity_hash', '=', identity_hash),
    ], order='cycle_no')


def evaluate(config, identity_hash, history_rows):
    records = cycles_for(config, identity_hash)
    return Evaluation([r.to_cycle() for r in records], history_rows or [])


def history_lines(config, identity_hash, limit=None):
    limit = limit or config.history_shown or 3
    events = config.env['dashboard.projection.event'].sudo().search([
        ('config_id', '=', config.id), ('identity_hash', '=', identity_hash),
        ('action', 'in', list(USER_FACING_ACTIONS)),
    ], order='id desc', limit=limit)
    return [e.to_history_dict() for e in events]


# ── Payload ──────────────────────────────────────────────────────────────────

def identity_payload(config, identity_hash, evaluation, month, user):
    """The identity object the drawer shows for the row of ``month``."""
    allow_hist = bool(config.allow_historical_mark)
    cycles = {}
    for cycle in evaluation.cycles:
        rec = cycle.record
        data = rec.to_public_dict()
        data['match_month'] = evaluation.match_month(cycle) or ''
        policy_ok = _policy_allows(config, user, rec)
        data['can_edit'] = bool(evaluation.can_edit(cycle, month) and policy_ok)
        data['can_reproject'] = bool(
            evaluation.can_reproject(cycle, month, allow_hist) and policy_ok)
        data['can_undo'] = bool(evaluation.can_undo(cycle, month) and policy_ok)
        cycles[str(cycle.cycle_no)] = data
    covering = evaluation.covering(month)
    return {
        'type_key': config.key,
        'identity_hash': identity_hash,
        'identity_revision': evaluation.identity_revision,
        'latest_month': evaluation.latest_month,
        'month': month,
        'outcome': evaluation.outcome(month),
        'covering_cycle_no': covering.cycle_no if covering else 0,
        'can_mark': bool(evaluation.can_mark(month, allow_hist)),
        'cycles': cycles,
        'history': history_lines(config, identity_hash),
    }


# ── Mutations ────────────────────────────────────────────────────────────────

_ACTIONS = ('mark', 'edit', 'reproject', 'undo')


def _clean_fields(config, params):
    """Validate the optional popover fields."""
    note = params.get('note')
    note = '' if note is None else str(note)
    if len(note) > NOTE_MAX_LEN:
        raise ProjectionError(400, 'note_too_long', 'The comment is too long.')
    if note and not config.note_enabled:
        raise ProjectionError(400, 'note_disabled', 'Comments are not enabled for this type.')
    expected = params.get('expected_date') or ''
    expected_date = None
    if expected:
        if not config.expected_date_enabled:
            raise ProjectionError(400, 'date_disabled',
                                  'The closure date is not enabled for this type.')
        try:
            expected_date = fields.Date.from_string(str(expected)[:10])
        except (ValueError, TypeError):
            raise ProjectionError(400, 'bad_date', 'The closure date must be YYYY-MM-DD.')
    evidence = str(params.get('evidence') or '').strip()
    if len(evidence) > EVIDENCE_MAX_LEN:
        raise ProjectionError(400, 'bad_evidence', 'Evidence value is too long.')
    choices = [v for v, _ in config.evidence_choices()]
    if evidence and choices and evidence not in choices:
        raise ProjectionError(400, 'bad_evidence', 'Unknown evidence option.')
    return {'note': note, 'expected_date': expected_date, 'evidence': evidence}


def _fingerprint(user, action, config, identity_hash, expected_revision, submitted):
    body = json.dumps([user.id, action, config.id, identity_hash, int(expected_revision or 0),
                       submitted], sort_keys=True, default=str)
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def _lock_identity(env, config, identity_hash):
    env.cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                   ['projection:%s:%s' % (config.id, identity_hash)])


def _replayed(config, request_id, fingerprint):
    """Result of an identical earlier request, or ``None``."""
    if not request_id:
        raise ProjectionError(400, 'missing_request_id', 'request_id is required.')
    Event = config.env['dashboard.projection.event'].sudo()
    prior = Event.search([('config_id', '=', config.id), ('request_id', '=', request_id)], limit=1)
    if not prior:
        return None
    if prior.request_fingerprint != fingerprint:
        raise ProjectionError(409, 'request_conflict',
                              'This request id was already used for a different change.')
    try:
        return json.loads(prior.result_json or '{}')
    except (ValueError, TypeError):
        return {}


def _row_label(config, aliases, row):
    return ' · '.join(pid.normalize_component(row.get(alias)) for _, alias in aliases)


def mutate(env, user, app, action, params, portal_ctx, providers=None):
    """Entry point for the four portal actions. Returns the identity payload."""
    if action not in _ACTIONS:
        raise ProjectionError(400, 'bad_action', 'Unknown action.')
    config = find_config(env, app, params.get('type_key'))
    widget = env['dashboard.widget'].sudo().browse(int(params.get('widget_id') or 0))
    if not widget.exists() or not widget.is_active or widget.page_id.app_id.id != app.id:
        raise ProjectionError(404, 'widget_not_found', 'Widget not found.')
    section, block = load_block(widget, params.get('section_id'))
    if (block.get('type_key') or '') != config.key:
        raise ProjectionError(400, 'type_mismatch', 'The drawer block uses another Projection Type.')
    identity_hash = str(params.get('identity_hash') or '').strip().lower()
    if len(identity_hash) != 32:
        raise ProjectionError(400, 'bad_identity', 'identity_hash is required.')
    snapshot = pid.normalize_component(params.get('snapshot'))
    if not snapshot:
        raise ProjectionError(400, 'missing_snapshot', 'snapshot (month) is required.')
    row_key = params.get('row_key')
    if row_key in (None, ''):
        raise ProjectionError(400, 'missing_row_key', 'row_key is required.')

    scope_values = authorize(config, user, app, providers)
    row = resolve_row(config, widget, section, block, row_key, identity_hash, snapshot,
                      portal_ctx, scope_values)
    member_col = block.get('member_key_column') or ''
    if member_col not in row:
        raise ProjectionError(400, 'member_key_missing',
                              'member_key_column %r is not returned by the section SQL.' % member_col)
    history = load_history(config, member_col, row.get(member_col), scope_values)
    fields_in = _clean_fields(config, params) if action != 'undo' else {}
    expected_revision = int(params.get('expected_revision') or 0)
    request_id = str(params.get('request_id') or '').strip()[:64]
    submitted = {'note': fields_in.get('note', ''), 'evidence': fields_in.get('evidence', ''),
                 'expected_date': fields.Date.to_string(fields_in['expected_date'])
                 if fields_in.get('expected_date') else '',
                 'cycle_no': int(params.get('cycle_no') or 0), 'snapshot': snapshot}
    fingerprint = _fingerprint(user, action, config, identity_hash, expected_revision, submitted)

    _lock_identity(env, config, identity_hash)
    replay = _replayed(config, request_id, fingerprint)
    if replay is not None:
        return replay

    evaluation = evaluate(config, identity_hash, history.get(identity_hash, []))
    if expected_revision != evaluation.identity_revision:
        latest = _latest_event(config, identity_hash)
        raise ProjectionError(
            409, 'stale_revision',
            '%s updated this measure at %s. Your changes were not saved. Review the '
            'latest version.' % (latest and latest.actor_name or 'Someone',
                                 latest and fields.Datetime.to_string(latest.at) or '—'),
            conflict={'revision': evaluation.identity_revision,
                      'actor_name': latest and latest.actor_name or '',
                      'at': latest and fields.Datetime.to_string(latest.at) or '',
                      'action': latest and latest.action or ''})

    now = fields.Datetime.now()
    new_revision = evaluation.identity_revision + 1
    aliases = block_identity_aliases(config, block)
    source_snapshot = {
        'member_key_column': member_col,
        'member_key': pid.normalize_component(row.get(member_col)),
        'snapshot': snapshot,
        'status': pid.normalize_component(row.get(section['card'].get('status_column') or '')),
        'row': {k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v))
                for k, v in row.items()},
    }
    handler = {'mark': _do_mark, 'edit': _do_edit, 'reproject': _do_reproject,
               'undo': _do_undo}[action]

    try:
        with env.cr.savepoint():
            record, event_vals = handler(
                config, user, evaluation, snapshot, row, fields_in, params, now,
                new_revision, aliases, source_snapshot, section)
            env.flush_all()
    except psycopg2.IntegrityError as exc:
        _logger.info('projection: concurrent write on %s/%s (%s) — retrying',
                     config.id, identity_hash, exc.__class__.__name__)
        raise ConcurrencyError('projection revision conflict') from exc

    # The event first (so the history lines include this change), then the
    # response, stored on the event for idempotent replay.
    event = _write_event(config, record, event_vals, user, now, new_revision,
                         request_id, fingerprint)
    evaluation = evaluate(config, identity_hash, history.get(identity_hash, []))
    result = identity_payload(config, identity_hash, evaluation, snapshot, user)
    event.write({'result_json': json.dumps(result, default=str)})
    _schedule_publish(env, config, event)
    return result


def _schedule_publish(env, config, event):
    """ClickHouse types: mirror the event right after commit (own cursor);
    the cron retries anything that fails. PG types have nothing to publish."""
    if event.publish_state == 'pending':
        from ..utils.projection_publisher import schedule_post_commit
        schedule_post_commit(env, [event.id])


def _latest_event(config, identity_hash):
    return config.env['dashboard.projection.event'].sudo().search([
        ('config_id', '=', config.id), ('identity_hash', '=', identity_hash)],
        order='id desc', limit=1)


def _write_event(config, record, event_vals, user, now, revision, request_id,
                 fingerprint):
    Event = config.env['dashboard.projection.event'].sudo()
    vals = {
        'projection_id': record.id,
        'config_id': config.id,
        'identity_hash': record.identity_hash,
        'cycle_no': record.cycle_no,
        'actor_id': user.id,
        'actor_name': user.name,
        'at': now,
        'revision': revision,
        'request_id': request_id or False,
        'request_fingerprint': fingerprint or False,
        'payload_json': json.dumps(record.to_publish_payload(), default=str),
        'publish_state': 'pending' if config.engine == 'clickhouse' else 'none',
    }
    vals.update(event_vals)
    try:
        with config.env.cr.savepoint():
            event = Event.create(vals)
            config.env.flush_all()
    except psycopg2.IntegrityError as exc:
        raise ConcurrencyError('projection event conflict') from exc
    record.write({'publish_state': vals['publish_state'],
                  'published_revision': revision if vals['publish_state'] == 'none'
                  else record.published_revision})
    return event


def _snapshot_of(record):
    return json.dumps(record.to_public_dict(), default=str) if record else ''


def _do_mark(config, user, evaluation, snapshot, row, fields_in, params, now,
             new_revision, aliases, source_snapshot, section):
    allow_hist = bool(config.allow_historical_mark)
    row_eval = evaluation.row_for(snapshot)
    if row_eval is None:
        raise ProjectionError(409, 'month_not_in_history',
                              'The selected month is not in the member history.')
    if not row_eval.eligible:
        raise ProjectionError(400, 'not_eligible', 'This measure is not eligible.')
    if row_eval.compliant:
        raise ProjectionError(400, 'already_compliant', 'This measure is already compliant.')
    if not allow_hist and snapshot != evaluation.latest_month:
        raise ProjectionError(
            400, 'not_latest_month',
            'Projections can only be made on the latest month (%s).' % evaluation.latest_month,
            latest_month=evaluation.latest_month)
    open_cycle = evaluation.open_cycle(snapshot)
    if open_cycle is not None:
        raise ProjectionError(409, 'already_active',
                              'A projection is already open for this measure.',
                              cycle_no=open_cycle.cycle_no)
    latest = evaluation.latest_cycle
    cycle_no = (latest.cycle_no + 1) if latest else 1
    Proj = config.env['dashboard.projection'].sudo()
    record = Proj.create({
        'config_id': config.id,
        'identity_hash': params['identity_hash'].strip().lower(),
        'identity_json': json.dumps(
            [pid.normalize_component(row.get(alias)) for _, alias in aliases]),
        'identity_label': _row_label(config, aliases, row),
        'cycle_no': cycle_no,
        'state': 'active',
        'revision': new_revision,
        'attempt_no': 1,
        'first_applies_from': snapshot,
        'applies_from': snapshot,
        'attempt_months': snapshot,
        'undone_month': '',
        'expected_date': fields_in['expected_date'],
        'evidence': fields_in['evidence'],
        'note': fields_in['note'],
        'owner_id': user.id,
        'owner_name': user.name,
        'asserted_at': now,
        'last_action_at': now,
        'source_snapshot': json.dumps(source_snapshot, default=str),
    })
    return record, {'action': 'mark', 'before_json': '', 'after_json': _snapshot_of(record)}


def _target_cycle(config, evaluation, params, snapshot):
    """The cycle the card displayed; must be the cycle covering the month."""
    cycle_no = int(params.get('cycle_no') or 0)
    covering = evaluation.covering(snapshot)
    if not cycle_no or covering is None or covering.cycle_no != cycle_no:
        raise ProjectionError(409, 'cycle_mismatch',
                              'The projection shown is not the one covering this month. Refresh.',
                              covering_cycle_no=covering.cycle_no if covering else 0)
    return covering


def _do_edit(config, user, evaluation, snapshot, row, fields_in, params, now,
             new_revision, aliases, source_snapshot, section):
    cycle = _target_cycle(config, evaluation, params, snapshot)
    record = cycle.record
    if not evaluation.can_edit(cycle, snapshot):
        raise ProjectionError(409, 'not_editable', 'This projection cannot be edited.')
    if not _policy_allows(config, user, record):
        raise ProjectionError(403, 'not_owner', 'Only the owner or an admin may edit this.')
    before = _snapshot_of(record)
    record.write({
        'revision': new_revision,
        'expected_date': fields_in['expected_date'],
        'evidence': fields_in['evidence'],
        'note': fields_in['note'],
        'last_action_at': now,
        'source_snapshot': json.dumps(source_snapshot, default=str),
    })
    return record, {'action': 'edit', 'before_json': before, 'after_json': _snapshot_of(record)}


def _do_reproject(config, user, evaluation, snapshot, row, fields_in, params, now,
                  new_revision, aliases, source_snapshot, section):
    cycle = _target_cycle(config, evaluation, params, snapshot)
    record = cycle.record
    if not evaluation.can_reproject(cycle, snapshot, bool(config.allow_historical_mark)):
        raise ProjectionError(409, 'not_reprojectable',
                              'Re-project is only possible on a not-matched latest month.',
                              latest_month=evaluation.latest_month)
    if not _policy_allows(config, user, record):
        raise ProjectionError(403, 'not_owner', 'Only the owner or an admin may re-project.')
    before = _snapshot_of(record)
    months = record.attempt_month_list()
    if snapshot not in months:
        months.append(snapshot)
    record.write({
        'revision': new_revision,
        'attempt_no': record.attempt_no + 1,
        'applies_from': snapshot,
        'attempt_months': ','.join(months),
        'expected_date': fields_in['expected_date'],
        'evidence': fields_in['evidence'],
        'note': fields_in['note'],
        'last_action_at': now,
        'source_snapshot': json.dumps(source_snapshot, default=str),
    })
    return record, {'action': 'reproject', 'before_json': before, 'after_json': _snapshot_of(record)}


def _do_undo(config, user, evaluation, snapshot, row, fields_in, params, now,
             new_revision, aliases, source_snapshot, section):
    cycle = _target_cycle(config, evaluation, params, snapshot)
    record = cycle.record
    if not evaluation.can_undo(cycle, snapshot):
        raise ProjectionError(409, 'not_undoable',
                              'Undo is only possible while no month has matched.')
    if not _policy_allows(config, user, record):
        raise ProjectionError(403, 'not_owner', 'Only the owner or an admin may undo this.')
    before = _snapshot_of(record)
    record.write({
        'revision': new_revision,
        'state': 'undone',
        'undone_month': evaluation.latest_month or snapshot,
        'undone_at': now,
        'undone_by_id': user.id,
        'last_action_at': now,
    })
    return record, {'action': 'undo', 'before_json': before, 'after_json': _snapshot_of(record)}


# ── Admin actions (backend, audited) ─────────────────────────────────────────

def _admin_history(record):
    """Monthly history for a stored cycle (member key from the record)."""
    try:
        snap = json.loads(record.source_snapshot or '{}')
    except (ValueError, TypeError):
        snap = {}
    col, value = snap.get('member_key_column'), snap.get('member_key')
    if not col or value in (None, ''):
        return {}
    return load_history(record.config_id, col, value, None)


def _admin_mutate(env, user, record, action, reason=None):
    from odoo.exceptions import UserError
    config = record.config_id.sudo()
    record = record.sudo()
    if action == 'admin_void' and not (reason or '').strip():
        raise UserError('A reason is required to void a projection.')
    _lock_identity(env, config, record.identity_hash)
    history = _admin_history(record) if action == 'admin_undo' else {}
    evaluation = evaluate(config, record.identity_hash, history.get(record.identity_hash, []))
    if record.state != 'active':
        raise UserError('This projection is already undone.')
    if action == 'admin_undo' and not evaluation.latest_month:
        raise UserError('The monthly history could not be read; cannot determine the '
                        'effective month. Use Void to remove the projection entirely.')
    now = fields.Datetime.now()
    new_revision = evaluation.identity_revision + 1
    before = _snapshot_of(record)
    undone_month = record.first_applies_from if action == 'admin_void' else evaluation.latest_month
    try:
        with env.cr.savepoint():
            record.write({
                'revision': new_revision,
                'state': 'undone',
                'undone_month': undone_month,
                'undone_at': now,
                'undone_by_id': user.id,
                'last_action_at': now,
            })
            env.flush_all()
    except psycopg2.IntegrityError as exc:
        raise ConcurrencyError('projection revision conflict') from exc
    event = _write_event(
        config, record, {'action': action, 'reason': (reason or '').strip() or False,
                         'before_json': before, 'after_json': _snapshot_of(record)},
        user, now, new_revision, None, None)
    evaluation = evaluate(config, record.identity_hash, history.get(record.identity_hash, []))
    result = identity_payload(config, record.identity_hash, evaluation,
                              record.applies_from, user)
    event.write({'result_json': json.dumps(result, default=str)})
    _schedule_publish(env, config, event)
    return result


def admin_undo(env, user, record):
    return _admin_mutate(env, user, record, 'admin_undo')


def admin_void(env, user, record, reason):
    return _admin_mutate(env, user, record, 'admin_void', reason)
