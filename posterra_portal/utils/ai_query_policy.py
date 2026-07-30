# -*- coding: utf-8 -*-
"""AI Assist SQL policy — the chatbot-specific execution boundary.

``QueryBuilder.validate_query`` (SELECT/WITH-only, blocked keywords, no
semicolons) was designed for admin-authored widget SQL. The chatbot accepts
SQL authored by an external LLM on behalf of a portal user, which needs a
stricter, source-allowlist-aware policy layered ON TOP of it:

  1. Engine gate — ``postgres_local`` sources are refused in v1: their
     executor runs on Odoo's own database cursor, so arbitrary AI SQL could
     read any Odoo table (res_users, tokens, ...). Only sources on external
     connections (ClickHouse / Snowflake), where DB-level grants and row
     policies bound the blast radius, are queryable.
  2. Table allowlist — every base table referenced in FROM/JOIN must map to
     an AI-visible source **on the same connection** as the requested
     source (CTE names are excluded from the check). ``source_id=A`` with
     SQL reading table B is rejected unless B is itself AI-visible.
  3. System-surface block — system./information_schema/pg_catalog and
     ClickHouse table functions (url, remote, s3, file, ...) are refused.
  4. LIMIT cap — an explicit ``LIMIT`` literal above the cap is rejected
     outright (the shared macro layer only appends LIMIT when absent, so a
     large literal would otherwise sail through).

Pure functions on plain data — no Odoo imports — so the policy is unit
-testable without a database. ``check_ai_sql`` raises ``ValueError`` with a
message the desktop model can read and act on.
"""

import re

# CH table functions + engine escape hatches. Matched as ``name(`` calls.
_BLOCKED_FUNCS_RE = re.compile(
    r'\b(url|file|remote|remoteSecure|s3|s3Cluster|azureBlobStorage|jdbc|'
    r'odbc|mysql|postgresql|mongodb|hdfs|iceberg|deltaLake|hudi|input|'
    r'cluster|clusterAllReplicas|merge|numbers|zeros|generateRandom|'
    r'executable|format|dictionary|view|loop|fuzzJSON|gcs)\s*\(',
    re.IGNORECASE)

_BLOCKED_SCHEMA_PREFIXES = (
    'system.', 'information_schema.', 'pg_catalog.', 'pg_', 'mysql.',
)

# FROM/JOIN followed by an identifier (optionally schema-qualified and/or
# double-quoted / backticked). Subqueries start with '(' and don't match.
_TABLE_REF_RE = re.compile(
    r'\b(?:from|join)\s+((?:"[^"]+"|`[^`]+`|[A-Za-z0-9_]+)'
    r'(?:\.(?:"[^"]+"|`[^`]+`|[A-Za-z0-9_]+))?)',
    re.IGNORECASE)

# WITH alias AS ( ... )  /  , alias AS ( ... )  — captures CTE names.
_CTE_RE = re.compile(
    r'(?:\bwith\s+(?:recursive\s+)?|,\s*)("?[A-Za-z0-9_]+"?)\s*'
    r'(?:\([^)]*\))?\s+as\s*\(',
    re.IGNORECASE)

_LIMIT_RE = re.compile(r'\blimit\s+(\d+)', re.IGNORECASE)

_COMMENT_RE = re.compile(r'/\*.*?\*/|--[^\n]*', re.DOTALL)


def _norm(ident):
    """Normalize an identifier: strip quotes/backticks, lowercase."""
    return ident.replace('"', '').replace('`', '').strip().lower()


def _strip_comments(sql):
    return _COMMENT_RE.sub(' ', sql)


def build_allowed_tables(visible_sources_same_conn):
    """Build the allowed-table set from (table_name, ...) strings.

    Accepts both the fully qualified form (``gold.fact_x``) and the bare
    table (``fact_x``) so the LLM may write either — CH tables are often
    schema-qualified in the source record but not always in SQL.
    """
    allowed = set()
    for table_name in visible_sources_same_conn:
        full = _norm(table_name or '')
        if not full:
            continue
        allowed.add(full)
        if '.' in full:
            allowed.add(full.rsplit('.', 1)[-1])
    return allowed


def check_ai_sql(sql, engine, allowed_tables, max_limit):
    """Raise ValueError if ``sql`` violates the AI execution policy."""
    if engine in (None, '', 'postgres_local'):
        raise ValueError(
            'This source runs on the local application database, which is '
            'not queryable through AI Assist. Only sources on external '
            'analytics connections are available.')

    cleaned = _strip_comments(sql)

    if _BLOCKED_FUNCS_RE.search(cleaned):
        raise ValueError(
            'SQL uses a table function or engine escape hatch that is not '
            'permitted (url/file/remote/s3/... are blocked).')

    for m in _LIMIT_RE.finditer(cleaned):
        if int(m.group(1)) > max_limit:
            raise ValueError(
                f'LIMIT {m.group(1)} exceeds the maximum of {max_limit} '
                'rows — lower the LIMIT and retry.')

    cte_names = {_norm(m.group(1)) for m in _CTE_RE.finditer(cleaned)}
    refs = [_norm(m.group(1)) for m in _TABLE_REF_RE.finditer(cleaned)]
    if not refs:
        raise ValueError('SQL references no recognizable table.')
    for ref in refs:
        if ref in cte_names:
            continue
        if ref.startswith(_BLOCKED_SCHEMA_PREFIXES):
            raise ValueError(
                f'Reference to system surface {ref!r} is not permitted.')
        if ref not in allowed_tables:
            raise ValueError(
                f'Table {ref!r} is not available to AI Assist for this app. '
                'Query only the tables returned by list_sources/get_schema.')
