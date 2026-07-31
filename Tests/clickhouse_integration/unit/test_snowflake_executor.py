# -*- coding: utf-8 -*-
"""Unit tests for the Snowflake executor's pure helpers.

Covers the security-relevant, Odoo-free logic: deterministic IN-expansion
(with string/comment safety), SELECT-only validation, identifier safety, and
rich-type reconstruction. The connection/audit/guard paths need the live Odoo
runtime and are exercised by the integration suite.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_package, load_source  # noqa: E402

load_package(
    os.path.join("posterra_portal", "utils", "query_executors"),
    package_name="sf_qe_pkg",
)
load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "base.py"),
    package="sf_qe_pkg",
)
_sf = load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "snowflake.py"),
    package="sf_qe_pkg",
)

expand = _sf._expand_in_params
mask = _sf._mask_literals
validate = _sf._validate_select_only
safe_table = _sf._safe_sf_table
rich_type = _sf._rich_sf_type


class TestExpandInParams:
    def test_scalars_unchanged(self):
        sql = "SELECT * FROM v WHERE a = %(a)s AND b = %(b)s"
        out_sql, out_params = expand(sql, {"a": 1, "b": "x"})
        assert out_sql == sql
        assert out_params == {"a": 1, "b": "x"}

    def test_many_values(self):
        sql = "SELECT * FROM v WHERE state IN %(states)s"
        out_sql, out_params = expand(sql, {"states": ("AR", "TX", "IL")})
        assert "state IN (%(states__0)s, %(states__1)s, %(states__2)s)" in out_sql
        assert out_params == {"states__0": "AR", "states__1": "TX", "states__2": "IL"}
        assert "states" not in out_params

    def test_single_value(self):
        sql = "SELECT * FROM v WHERE y IN %(y)s"
        out_sql, out_params = expand(sql, {"y": ["2024"]})
        assert "y IN (%(y__0)s)" in out_sql
        assert out_params == {"y__0": "2024"}

    def test_all_sentinel_single_tuple(self):
        # The ('__all__',) sentinel must not produce a trailing-comma literal.
        sql = "SELECT * FROM v WHERE y IN %(y)s"
        out_sql, out_params = expand(sql, {"y": ("__all__",)})
        assert "y IN (%(y__0)s)" in out_sql
        assert out_params == {"y__0": "__all__"}
        assert "(__all__,)" not in out_sql

    def test_empty_collection_false_predicate(self):
        sql = "SELECT * FROM v WHERE y IN %(y)s"
        out_sql, out_params = expand(sql, {"y": []})
        assert "y IN (NULL)" in out_sql
        assert out_params == {}

    def test_not_in(self):
        sql = "SELECT * FROM v WHERE state NOT IN %(s)s"
        out_sql, out_params = expand(sql, {"s": ("AR", "TX")})
        assert "NOT IN (%(s__0)s, %(s__1)s)" in out_sql

    def test_parenthesised_in_no_double_wrap(self):
        sql = "SELECT * FROM v WHERE state IN (%(s)s)"
        out_sql, _ = expand(sql, {"s": ("AR", "TX")})
        # Author parens preserved; must NOT become IN ((...)).
        assert "state IN (%(s__0)s, %(s__1)s)" in out_sql
        assert "((" not in out_sql

    def test_parenthesised_in_empty(self):
        sql = "SELECT * FROM v WHERE state IN (%(s)s)"
        out_sql, _ = expand(sql, {"s": []})
        assert "state IN (NULL)" in out_sql

    def test_repeated_placeholder_both_expanded(self):
        sql = "SELECT * FROM v WHERE a IN %(x)s OR b IN %(x)s"
        out_sql, out_params = expand(sql, {"x": ("p", "q")})
        assert out_sql.count("%(x__0)s") == 2
        assert out_params == {"x__0": "p", "x__1": "q"}

    def test_collection_outside_in_rejected(self):
        sql = "SELECT * FROM v WHERE a = %(a)s"
        with pytest.raises(ValueError, match="only supported inside an IN"):
            expand(sql, {"a": ("x", "y")})

    def test_placeholder_in_string_literal_ignored(self):
        # A %(x)s that is actually inside a string literal must NOT be expanded.
        sql = "SELECT 'literal %(x)s text' AS c, b FROM v WHERE b IN %(x)s"
        out_sql, out_params = expand(sql, {"x": ("p", "q")})
        # the literal copy stays intact; only the real IN placeholder expands
        assert "'literal %(x)s text'" in out_sql
        assert "b IN (%(x__0)s, %(x__1)s)" in out_sql

    def test_collision_safe_generated_names(self):
        sql = "SELECT * FROM v WHERE a IN %(x)s AND b = %(x__0)s"
        out_sql, out_params = expand(sql, {"x": ("p", "q"), "x__0": "pre"})
        # existing x__0 preserved; generated names avoid clobbering it
        assert out_params["x__0"] == "pre"
        assert "p" in out_params.values() and "q" in out_params.values()


class TestMaskLiterals:
    def test_masks_string_and_keeps_length(self):
        sql = "a 'b c' d"
        masked = mask(sql)
        assert len(masked) == len(sql)
        assert "b c" not in masked
        assert masked.startswith("a ") and masked.endswith(" d")

    def test_masks_line_and_block_comments(self):
        sql = "SELECT 1 -- IN %(x)s\n, 2 /* IN %(y)s */"
        masked = mask(sql)
        assert "%(x)s" not in masked
        assert "%(y)s" not in masked


class TestValidateSelectOnly:
    def test_select_ok(self):
        validate("SELECT 1")
        validate("  with cte as (select 1) select * from cte")

    def test_non_select_rejected(self):
        with pytest.raises(ValueError):
            validate("UPDATE t SET x = 1")

    def test_multiple_statements_rejected(self):
        with pytest.raises(ValueError, match="Multiple SQL statements"):
            validate("SELECT 1; SELECT 2")

    def test_dml_keyword_rejected(self):
        with pytest.raises(ValueError):
            validate("SELECT * FROM v; DROP TABLE v")

    def test_trailing_semicolon_ok(self):
        validate("SELECT 1;")


class TestSafeTable:
    def test_valid_names(self):
        assert safe_table("V") == "V"
        assert safe_table("schema.view") == "schema.view"
        assert safe_table("db.schema.view") == "db.schema.view"

    def test_injection_rejected(self):
        for bad in ("v; drop table x", "v WHERE 1=1", "a.b.c.d", "'v'", "v)"):
            with pytest.raises(ValueError):
                safe_table(bad)


class TestRichType:
    def test_number_scale_zero(self):
        assert rich_type("NUMBER", 38, 0, None) == "NUMBER(38,0)"

    def test_number_scale_nonzero(self):
        assert rich_type("NUMBER", 10, 2, None) == "NUMBER(10,2)"

    def test_varchar_len(self):
        assert rich_type("VARCHAR", None, None, 255) == "VARCHAR(255)"

    def test_plain_type(self):
        assert rich_type("TIMESTAMP_NTZ", None, None, None) == "TIMESTAMP_NTZ"
