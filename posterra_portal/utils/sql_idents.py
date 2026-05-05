# -*- coding: utf-8 -*-
"""SQL identifier validation + safe quoting.

Centralises the regexes and quoting helpers shared by widget, filter,
section, badge, and scope SQL paths. Exists so a single change here
(e.g. allowing three-segment names ``cluster.db.table``) propagates to
every emission point without grep-and-pray.
"""

import re


# A single SQL identifier (column name, parameter name, alias).
# No dots, no spaces, must start with a letter or underscore.
IDENT_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

# A table reference, optionally qualified with a database/schema.
#   - ``mv_hha_kpi_summary``       (Postgres MV in the public schema)
#   - ``gold.fact_referrals``      (ClickHouse db.table)
#   - ``shared.dim_geo``           (ClickHouse cross-tenant reference)
TABLE_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$')


def is_valid_ident(name):
    """Return True if ``name`` is a safe SQL identifier (column/param)."""
    return bool(name) and bool(IDENT_RE.match(name))


def is_valid_table(name):
    """Return True if ``name`` is a safe table reference (optionally
    qualified with a database/schema)."""
    return bool(name) and bool(TABLE_RE.match(name))


def quote_ident(name):
    """Quote a single SQL identifier. Caller must validate first."""
    return f'"{name}"'


def quote_table(name):
    """Quote a (possibly schema-qualified) table reference.

    ``mv_hha_kpi_summary`` → ``"mv_hha_kpi_summary"``
    ``gold.fact_referrals`` → ``"gold"."fact_referrals"``

    Each segment is quoted independently so SQL parsers see two
    identifiers (database + table), not one identifier with a dot
    inside it. Caller MUST validate ``name`` against ``TABLE_RE``
    before passing it in.
    """
    if '.' in name:
        db, tbl = name.split('.', 1)
        return f'"{db}"."{tbl}"'
    return f'"{name}"'
