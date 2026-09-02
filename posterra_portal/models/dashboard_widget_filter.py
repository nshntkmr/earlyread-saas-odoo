# -*- coding: utf-8 -*-
"""Widget-level filters — N independent controls on ONE widget.

A ``dashboard.widget.filter`` is a dropdown / multi-select / toggle rendered in
the widget header whose value is bound into THAT widget's SQL only (the page
and every other widget are unaffected). It complements the single scope
control (``scope_mode`` / ``scope_option_ids``), which stays untouched.

Three option modes:

* ``static``  — admin types ``value|Label`` lines (like a page filter's Manual
  Options). Own param name.
* ``schema``  — DISTINCT values of a schema-source column, fetched through the
  executor (PG / ClickHouse alike). Own param name.
* ``mirror``  — borrows a PAGE filter's options AND param name; the widget's
  value overrides the page value for this widget only, blank inherits.

Runtime contract (see ``utils/widget_filters.py``): the client sends
``_wf_<param>=<value>``; only declared params are read; values are bound as
SQL parameters, never interpolated. SQL uses the usual
``[[ AND col = %(param)s ]]`` — identical to page filters.

Guard rails:
* a static/schema filter may NOT reuse an active page filter's runtime key
  (that would silently override the page — mirror mode is the sanctioned way);
* a mirror may NOT target a provider-selector, HHA-scoped, auto-filled or
  hidden page filter — widget filters must never become a way around
  tenant / provider scoping;
* two active filters on one widget cannot share a runtime key.
"""

import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..utils.sql_idents import IDENT_RE, TABLE_RE, quote_ident, quote_table

_logger = logging.getLogger(__name__)

# Cap on DISTINCT rows pulled for a schema-mode dropdown: a widget filter is a
# small control, not a roster search.
SCHEMA_OPTIONS_LIMIT = 500


class DashboardWidgetFilter(models.Model):
    _name = 'dashboard.widget.filter'
    _description = 'Widget-level Filter'
    _order = 'sequence asc, id asc'

    # ── Placement ─────────────────────────────────────────────────────────
    widget_id = fields.Many2one(
        'dashboard.widget', required=True, ondelete='cascade', string='Widget',
        index=True)
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)

    # ── Identity ──────────────────────────────────────────────────────────
    label = fields.Char(required=True, string='Label',
        help='Control label shown in the widget header (e.g. "Age Group").')
    param_name = fields.Char(string='SQL Param',
        help='Placeholder name used in this widget\'s SQL, e.g. age_group → '
             'the SQL binds it as a named parameter. Mirror mode ignores this '
             'and uses the mirrored page filter\'s param.')
    ui_type = fields.Selection([
        ('dropdown', 'Dropdown'),
        ('multiselect', 'Multi-select'),
        ('toggle', 'Toggle Buttons'),
    ], default='dropdown', required=True, string='UI')
    is_searchable = fields.Boolean(default=False, string='Searchable',
        help='Type-to-filter dropdown (useful for 50+ options).')

    # ── Options ───────────────────────────────────────────────────────────
    options_mode = fields.Selection([
        ('static', 'Static list'),
        ('schema', 'Schema source column'),
        ('mirror', 'Mirror page filter'),
    ], default='static', required=True, string='Options')
    manual_options = fields.Text(string='Static Options',
        help='One option per line. Format: "value" or "value|Display Label".')
    schema_source_id = fields.Many2one(
        'dashboard.schema.source', string='Schema Source', ondelete='set null',
        help='Schema mode: table whose column supplies the DISTINCT values.')
    value_column = fields.Char(string='Value Column',
        help='Schema mode: column with the option values (bound into SQL).')
    label_column = fields.Char(string='Label Column',
        help='Schema mode: optional column with display labels.')
    page_filter_id = fields.Many2one(
        'dashboard.page.filter', string='Page Filter', ondelete='cascade',
        help='Mirror mode: the page filter whose options and param this '
             'control borrows. The widget value overrides the page value for '
             'this widget only; blank inherits the page value.')

    default_value = fields.Char(string='Default Value',
        help='Initial value. Blank = All (static/schema) or inherit the page '
             'value (mirror). Multi-select: comma-separated.')
    include_all_option = fields.Boolean(default=True, string='Include All',
        help='Show an "All" entry (blank value).')

    # ── Computed ──────────────────────────────────────────────────────────
    runtime_param = fields.Char(compute='_compute_runtime', string='Runtime Param')
    is_multiselect = fields.Boolean(compute='_compute_runtime', string='Multi-select')

    @api.depends('options_mode', 'param_name', 'ui_type',
                 'page_filter_id.param_name', 'page_filter_id.field_name',
                 'page_filter_id.is_multiselect')
    def _compute_runtime(self):
        for rec in self:
            if rec.options_mode == 'mirror' and rec.page_filter_id:
                pf = rec.page_filter_id
                rec.runtime_param = (pf.param_name or pf.field_name or '').strip()
                rec.is_multiselect = bool(pf.is_multiselect)
            else:
                rec.runtime_param = (rec.param_name or '').strip()
                rec.is_multiselect = rec.ui_type == 'multiselect'

    @api.onchange('page_filter_id', 'options_mode')
    def _onchange_mirror_param(self):
        if self.options_mode == 'mirror' and self.page_filter_id:
            pf = self.page_filter_id
            self.param_name = pf.param_name or pf.field_name or ''
            if not self.label:
                self.label = pf.display_label or pf.field_name or ''

    # ── Validation ────────────────────────────────────────────────────────

    @api.constrains('options_mode', 'param_name', 'manual_options',
                    'schema_source_id', 'value_column', 'label_column',
                    'page_filter_id', 'widget_id', 'is_active')
    def _check_mode_requirements(self):
        for rec in self:
            if not rec.is_active:
                continue
            if rec.options_mode == 'mirror':
                pf = rec.page_filter_id
                if not pf:
                    raise ValidationError(
                        "Widget filter '%s': Mirror mode needs a Page Filter."
                        % rec.label)
                if rec.widget_id.page_id and pf.page_id.id != rec.widget_id.page_id.id:
                    raise ValidationError(
                        "Widget filter '%s': the mirrored page filter must "
                        "belong to the widget's page." % rec.label)
                if (pf.is_provider_selector or pf.scope_to_user_hha
                        or pf.auto_fill_from_hha or not pf.is_visible):
                    raise ValidationError(
                        "Widget filter '%s': page filter '%s' is a provider / "
                        "HHA-scoped / auto-filled / hidden filter and cannot "
                        "be mirrored — widget filters must not bypass tenant "
                        "scoping." % (rec.label, pf.display_name))
                key = (pf.param_name or pf.field_name or '').strip()
                if not key:
                    raise ValidationError(
                        "Widget filter '%s': the mirrored page filter has no "
                        "param name." % rec.label)
                continue

            key = (rec.param_name or '').strip()
            if not key or not IDENT_RE.match(key):
                raise ValidationError(
                    "Widget filter '%s': SQL Param must be a plain identifier "
                    "(letters, digits, underscore), got %r." % (rec.label, key))
            if rec.options_mode == 'static':
                if not (rec.manual_options or '').strip():
                    raise ValidationError(
                        "Widget filter '%s': Static list mode needs at least "
                        "one option line." % rec.label)
            elif rec.options_mode == 'schema':
                if not rec.schema_source_id:
                    raise ValidationError(
                        "Widget filter '%s': Schema mode needs a Schema Source."
                        % rec.label)
                vc = (rec.value_column or '').strip()
                if not vc or not IDENT_RE.match(vc):
                    raise ValidationError(
                        "Widget filter '%s': Value Column must be a plain "
                        "identifier, got %r." % (rec.label, vc))
                lc = (rec.label_column or '').strip()
                if lc and not IDENT_RE.match(lc):
                    raise ValidationError(
                        "Widget filter '%s': Label Column must be a plain "
                        "identifier, got %r." % (rec.label, lc))

    @api.constrains('options_mode', 'param_name', 'page_filter_id',
                    'widget_id', 'is_active')
    def _check_runtime_key_collision(self):
        """A static/schema filter must not shadow a page filter's runtime key
        (mirror mode is the explicit way to do that), and two active filters
        on one widget cannot share a key."""
        if self.env.context.get('install_mode'):
            return
        PageFilter = self.env['dashboard.page.filter']
        for rec in self:
            if not rec.is_active:
                continue
            key = rec.runtime_param
            if not key:
                continue
            # Same-widget duplicate (any mode).
            siblings = self.search([
                ('widget_id', '=', rec.widget_id.id),
                ('is_active', '=', True),
                ('id', '!=', rec.id),
            ]).filtered(lambda f: f.runtime_param == key)
            if siblings:
                raise ValidationError(
                    "Widget filter '%s': another filter on this widget already "
                    "uses the param '%s'." % (rec.label, key))
            if rec.options_mode == 'mirror':
                continue
            page = rec.widget_id.page_id
            if not page:
                continue
            clash = PageFilter.search([
                ('page_id', '=', page.id),
                ('is_active', '=', True),
            ]).filtered(lambda f: (f.param_name or f.field_name) == key)
            if clash:
                raise ValidationError(
                    "Widget filter '%s': this page already has a filter with "
                    "the param '%s' ('%s'). Use Mirror page filter mode to "
                    "override a page filter for this widget, or pick a "
                    "different param name." % (rec.label, key, clash[0].display_name))

    # ── Options ───────────────────────────────────────────────────────────

    def get_manual_options_list(self):
        """Parse ``manual_options`` into [{value, label}] (same format as
        ``dashboard.page.filter.manual_options``)."""
        self.ensure_one()
        options = []
        for line in (self.manual_options or '').strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if '|' in line:
                value, label = line.split('|', 1)
                options.append({'value': value.strip(), 'label': label.strip()})
            else:
                options.append({'value': line, 'label': line})
        return options

    def _get_schema_options(self):
        """DISTINCT values of ``value_column`` (+ optional label) through the
        executor. Fails soft (empty list + warning) — a broken filter must not
        take the whole widget down."""
        self.ensure_one()
        source = self.schema_source_id
        table = source.table_name if source else ''
        vcol = (self.value_column or '').strip()
        lcol = (self.label_column or '').strip()
        if (not table or not TABLE_RE.match(table) or not vcol
                or not IDENT_RE.match(vcol) or (lcol and not IDENT_RE.match(lcol))):
            return []
        cols = [vcol] + ([lcol] if lcol and lcol != vcol else [])
        sql = (
            'SELECT DISTINCT %s FROM %s ORDER BY %s LIMIT %d'
            % (', '.join(quote_ident(c) for c in cols), quote_table(table),
               quote_ident(lcol or vcol), SCHEMA_OPTIONS_LIMIT)
        )
        try:
            from ..utils.query_executors import get_executor
            _cols, rows = get_executor(self.env, source).execute(sql, {})
        except Exception as exc:
            _logger.warning(
                'dashboard.widget.filter %s (%s): schema options error: %s',
                self.id, self.label, exc.__class__.__name__)
            _logger.debug('widget filter %s options SQL: %s | %s', self.id, sql, exc)
            return []
        options = []
        seen = set()
        for row in rows:
            raw = row[0] if row else None
            if raw is None:
                continue
            value = str(raw).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            label = value
            if lcol and len(row) > 1 and row[1] is not None:
                label = str(row[1]).strip() or value
            options.append({'value': value, 'label': label})
        return options

    def get_options(self):
        """[{value, label}] for static / schema modes. Mirror returns [] —
        React reads the page filter's options (incl. cascaded ones)."""
        self.ensure_one()
        if self.options_mode == 'static':
            return self.get_manual_options_list()
        if self.options_mode == 'schema':
            return self._get_schema_options()
        return []

    # ── Serialisation ─────────────────────────────────────────────────────

    def to_declaration(self):
        """Runtime declaration consumed by ``utils.widget_filters``."""
        self.ensure_one()
        return {
            'param_name': self.runtime_param,
            'mode': self.options_mode,
            'is_multiselect': self.is_multiselect,
            'default_value': (self.default_value or '').strip(),
        }

    def to_portal_payload(self):
        """Per-widget payload for the React shell (portal.py)."""
        self.ensure_one()
        pf = self.page_filter_id if self.options_mode == 'mirror' else None
        return {
            'id': self.id,
            'label': self.label or '',
            'param_name': self.runtime_param,
            'mode': self.options_mode,
            'ui_type': self.ui_type or 'dropdown',
            'is_multiselect': self.is_multiselect,
            'is_searchable': bool(self.is_searchable),
            'include_all_option': bool(self.include_all_option),
            'default_value': (self.default_value or '').strip(),
            # Mirror: React resolves options from pageConfig.filters by param.
            'filter_param': self.runtime_param if pf else '',
            'filter_id': pf.id if pf else None,
            'options': self.get_options(),
        }

    def to_config_dict(self):
        """Portable dict for the Designer, library stash and page templates.
        Schema source travels as table name (+ id for same-DB round trips);
        the mirrored page filter travels as its param name."""
        self.ensure_one()
        pf = self.page_filter_id
        return {
            'label': self.label or '',
            'param_name': self.param_name or '',
            'sequence': self.sequence,
            'is_active': bool(self.is_active),
            'ui_type': self.ui_type or 'dropdown',
            'is_searchable': bool(self.is_searchable),
            'options_mode': self.options_mode or 'static',
            'manual_options': self.manual_options or '',
            'schema_source_id': self.schema_source_id.id if self.schema_source_id else None,
            'schema_source_table': self.schema_source_id.table_name if self.schema_source_id else '',
            'value_column': self.value_column or '',
            'label_column': self.label_column or '',
            'page_filter_param': (pf.param_name or pf.field_name or '') if pf else '',
            'default_value': self.default_value or '',
            'include_all_option': bool(self.include_all_option),
        }

    @api.model
    def _vals_from_config(self, widget, item, filter_map=None, strict=False):
        """Build create() vals from a ``to_config_dict`` item for ``widget``.

        ``filter_map`` (param → page filter id) is the template restore map;
        without it the page filter is looked up on the widget's page. Returns
        None when a mirror cannot be resolved (or raises when ``strict``)."""
        item = item or {}
        mode = item.get('options_mode') or 'static'
        vals = {
            'widget_id': widget.id,
            'label': item.get('label') or item.get('param_name') or 'Filter',
            'param_name': item.get('param_name') or '',
            'sequence': item.get('sequence', 10) or 10,
            'is_active': bool(item.get('is_active', True)),
            'ui_type': item.get('ui_type') or 'dropdown',
            'is_searchable': bool(item.get('is_searchable', False)),
            'options_mode': mode,
            'manual_options': item.get('manual_options') or '',
            'value_column': item.get('value_column') or '',
            'label_column': item.get('label_column') or '',
            'default_value': item.get('default_value') or '',
            'include_all_option': bool(item.get('include_all_option', True)),
        }
        if mode == 'schema':
            Source = self.env['dashboard.schema.source'].sudo()
            src = Source.browse()
            sid = item.get('schema_source_id')
            if sid:
                try:
                    src = Source.browse(int(sid))
                    if not src.exists():
                        src = Source.browse()
                except (TypeError, ValueError):
                    src = Source.browse()
            if not src and item.get('schema_source_table'):
                src = Source.search(
                    [('table_name', '=', item['schema_source_table'])], limit=1)
            if src:
                vals['schema_source_id'] = src.id
            elif strict:
                raise ValidationError(
                    "Widget filter '%s': schema source '%s' was not found."
                    % (vals['label'], item.get('schema_source_table') or sid))
        if mode == 'mirror':
            pf_param = (item.get('page_filter_param') or item.get('param_name') or '').strip()
            pf_id = (filter_map or {}).get(pf_param)
            if not pf_id and widget.page_id and pf_param:
                pf = self.env['dashboard.page.filter'].sudo().search([
                    ('page_id', '=', widget.page_id.id),
                    ('is_active', '=', True),
                ]).filtered(lambda f: (f.param_name or f.field_name) == pf_param)[:1]
                pf_id = pf.id if pf else None
            if not pf_id:
                if strict:
                    raise ValidationError(
                        "Widget filter '%s': mirrored page filter '%s' does "
                        "not exist on this page." % (vals['label'], pf_param))
                _logger.warning(
                    'widget %s: mirror widget filter %r skipped — page filter '
                    '%r not found on page', widget.id, vals['label'], pf_param)
                return None
            vals['page_filter_id'] = pf_id
            vals['param_name'] = pf_param
        return vals

    @api.model
    def sync_for_widgets(self, widgets, items, filter_map=None, strict=False):
        """Replace the widget filters of every widget in ``widgets`` with
        ``items`` (list of ``to_config_dict`` dicts). Used by the Designer
        (create / update / place), the builder API and template restore."""
        items = [i for i in (items or []) if isinstance(i, dict)]
        for widget in widgets:
            widget.widget_filter_ids.unlink()
            for item in items:
                vals = self._vals_from_config(widget, item, filter_map=filter_map,
                                              strict=strict)
                if vals:
                    self.create(vals)
