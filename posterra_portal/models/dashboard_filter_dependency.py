# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardFilterDependency(models.Model):
    _name = 'dashboard.filter.dependency'
    _description = 'Filter Dependency Edge'
    _order = 'sequence asc, id asc'

    page_id = fields.Many2one(
        'dashboard.page',
        required=True,
        ondelete='cascade',
        index=True,
        help='Denormalized from source/target for fast lookup and same-page constraint.',
    )

    source_filter_id = fields.Many2one(
        'dashboard.page.filter',
        string='When this changes…',
        required=True,
        ondelete='cascade',
        index=True,
        domain="[('page_id', '=', page_id)]",
        help='The filter whose value change triggers a refresh of the target.',
    )
    target_filter_id = fields.Many2one(
        'dashboard.page.filter',
        string='…refresh this',
        required=True,
        ondelete='cascade',
        index=True,
        domain="[('page_id', '=', page_id)]",
        help='The filter whose options are refreshed when the source changes.',
    )

    propagation = fields.Selection(
        [('required', 'Required'), ('optional', 'Optional')],
        default='required',
        required=True,
        help='Required: always cascade and optionally reset value.\n'
             'Optional: refresh options only, never reset value.',
    )
    resets_target = fields.Boolean(
        string='Reset Value',
        default=True,
        help='When ON, the target filter value is reset to "" (All) when the '
             'source changes. When OFF, only the option list is refreshed.\n'
             'Automatically forced OFF when propagation is "optional".',
    )
    sequence = fields.Integer(default=10)

    # ── Stored helper fields for frontend ────────────────────────────────────
    source_param = fields.Char(
        compute='_compute_params', store=True, readonly=True,
    )
    target_param = fields.Char(
        compute='_compute_params', store=True, readonly=True,
    )

    @api.depends(
        'source_filter_id.param_name', 'source_filter_id.field_name',
        'target_filter_id.param_name', 'target_filter_id.field_name',
    )
    def _compute_params(self):
        for rec in self:
            src = rec.source_filter_id
            tgt = rec.target_filter_id
            rec.source_param = (src.param_name or src.field_name or '') if src else ''
            rec.target_param = (tgt.param_name or tgt.field_name or '') if tgt else ''

    # ── SQL constraints ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('unique_edge',
         'UNIQUE(source_filter_id, target_filter_id)',
         'A dependency edge between the same source and target already exists.'),
    ]

    # ── Python constraints ───────────────────────────────────────────────────
    @api.constrains('source_filter_id', 'target_filter_id')
    def _check_no_self_loop(self):
        for rec in self:
            if rec.source_filter_id.id == rec.target_filter_id.id:
                raise ValidationError(
                    'A filter cannot depend on itself. '
                    'Source and target must be different filters.')

    @api.constrains('source_filter_id', 'target_filter_id', 'page_id')
    def _check_same_page(self):
        for rec in self:
            src_page = rec.source_filter_id.page_id.id
            tgt_page = rec.target_filter_id.page_id.id
            if src_page != tgt_page:
                raise ValidationError(
                    'Source and target filters must belong to the same page.')
            if rec.page_id.id and rec.page_id.id not in (src_page, tgt_page):
                raise ValidationError(
                    'Dependency page_id must match the filters\' page.')

    @api.constrains('source_filter_id', 'target_filter_id')
    def _check_no_cycle(self):
        """Validate the dependency graph remains a DAG (no cycles).

        Uses DFS cycle detection on all edges for the same page.
        Runs on every edge create/update to prevent circular cascades.
        """
        pages_to_check = set()
        for rec in self:
            if rec.page_id:
                pages_to_check.add(rec.page_id.id)

        for pid in pages_to_check:
            all_edges = self.search([('page_id', '=', pid)])
            # Build adjacency list: source → [target, ...]
            adj = {}
            for edge in all_edges:
                sid = edge.source_filter_id.id
                tid = edge.target_filter_id.id
                adj.setdefault(sid, []).append(tid)

            # DFS cycle detection
            WHITE, GRAY, BLACK = 0, 1, 2
            color = {}
            for node in adj:
                color[node] = WHITE
            # Also add nodes that are only targets (no outgoing edges)
            for targets in adj.values():
                for t in targets:
                    if t not in color:
                        color[t] = WHITE

            def _has_cycle(node):
                color[node] = GRAY
                for neighbor in adj.get(node, []):
                    if color.get(neighbor, WHITE) == GRAY:
                        return True  # back edge → cycle
                    if color.get(neighbor, WHITE) == WHITE and _has_cycle(neighbor):
                        return True
                color[node] = BLACK
                return False

            for node in list(color):
                if color[node] == WHITE:
                    if _has_cycle(node):
                        raise ValidationError(
                            'Adding this dependency would create a circular '
                            'cascade loop. Filter dependencies must form a '
                            'directed acyclic graph (DAG).')

    @api.onchange('source_filter_id')
    def _onchange_source_filter(self):
        """Auto-fill page_id from source filter."""
        if self.source_filter_id:
            self.page_id = self.source_filter_id.page_id

    @api.onchange('propagation')
    def _onchange_propagation(self):
        """Optional propagation never resets the target value."""
        if self.propagation == 'optional':
            self.resets_target = False
