# -*- coding: utf-8 -*-
"""AI Assist gateway — the ONLY data path for the AI chatbot surfaces.

Serves the MCP service (desktop clients: Claude Desktop / ChatGPT Desktop)
today and the embedded portal panel later. Design contract
(docs/design/ai-assist-architecture.md + the M1 plan):

  - Auth: per-person Odoo API key (``res.users.apikeys``, scope
    ``'posterra_ai'``) in ``X-API-Key`` + target app in ``X-App-Key``.
    Every request re-checks user/app/membership — revocation is immediate.
  - ``request.tenant_id = app.app_key`` is set by the guard BEFORE any
    query executes (ClickHouse row policies depend on it).
  - Visibility: ``dashboard.schema.source.get_ai_visible_sources(app)`` is
    the single source of truth (app toggle + per-source opt-in + active +
    non-PHI + app scoping). ``source_id`` inputs are ALWAYS re-checked
    against it — never trusted.
  - Execution: everything funnels through ``QueryBuilder.validate_query``
    + ``execute_preview`` (SELECT-only, blocked keywords, LIMIT append,
    executor dispatch with tenant setting + resource caps). The desktop
    LLM authors SQL; server-side validation — not server-side authorship —
    is the security control.
  - Rate limit: per-user daily cap counted from ``ai.query.log`` (which is
    also the audit trail).
"""

import logging
import re
import time
from datetime import datetime, time as dtime, timedelta

from odoo import http
from odoo.http import request

from odoo.addons.dashboard_builder.controllers.utils import (
    _json_error,
    _json_response,
    _get_request_json,
)

_logger = logging.getLogger(__name__)

AI_APIKEY_SCOPE = 'posterra_ai'
DEFAULT_ROW_LIMIT = 200
MAX_ROW_LIMIT = 500
DAILY_LIMIT_PARAM = 'posterra_ai.daily_query_limit'
DEFAULT_DAILY_LIMIT = 200


class RateLimited(Exception):
    """Raised when the per-user daily query cap is exhausted."""

    def __init__(self, resets_at):
        self.resets_at = resets_at
        super().__init__('Daily AI query limit reached')


# ── Auth guard ─────────────────────────────────────────────────────────────

def _check_api_key(key):
    """Resolve an API key to a uid via core res.users.apikeys.

    Core's ``_check_credentials`` is keyword-only in recent Odoo; guard the
    call shape so a signature drift degrades to a clean auth failure, never
    a 500.
    """
    Apikeys = request.env['res.users.apikeys'].sudo()
    try:
        return Apikeys._check_credentials(scope=AI_APIKEY_SCOPE, key=key)
    except TypeError:
        try:
            return Apikeys._check_credentials(AI_APIKEY_SCOPE, key)
        except Exception:
            return None
    except Exception:
        return None


def _get_ai_user():
    """X-API-Key + X-App-Key → (user, app); sets request.tenant_id.

    Mirrors ``widget_api._get_api_user()`` step-for-step, substituting key
    auth for JWT. Raises:
        ValueError      → 401 (authentication failed)
        PermissionError → 403 (authenticated but not allowed)
    """
    key = (request.httprequest.headers.get('X-API-Key') or '').strip()
    if not key:
        raise ValueError('Missing X-API-Key header')
    uid = _check_api_key(key)
    if not uid:
        raise ValueError('Invalid, expired, or revoked API key')

    user = request.env['res.users'].sudo().browse(uid)
    if not user.exists() or not user.active:
        raise ValueError('User account is deactivated')

    app_key = (request.httprequest.headers.get('X-App-Key')
               or request.httprequest.args.get('app_key') or '').strip().lower()
    if not app_key:
        raise ValueError('Missing X-App-Key header (target app)')
    app = request.env['saas.app'].sudo().search(
        [('app_key', '=', app_key)], limit=1)
    if not app or not app.is_active:
        raise ValueError('Unknown or inactive app')
    if not app.ai_assist_enabled:
        raise PermissionError('AI Assist is not enabled for this app')

    from ..utils.access import user_can_access_app
    from .portal import _is_dashboard_admin
    if not _is_dashboard_admin(user) and not user_can_access_app(user, app):
        raise PermissionError('Access to this app has been revoked')

    # v1 user-scope contract: chatbot SQL sees the whole tenant, not the
    # user's provider slice — so gate on an explicit internal-analyst
    # group. NOTE: Odoo also accepts NULL-scope ("global") API keys for
    # any requested scope; a global key is a strictly stronger credential
    # the user already holds, and this group gate bounds who can use the
    # AI surface regardless of which of their keys they present.
    if not (user.has_group('posterra_portal.group_ai_assist_user')
            or user.has_group('posterra_portal.group_posterra_admin')
            or user.has_group('base.group_system')):
        raise PermissionError(
            'AI Assist requires the "AI Assist Desktop User" group')

    # Tenant context BEFORE any executor dispatch (CH row policies).
    request.tenant_id = app.app_key
    return user, app


def _check_rate_limit(user):
    """Per-user daily cap, counted from ai.query.log (UTC day)."""
    ICP = request.env['ir.config_parameter'].sudo()
    try:
        cap = int(ICP.get_param(DAILY_LIMIT_PARAM, DEFAULT_DAILY_LIMIT))
    except (TypeError, ValueError):
        cap = DEFAULT_DAILY_LIMIT
    if cap <= 0:
        return
    midnight = datetime.combine(datetime.utcnow().date(), dtime.min)
    used = request.env['ai.query.log'].sudo().search_count([
        ('user_id', '=', user.id),
        ('create_date', '>=', midnight),
    ])
    if used >= cap:
        raise RateLimited(midnight + timedelta(days=1))


def _log_query(user, app, source, mode, question, sql, row_count,
               duration_ms, status, error=None, requested_sql=None):
    try:
        request.env['ai.query.log'].sudo().create({
            'user_id': user.id,
            'app_id': app.id,
            'app_key': app.app_key,
            'source_id': source.id if source else False,
            'channel': 'mcp',
            'mode': mode,
            'question': question or False,
            'requested_sql': requested_sql or False,
            'sql': sql or False,
            'row_count': row_count or 0,
            'duration_ms': duration_ms or 0,
            'status': status,
            'error': (error or '')[:500] or False,
        })
    except Exception:  # noqa: BLE001 — logging must never mask the response
        _logger.exception('ai.query.log write failed')


# ── Payload builders ───────────────────────────────────────────────────────

def _dialect_notes(engines):
    """Per-engine SQL dialect guidance for the desktop LLM, lifted from the
    prompt tails the in-house generator already maintains."""
    from odoo.addons.dashboard_builder.services import ai_sql_generator as gen
    notes = {}
    mapping = {
        'clickhouse': getattr(gen, '_PROMPT_CLICKHOUSE', ''),
        'snowflake': getattr(gen, '_PROMPT_SNOWFLAKE', ''),
        'postgres_local': getattr(gen, '_PROMPT_POSTGRES', ''),
    }
    for engine in engines:
        note = mapping.get(engine)
        if note:
            notes[engine] = note.strip()
    return notes


def _source_payload(src, visible_ids, detail='full'):
    from odoo.addons.dashboard_builder.services.ai_sql_generator import (
        AiSqlGenerator,
    )
    payload = {
        'id': src.id,
        'name': src.name,
        'table_name': src.table_name,
        'engine': src.engine or 'postgres_local',
        'description': src.description or '',
    }
    if detail == 'full':
        payload['columns'] = [
            AiSqlGenerator._build_column_context(c) for c in src.column_ids]
        # Only expose relations whose target is itself AI-visible for this
        # app AND on the same connection — a join edge to a PHI /
        # non-assigned source must not leak even its table name, and a
        # cross-connection target cannot be joined in one query anyway.
        payload['relations'] = [{
            'target_source_id': rel.target_source_id.id,
            'target_table': rel.target_source_id.table_name,
            'join_type': rel.join_type,
            'from_column': rel.source_column,
            'to_column': rel.target_column,
        } for rel in src.relation_ids
            if rel.target_source_id.id in visible_ids
            and rel.target_source_id.connection_id.id
                == src.connection_id.id]
    else:
        payload['column_count'] = len(src.column_ids)
    return payload


_HOST_RE = re.compile(
    r'(https?://\S+|[A-Za-z0-9.-]+\.(?:internal|local|svc|azure\.com|'
    r'windows\.net|clickhouse\.cloud)\S*|:\d{2,5}\b)')


def _sanitize_error(exc):
    """First line only, hosts/URLs/ports stripped, capped at 300 chars —
    enough signal for the desktop model to fix its SQL, no infra leakage."""
    msg = str(exc).splitlines()[0] if str(exc) else 'query error'
    msg = _HOST_RE.sub('[redacted]', msg)
    return msg[:300]


_AVG_RE = re.compile(r'\bAVG\s*\(\s*"?([A-Za-z0-9_]+)"?\s*\)', re.IGNORECASE)


def _never_avg_warnings(sql, src):
    """Advisory: AVG() over a pre-computed-rate column is mathematically
    wrong (per-row denominators differ). Warn, never block."""
    never_avg = {c.column_name.lower() for c in src.column_ids if c.never_avg}
    hits = [m.group(1) for m in _AVG_RE.finditer(sql)
            if m.group(1).lower() in never_avg]
    return [
        f"AVG({col}) averages a pre-computed rate — use "
        f"SUM(numerator)/NULLIF(SUM(denominator),0) instead."
        for col in dict.fromkeys(hits)
    ]


# ── Routes ─────────────────────────────────────────────────────────────────

class AiAssistAPI(http.Controller):

    @http.route('/api/v1/ai/scope', type='http', auth='none',
                methods=['GET'], csrf=False, readonly=True)
    def ai_scope(self, **kw):
        try:
            user, app = _get_ai_user()
        except ValueError as e:
            return _json_error(401, str(e))
        except PermissionError as e:
            return _json_error(403, str(e))

        detail = (kw.get('detail') or 'full').lower()
        Source = request.env['dashboard.schema.source']
        sources = Source.get_ai_visible_sources(app)
        visible_ids = set(sources.ids)
        engines = {s.engine or 'postgres_local' for s in sources}
        return _json_response({
            'app': {'app_key': app.app_key, 'name': app.name},
            'sources': [
                _source_payload(s, visible_ids, detail) for s in sources],
            'sql_dialect_notes': _dialect_notes(engines),
            'usage': {
                'row_cap': MAX_ROW_LIMIT,
                'default_limit': DEFAULT_ROW_LIMIT,
            },
        })

    @http.route('/api/v1/ai/schema/<int:source_id>', type='http', auth='none',
                methods=['GET'], csrf=False, readonly=True)
    def ai_schema(self, source_id, **kw):
        try:
            user, app = _get_ai_user()
        except ValueError as e:
            return _json_error(401, str(e))
        except PermissionError as e:
            return _json_error(403, str(e))

        Source = request.env['dashboard.schema.source']
        sources = Source.get_ai_visible_sources(app)
        src = sources.filtered(lambda s: s.id == source_id)
        if not src:
            return _json_error(403, 'Source is not available to AI Assist '
                                    'for this app')
        payload = _source_payload(src, set(sources.ids), 'full')
        payload['sql_dialect_notes'] = _dialect_notes(
            {src.engine or 'postgres_local'})
        return _json_response(payload)

    @http.route('/api/v1/ai/query', type='http', auth='none',
                methods=['POST'], csrf=False)
    def ai_query(self, **kw):
        try:
            user, app = _get_ai_user()
        except ValueError as e:
            return _json_error(401, str(e))
        except PermissionError as e:
            return _json_error(403, str(e))

        body = _get_request_json()
        source_id = body.get('source_id')
        sql = (body.get('sql') or '').strip()
        # v1 is MCP-first: the desktop client's model authors the SQL. The
        # server-side NL→SQL mode ('question') was cut per review — it
        # duplicated the desktop model's job and doubled the LLM surface.
        if body.get('question'):
            return _json_error(
                400, "'question' mode is not available — author SQL from "
                     "get_schema() and send it as 'sql'")
        if not sql:
            return _json_error(400, "Missing 'sql'")
        try:
            # Clamp BOTH bounds — a negative request limit must not reach
            # execute_preview's LIMIT-append logic.
            limit = max(1, min(int(body.get('limit') or DEFAULT_ROW_LIMIT),
                               MAX_ROW_LIMIT))
        except (TypeError, ValueError):
            limit = DEFAULT_ROW_LIMIT
        mode = 'sql'
        question = ''

        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            return _json_error(400, "Missing or invalid 'source_id'")

        # Re-verify the source against the visibility rule — NEVER trust ids.
        Source = request.env['dashboard.schema.source']
        src = Source.get_ai_visible_sources(app).filtered(
            lambda s: s.id == source_id)
        if not src:
            return _json_error(403, 'Source is not available to AI Assist '
                                    'for this app')

        try:
            _check_rate_limit(user)
        except RateLimited as e:
            _log_query(user, app, src, mode, question, sql, 0, 0,
                       'rate_limited')
            return _json_response(
                {'error': str(e), 'resets_at': str(e.resets_at)}, status=429)

        from odoo.addons.dashboard_builder.services.query_builder import (
            QueryBuilder,
        )
        from ..utils.ai_query_policy import (
            build_allowed_tables,
            validate_and_rewrite_ai_sql,
        )
        qb = QueryBuilder(request.env)
        started = time.monotonic()

        # AI-specific policy (see utils/ai_query_policy.py): engine gate,
        # scope-aware table allowlist (same-connection AI-visible sources,
        # exact names), SETTINGS/FORMAT/function blocks — and the outer
        # row cap is enforced by AST REWRITE, so the SQL executed below is
        # the policy's sanitized output, not the caller's raw text.
        visible = Source.get_ai_visible_sources(app)
        same_conn = visible.filtered(
            lambda s: s.connection_id.id == src.connection_id.id)
        allowed = build_allowed_tables(same_conn.mapped('table_name'))
        requested_sql = sql
        try:
            sql = validate_and_rewrite_ai_sql(
                sql, src.engine, allowed, limit, MAX_ROW_LIMIT)
        except ValueError as e:
            _log_query(user, app, src, mode, question, sql, 0,
                       int((time.monotonic() - started) * 1000),
                       'validation_error', str(e),
                       requested_sql=requested_sql)
            return _json_error(400, f'SQL rejected: {e}')

        ok, err = qb.validate_query(sql)
        if not ok:
            _log_query(user, app, src, mode, question, sql, 0,
                       int((time.monotonic() - started) * 1000),
                       'validation_error', err)
            return _json_error(400, f'SQL rejected: {err}')

        try:
            columns, rows = qb.execute_preview(
                sql, params={}, limit=limit, schema_source=src)
        except Exception as e:  # noqa: BLE001 — sanitized driver message
            # still helps the desktop model self-correct on its next try.
            duration = int((time.monotonic() - started) * 1000)
            msg = _sanitize_error(e)
            _log_query(user, app, src, mode, question, sql, 0, duration,
                       'exec_error', msg, requested_sql=requested_sql)
            return _json_error(400, f'Query failed: {msg}')

        # Hard cap regardless of what the SQL's own LIMIT allowed through.
        truncated = len(rows) > limit
        rows = rows[:limit]
        duration = int((time.monotonic() - started) * 1000)
        _log_query(user, app, src, mode, question, sql, len(rows), duration,
                   'ok', requested_sql=requested_sql)
        return _json_response({
            'sql': sql,
            'columns': columns,
            'rows': rows,
            'row_count': len(rows),
            'truncated': truncated or len(rows) >= limit,
            'duration_ms': duration,
            'warnings': _never_avg_warnings(sql, src),
        })
