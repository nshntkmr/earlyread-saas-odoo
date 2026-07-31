# -*- coding: utf-8 -*-
"""Tests for the shared SQL identifier helpers.

The regexes and quoting functions are used by every widget/filter/
section/badge/scope SQL emission point — bugs here cascade everywhere,
so the validation surface is locked down with explicit cases.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_source  # noqa: E402

_idents = load_source(
    os.path.join("posterra_portal", "utils", "sql_idents.py"),
    module_name="sql_idents_under_test",
)
is_valid_ident = _idents.is_valid_ident
is_valid_table = _idents.is_valid_table
quote_ident = _idents.quote_ident
quote_table = _idents.quote_table


class TestIsValidIdent:
    @pytest.mark.parametrize("name", [
        "hha_ccn",
        "year",
        "_private",
        "Col1",
        "a",
    ])
    def test_accepts_simple(self, name):
        assert is_valid_ident(name)

    @pytest.mark.parametrize("name", [
        "",
        None,
        "1col",            # starts with digit
        "col-name",         # hyphen
        "col name",         # space
        "col;DROP TABLE",   # injection
        "col'",             # quote
        "col.name",         # column names must NOT be dotted
    ])
    def test_rejects_invalid(self, name):
        assert not is_valid_ident(name)


class TestIsValidTable:
    @pytest.mark.parametrize("name", [
        "mv_hha_kpi_summary",         # PG MV (no schema prefix)
        "hha_provider",
        "gold.fact_referrals",        # CH db.table
        "shared.dim_geo",             # CH cross-tenant reference
        "_internal._stuff",
    ])
    def test_accepts_simple_and_dotted(self, name):
        assert is_valid_table(name)

    @pytest.mark.parametrize("name", [
        "",
        None,
        "gold..fact",        # double dot
        ".fact",             # leading dot
        "gold.",             # trailing dot
        "gold.fact.detail",  # 3 segments — current scope is 2 max
        "gold fact",         # space
        "1bad.table",        # starts with digit
        "gold.1bad",         # second segment starts with digit
        "gold;drop table",   # injection
        '"quoted"',          # already-quoted
    ])
    def test_rejects_invalid(self, name):
        assert not is_valid_table(name)


class TestQuoteIdent:
    def test_simple(self):
        assert quote_ident("hha_ccn") == '"hha_ccn"'


class TestQuoteTable:
    def test_simple(self):
        assert quote_table("mv_hha_kpi_summary") == '"mv_hha_kpi_summary"'

    def test_dotted(self):
        # Each segment quoted separately so the SQL parser sees
        # ``"gold"."fact_referrals"`` (db.table) not
        # ``"gold.fact_referrals"`` (one identifier with a dot).
        assert quote_table("gold.fact_referrals") == '"gold"."fact_referrals"'

    def test_shared_dim(self):
        assert quote_table("shared.dim_geo") == '"shared"."dim_geo"'
