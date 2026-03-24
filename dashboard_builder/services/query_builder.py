# -*- coding: utf-8 -*-
"""
Query Builder Service — WB-3

Generates safe, read-only SQL from structured widget builder configs.
All queries are SELECT-only with transaction-level safety enforced.

Usage:
    from dashboard_builder.services.query_builder import QueryBuilder

    qb = QueryBuilder(env)
    sql = qb.build_select_query(config)
    cols, rows = qb.execute_preview(sql, params)
"""

import json
import logging
import re

_logger = logging.getLogger(__name__)

# ── DML / DDL keywords that must NEVER appear in generated or custom SQL ─────
_BLOCKED_KEYWORDS = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|COPY|EXECUTE)\b',
    re.IGNORECASE,
)

# ── Allowed aggregation functions ────────────────────────────────────────────
_VALID_AGGS = {'sum', 'count', 'avg', 'min', 'max'}

# ── Allowed filter operators ─────────────────────────────────────────────────
_VALID_OPS = {'=', '!=', '>', '<', '>=', '<=', 'IN', 'NOT IN', 'LIKE', 'ILIKE'}

# ── SQL identifier validation (table/column names) ──────────────────────────
_IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _safe_ident(name):
    """Validate and quote a SQL identifier to prevent injection."""
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


def _safe_alias(alias):
    """Validate a short SQL alias (1-5 chars, alphanumeric/underscore)."""
    if not alias or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,4}$', alias):
        raise ValueError(f"Invalid SQL alias: {alias!r}")
    return alias


class QueryBuilder:
    """Generates safe SQL from structured widget builder config.

    Usage:
        qb = QueryBuilder(env)
        sql = qb.build_select_query(config)
        cols, rows = qb.execute_preview(sql, params)
    """

    def __init__(self, env):
        self.env = env

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def build_select_query(self, config, multiselect_params=None):
        """Build a SELECT query from structured config.

        Config schema:
        {
            "source_ids": [1, 2],
            "columns": [
                {"source_id": 1, "column": "hha_state", "alias": "state"},
                {"source_id": 2, "column": "total_admits", "agg": "sum", "alias": "admits"}
            ],
            "filters": [
                {"source_id": 1, "column": "hha_state", "op": "=", "param": "hha_state"}
            ],
            "group_by": [{"source_id": 1, "column": "hha_state"}],
            "order_by": [{"alias": "admits", "dir": "DESC"}],
            "limit": 10
        }

        Args:
            config: dict — structured query config from the React builder.
            multiselect_params: set[str] | None — param names that are
                multiselect page filters. When provided, these filters
                generate ``[[...IN %(param)s]]`` optional clauses that
                auto-suppress when the value is ``('__all__',)``.
                Numeric columns get ``::text`` cast for tuple comparison.

        Returns: SQL string with %(param)s placeholders.
        Raises: ValueError if columns/tables invalid or no relation between tables.
        """
        if not config or not isinstance(config, dict):
            raise ValueError("Config must be a non-empty dict.")

        source_ids = config.get('source_ids', [])
        columns = config.get('columns', [])
        filters = config.get('filters', [])
        group_by = config.get('group_by', [])
        order_by = config.get('order_by', [])
        limit = config.get('limit')

        if not source_ids:
            raise ValueError("Config must include at least one source_id.")
        if not columns:
            raise ValueError("Config must include at least one column.")

        # ── Load sources and build alias map ─────────────────────────────────
        Source = self.env['dashboard.schema.source'].sudo()
        sources = Source.browse(source_ids).exists()
        if len(sources) != len(source_ids):
            missing = set(source_ids) - set(sources.ids)
            raise ValueError(f"Schema source(s) not found: {missing}")

        alias_map = self._build_alias_map(sources)

        # ── Validate columns exist in schema ─────────────────────────────────
        self._validate_columns(columns, sources)

        # ── Build SELECT clause ──────────────────────────────────────────────
        select_parts = []
        for col_cfg in columns:
            sid = col_cfg['source_id']
            col_name = col_cfg['column']
            alias = col_cfg.get('alias', col_name)
            agg = col_cfg.get('agg')

            qualified = f'{alias_map[sid]}.{_safe_ident(col_name)}'

            if agg:
                agg_lower = agg.lower()
                if agg_lower not in _VALID_AGGS:
                    raise ValueError(
                        f"Invalid aggregation '{agg}'. "
                        f"Allowed: {', '.join(sorted(_VALID_AGGS))}")
                select_parts.append(f'{agg_lower.upper()}({qualified}) AS {_safe_ident(alias)}')
            else:
                if alias != col_name:
                    select_parts.append(f'{qualified} AS {_safe_ident(alias)}')
                else:
                    select_parts.append(qualified)

        select_clause = ', '.join(select_parts)

        # ── Build FROM + JOIN clauses ────────────────────────────────────────
        from_clause = self._build_from_joins(sources, alias_map)

        # ── Build column type lookup for multiselect casting ─────────────
        _NUMERIC_TYPES = frozenset({'integer', 'float'})
        col_type_map = {}  # {(source_id, column_name): data_type}
        for src in sources:
            for col_rec in src.column_ids:
                col_type_map[(src.id, col_rec.column_name)] = col_rec.data_type

        multiselect_params = multiselect_params or set()

        # ── Build WHERE clause ───────────────────────────────────────────────
        where_parts = []
        for flt in filters:
            sid = flt['source_id']
            col_name = flt['column']
            op = flt.get('op', '=').upper()
            param = flt.get('param', col_name)

            if op not in _VALID_OPS:
                raise ValueError(
                    f"Invalid filter operator '{op}'. "
                    f"Allowed: {', '.join(sorted(_VALID_OPS))}")

            qualified = f'{alias_map[sid]}.{_safe_ident(col_name)}'
            is_multi = param in multiselect_params
            col_type = col_type_map.get((sid, col_name), 'text')

            if is_multi:
                # Multiselect: wrap in [[optional clause]] so __all__
                # sentinel suppresses the clause. Cast numeric columns
                # to text since tuple values are always strings.
                col_ref = f'{qualified}::text' if col_type in _NUMERIC_TYPES else qualified
                where_parts.append(f'[[AND {col_ref} IN %({param})s]]')
            elif op in ('IN', 'NOT IN'):
                # Admin explicitly chose IN/NOT IN operator
                where_parts.append(f'{qualified} {op} %({param})s')
            else:
                # Single-select: standard = / != / > / < etc.
                where_parts.append(f'{qualified} {op} %({param})s')

        where_clause = ''
        if where_parts:
            # Separate standard clauses from [[optional]] clauses
            standard = [p for p in where_parts if not p.startswith('[[')]
            optional = [p for p in where_parts if p.startswith('[[')]
            parts = []
            if standard:
                parts.append('WHERE ' + ' AND '.join(standard))
            elif optional:
                parts.append('WHERE TRUE')
            if optional:
                parts.extend('  ' + clause for clause in optional)
            where_clause = '\n'.join(parts)

        # ── Build GROUP BY clause ────────────────────────────────────────────
        group_parts = []
        for gb in group_by:
            sid = gb['source_id']
            col_name = gb['column']
            group_parts.append(f'{alias_map[sid]}.{_safe_ident(col_name)}')

        group_clause = ''
        if group_parts:
            group_clause = 'GROUP BY ' + ', '.join(group_parts)

        # ── Build ORDER BY clause ────────────────────────────────────────────
        order_parts = []
        for ob in order_by:
            alias = ob.get('alias', '')
            direction = ob.get('dir', 'ASC').upper()
            if direction not in ('ASC', 'DESC'):
                direction = 'ASC'
            order_parts.append(f'{_safe_ident(alias)} {direction}')

        order_clause = ''
        if order_parts:
            order_clause = 'ORDER BY ' + ', '.join(order_parts)

        # ── Build LIMIT clause ───────────────────────────────────────────────
        limit_clause = ''
        if limit and isinstance(limit, int) and limit > 0:
            limit_clause = f'LIMIT {int(limit)}'

        # ── Assemble SQL ─────────────────────────────────────────────────────
        parts = [
            f'SELECT {select_clause}',
            from_clause,
            where_clause,
            group_clause,
            order_clause,
            limit_clause,
        ]
        sql = '\n'.join(p for p in parts if p)

        # Final safety check
        is_valid, err = self.validate_query(sql)
        if not is_valid:
            raise ValueError(f"Generated SQL failed validation: {err}")

        return sql

    def build_drill_query(self, widget, click_column, detail_columns=None):
        """Auto-generates drill-down query from widget's builder_config.

        1. Reads widget.builder_config JSON
        2. Keeps the same FROM + JOIN clauses
        3. Removes aggregation and GROUP BY
        4. Selects detail_columns (or all non-aggregated columns if not specified)
        5. Adds WHERE click_column = %(click_value)s
        6. Adds LIMIT 50

        Args:
            widget: dashboard.widget or dashboard.widget.definition record
            click_column: str — the column the user clicked on
            detail_columns: list[str] or None — columns to show in drill modal

        Returns: SQL string with %(click_value)s + original filter params.
        """
        config_str = widget.builder_config or '{}'
        try:
            config = json.loads(config_str)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("Widget has no valid builder_config for drill-down.")

        if not config.get('source_ids'):
            raise ValueError("Widget builder_config has no source_ids.")

        source_ids = config['source_ids']

        # ── Load sources and build alias map ─────────────────────────────────
        Source = self.env['dashboard.schema.source'].sudo()
        sources = Source.browse(source_ids).exists()
        alias_map = self._build_alias_map(sources)

        # ── Build FROM + JOIN (reuse same logic) ─────────────────────────────
        from_clause = self._build_from_joins(sources, alias_map)

        # ── Build SELECT: detail columns without aggregation ─────────────────
        if detail_columns:
            # Use provided detail columns
            cols = [c.strip() for c in detail_columns if c.strip()]
        else:
            # Use all columns from config, but strip aggregation
            cols = []
            for col_cfg in config.get('columns', []):
                cols.append(col_cfg.get('alias', col_cfg['column']))

        if not cols:
            raise ValueError("No columns for drill-down query.")

        # Build SELECT: try to qualify columns, fall back to unqualified
        select_parts = []
        for col_name in cols:
            # Try to find the column in source metadata for qualification
            qualified = self._try_qualify_column(col_name, config, alias_map)
            select_parts.append(qualified)

        select_clause = ', '.join(select_parts)

        # ── Build WHERE: original filters + click filter ─────────────────────
        where_parts = []

        # Preserve original filters
        for flt in config.get('filters', []):
            sid = flt['source_id']
            col_name = flt['column']
            op = flt.get('op', '=').upper()
            param = flt.get('param', col_name)
            qualified = f'{alias_map[sid]}.{_safe_ident(col_name)}'

            if op in ('IN', 'NOT IN'):
                where_parts.append(f'{qualified} {op} (%({param})s)')
            else:
                where_parts.append(f'{qualified} {op} %({param})s')

        # Add click value filter
        click_qualified = self._try_qualify_column(click_column, config, alias_map)
        where_parts.append(f'{click_qualified} = %(click_value)s')

        where_clause = 'WHERE ' + ' AND '.join(where_parts)

        # ── Assemble (no GROUP BY, no aggregation) ───────────────────────────
        parts = [
            f'SELECT {select_clause}',
            from_clause,
            where_clause,
            'LIMIT 50',
        ]
        sql = '\n'.join(p for p in parts if p)

        is_valid, err = self.validate_query(sql)
        if not is_valid:
            raise ValueError(f"Generated drill SQL failed validation: {err}")

        return sql

    def validate_query(self, sql):
        """Checks SQL against blocked keywords.

        Returns: (is_valid: bool, error_message: str or None)
        """
        if not sql or not sql.strip():
            return False, "Empty SQL query."

        # Strip comments before checking
        sql_clean = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        sql_clean = re.sub(r'--[^\n]*', ' ', sql_clean)

        first_word = sql_clean.strip().split()[0].upper() if sql_clean.strip() else ''
        if first_word not in ('SELECT', 'WITH'):
            return False, "Only SELECT or WITH (CTE) queries are allowed."

        if _BLOCKED_KEYWORDS.search(sql_clean):
            match = _BLOCKED_KEYWORDS.search(sql_clean)
            return False, f"SQL contains blocked keyword: {match.group()}"

        # No semicolons (prevents statement chaining)
        if ';' in sql_clean:
            return False, "Semicolons not allowed (prevents statement chaining)."

        return True, None

    def execute_preview(self, sql, params=None, limit=25):
        """Executes SQL in read-only transaction with timeout.

        Resolves ``[[...]]`` optional clauses before execution.
        A clause is included only when every ``%(param)s`` inside has
        a meaningful value (not None, empty, 'all', or ``('__all__',)``).
        This ensures multiselect "All" selections suppress their clause.

        Returns: (columns: list[str], rows: list[tuple])
        """
        if params is None:
            params = {}

        is_valid, err = self.validate_query(sql)
        if not is_valid:
            raise ValueError(f"Query validation failed: {err}")

        cr = self.env.cr

        try:
            # Enforce read-only transaction and timeout
            cr.execute("SET TRANSACTION READ ONLY")
            cr.execute("SET LOCAL statement_timeout = '10s'")

            # Resolve [[optional clauses]] — same as filter_builder
            exec_sql = sql
            if '[[' in exec_sql:
                from odoo.addons.posterra_portal.utils.filter_builder import resolve_optional_clauses
                exec_sql = resolve_optional_clauses(exec_sql, params)

            # Apply limit if not already in the SQL
            if limit and 'LIMIT' not in exec_sql.upper():
                exec_sql = f'{exec_sql}\nLIMIT {int(limit)}'

            cr.execute(exec_sql, params)
            columns = [desc[0] for desc in cr.description] if cr.description else []
            rows = cr.fetchall()

            return columns, rows

        except Exception as e:
            _logger.error("Query execution failed: %s\nSQL: %s\nParams: %s",
                          e, sql, params)
            raise ValueError(f"Query execution failed: {e}")
        finally:
            # Reset transaction mode so subsequent ORM writes work
            try:
                cr.execute("SET TRANSACTION READ WRITE")
            except Exception:
                pass  # Already in a failed transaction state

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _build_alias_map(self, sources):
        """Build {source_id: alias} map from schema sources.
        Uses table_alias if set, otherwise auto-assigns a, b, c, ..."""
        alias_map = {}
        auto_idx = 0
        auto_letters = 'abcdefghijklmnopqrstuvwxyz'

        for src in sources:
            if src.table_alias:
                alias_map[src.id] = _safe_alias(src.table_alias)
            else:
                while auto_idx < len(auto_letters):
                    candidate = auto_letters[auto_idx]
                    auto_idx += 1
                    if candidate not in alias_map.values():
                        alias_map[src.id] = candidate
                        break
                else:
                    raise ValueError("Too many tables (exceeded 26 auto-aliases).")

        return alias_map

    def _validate_columns(self, columns, sources):
        """Verify every column referenced exists in the schema registry."""
        Column = self.env['dashboard.schema.column'].sudo()

        # Build lookup: {source_id: set of column_names}
        col_lookup = {}
        for src in sources:
            col_lookup[src.id] = set(src.column_ids.mapped('column_name'))

        for col_cfg in columns:
            sid = col_cfg.get('source_id')
            col_name = col_cfg.get('column')

            if sid not in col_lookup:
                raise ValueError(
                    f"Column '{col_name}' references source_id={sid} "
                    f"which is not in source_ids.")

            if col_name not in col_lookup[sid]:
                src = self.env['dashboard.schema.source'].sudo().browse(sid)
                raise ValueError(
                    f"Column '{col_name}' not found in schema source "
                    f"'{src.name}' ({src.table_name}). "
                    f"Run 'Discover Columns' to sync.")

    def _build_from_joins(self, sources, alias_map):
        """Build FROM + JOIN clause from schema sources and relations.

        Returns: "FROM table_a a LEFT JOIN table_b b ON a.col = b.col"
        """
        if len(sources) == 1:
            src = sources[0]
            return f'FROM {_safe_ident(src.table_name)} {alias_map[src.id]}'

        # Multiple tables: need relations
        Relation = self.env['dashboard.schema.relation'].sudo()
        source_ids = sources.ids

        # Find all relations between the given sources
        relations = Relation.search([
            '|',
            '&', ('source_id', 'in', source_ids), ('target_source_id', 'in', source_ids),
            '&', ('target_source_id', 'in', source_ids), ('source_id', 'in', source_ids),
        ])

        if not relations:
            table_names = ', '.join(s.table_name for s in sources)
            raise ValueError(
                f"No relations found between tables: {table_names}. "
                f"Create relations in Schema Sources → Relations tab.")

        # Build JOIN chain: first source is the FROM table
        primary = sources[0]
        joined_ids = {primary.id}
        from_parts = [f'FROM {_safe_ident(primary.table_name)} {alias_map[primary.id]}']

        # Iterate remaining sources and find relations
        remaining = list(sources[1:])
        max_iterations = len(remaining) * 2  # prevent infinite loop

        iterations = 0
        while remaining and iterations < max_iterations:
            iterations += 1
            joined_this_pass = False

            for src in list(remaining):
                # Find a relation connecting src to any already-joined table
                rel = self._find_relation(relations, joined_ids, src.id)
                if rel:
                    # Determine direction
                    if rel.source_id.id in joined_ids and rel.target_source_id.id == src.id:
                        # Forward: source → target
                        join_type = rel.join_type.upper()
                        on_left = f'{alias_map[rel.source_id.id]}.{_safe_ident(rel.source_column)}'
                        on_right = f'{alias_map[src.id]}.{_safe_ident(rel.target_column)}'
                    else:
                        # Reverse: target → source
                        join_type = rel.join_type.upper()
                        on_left = f'{alias_map[rel.target_source_id.id]}.{_safe_ident(rel.target_column)}'
                        on_right = f'{alias_map[src.id]}.{_safe_ident(rel.source_column)}'

                    from_parts.append(
                        f'{join_type} JOIN {_safe_ident(src.table_name)} {alias_map[src.id]} '
                        f'ON {on_left} = {on_right}'
                    )
                    joined_ids.add(src.id)
                    remaining.remove(src)
                    joined_this_pass = True

            if not joined_this_pass:
                unjoined = ', '.join(
                    self.env['dashboard.schema.source'].sudo().browse(s.id).table_name
                    for s in remaining
                )
                raise ValueError(
                    f"Cannot find JOIN path for table(s): {unjoined}. "
                    f"Create relations in Schema Sources → Relations tab.")

        return '\n'.join(from_parts)

    def _find_relation(self, relations, joined_ids, target_id):
        """Find a relation connecting target_id to any source in joined_ids."""
        for rel in relations:
            # Forward: joined source → target
            if rel.source_id.id in joined_ids and rel.target_source_id.id == target_id:
                return rel
            # Reverse: target → joined source
            if rel.target_source_id.id in joined_ids and rel.source_id.id == target_id:
                return rel
        return None

    def _try_qualify_column(self, col_name, config, alias_map):
        """Try to qualify a column name with table alias.
        Falls back to unqualified if not found in config."""
        # Search in config columns for a match
        for col_cfg in config.get('columns', []):
            actual_name = col_cfg.get('alias', col_cfg['column'])
            if actual_name == col_name:
                sid = col_cfg['source_id']
                if sid in alias_map:
                    return f'{alias_map[sid]}.{_safe_ident(col_cfg["column"])}'

        # Fallback: return as safe identifier (unqualified)
        return _safe_ident(col_name)
