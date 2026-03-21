# -*- coding: utf-8 -*-

import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class DashboardPageFilter(models.Model):
    _name = 'dashboard.page.filter'
    _description = 'Dashboard Page Filter'
    _order = 'sequence asc, id asc'

    page_id = fields.Many2one('dashboard.page', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    is_active = fields.Boolean(default=True)
    is_required = fields.Boolean(default=False)

    # ── Data source ─────────────────────────────────────────────────────────────
    # Admin picks any table installed in the system, then any column from that
    # table.  The portal controller queries distinct values at render time.

    model_id = fields.Many2one(
        'ir.model',
        string='Table',
        help='The model/table to pull distinct filter values from '
             '(e.g. hha.provider, res.country, …).',
        ondelete='set null',
    )
    field_id = fields.Many2one(
        'ir.model.fields',
        string='Column',
        domain="[('model_id', '=', model_id), "
               "('ttype', 'in', ['char', 'text', 'selection', "
               "                 'integer', 'float', 'date', "
               "                 'datetime', 'many2one'])]",
        help='The column whose distinct values populate the filter dropdown.',
        ondelete='set null',
    )

    # Stored so the controller can read them in a single query (no extra joins).
    model_name = fields.Char(
        related='model_id.model',
        store=True,
        readonly=True,
        string='Model Name',
    )
    field_name = fields.Char(
        related='field_id.name',
        store=True,
        readonly=True,
        string='Field Name',
    )

    # ── Schema Source (alternative to Table/Column for MVs/views) ──────────────
    # When the filter's data lives in a materialized view or raw table that is
    # NOT registered as an Odoo model, admin can pick a Schema Source instead.
    # Options are fetched via raw SQL (SELECT DISTINCT) rather than ORM.

    schema_source_id = fields.Many2one(
        'dashboard.schema.source',
        string='Schema Source',
        help='Alternative to Table.  Pick a registered schema source '
             '(materialized view, view, or raw table) to pull distinct '
             'filter values via SQL instead of the ORM.',
        ondelete='set null',
    )
    schema_column_id = fields.Many2one(
        'dashboard.schema.column',
        string='Source Column',
        domain="[('source_id', '=', schema_source_id)]",
        help='Column from the schema source whose distinct values '
             'populate the filter dropdown.',
        ondelete='set null',
    )
    # Stored for easy access in get_options() and portal_ctx.
    schema_table_name = fields.Char(
        related='schema_source_id.table_name',
        store=True,
        readonly=True,
        string='Schema Table',
    )
    schema_column_name = fields.Char(
        related='schema_column_id.column_name',
        store=True,
        readonly=True,
        string='Schema Column Name',
    )

    # ── Dependency ──────────────────────────────────────────────────────────────
    # Optional: when the parent filter's value changes, this filter is reset and
    # its option list is re-scoped to matching values (same-model only).
    # Edge cases handled:
    #   • Self-dependency     → caught by _check_dependency constraint
    #   • Circular chain      → caught by _check_dependency constraint
    #   • Cross-page          → caught by _check_dependency constraint
    #   • Parent deleted      → ondelete='set null' → filter becomes independent
    #   • Different models    → get_options() falls back to all options gracefully
    depends_on_filter_id = fields.Many2one(
        'dashboard.page.filter',
        string='Depends On',
        domain="[('page_id', '=', page_id), ('id', '!=', id)]",
        ondelete='set null',
        help='Optional parent filter. When the parent value changes, this filter '
             'resets and its options are narrowed to values matching the parent '
             '(only when both filters use the same Table).',
    )
    # Stored so the JS/template can reference the parent field name without
    # an extra ORM traversal.
    depends_on_field_name = fields.Char(
        related='depends_on_filter_id.field_name',
        store=True,
        readonly=True,
        string='Parent Field Name',
    )

    # ── Multi-directional dependencies (new system) ──────────────────────
    outgoing_dependency_ids = fields.One2many(
        'dashboard.filter.dependency', 'source_filter_id',
        string='Outgoing Dependencies',
        help='When this filter changes, these targets are refreshed.',
    )
    incoming_dependency_ids = fields.One2many(
        'dashboard.filter.dependency', 'target_filter_id',
        string='Incoming Dependencies',
        help='When these sources change, this filter is refreshed.',
    )

    # ── Display config ──────────────────────────────────────────────────────────
    label = fields.Char(
        string='Label',
        help='Override the default column label shown in the portal filter bar.',
    )
    default_value = fields.Char(
        help='Value used when no URL parameter is present.',
    )
    placeholder = fields.Char(
        help='Placeholder shown when no value is selected.',
    )

    # ── Manual options ───────────────────────────────────────────────────────────
    # When set, the dropdown is populated from this list instead of querying
    # the database.  Useful for static filters like Year, Payer type, etc.
    # Two line formats are supported:
    #   value           →  option value = label = "value"
    #   value|Label     →  option value = "value", displayed as "Label"
    # Example for a Year filter:
    #   2023
    #   2024
    #   2025|Current Year
    manual_options = fields.Text(
        string='Manual Options',
        help='One option per line.\n'
             'Format: "value" or "value|Display Label"\n'
             'Example: "2025|Current Year"\n'
             'When set, overrides DB-driven options.',
    )

    # ── URL parameter name ───────────────────────────────────────────────────────
    # For DB-driven filters this is auto-filled from the Column field name.
    # For manual-options filters (no Table/Column), type the URL param here,
    # e.g. "year" or "payer".  This becomes the ?year=2025 URL parameter.
    param_name = fields.Char(
        string='URL Param',
        help='URL parameter name for this filter.\n'
             'Auto-filled from Column for DB-driven filters.\n'
             'Must be set manually for manual-options filters.\n'
             'Example: "year", "payer"',
    )

    @api.onchange('field_id')
    def _onchange_field_id_param(self):
        """Auto-fill param_name from field_id when field changes."""
        if self.field_id:
            self.param_name = self.field_id.name

    @api.onchange('schema_source_id')
    def _onchange_schema_source_id(self):
        """Clear columns when source changes."""
        self.schema_column_id = False
        self.hha_scope_column_id = False

    @api.onchange('schema_column_id')
    def _onchange_schema_column_id_param(self):
        """Auto-fill param_name from schema column when column changes."""
        if self.schema_column_id:
            self.param_name = self.schema_column_id.column_name

    # ── HHA scoping & auto-fill behaviour ────────────────────────────────────────
    # These two toggles give the admin fine-grained control over how each filter
    # interacts with the HHA selection in the top bar.

    scope_to_user_hha = fields.Boolean(
        string='Scope to User\'s HHAs',
        default=False,
        help='When ON, the options for this filter are restricted to values that '
             'exist within the logged-in user\'s accessible HHAs.\n'
             'Example: with this ON, the County dropdown only shows counties where '
             'that user\'s providers actually operate — not every county in the '
             'national dataset.\n'
             'Recommended: ON for all geo filters (State, County, City).\n'
             'Leave OFF for filters on shared reference data (Year, Payer, etc.).',
    )

    hha_scope_column_id = fields.Many2one(
        'dashboard.schema.column',
        string='HHA Scope Column',
        domain="[('source_id', '=', schema_source_id)]",
        ondelete='set null',
        help='When "Scope to User HHAs" is ON and this filter uses a schema source, '
             'pick the column that contains HHA CCN values (e.g. hha_ccn).\n'
             'The system will add WHERE <column> IN (...user CCNs...) to restrict options.\n'
             'Also used for cascade from Provider filter (resolves Odoo ID → CCN).\n'
             'Leave blank for filters that don\'t need HHA scoping (Year, Payer, etc.).',
    )

    auto_fill_from_hha = fields.Boolean(
        string='Auto-fill from Selected HHA',
        default=False,
        help='When ON and a single HHA is selected from the top bar, this filter '
             'is automatically pre-populated with the matching field value from '
             'that HHA\'s record.\n'
             'Example: with this ON for the State filter, selecting HHA #1234 '
             '(which is in Ohio) automatically sets State = Ohio.\n'
             'The URL parameter name (URL Param field) must match the hha.provider '
             'field name for auto-fill to work (e.g. "hha_state" for State).',
    )

    is_provider_selector = fields.Boolean(
        string='Provider Selector',
        default=False,
        help='Mark this filter as the Provider selector for this page.\n'
             'When ON, the system uses this filter\'s URL parameter to resolve '
             'the selected HHA provider for auto-fill and geo resolution.\n'
             'Only ONE filter per page should have this enabled.',
    )

    is_visible = fields.Boolean(
        string='Visible in Portal',
        default=True,
        help='When OFF, this filter is hidden from the portal filter bar but '
             'its value is still included in widget SQL params.\n'
             'Use this for "context-only" params (e.g. hha_ccn, hha_name) that '
             'widgets need in SQL but users should not see or change.',
    )

    is_multiselect = fields.Boolean(
        string='Multi-select',
        default=False,
        help='When ON, the portal dropdown allows selecting multiple values.\n'
             'Selected values are comma-separated in the URL (e.g. ?hha_state=Arkansas,Ohio).\n'
             'Widget SQL should use WHERE col = ANY(%(param)s) instead of = %(param)s.',
    )
    is_searchable = fields.Boolean(
        string='Searchable',
        default=False,
        help='When ON, the portal dropdown includes a type-to-filter search box.\n'
             'Useful for filters with many options (50+ states, counties, providers).',
    )

    # ── Display template ───────────────────────────────────────────────────────
    # When the filter's Column is 'id' (record primary key), the raw value
    # is a numeric ID — not useful as a dropdown label.  display_template
    # lets the admin format labels from other columns on the same table.
    #
    # Example: "{hha_ccn} - {hha_brand_name}" → "197161 - Elara Caring"
    #
    # When blank, labels come from the Column value itself (current behavior).
    display_template = fields.Char(
        string='Display Template',
        help='Optional template for dropdown option labels.\n'
             'Use {field_name} placeholders to insert column values.\n'
             'Example: "{hha_ccn} - {hha_brand_name}"\n'
             'Only needed when Column = id and you want a human-readable label.',
    )
    display_template_source = fields.Selection(
        [('table', 'Table (ORM)'), ('schema', 'Schema Source')],
        string='Template Source',
        help='Where to resolve {placeholder} fields in the display template.\n'
             '"Table" uses ORM search_read on the Table/Column model.\n'
             '"Schema Source" uses SQL on the schema source table.',
    )

    # ── "All" option ─────────────────────────────────────────────────────────
    # When ON, the dropdown prepends an "All" option (value='') at the top.
    # For Provider: "All 63 HHAs".  For geo filters: already handled by
    # React's hardcoded <option value="">All</option>.
    include_all_option = fields.Boolean(
        string='Include "All" Option',
        default=False,
        help='When ON, the portal dropdown shows an "All" option at the top.\n'
             'The label is "All" followed by the option count (e.g. "All 63 HHAs").\n'
             'Use for the Provider filter or any filter where "no selection" = "all".',
    )

    # ── Computed display label (used directly in portal QWeb template) ──────────
    @api.depends('label', 'field_id', 'schema_column_id')
    def _compute_display_label(self):
        for rec in self:
            rec.display_label = (
                rec.label
                or rec.field_id.field_description
                or (rec.schema_column_id.display_name if rec.schema_column_id else '')
                or rec.field_name
                or rec.schema_column_name
                or ''
            )

    display_label = fields.Char(compute='_compute_display_label')

    # ── Record display name — shown in Many2one dropdowns (e.g. "Depends On") ──
    # Without this, Odoo falls back to "dashboard.page.filter,<id>" which is
    # unreadable.  We show: "State (HHA Provider)" or "ffs_ma (HHA KPI Summary)"
    @api.depends('label', 'field_id', 'model_id', 'schema_source_id', 'schema_column_id')
    def _compute_display_name(self):
        for rec in self:
            human_label = (
                rec.label
                or rec.field_id.field_description
                or (rec.schema_column_id.display_name if rec.schema_column_id else '')
                or rec.field_name
                or rec.schema_column_name
                or f'Filter #{rec.id}'
            )
            if rec.model_id:
                rec.display_name = f'{human_label} ({rec.model_id.name})'
            elif rec.schema_source_id:
                rec.display_name = f'{human_label} ({rec.schema_source_id.name})'
            else:
                rec.display_name = human_label

    # ── Constraint: prevent self/circular/cross-page dependencies ───────────────
    @api.constrains('depends_on_filter_id')
    def _check_dependency(self):
        for rec in self:
            dep = rec.depends_on_filter_id
            if not dep:
                continue

            # ① Self-dependency
            if dep.id == rec.id:
                raise ValidationError(
                    f'Filter "{rec.label or rec.field_name}" cannot depend on itself.')

            # ② Cross-page dependency
            if dep.page_id.id != rec.page_id.id:
                raise ValidationError(
                    f'Filter "{rec.label or rec.field_name}" can only depend on a '
                    f'filter from the same Dashboard Page.')

            # ③ Circular chain detection: walk the ancestor chain
            visited = {rec.id}
            current = dep
            while current:
                if current.id in visited:
                    raise ValidationError(
                        f'Circular dependency detected: the filter chain loops '
                        f'back to "{rec.label or rec.field_name}". '
                        f'Check the "Depends On" settings of all related filters.')
                visited.add(current.id)
                current = current.depends_on_filter_id

    # ── Onchange: clear field_id when the table changes ────────────────────────
    @api.onchange('model_id')
    def _onchange_model_id(self):
        self.field_id = False

    # ── Multi-value helpers ─────────────────────────────────────────────────────
    def _parse_multi_parent(self, parent_value):
        """Split a CSV parent_value into a list when it contains commas.

        Returns (is_multi, parsed):
            is_multi=True,  parsed=list   — when parent has multiple values
            is_multi=False, parsed=str    — when parent is a single value
        """
        if not parent_value or parent_value == 'all':
            return False, parent_value
        s = str(parent_value)
        if ',' in s:
            return True, [v.strip() for v in s.split(',') if v.strip()]
        return False, parent_value

    # ── Dynamic options ─────────────────────────────────────────────────────────
    def get_manual_options_list(self):
        """Parse manual_options text into [{value, label}, ...].

        Supports two line formats:
            value           →  {'value': 'value', 'label': 'value'}
            value|Label     →  {'value': 'value', 'label': 'Label'}
        Blank lines are skipped.
        """
        self.ensure_one()
        if not self.manual_options:
            return []
        options = []
        for line in self.manual_options.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if '|' in line:
                parts = line.split('|', 1)
                options.append({
                    'value': parts[0].strip(),
                    'label': parts[1].strip(),
                })
            else:
                options.append({'value': line, 'label': line})
        return options

    def to_filter_defs(self):
        """Export active filters as plain dicts for DashboardFilterBuilder.

        Returns a list of dicts with keys: param_name, db_column,
        is_multiselect, col_type.  Only includes filters that have both
        a param_name and a db_column (required for SQL binding).
        """
        defs = []
        for f in self.filtered('is_active'):
            param = f.param_name or f.field_name
            db_col = f.schema_column_name or f.field_name
            if not param or not db_col:
                continue
            col_type = f.schema_column_id.data_type if f.schema_column_id else 'text'
            defs.append({
                'param_name': param,
                'db_column': db_col,
                'is_multiselect': f.is_multiselect,
                'col_type': col_type or 'text',
            })
        return defs

    # ── Constraint resolution helpers ──────────────────────────────────────
    def _resolve_constraint_values(self, parent_value=None, constraint_values=None):
        """Normalise constraint inputs into a dict {filter_record: value}.

        Supports two call patterns:
        1) Legacy: parent_value (single string) + depends_on_filter_id
        2) New:    constraint_values dict {source_filter_id: value, ...}

        Returns dict mapping source filter records → value string.
        Empty/falsy values are excluded.
        """
        result = {}
        if constraint_values:
            FilterModel = self.env['dashboard.page.filter'].sudo()
            for src_id, val in constraint_values.items():
                val_str = str(val).strip() if val else ''
                if not val_str or val_str == 'all':
                    continue
                src = FilterModel.browse(int(src_id))
                if src.exists():
                    result[src] = val_str
        elif parent_value and self.depends_on_filter_id:
            val_str = str(parent_value).strip()
            if val_str and val_str != 'all':
                result[self.depends_on_filter_id] = val_str
        return result

    def _build_orm_domain_from_constraints(self, constraints,
                                           all_filter_values=None):
        """Build an ORM domain list from resolved constraints.

        constraints: dict {source_filter_record: value_string}
        all_filter_values: dict {param_name: value} — full filter state
        Returns: list of Odoo domain tuples.
        """
        domain = []
        self_model = self.model_name or ''
        # Track which filter IDs are already handled via explicit constraints
        handled_filter_ids = {src.id for src in constraints}

        for src_filter, value in constraints.items():
            dep_model = (src_filter.model_id.model or src_filter.model_name or '').strip()
            dep_field = (src_filter.field_id.name or src_filter.field_name or '').strip()
            if not dep_field or not dep_model:
                continue
            if dep_model != self_model:
                continue  # cross-model: silently skip for ORM path
            is_multi, parsed = self._parse_multi_parent(value)
            if dep_field == 'id':
                try:
                    if is_multi:
                        domain.append(('id', 'in', [int(v) for v in parsed]))
                    else:
                        domain.append(('id', '=', int(value)))
                except (ValueError, TypeError):
                    pass
            else:
                if is_multi:
                    domain.append((dep_field, 'in', parsed))
                else:
                    domain.append((dep_field, '=', value))

        # ── Apply constraints from ALL active filters on the same model ──
        if all_filter_values and self_model:
            sibling_filters = self.env['dashboard.page.filter'].sudo().search([
                ('page_id', '=', self.page_id.id),
                ('id', '!=', self.id),
                ('id', 'not in', list(handled_filter_ids)),
                ('model_name', '=', self_model),
                ('field_name', '!=', False),
                ('is_active', '=', True),
            ])
            for sib in sibling_filters:
                sib_param = sib.param_name or sib.field_name or ''
                sib_val = (all_filter_values.get(sib_param) or '').strip()
                if not sib_val or sib_val == 'all':
                    continue
                sib_field = (sib.field_name or '').strip()
                if not sib_field:
                    continue
                is_multi, parsed = self._parse_multi_parent(sib_val)
                if sib_field == 'id':
                    try:
                        if is_multi:
                            domain.append(('id', 'in', [int(v) for v in parsed]))
                        else:
                            domain.append(('id', '=', int(sib_val)))
                    except (ValueError, TypeError):
                        pass
                else:
                    if is_multi:
                        domain.append((sib_field, 'in', parsed))
                    else:
                        domain.append((sib_field, '=', sib_val))

        return domain

    def get_options(self, parent_value=None, constraint_values=None,
                    provider_ids=None, all_filter_values=None):
        """Return a sorted list of {value, label} dicts for this filter.

        If manual_options is set, returns those instead of querying the DB.

        parent_value (str | None):
            Legacy single-parent constraint.  When this filter has a
            depends_on_filter_id AND both filters use the same Table, the
            options are narrowed to rows where parent_field = parent_value.

        constraint_values (dict | None):
            Multi-constraint dict {source_filter_id: value, ...}.
            When provided, takes precedence over parent_value.

        provider_ids (list[int] | None):
            When scope_to_user_hha=True AND this filter is on hha.provider,
            restrict the query to these provider record IDs.

        all_filter_values (dict | None):
            Full filter state from the frontend: {param_name: value}.
            Used to apply WHERE constraints from ALL active filters on the
            same schema_source/model, not just explicit dependency edges.
        """
        self.ensure_one()
        # Manual options take priority — no DB query needed.
        if self.manual_options:
            return self.get_manual_options_list()

        # Resolve constraints (supports both legacy and new format).
        constraints = self._resolve_constraint_values(parent_value, constraint_values)

        # ── Schema source path (raw SQL on MVs/views) ────────────────────
        if self.schema_source_id and self.schema_column_id:
            if self.display_template and self.display_template_source == 'schema':
                return self._get_schema_options_with_template(
                    constraints=constraints, provider_ids=provider_ids,
                    all_filter_values=all_filter_values)
            return self._get_schema_source_options(
                constraints=constraints, provider_ids=provider_ids,
                all_filter_values=all_filter_values)

        # Neither ORM model nor schema source configured — no options.
        if not self.model_name or not self.field_name:
            return []

        try:
            Model = self.env[self.model_name].sudo()
        except KeyError:
            _logger.warning(
                'dashboard.page.filter %s: model %r not found in registry',
                self.id, self.model_name,
            )
            return []

        # Build domain from all constraints.
        domain = self._build_orm_domain_from_constraints(
            constraints, all_filter_values=all_filter_values)

        # HHA scoping: restrict to user's accessible providers.
        if (self.scope_to_user_hha
                and provider_ids
                and self.model_name == 'hha.provider'):
            domain = domain + [('id', 'in', provider_ids)]

        # ── Display-template path: composite labels from multiple columns ────
        if self.display_template:
            options = self._get_options_with_template(Model, domain)
            return self._prepend_all_option(options)

        # ── Standard _read_group path ─────────────────────────────────────
        try:
            groups = Model._read_group(
                domain=domain,
                groupby=[self.field_name],
                aggregates=[],
            )
            options = []
            for (raw,) in groups:
                if raw is None or raw is False or raw == '':
                    continue
                # Many2one fields return a recordset in _read_group
                if hasattr(raw, 'id') and hasattr(raw, 'display_name'):
                    options.append({
                        'value': str(raw.id).strip(),
                        'label': str(raw.display_name or '').strip(),
                    })
                else:
                    val = str(raw).strip()
                    options.append({'value': val, 'label': val})
            options = sorted(options, key=lambda o: o['label'].lower())
            return self._prepend_all_option(options)

        except Exception as exc:
            _logger.warning(
                'dashboard.page.filter %s: get_options error: %s',
                self.id, exc,
            )
            return []

    # ── Schema source options (raw SQL) ─────────────────────────────────────
    _IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

    def _build_schema_where(self, constraints, provider_ids=None,
                            all_filter_values=None):
        """Build WHERE parts and params for schema source queries.

        Shared by _get_schema_source_options and _get_schema_options_with_template.
        constraints: dict {source_filter_record: value_string}
        all_filter_values: dict {param_name: value} — full filter state

        Returns (where_parts, params) tuple.
        """
        where_parts = []
        params = {}
        param_counter = [0]  # mutable counter for unique param names

        def _next_param(prefix):
            param_counter[0] += 1
            return f'{prefix}_{param_counter[0]}'

        # Resolve hha_scope_column once (used by both cascade and scoping).
        scope_col = ''
        if self.hha_scope_column_id:
            scope_col = self.hha_scope_column_id.column_name or ''
            if scope_col and not self._IDENT_RE.match(scope_col):
                scope_col = ''

        # ── 1. Cascade constraints ───────────────────────────────────────
        for src_filter, value in constraints.items():
            _logger.info(
                '[CASCADE-SQL] target_filter=%s(id=%s), src_filter=%s(id=%s), '
                'src.model_name=%r, src.field_name=%r, src.schema_column_name=%r, '
                'value=%r, scope_col=%r',
                self.display_label, self.id,
                src_filter.display_label, src_filter.id,
                src_filter.model_name, src_filter.field_name,
                src_filter.schema_column_name, value, scope_col,
            )
            dep_is_hha_provider_id = (
                src_filter.model_name == 'hha.provider'
                and src_filter.field_name == 'id'
                and not src_filter.schema_source_id
            )
            _logger.info('[CASCADE-SQL]   dep_is_hha_provider_id=%s', dep_is_hha_provider_id)
            is_multi, parsed = self._parse_multi_parent(value)

            if dep_is_hha_provider_id and scope_col:
                # Cross-type: resolve Odoo provider ID(s) → CCN string(s).
                try:
                    if is_multi:
                        prov_ids = [int(v) for v in parsed]
                        providers = self.env['hha.provider'].sudo().browse(prov_ids)
                        ccns = [p.hha_ccn for p in providers if p.exists() and p.hha_ccn]
                        if ccns:
                            pname = _next_param('ccn_list')
                            where_parts.append(f'"{scope_col}" IN %({pname})s')
                            params[pname] = tuple(ccns)
                    else:
                        provider = self.env['hha.provider'].sudo().browse(int(value))
                        if provider.exists() and provider.hha_ccn:
                            pname = _next_param('ccn_val')
                            where_parts.append(f'"{scope_col}" = %({pname})s')
                            params[pname] = provider.hha_ccn
                except (ValueError, TypeError):
                    pass
            else:
                # Same-source cascade.
                parent_col = (
                    src_filter.schema_column_name or src_filter.param_name
                    or src_filter.field_name or ''
                ).strip()
                _logger.info('[CASCADE-SQL]   else branch: parent_col=%r', parent_col)
                if parent_col and self._IDENT_RE.match(parent_col):
                    if is_multi:
                        pname = _next_param('val_list')
                        where_parts.append(f'"{parent_col}" IN %({pname})s')
                        params[pname] = tuple(parsed)
                    else:
                        pname = _next_param('val')
                        where_parts.append(f'"{parent_col}" = %({pname})s')
                        params[pname] = value
                else:
                    _logger.warning('[CASCADE-SQL]   ⚠ parent_col empty or invalid, skipping constraint!')

        # ── 1b. Same-table constraints from ALL active filters ────────────
        # Iterate all filters on this page that share the same schema_source
        # and have an active value, applying them as WHERE constraints even
        # if no explicit dependency edge exists.
        if all_filter_values and self.schema_source_id:
            handled_filter_ids = {src.id for src in constraints}
            sibling_filters = self.env['dashboard.page.filter'].sudo().search([
                ('page_id', '=', self.page_id.id),
                ('id', '!=', self.id),
                ('id', 'not in', list(handled_filter_ids)),
                ('schema_source_id', '=', self.schema_source_id.id),
                ('schema_column_name', '!=', False),
                ('is_active', '=', True),
            ])
            for sib in sibling_filters:
                sib_param = sib.param_name or sib.field_name or ''
                sib_val = (all_filter_values.get(sib_param) or '').strip()
                if not sib_val or sib_val == 'all':
                    continue
                sib_col = (sib.schema_column_name or '').strip()
                if not sib_col or not self._IDENT_RE.match(sib_col):
                    continue
                _logger.info(
                    '[CASCADE-SQL]   same-table sibling: %s(id=%s), col=%r, val=%r',
                    sib.display_label, sib.id, sib_col, sib_val,
                )
                is_multi, parsed = self._parse_multi_parent(sib_val)
                if is_multi:
                    pname = _next_param('sib_list')
                    where_parts.append(f'"{sib_col}" IN %({pname})s')
                    params[pname] = tuple(parsed)
                else:
                    pname = _next_param('sib_val')
                    where_parts.append(f'"{sib_col}" = %({pname})s')
                    params[pname] = sib_val

        _logger.info('[CASCADE-SQL] final where_parts=%s, params=%s', where_parts, params)

        # ── 2. HHA user scoping ──────────────────────────────────────────
        if self.scope_to_user_hha and provider_ids and scope_col:
            ccn_values = list(
                self.env['hha.provider'].sudo().browse(provider_ids)
                .mapped('hha_ccn')
            )
            ccn_values = [c for c in ccn_values if c]
            if ccn_values:
                where_parts.append(f'"{scope_col}" IN %(hha_ccn_list)s')
                params['hha_ccn_list'] = tuple(ccn_values)

        return where_parts, params

    def _get_schema_source_options(self, constraints=None, provider_ids=None,
                                   all_filter_values=None):
        """Fetch distinct values from a schema source via raw SQL.

        constraints: dict {source_filter_record: value_string}
        provider_ids: list[int] | None
        all_filter_values: dict {param_name: value} | None
        """
        self.ensure_one()
        constraints = constraints or {}
        table = self.schema_source_id.table_name if self.schema_source_id else self.schema_table_name
        column = self.schema_column_id.column_name if self.schema_column_id else self.schema_column_name
        if not table or not column:
            return []

        if not self._IDENT_RE.match(table) or not self._IDENT_RE.match(column):
            _logger.warning(
                'dashboard.page.filter %s: invalid identifier '
                'table=%r column=%r', self.id, table, column,
            )
            return []

        where_parts, params = self._build_schema_where(
            constraints, provider_ids, all_filter_values=all_filter_values)
        where_clause = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''
        sql = (
            f'SELECT DISTINCT "{column}" FROM "{table}" '
            f'{where_clause} ORDER BY "{column}"'
        )
        _logger.info('[CASCADE-SQL] _get_schema_source_options SQL: %s | params: %s', sql, params)

        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(sql, params)
                rows = self.env.cr.fetchall()
        except Exception as exc:
            _logger.warning(
                'dashboard.page.filter %s: schema source SQL error: %s',
                self.id, exc,
            )
            return []

        options = []
        for (raw,) in rows:
            if raw is None or raw == '':
                continue
            val = str(raw).strip()
            options.append({'value': val, 'label': val})

        _logger.info('[CASCADE-SQL] _get_schema_source_options: %d options returned', len(options))
        return self._prepend_all_option(options)

    # ── Schema source template-based options ──────────────────────────────────
    def _get_schema_options_with_template(self, constraints=None,
                                         provider_ids=None,
                                         all_filter_values=None):
        """Fetch options from a schema source with display_template formatting.

        constraints: dict {source_filter_record: value_string}
        provider_ids: list[int] | None
        all_filter_values: dict {param_name: value} | None
        """
        self.ensure_one()
        constraints = constraints or {}
        template = self.display_template
        template_fields = re.findall(r'\{(\w+)\}', template)

        table = self.schema_source_id.table_name if self.schema_source_id else self.schema_table_name
        value_col = self.schema_column_id.column_name if self.schema_column_id else self.schema_column_name
        if not table or not value_col:
            return []

        select_cols = list(dict.fromkeys([value_col] + template_fields))

        if not self._IDENT_RE.match(table):
            _logger.warning(
                'dashboard.page.filter %s: invalid table identifier %r',
                self.id, table,
            )
            return []
        for col in select_cols:
            if not self._IDENT_RE.match(col):
                _logger.warning(
                    'dashboard.page.filter %s: invalid column identifier %r',
                    self.id, col,
                )
                return []

        where_parts, params = self._build_schema_where(
            constraints, provider_ids, all_filter_values=all_filter_values)
        where_clause = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''
        cols_sql = ', '.join(f'"{c}"' for c in select_cols)
        sql = f'SELECT DISTINCT {cols_sql} FROM "{table}" {where_clause} ORDER BY "{value_col}"'
        _logger.info('[CASCADE-SQL] _get_schema_options_with_template SQL: %s | params: %s', sql, params)

        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(sql, params)
                rows = self.env.cr.fetchall()
        except Exception as exc:
            _logger.warning(
                'dashboard.page.filter %s: schema template SQL error: %s | SQL: %s',
                self.id, exc, sql,
            )
            return []

        options = []
        for row in rows:
            row_dict = dict(zip(select_cols, row))
            raw_val = row_dict.get(value_col)
            if raw_val is None or raw_val == '':
                continue
            label = template
            for tf in template_fields:
                val = row_dict.get(tf, '') or ''
                label = label.replace('{' + tf + '}', str(val).strip())
            label = label.strip()
            value = str(raw_val).strip()
            if value and label:
                options.append({'value': value, 'label': label})

        options = sorted(options, key=lambda o: o['label'].lower())
        return self._prepend_all_option(options)

    # ── Template-based options ───────────────────────────────────────────────
    def _get_options_with_template(self, Model, domain):
        """Fetch options using search_read + display_template formatting.

        Used when the filter value is a record ID but the label needs
        columns from the same record (e.g. "{hha_ccn} - {hha_brand_name}").
        """
        template = self.display_template
        # Extract {field_name} placeholders
        template_fields = re.findall(r'\{(\w+)\}', template)
        read_fields = list(set([self.field_name] + template_fields))

        order = (template_fields[0] + ' asc') if template_fields else 'id asc'
        try:
            records = Model.search_read(
                domain,
                fields=read_fields,
                order=order,
            )
        except Exception as exc:
            _logger.warning(
                'dashboard.page.filter %s: search_read error: %s',
                self.id, exc,
            )
            return []

        options = []
        for rec in records:
            raw_val = rec.get(self.field_name)
            if raw_val is None or raw_val is False:
                continue
            # Build label from template
            label = template
            for tf in template_fields:
                val = rec.get(tf, '') or ''
                label = label.replace('{' + tf + '}', str(val).strip())
            label = label.strip()
            # Value = string of the filter column value (typically 'id')
            value = str(raw_val).strip()
            if value and label:
                options.append({'value': value, 'label': label})

        return sorted(options, key=lambda o: o['label'].lower())

    # ── "All" option prepender ───────────────────────────────────────────────
    def _prepend_all_option(self, options):
        """Prepend an "All N <label>" option when include_all_option is ON."""
        if self.include_all_option and options:
            all_label = f'All {len(options)} {self.label or "items"}'
            options.insert(0, {'value': '', 'label': all_label})
        return options
