# -*- coding: utf-8 -*-
"""Server-side filter state storage for permalink tokens.

Stores complete filter configurations as JSONB so the URL can use a short
token instead of encoding all filter values as query parameters.

Resolution priority (in portal.py):
    permalink key → URL query params → user's last saved → dashboard defaults
"""

import logging
import uuid

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Default TTL for filter state records (hours)
_DEFAULT_TTL_HOURS = 168  # 7 days


class DashboardFilterState(models.Model):
    _name = 'dashboard.filter.state'
    _description = 'Persisted Filter State (Permalink)'
    _order = 'create_date desc'

    key = fields.Char(
        string='Permalink Key',
        required=True,
        index=True,
        default=lambda self: uuid.uuid4().hex[:12],
        help='Short URL-safe token used in the permalink URL.',
    )
    app_id = fields.Many2one(
        'saas.app',
        required=True,
        ondelete='cascade',
        index=True,
        help='App this state belongs to — used for access control scoping.',
    )
    page_id = fields.Many2one(
        'dashboard.page',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        ondelete='set null',
        index=True,
        help='User who created this state. NULL for anonymous/shared links.',
    )
    filter_config = fields.Json(
        string='Filter Configuration',
        required=True,
        help='Complete filter state as {param_name: value, ...}.',
    )
    expires_at = fields.Datetime(
        string='Expires At',
        default=lambda self: fields.Datetime.add(
            fields.Datetime.now(), hours=_DEFAULT_TTL_HOURS),
        index=True,
        help='State records are cleaned up after expiry by the cron job.',
    )

    _sql_constraints = [
        ('unique_key', 'UNIQUE(key)', 'Permalink key must be unique.'),
    ]

    # ── Public API ─────────────────────────────────────────────────────────

    @api.model
    def save_state(self, app_id, page_id, filter_config, user_id=None):
        """Persist filter state and return the short permalink key.

        Args:
            app_id: saas.app ID — required for access control scoping
            page_id: dashboard.page ID
            filter_config: dict of {param_name: value}
            user_id: optional res.users ID

        Returns:
            str: the permalink key (e.g. 'a3f8b2c1d4e5')
        """
        record = self.create({
            'app_id': app_id,
            'page_id': page_id,
            'filter_config': filter_config,
            'user_id': user_id,
        })
        _logger.info(
            '[PERMALINK] Saved state key=%s app=%s page=%s user=%s filters=%d',
            record.key, app_id, page_id, user_id, len(filter_config),
        )
        return record.key

    @api.model
    def load_state(self, key, app_id=None):
        """Load filter state by permalink key, scoped to an app.

        Args:
            key: permalink token string
            app_id: saas.app ID — when provided, validates the state
                belongs to this app (cross-app access prevention).

        Returns:
            dict: filter_config or empty dict if not found/expired/wrong app.
        """
        domain = [
            ('key', '=', key),
            '|',
            ('expires_at', '=', False),
            ('expires_at', '>', fields.Datetime.now()),
        ]
        if app_id:
            domain.insert(0, ('app_id', '=', app_id))
        record = self.search(domain, limit=1)
        if record:
            return record.filter_config or {}
        return {}

    @api.model
    def cleanup_expired(self):
        """Delete expired filter state records. Called by cron."""
        expired = self.search([
            ('expires_at', '!=', False),
            ('expires_at', '<', fields.Datetime.now()),
        ])
        count = len(expired)
        if count:
            expired.unlink()
            _logger.info('[PERMALINK] Cleaned up %d expired filter states', count)
        return count
