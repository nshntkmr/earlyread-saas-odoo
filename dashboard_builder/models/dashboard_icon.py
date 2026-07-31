# -*- coding: utf-8 -*-
"""Global icon registry (``dashboard.icon``).

Stable keys → Font Awesome 4 classes. SQL and widget configs reference icons
by KEY only (``clock``, ``user-md``) — never by CSS class — so the glyph an
admin sees is always one this registry vouches for.

Lifecycle contract (plan v5):
  • ``key`` is immutable after create and unique at the DB level.
  • Archiving (``active=False``) removes an icon from NEW selection (pickers
    filter active) but ``get_icon_map()`` still includes it, so saved
    dashboards keep rendering their archived glyphs.
  • Deleting is blocked while any widget config or page template references
    the key — archive instead.
  • Runtime resolution goes through ``sudo().get_icon_map()`` (portal users
    have no ACL on this model) which is ``ormcache``d per registry and
    invalidated on any write.
"""

import re

from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError

_KEY_RE = re.compile(r'^[a-z0-9_-]{1,64}$')
_FA_CLASS_RE = re.compile(r'^fa-[a-z0-9-]{1,40}$')


class DashboardIcon(models.Model):
    _name = 'dashboard.icon'
    _description = 'Dashboard Icon Registry'
    _order = 'category, sequence, key'

    key = fields.Char(
        required=True, index=True,
        help='Stable identifier used by widget configs and SQL results '
             '(e.g. "clock"). Immutable after creation — stored JSON configs '
             'reference it verbatim.')
    label = fields.Char(required=True, help='Human-readable name for pickers.')
    fa_class = fields.Char(
        required=True, string='Font Awesome Class',
        help='FA4 modifier class, e.g. "fa-clock-o". Renderers add the base '
             '"fa" class themselves. The picker preview derives from this — '
             'no stored preview.')
    category = fields.Char(default='general', help='Picker grouping.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
        help='Archived icons disappear from pickers but keep rendering in '
             'widgets that already reference them.')

    _key_unique = models.Constraint(
        'UNIQUE (key)', 'Icon keys must be unique.')

    # ── Validation ────────────────────────────────────────────────────────────

    @api.constrains('key', 'fa_class')
    def _check_key_and_class(self):
        for rec in self:
            if not _KEY_RE.match(rec.key or ''):
                raise ValidationError(
                    'Icon key %r must match %s.' % (rec.key, _KEY_RE.pattern))
            if not _FA_CLASS_RE.match(rec.fa_class or ''):
                raise ValidationError(
                    'Font Awesome class %r must match %s (e.g. "fa-clock-o").'
                    % (rec.fa_class, _FA_CLASS_RE.pattern))

    # ── Lifecycle: immutable key, guarded unlink, cache invalidation ─────────

    def write(self, vals):
        if 'key' in vals:
            for rec in self:
                if vals['key'] != rec.key:
                    raise ValidationError(
                        'Icon keys are immutable — stored widget configs '
                        'reference %r verbatim. Archive this icon and create '
                        'a new one instead.' % rec.key)
        res = super().write(vals)
        self.env.registry.clear_cache()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def unlink(self):
        referencing = []
        for rec in self:
            refs = rec._find_references()
            if refs:
                referencing.append('%s (used by %s)' % (rec.key, refs))
        if referencing:
            raise ValidationError(
                'Cannot delete icons still referenced by saved '
                'configurations: %s. Archive them instead — archived icons '
                'keep rendering where already used.' % '; '.join(referencing))
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    def _find_references(self):
        """Human-readable summary of configs referencing this key, or ''.

        JSON configs quote keys ("clock"), so a LIKE on the quoted key
        matches both scalar fields and allowed_keys arrays. Models from
        higher layers (posterra_portal) are scanned only when installed.
        """
        self.ensure_one()
        needle = '"%s"' % self.key
        hits = []
        scan = [('dashboard.widget.definition', 'widget definitions')]
        if 'dashboard.widget' in self.env:
            scan.append(('dashboard.widget', 'placed widgets'))
        if 'dashboard.page.template' in self.env:
            scan.append(('dashboard.page.template', 'page templates'))
        for model, human in scan:
            Model = self.env[model].sudo()
            domain = []
            if model == 'dashboard.page.template':
                domain = [('page_config', 'like', needle)]
            else:
                domain = ['|',
                          ('attribute_grid_config', 'like', needle),
                          ('metric_list_config', 'like', needle)]
            count = Model.search_count(domain)
            if count:
                hits.append('%d %s' % (count, human))
        return ', '.join(hits)

    # ── Runtime resolution (cached, includes inactive) ────────────────────────

    @api.model
    @tools.ormcache()
    def get_icon_map(self):
        """{key: {'fa_class', 'label', 'active'}} for the WHOLE registry —
        inactive included, so archived glyphs keep rendering. Callers must
        treat the returned dict as read-only (it is the cached object)."""
        rows = self.sudo().with_context(active_test=False).search_read(
            [], ['key', 'fa_class', 'label', 'active'])
        return {r['key']: {'fa_class': r['fa_class'],
                           'label': r['label'],
                           'active': r['active']} for r in rows}

    @api.model
    def get_picker_entries(self):
        """Active icons only, ordered, for Designer/Odoo pickers."""
        rows = self.search_read(
            [('active', '=', True)],
            ['key', 'label', 'fa_class', 'category', 'sequence'],
            order='category, sequence, key')
        return [{'key': r['key'], 'label': r['label'],
                 'fa_class': r['fa_class'], 'category': r['category']}
                for r in rows]
