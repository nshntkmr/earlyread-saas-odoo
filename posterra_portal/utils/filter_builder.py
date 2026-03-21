# -*- coding: utf-8 -*-
"""Config-driven WHERE clause generator for dashboard widgets.

No Odoo imports — testable standalone with plain dicts.
"""

import re

_IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
_ALL_SENTINEL = '__all__'
_NUMERIC_TYPES = frozenset({'integer', 'float'})


class DashboardFilterBuilder:
    """Build parameterised WHERE clauses from filter definitions.

    Parameters
    ----------
    user_params : dict
        ``{param_name: value}`` resolved by the portal controller.
        Multi-select params are tuples; single-select are strings.
    filter_defs : list[dict]
        Each dict has keys: ``param_name``, ``db_column``,
        ``is_multiselect``, ``col_type`` (text/integer/float/date/boolean).
    source_columns : set[str] | None
        Column names available in the widget's schema source (MV/table).
        When provided, only filters whose ``db_column`` exists in this set
        produce a WHERE clause.  ``None`` means "accept all".
    exclude_params : list[str] | None
        Parameter names to skip during auto-generation.  Widgets with
        custom logic for specific filters (e.g. year with prior-year
        comparison) pass ``exclude_params=['year']`` so the builder
        handles all other filters automatically.
    """

    def __init__(self, user_params, filter_defs, source_columns=None,
                 exclude_params=None):
        self.user_params = user_params
        self.filter_defs = filter_defs
        self.source_columns = source_columns
        self.exclude_params = set(exclude_params or ())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self, exclude_params=None):
        """Return ``(where_sql, safe_params)``.

        *where_sql* is ready to drop into ``WHERE {where_clause}``.
        Returns ``'1=1'`` when no clauses apply so the SQL stays valid.

        Parameters
        ----------
        exclude_params : list[str] | None
            Additional param names to skip (merged with constructor's
            ``exclude_params``).  Convenience for one-off overrides.
        """
        clauses, params = self.build_clauses(exclude_params=exclude_params)
        where_sql = ' AND '.join(clauses) if clauses else '1=1'
        return where_sql, params

    def build_clauses(self, exclude_params=None):
        """Return ``(clause_list, safe_params)`` for advanced composition."""
        merged_excludes = self.exclude_params
        if exclude_params:
            merged_excludes = merged_excludes | set(exclude_params)

        clauses = []
        params = dict(self.user_params)  # copy — we may add derived keys

        # Always derive year helpers regardless of exclusion, so widgets
        # referencing %(_year_single)s / %(_year_prior)s get valid params.
        self._prepare_year_params(params)

        for fdef in self.filter_defs:
            param = fdef.get('param_name')
            db_col = fdef.get('db_column')
            if not param or not db_col:
                continue

            # Excluded params: skip clause generation but still derive helpers
            if param in merged_excludes:
                continue

            # Safety: reject non-identifier column names
            if not _IDENT_RE.match(db_col):
                continue

            # Schema-column check
            if self.source_columns is not None and db_col not in self.source_columns:
                continue

            value = self.user_params.get(param)
            if value is None:
                continue

            is_multi = fdef.get('is_multiselect', False)
            col_type = fdef.get('col_type', 'text')

            # Build the column reference with optional cast
            col_ref = '"%s"' % db_col
            if is_multi and col_type in _NUMERIC_TYPES:
                col_ref = '"%s"::text' % db_col

            if is_multi:
                clause = self._multi_clause(param, value, col_ref, params)
            else:
                clause = self._single_clause(param, value, col_ref)

            if clause:
                clauses.append(clause)

        return clauses, params

    # ------------------------------------------------------------------
    # Year parameter preparation
    # ------------------------------------------------------------------

    def _prepare_year_params(self, params):
        """Inject ``_year_single`` and ``_year_prior`` into *params*.

        Handles three cases:
        - Single year selected (e.g. ``('2024',)``)
            → ``_year_single = 2024``, ``_year_prior = 2023``
        - Multiple years or 'All' selected
            → both ``None`` (sum everything, no comparison)
        - Already set by the controller
            → leave untouched

        These are available in any widget SQL as ``%(_year_single)s``
        and ``%(_year_prior)s`` for YoY comparison logic.
        """
        # Scan filter_defs for all multiselect numeric params and derive helpers
        for fdef in self.filter_defs:
            param = fdef.get('param_name')
            if not param:
                continue
            is_multi = fdef.get('is_multiselect', False)
            if not is_multi:
                continue
            value = self.user_params.get(param)
            if value is None:
                continue
            self._derive_numeric_helpers(param, value, params)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _multi_clause(self, param, value, col_ref, params):
        """Handle a multi-select filter value (tuple/list or CSV string)."""
        # Normalise to tuple
        if isinstance(value, str):
            if not value or value.lower() == 'all':
                return None
            value = tuple(v.strip() for v in value.split(',') if v.strip())
            params[param] = value
            if not value:
                return None

        if isinstance(value, (list, tuple)):
            if _ALL_SENTINEL in value:
                return None
            if not value:
                return None
            return '%s IN %%(%s)s' % (col_ref, param)

        # Scalar fallback (shouldn't happen for multi, but be safe)
        if value == '' or str(value).lower() == 'all':
            return None
        return '%s = %%(%s)s' % (col_ref, param)

    def _single_clause(self, param, value, col_ref):
        """Handle a single-select filter value (plain string)."""
        if isinstance(value, str) and (value == '' or value.lower() == 'all'):
            return None
        return '%s = %%(%s)s' % (col_ref, param)

    def _derive_numeric_helpers(self, param, value, params):
        """For single-numeric multi-select, emit ``_<param>_single`` / ``_prior``.

        When the user selects a single year (e.g. '2024'):
            _year_single = 2024, _year_prior = 2023

        When the user selects 'All' or multiple years:
            _year_single = None, _year_prior = None
            (sum everything, no comparison — frontend shows no arrow)
        """
        single_key = '_%s_single' % param
        prior_key = '_%s_prior' % param
        # Only derive if not already present (controller may have set them)
        if single_key in params:
            return

        # Normalise value to tuple
        if isinstance(value, str):
            if not value or value.lower() == 'all':
                params[single_key] = None
                params[prior_key] = None
                return
            parts = tuple(v.strip() for v in value.split(',') if v.strip())
        elif isinstance(value, (list, tuple)):
            if _ALL_SENTINEL in value:
                params[single_key] = None
                params[prior_key] = None
                return
            parts = value
        else:
            params[single_key] = None
            params[prior_key] = None
            return

        numeric = [v for v in parts if isinstance(v, str) and v.isdigit()]
        if len(parts) == 1 and numeric:
            params[single_key] = int(numeric[0])
            params[prior_key] = int(numeric[0]) - 1
        else:
            params[single_key] = None
            params[prior_key] = None
