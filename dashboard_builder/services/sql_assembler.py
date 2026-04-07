# -*- coding: utf-8 -*-
"""Deterministic SQL assembler for the AI Intent Pipeline.

Takes a structured intent (from the AI) + page filter definitions (from DB)
and builds a complete, correct SQL query. The AI decides WHAT to compute
(SELECT expressions); this module handles HOW to filter (WHERE clauses).

No Odoo imports -- testable standalone with plain dicts.
"""

import re
import logging

_logger = logging.getLogger(__name__)

_IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
_NUMERIC_TYPES = frozenset({'integer', 'float', 'bigint', 'numeric'})

# Blocked keywords in extra_conditions to prevent SQL injection
_BLOCKED_KEYWORDS_RE = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|'
    r'COPY|EXECUTE|CALL|SET|LOAD|IMPORT)\b',
    re.IGNORECASE,
)
_BLOCKED_CHARS_RE = re.compile(r'[;]')  # No statement terminators

# Regex to find aggregate functions: SUM(...), COUNT(...), COUNT(DISTINCT ...),
# AVG(...), MIN(...), MAX(...)
# Captures the function name and the full argument (including nested parens).
_AGG_RE = re.compile(
    r'\b(SUM|COUNT|AVG|MIN|MAX)\s*\(',
    re.IGNORECASE,
)


class SqlAssembler:
    """Build SQL from structured intent + filter definitions.

    Parameters
    ----------
    table_name : str
        The materialized view or table to query (e.g. 'mv_hha_final_inhome').
    filter_defs : list[dict]
        Each dict has keys: ``param_name``, ``db_column``,
        ``is_multiselect`` (bool), ``col_type`` (text/integer/float/etc.).
        Sourced from dashboard.page.filter records at runtime.
    source_columns : set[str] | None
        Column names available in the schema source. When provided, filter
        clauses for columns not in this set are skipped. None = accept all.
    """

    def __init__(self, table_name, filter_defs, source_columns=None):
        if not table_name or not _IDENT_RE.match(table_name):
            raise ValueError(
                'Invalid table name: %r. Must be alphanumeric/underscore.' % table_name
            )
        self.table_name = table_name
        self.filter_defs = filter_defs or []
        self.source_columns = set(source_columns) if source_columns else None

    # =====================================================================
    # Public API
    # =====================================================================

    def assemble(self, intent):
        """Assemble SQL from a structured intent dict.

        Parameters
        ----------
        intent : dict
            Structured intent from the AI. Required keys:
            - mode: 'simple' | 'union_all' | 'cte' | 'raw_override'
            - measures: list of {expression, alias, is_prior_year?, description?}
            For union_all: union_blocks (list of sub-intents)
            For cte: cte_sql (string)
            For raw_override: raw_sql (string)

        Returns
        -------
        dict
            {sql, x_column, y_columns, series_column, explanation, warnings, intent}
        """
        mode = intent.get('mode', 'simple')
        try:
            if mode == 'simple':
                sql = self._assemble_simple(intent)
            elif mode == 'union_all':
                sql = self._assemble_union(intent)
            elif mode == 'cte':
                sql = self._assemble_cte(intent)
            elif mode == 'raw_override':
                sql = self._assemble_raw(intent)
            else:
                raise ValueError('Unknown intent mode: %r' % mode)
        except Exception as exc:
            _logger.warning('SqlAssembler.assemble failed: %s', exc)
            raise ValueError('SQL assembly failed: %s' % exc) from exc

        return {
            'sql': sql,
            'x_column': intent.get('x_column', ''),
            'y_columns': intent.get('y_columns', ''),
            'series_column': intent.get('series_column', ''),
            'explanation': intent.get('explanation', ''),
            'warnings': intent.get('warnings', []),
            'intent': intent,
        }

    # =====================================================================
    # Mode: simple — single SELECT (KPI, bar, line, donut, table, etc.)
    # =====================================================================

    def _assemble_simple(self, intent):
        measures = intent.get('measures', [])
        dimensions = intent.get('dimensions', [])
        extra_conditions = intent.get('extra_conditions', [])
        order_by = intent.get('order_by', [])
        limit = intent.get('limit')

        if not measures and not dimensions:
            raise ValueError('Intent must have at least one measure or dimension.')

        has_prior_year = any(m.get('is_prior_year') for m in measures)

        # SELECT
        select_parts = self._build_select(measures, dimensions, has_prior_year)
        select_clause = 'SELECT\n    ' + ',\n    '.join(select_parts)

        # FROM
        from_clause = 'FROM "%s"' % self.table_name

        # WHERE
        where_clause = self._build_where(extra_conditions, has_prior_year)

        # GROUP BY
        group_by_clause = ''
        if dimensions:
            group_cols = []
            for d in dimensions:
                col = d.get('column', '')
                if col and _IDENT_RE.match(col):
                    group_cols.append('"%s"' % col)
            if group_cols:
                group_by_clause = 'GROUP BY ' + ', '.join(group_cols)

        # ORDER BY
        order_by_clause = ''
        if order_by:
            order_parts = []
            for o in order_by:
                col = o.get('column', '')
                direction = o.get('direction', 'ASC').upper()
                if direction not in ('ASC', 'DESC'):
                    direction = 'ASC'
                if col and _IDENT_RE.match(col):
                    # ORDER BY uses unquoted names — they can reference
                    # both table columns and SELECT aliases
                    order_parts.append('%s %s' % (col, direction))
            if order_parts:
                order_by_clause = 'ORDER BY ' + ', '.join(order_parts)

        # LIMIT
        limit_clause = ''
        if limit and isinstance(limit, int) and limit > 0:
            limit_clause = 'LIMIT %d' % limit

        # Assemble
        parts = [select_clause, from_clause, where_clause]
        if group_by_clause:
            parts.append(group_by_clause)
        if order_by_clause:
            parts.append(order_by_clause)
        if limit_clause:
            parts.append(limit_clause)

        return '\n'.join(parts)

    # =====================================================================
    # Mode: union_all — multiple metrics (bullet gauge, RAG, multi-ring)
    # =====================================================================

    def _assemble_union(self, intent):
        blocks = intent.get('union_blocks', [])
        if not blocks:
            raise ValueError('union_all mode requires union_blocks.')

        sql_parts = []
        for i, block in enumerate(blocks):
            measures = block.get('measures', [])
            label = block.get('label', 'Metric %d' % (i + 1))
            extra_conditions = block.get('extra_conditions', [])
            has_prior_year = any(m.get('is_prior_year') for m in measures)

            select_parts = ["'%s' AS metric_name" % label.replace("'", "''")]
            select_parts.extend(self._build_select(measures, [], has_prior_year))

            select_clause = 'SELECT ' + ', '.join(select_parts)
            from_clause = 'FROM "%s"' % self.table_name
            where_clause = self._build_where(extra_conditions, has_prior_year)

            sql_parts.append('%s\n%s\n%s' % (select_clause, from_clause, where_clause))

        return '\nUNION ALL\n'.join(sql_parts)

    # =====================================================================
    # Mode: cte — WITH clause for sparkline, complex benchmarks
    # =====================================================================

    def _assemble_cte(self, intent):
        cte_sql = intent.get('cte_sql', '')
        if not cte_sql:
            raise ValueError('cte mode requires cte_sql.')

        # The AI provides the CTE body. We inject the WHERE clause
        # by replacing {where_clause} if present, or appending it.
        extra_conditions = intent.get('extra_conditions', [])
        has_prior_year = any(
            m.get('is_prior_year') for m in intent.get('measures', [])
        )
        where_clause = self._build_where(extra_conditions, has_prior_year)

        # Replace {where_clause} placeholder if present in the CTE
        if '{where_clause}' in cte_sql:
            # Strip the leading "WHERE " since {where_clause} is a replacement
            where_body = where_clause
            if where_body.startswith('WHERE '):
                where_body = where_body[6:]
            return cte_sql.replace('{where_clause}', where_body)

        return cte_sql

    # =====================================================================
    # Mode: raw_override — escape hatch for fully custom SQL
    # =====================================================================

    def _assemble_raw(self, intent):
        raw_sql = intent.get('raw_sql', '')
        if not raw_sql:
            raise ValueError('raw_override mode requires raw_sql.')
        return raw_sql

    # =====================================================================
    # SELECT builder
    # =====================================================================

    def _build_select(self, measures, dimensions, has_prior_year):
        """Build SELECT column expressions.

        For measures with is_prior_year=True, wraps aggregates in
        CASE WHEN year = %(_year_prior)s. For non-prior measures when
        YoY is active, wraps in CASE WHEN year IN %(year)s.
        """
        parts = []

        # Dimensions first
        for d in dimensions:
            col = d.get('column', '')
            alias = d.get('alias', '')
            if col and _IDENT_RE.match(col):
                if alias and alias != col and _IDENT_RE.match(alias):
                    parts.append('"%s" AS %s' % (col, alias))
                else:
                    parts.append('"%s"' % col)

        # Measures
        for m in measures:
            expr = m.get('expression', '')
            alias = m.get('alias', '')
            is_prior = m.get('is_prior_year', False)

            if not expr or not alias:
                continue

            if has_prior_year and is_prior:
                # Wrap aggregates for prior year
                expr = self._rewrite_for_prior_year(expr)
            elif has_prior_year and not is_prior:
                # Wrap aggregates for current year
                expr = self._rewrite_for_current_year(expr)

            if _IDENT_RE.match(alias):
                parts.append('%s AS %s' % (expr, alias))
            else:
                parts.append(expr)

        return parts

    # =====================================================================
    # WHERE builder — the critical method
    # =====================================================================

    def _build_where(self, extra_conditions=None, has_prior_year=False):
        """Build WHERE clause deterministically from filter_defs.

        - Multiselect filters -> [[AND col IN %(param)s]]
        - Single-select filters -> [[AND col = %(param)s]]
        - Year scoping for YoY -> (year IN %(year)s OR year = %(_year_prior)s)
          with parentheses to prevent OR from bypassing other filters
        - extra_conditions -> hardcoded business logic from user's request
        """
        parts = []      # mandatory conditions (year scope, extra_conditions)
        clauses = []    # optional filter clauses ([[AND ...]])

        # 1. Year scoping (if YoY comparison needed)
        year_param = self._find_year_filter()
        if has_prior_year and year_param:
            year_fdef = self._get_filter_def(year_param)
            year_col = year_fdef.get('db_column', 'year') if year_fdef else 'year'
            col_type = year_fdef.get('col_type', 'text') if year_fdef else 'text'
            # Year columns are often bigint — need ::text for IN with string tuples
            cast = '::text' if col_type in _NUMERIC_TYPES else ''
            # Build the year scope with explicit string concatenation
            # to avoid format() interpreting %(...) as format keys
            year_scope = (
                '("{col}"{cast} IN %({param})s'
                ' OR '
                '"{col}"{cast} = %(_year_prior)s{cast})'
            ).replace('{col}', year_col).replace('{cast}', cast).replace('{param}', year_param)
            parts.append(year_scope)

        # 2. Extra conditions from intent (business logic)
        for cond in (extra_conditions or []):
            cond_clean = cond.strip()
            if not cond_clean:
                continue
            # Validate: block dangerous SQL patterns
            if _BLOCKED_KEYWORDS_RE.search(cond_clean):
                _logger.warning(
                    'SqlAssembler: blocked dangerous extra_condition: %r', cond_clean
                )
                continue
            if _BLOCKED_CHARS_RE.search(cond_clean):
                _logger.warning(
                    'SqlAssembler: blocked extra_condition with semicolon: %r', cond_clean
                )
                continue
            parts.append(cond_clean)

        # 3. Page filter clauses (deterministic, from filter_defs)
        for fdef in self.filter_defs:
            param = fdef.get('param_name', '')
            db_col = fdef.get('db_column', '')
            if not param or not db_col:
                continue

            # Skip year filter if already handled above
            if has_prior_year and param == year_param:
                continue

            # Safety: reject non-identifier column names
            if not _IDENT_RE.match(db_col):
                continue

            # Schema-column check
            if self.source_columns is not None and db_col not in self.source_columns:
                continue

            is_multi = fdef.get('is_multiselect', False)
            col_type = fdef.get('col_type', 'text')

            # Build the column reference with optional cast
            col_ref = '"%s"' % db_col
            if is_multi and col_type in _NUMERIC_TYPES:
                col_ref = '"%s"::text' % db_col

            if is_multi:
                clauses.append('[[AND %s IN %%(%s)s]]' % (col_ref, param))
            else:
                clauses.append('[[AND %s = %%(%s)s]]' % (col_ref, param))

        # Build the WHERE clause. Always start with WHERE 1=1 so all
        # subsequent parts can use AND (mandatory) or [[AND ...]] (optional).
        # The [[...]] wrapper is resolved at runtime: when the param is
        # empty/"All", the entire [[...]] including the AND is dropped.
        where_lines = ['WHERE 1=1']

        # Mandatory parts (year scope, extra conditions)
        for p in parts:
            where_lines.append('  AND %s' % p)

        # Optional filter clauses (dropped when param is "All"/empty)
        for c in clauses:
            where_lines.append('  %s' % c)

        return '\n'.join(where_lines)

    # =====================================================================
    # Year filter detection
    # =====================================================================

    def _find_year_filter(self):
        """Find the param_name of the year filter (if any).

        Looks for a filter whose db_column is 'year' or param_name is 'year'.
        Returns the param_name string, or None.
        """
        for fdef in self.filter_defs:
            if fdef.get('db_column') == 'year' or fdef.get('param_name') == 'year':
                return fdef.get('param_name', 'year')
        return None

    def _get_filter_def(self, param_name):
        """Get filter def dict by param_name."""
        for fdef in self.filter_defs:
            if fdef.get('param_name') == param_name:
                return fdef
        return None

    # =====================================================================
    # Prior-year rewriting
    # =====================================================================

    def _rewrite_for_prior_year(self, expression):
        """Wrap aggregate functions for prior year comparison.

        Transforms: SUM(hha_admits)
        Into:       SUM(CASE WHEN "year"::text = %(_year_prior)s::text THEN hha_admits END)

        Handles compound expressions like:
          SUM(a+b) / NULLIF(SUM(c), 0) * 100
        Each SUM/COUNT/etc. is individually wrapped.
        """
        return self._rewrite_aggregates(
            expression,
            'CASE WHEN "year"::text = %(_year_prior)s::text THEN {arg} END'
        )

    def _rewrite_for_current_year(self, expression):
        """Wrap aggregate functions for current year (when YoY is active).

        Transforms: SUM(hha_admits)
        Into:       SUM(CASE WHEN "year"::text IN %(year)s THEN hha_admits END)
        """
        return self._rewrite_aggregates(
            expression,
            'CASE WHEN "year"::text IN %(year)s THEN {arg} END'
        )

    def _rewrite_aggregates(self, expression, case_template):
        """Rewrite all aggregate function calls to wrap their arguments.

        Parameters
        ----------
        expression : str
            SQL expression like 'SUM(hha_admits)' or
            'ROUND(SUM(a+b)::numeric / NULLIF(SUM(c), 0) * 100, 2)'
        case_template : str
            Template with {arg} placeholder, e.g.
            'CASE WHEN "year"::text IN %(year)s THEN {arg} END'

        Returns the expression with each aggregate's argument wrapped.
        """
        result = []
        i = 0
        expr = expression

        while i < len(expr):
            match = _AGG_RE.search(expr, i)
            if not match:
                result.append(expr[i:])
                break

            # Append everything before the match
            result.append(expr[i:match.start()])

            func_name = match.group(1)
            paren_start = match.end() - 1  # position of the '('

            # Find the matching closing paren
            paren_end = self._find_matching_paren(expr, paren_start)
            if paren_end is None:
                # No matching paren found — append rest as-is
                result.append(expr[match.start():])
                break

            # Extract the argument (between the parens)
            inner = expr[paren_start + 1:paren_end]

            # Handle COUNT(DISTINCT ...)
            distinct_prefix = ''
            arg = inner.strip()
            if arg.upper().startswith('DISTINCT '):
                distinct_prefix = 'DISTINCT '
                arg = arg[9:].strip()

            # Wrap the argument
            wrapped_arg = case_template.format(arg=arg)
            result.append('%s(%s%s)' % (func_name, distinct_prefix, wrapped_arg))

            i = paren_end + 1

        return ''.join(result)

    @staticmethod
    def _find_matching_paren(s, start):
        """Find the index of the closing paren matching the one at `start`."""
        if start >= len(s) or s[start] != '(':
            return None
        depth = 1
        i = start + 1
        while i < len(s):
            if s[i] == '(':
                depth += 1
            elif s[i] == ')':
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None
