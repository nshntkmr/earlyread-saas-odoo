# -*- coding: utf-8 -*-
"""Projection publisher — mirrors saved cycles into the ClickHouse projection
table (spec §4.2).

* Uses a **dedicated publisher connection** (``dashboard.connection`` with
  ``purpose = 'publisher'``, an INSERT-only ClickHouse user). The shared
  query executors refuse publisher connections, so the analytics path never
  gains write capability; this module talks to ``clickhouse_connect``
  directly and only ever calls ``client.insert`` on the configured table.
* Delivery is idempotent: every event carries the cycle's payload with its
  stable revision; the mirror is ``ReplacingMergeTree(revision)`` keyed by
  ``(tenant_id, config_key, identity_hash, cycle_no)``.
* After a successful save the service registers a post-commit hook that
  publishes that request's events in its own cursor. Failures leave the
  event ``pending``/``failed`` for the cron (every minute); ``dead`` after
  ``MAX_ATTEMPTS`` with an admin Republish.
* A daily check republishes cycles whose latest revision is missing from
  the mirror (reads through the normal read executor with the app's
  tenant).
"""

import json
import logging

from odoo import api, fields, SUPERUSER_ID

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 20

MIRROR_COLUMNS = [
    'tenant_id', 'config_key', 'identity_hash', 'identity_json', 'cycle_no', 'revision',
    'state', 'attempt_no', 'first_applies_from', 'applies_from', 'attempt_months',
    'undone_month', 'expected_date', 'evidence', 'note', 'actor', 'owner', 'asserted_at',
    'undone_at',
]


class PublisherError(Exception):
    pass


def _publisher_client(env, connection):
    """clickhouse-connect client for the publisher connection (cached like
    the read clients, but never handed to an executor)."""
    if connection.engine != 'clickhouse':
        raise PublisherError('Publisher connection %r is not ClickHouse.' % connection.name)
    if getattr(connection, 'purpose', 'analytics') != 'publisher':
        raise PublisherError('Connection %r is not a publisher connection.' % connection.name)
    if not connection.is_active:
        raise PublisherError('Publisher connection %r is inactive.' % connection.name)
    from .query_executors.clickhouse import _get_client
    return _get_client(env, connection)


def payload_row(payload):
    """Ordered row for ``client.insert`` from an event's payload dict."""
    row = []
    for col in MIRROR_COLUMNS:
        value = payload.get(col)
        if col in ('cycle_no', 'revision', 'attempt_no'):
            value = int(value or 0)
        elif col == 'attempt_months':
            value = [str(m) for m in (value or [])]
        else:
            value = '' if value is None else str(value)
        row.append(value)
    return row


def publish_events(env, events, client_factory=None):
    """Publish the given events (any state except ``none``). Returns
    ``(published_count, failed_count)``. Never raises for a delivery
    failure — the event keeps its outbox state for a later retry."""
    published = failed = 0
    by_config = {}
    for ev in events:
        if ev.publish_state in ('none', 'published'):
            continue
        by_config.setdefault(ev.config_id.id, []).append(ev)
    for config_id, evs in by_config.items():
        config = env['dashboard.projection.config'].sudo().browse(config_id)
        try:
            table = config.mirror_table
            if not table:
                raise PublisherError('No mirror table configured on %r.' % config.name)
            if not config.publisher_connection_id:
                raise PublisherError('No publisher connection on %r.' % config.name)
            client = (client_factory or _publisher_client)(env, config.publisher_connection_id)
        except Exception as exc:  # noqa: BLE001 — configuration problems fail all events
            _logger.warning('projection publisher: %s', exc)
            for ev in evs:
                _mark_failed(ev, str(exc)[:200])
                failed += 1
            continue
        for ev in sorted(evs, key=lambda e: e.id):
            try:
                payload = json.loads(ev.payload_json or '{}')
                client.insert(table, [payload_row(payload)], column_names=MIRROR_COLUMNS)
            except Exception as exc:  # noqa: BLE001
                _logger.warning('projection publisher: event %s failed: %s',
                                ev.id, exc.__class__.__name__)
                _mark_failed(ev, str(exc)[:200])
                failed += 1
                continue
            now = fields.Datetime.now()
            ev.write({'publish_state': 'published', 'published_at': now,
                      'last_error': False})
            proj = ev.projection_id.sudo()
            proj.write({
                'published_revision': max(proj.published_revision, ev.revision),
                'publish_state': 'published'
                if proj.revision <= max(proj.published_revision, ev.revision) else 'pending',
            })
            published += 1
    return published, failed


def _mark_failed(ev, error):
    attempts = ev.attempts + 1
    state = 'dead' if attempts >= MAX_ATTEMPTS else 'failed'
    ev.write({'publish_state': state, 'attempts': attempts, 'last_error': error})
    if state == 'dead':
        ev.projection_id.sudo().write({'publish_state': 'dead'})


def publish_pending(env, limit=500, client_factory=None):
    """Cron entry: retry pending/failed events in id order."""
    events = env['dashboard.projection.event'].sudo().search(
        [('publish_state', 'in', ('pending', 'failed'))], order='id', limit=limit)
    if not events:
        return 0, 0
    return publish_events(env, events, client_factory=client_factory)


def schedule_post_commit(env, event_ids):
    """Publish ``event_ids`` right after the current transaction commits,
    in a cursor of their own. A failure never affects the committed save."""
    if not event_ids:
        return
    dbname = env.cr.dbname
    ids = list(event_ids)

    def _run():
        try:
            from odoo.modules.registry import Registry
            registry = Registry(dbname)
            with registry.cursor() as cr:
                env2 = api.Environment(cr, SUPERUSER_ID, {})
                events = env2['dashboard.projection.event'].browse(ids).exists()
                publish_events(env2, events)
        except Exception as exc:  # noqa: BLE001 — the cron retries
            _logger.warning('projection publisher (post-commit): %s', exc)

    env.cr.postcommit.add(_run)


def republish_cycle(record):
    """Admin Republish: resend the latest event of the cycle."""
    record = record.sudo()
    latest = record.env['dashboard.projection.event'].sudo().search(
        [('projection_id', '=', record.id)], order='id desc', limit=1)
    if not latest:
        return False
    latest.write({'publish_state': 'pending', 'attempts': 0, 'last_error': False})
    record.write({'publish_state': 'pending'})
    return latest


def check_mirror(env, config, executor_factory=None):
    """Daily check: cycles whose latest revision is missing from the mirror
    are queued again. Reads the mirror through the normal read executor with
    the app's tenant. Returns the number of cycles re-queued."""
    config = config.sudo()
    if config.engine != 'clickhouse' or not config.mirror_table:
        return 0
    from .sql_idents import TABLE_RE, quote_table
    if not TABLE_RE.match(config.mirror_table):
        return 0
    if executor_factory is None:
        from .query_executors import get_executor
        executor = get_executor(env, config.source_id)
        # Cron has no request: pin the tenant explicitly for this read.
        executor.get_tenant_id = lambda: config.app_id.app_key
    else:
        executor = executor_factory(env, config)
    sql = ('SELECT identity_hash, cycle_no, max(revision) FROM %s '
           'WHERE tenant_id = %%(tenant)s AND config_key = %%(key)s '
           'GROUP BY identity_hash, cycle_no' % quote_table(config.mirror_table))
    try:
        _cols, rows = executor.execute(sql, {'tenant': config.app_id.app_key, 'key': config.key})
    except Exception as exc:  # noqa: BLE001
        _logger.warning('projection mirror check (%s): %s', config.key, exc.__class__.__name__)
        return 0
    mirrored = {(str(h), int(c)): int(r) for h, c, r in rows}
    requeued = 0
    for rec in env['dashboard.projection'].sudo().search([('config_id', '=', config.id)]):
        if mirrored.get((rec.identity_hash, rec.cycle_no), 0) < rec.revision:
            if republish_cycle(rec):
                requeued += 1
    if requeued:
        _logger.info('projection mirror check (%s): %s cycle(s) re-queued', config.key, requeued)
    return requeued
