# -*- coding: utf-8 -*-
"""AI Assist SQL policy — the chatbot-specific execution boundary.

``QueryBuilder.validate_query`` (SELECT/WITH-only, blocked keywords, no
semicolons) was designed for admin-authored widget SQL. The chatbot accepts
SQL authored by an external LLM on behalf of a portal user, which needs a
stricter, source-allowlist-aware policy layered ON TOP of it.

The policy is **parser-based** (sqlglot, dialect-aware for ClickHouse /
Snowflake) and **scope-aware**: base tables are resolved through
``traverse_scope`` so a CTE named like an allowed table cannot shadow an
unauthorized outer reference, and comma joins / subqueries are enumerated
like any other table expression.

``validate_and_rewrite_ai_sql`` both validates AND returns the SQL to
execute: the outer row cap is enforced by MUTATING the AST
(``tree.limit(n)`` — sqlglot wraps UNION roots in a subquery), so the
executed query always carries a true outer LIMIT regardless of substring
heuristics downstream (a ``'LIMIT'`` string literal or a nested-only LIMIT
would otherwise suppress the shared layer's appended cap).

Checks:
  1. Engine gate — only engines with an execution contract (ClickHouse,
     Snowflake dialects; visibility further restricts v1 to tenant-
     filtered ClickHouse). ``postgres_local`` refused: its executor runs
     on Odoo's own database cursor.
  2. Parseability + single SELECT-shaped statement (fail closed).
  3. Query-level modifier block — ``SETTINGS`` (could override the
     executor's per-query ``SQL_tenant_id``!), ``FORMAT``, ``INTO``
     anywhere in the tree are refused.
  4. Function denylist — data-accessor and engine-escape functions
     (``dictGet*``, ``joinGet*``, ``url``, ``s3``, ``remote*``, ...) are
     refused wherever they appear (SELECT list included), plus a keyword
     regex backstop.
  5. Scope-aware table allowlist — every real base table must EXACTLY
     match a registered AI-visible source table name on the same
     connection. No case folding, no bare-name expansion of qualified
     registrations: ClickHouse identifiers are case-sensitive and a bare
     name may resolve to ``default.<table>`` — a different object.
  6. System-surface block — system./information_schema/pg_catalog refs.
  7. LIMIT — every LIMIT in the tree must be an integer literal ≤ cap
     (kills ``LIMIT NULL`` — unlimited on Snowflake — and bounds inner
     query work); the OUTER limit is then rewritten to
     ``min(requested, existing_outer, cap)``.

If sqlglot is not installed, every check fails CLOSED — AI SQL is refused
with a clear operator-facing message, never waved through.

No Odoo imports — unit-testable without a database. Raises ``ValueError``
with messages the desktop model can read and act on.
"""

import re

try:
    import sqlglot
    from sqlglot import exp as _exp
    from sqlglot.optimizer.scope import traverse_scope as _traverse_scope
except ImportError:  # pragma: no cover — fail closed at check time
    sqlglot = None
    _exp = None
    _traverse_scope = None

_DIALECTS = {
    'clickhouse': 'clickhouse',
    'snowflake': 'snowflake',
}

# Denied function families. Exact names, except entries ending in '*'
# which are prefix matches (dictGet, dictGetOrDefault, dictGetString, ...).
_DENIED_FUNCS = (
    'dictget*', 'dicthas*', 'joinget*',
    'url', 'file', 'remote*', 's3*', 'azureblobstorage', 'hdfs',
    'jdbc', 'odbc', 'mysql', 'postgresql', 'mongodb', 'gcs',
    'iceberg', 'deltalake', 'hudi', 'input', 'merge',
    'cluster*', 'executable', 'dictionary', 'numbers', 'zeros',
    'generaterandom', 'fuzzjson', 'format', 'loop', 'view',
    # Infrastructure disclosure — reveal host/user/server config.
    'hostname', 'currentuser', 'getsetting', 'getserversetting',
    'getmacro', 'fqdn', 'tcpport', 'currentdatabase', 'currentroles',
)

# Keyword backstop — parser check on function nodes is primary.
_BLOCKED_FUNCS_RE = re.compile(
    r'\b(url|file|remote|remoteSecure|s3|s3Cluster|azureBlobStorage|jdbc|'
    r'odbc|mysql|postgresql|mongodb|hdfs|iceberg|deltaLake|hudi|input|'
    r'cluster|clusterAllReplicas|merge|generateRandom|dictGet\w*|'
    r'dictHas\w*|joinGet\w*|executable|dictionary|fuzzJSON|gcs)\s*\(',
    re.IGNORECASE)

_BLOCKED_SCHEMA_PREFIXES = (
    'system.', 'information_schema.', 'pg_catalog.', 'pg_', 'mysql.',
)


def _strip_quotes(ident):
    return (ident or '').replace('"', '').replace('`', '').strip()


def build_allowed_tables(visible_sources_same_conn):
    """Allowed-table set: EXACT registered names only (quote-stripped,
    case preserved). A qualified registration (``gold.fact_x``) does NOT
    admit the bare form — on ClickHouse ``fact_x`` would resolve to
    ``default.fact_x``, a different object; identifiers are also
    case-sensitive.
    """
    return {_strip_quotes(t) for t in visible_sources_same_conn
            if _strip_quotes(t)}


def _func_name_denied(name):
    n = (name or '').lower()
    for entry in _DENIED_FUNCS:
        if entry.endswith('*'):
            if n.startswith(entry[:-1]):
                return True
        elif n == entry:
            return True
    return False


def _table_ref(table):
    parts = [p for p in (table.catalog, table.db, table.name) if p]
    return '.'.join(_strip_quotes(str(p)) for p in parts)


def validate_and_rewrite_ai_sql(sql, engine, allowed_tables,
                                requested_limit, max_limit):
    """Validate ``sql`` against the AI policy and return the SQL to
    execute, with the outer row cap enforced by AST rewrite.

    Raises ValueError on any violation.
    """
    if engine in (None, '', 'postgres_local'):
        raise ValueError(
            'This source runs on the local application database, which is '
            'not queryable through AI Assist. Only sources on external '
            'analytics connections are available.')
    dialect = _DIALECTS.get(engine)
    if dialect is None:
        raise ValueError(
            f'Engine {engine!r} has no AI Assist execution contract.')

    if sqlglot is None:
        raise ValueError(
            'AI SQL validation is unavailable on this server (sqlglot is '
            'not installed) — queries are refused until it is.')

    if _BLOCKED_FUNCS_RE.search(sql):
        raise ValueError(
            'SQL uses a data-accessor or engine-escape function that is '
            'not permitted (url/file/remote/s3/dictGet/joinGet/... are '
            'blocked).')

    try:
        statements = sqlglot.parse(sql, read=dialect)
    except Exception as exc:
        raise ValueError(f'SQL could not be parsed: {str(exc)[:200]}')
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise ValueError('Exactly one SQL statement is allowed.')
    tree = statements[0]

    root = tree
    if isinstance(root, _exp.With):
        root = root.this
    if not isinstance(root, (_exp.Select, _exp.Union)):
        raise ValueError('Only SELECT queries are allowed.')

    # Query-level modifiers: SETTINGS could override the executor's
    # per-query SQL_tenant_id; FORMAT/INTO change output behaviour.
    # Checked on EVERY node so nested subqueries are covered.
    for node in tree.walk():
        if not isinstance(node, _exp.Expression):
            continue
        if node.args.get('settings'):
            raise ValueError(
                'Query-level SETTINGS clauses are not permitted.')
        if node.args.get('format'):
            raise ValueError('FORMAT clauses are not permitted.')
        if node.args.get('into'):
            raise ValueError('INTO clauses are not permitted.')

    # Function denylist — anywhere in the statement, not just FROM.
    for fn in tree.find_all(_exp.Anonymous):
        if _func_name_denied(str(fn.this)):
            raise ValueError(
                f'Function {fn.this!r} is not permitted in AI Assist SQL.')

    # Bare-table IN: ClickHouse treats ``x IN table_name`` as
    # ``x IN (SELECT * FROM table_name)`` — an unauthorized-read path the
    # scope traversal cannot see (the name parses as a Column, not a
    # Table). Require the explicit subquery form; its tables then go
    # through the normal scope-aware allowlist below.
    for in_node in tree.find_all(_exp.In):
        if in_node.args.get('field') is not None:
            raise ValueError(
                'Bare-table IN is not permitted — use an explicit '
                'subquery: x IN (SELECT col FROM table).')

    # LIMIT literals: integer ≤ cap everywhere (kills LIMIT NULL /
    # expressions before the outer rewrite). NOTE: this bounds the result
    # set, NOT warehouse work — ClickHouse may scan/sort/aggregate the
    # full input before applying LIMIT; the executor's per-query
    # max_execution_time / max_memory_usage / max_rows_to_read settings
    # are the workload bound.
    for lim in tree.find_all(_exp.Limit):
        # LIMIT ... BY <cols> is per-group and WITH TIES / percent
        # options change semantics — a global-LIMIT rewrite would
        # silently DROP them (verified against the pinned sqlglot).
        # Reject rather than mangle.
        if lim.args.get('expressions'):
            raise ValueError(
                'LIMIT ... BY is not supported in AI Assist SQL — '
                'aggregate per group instead.')
        if lim.args.get('limit_options'):
            raise ValueError(
                'LIMIT options (WITH TIES / percent) are not supported '
                'in AI Assist SQL.')
        expr = lim.expression
        if not (isinstance(expr, _exp.Literal) and not expr.is_string
                and str(expr.this).isdigit()):
            raise ValueError(
                'LIMIT must be a plain integer literal (LIMIT NULL / '
                'expressions are not permitted).')
        if int(expr.this) > max_limit:
            raise ValueError(
                f'LIMIT {expr.this} exceeds the maximum of {max_limit} '
                'rows — lower the LIMIT and retry.')

    # OFFSET: an unbounded-workload bypass (LIMIT 1 OFFSET 1e9 — and the
    # ``LIMIT 1e9, 1`` comma form parses to the same Offset node). This
    # is a chatbot, not a pagination surface: reject any nonzero offset.
    for off in tree.find_all(_exp.Offset):
        expr = off.expression
        is_zero = (isinstance(expr, _exp.Literal) and not expr.is_string
                   and str(expr.this).isdigit() and int(expr.this) == 0)
        if not is_zero:
            raise ValueError(
                'OFFSET is not supported in AI Assist SQL — use ORDER BY '
                'with a WHERE bound instead of paginating.')

    # Scope-aware base-table resolution: CTE/subquery sources resolve to
    # Scopes and are excluded per their ACTUAL scope — a CTE named like an
    # allowed table cannot shadow an unauthorized outer reference.
    try:
        scopes = list(_traverse_scope(tree))
    except Exception as exc:
        raise ValueError(
            f'SQL structure could not be analyzed: {str(exc)[:150]}')
    real_tables = []
    for scope in scopes:
        for source in scope.sources.values():
            if isinstance(source, _exp.Table):
                real_tables.append(source)

    if not real_tables:
        raise ValueError('SQL references no recognizable table.')

    for t in real_tables:
        if not isinstance(t.this, _exp.Identifier):
            raise ValueError(
                'Table functions and non-table FROM sources are not '
                'permitted.')
        ref = _table_ref(t)
        if not ref:
            raise ValueError('Unresolvable table reference in SQL.')
        if ref.lower().startswith(_BLOCKED_SCHEMA_PREFIXES):
            raise ValueError(
                f'Reference to system surface {ref!r} is not permitted.')
        if ref not in allowed_tables:
            raise ValueError(
                f'Table {ref!r} is not available to AI Assist for this '
                'app. Use the exact table_name values returned by '
                'list_sources/get_schema (they are case-sensitive and '
                'may be schema-qualified).')

    # Outer cap: min(requested, existing outer limit, hard cap), enforced
    # by AST mutation — sqlglot replaces/creates the outer LIMIT and
    # wraps UNION roots in a subquery. The executed SQL therefore always
    # carries a true outer LIMIT.
    effective = min(int(requested_limit), int(max_limit))
    outer_limit = root.args.get('limit')
    if (outer_limit is not None
            and isinstance(outer_limit.expression, _exp.Literal)):
        effective = min(effective, int(outer_limit.expression.this))
    try:
        limited = tree.limit(effective)
        return limited.sql(dialect=dialect)
    except Exception as exc:
        raise ValueError(
            f'Could not enforce the row cap on this query: '
            f'{str(exc)[:150]}')
