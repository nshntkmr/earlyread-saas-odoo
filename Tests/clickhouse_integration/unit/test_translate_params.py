# -*- coding: utf-8 -*-
"""Tests for the ClickHouse placeholder translator.

``translate_params`` rewrites psycopg2-style ``%(name)s`` placeholders
to ClickHouse-style ``{name:Type}`` placeholders, inferring the type
from the Python value bound to that name. This is the bridge that lets
admins author one dialect of placeholder and have it work against
either backend.
"""

import datetime
import os
import sys

import pytest

# Bring in the conftest helper without going through pytest's plugin
# system (so this file also runs under plain ``python -m unittest``).
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_package, load_source  # noqa: E402

_pkg = load_package(
    os.path.join("posterra_portal", "utils", "query_executors"),
    package_name="qe_pkg",
)
load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "base.py"),
    package="qe_pkg",
)
_clickhouse = load_source(
    os.path.join("posterra_portal", "utils", "query_executors", "clickhouse.py"),
    package="qe_pkg",
)
_infer_ch_type = _clickhouse._infer_ch_type
translate_params = _clickhouse.translate_params


# ── _infer_ch_type ──────────────────────────────────────────────────────────

class TestInferChType:
    def test_none_becomes_nullable_string(self):
        assert _infer_ch_type(None) == "Nullable(String)"

    def test_bool_before_int(self):
        # bool is a subclass of int, so it MUST be checked first or
        # True/False would map to Int64 and break CH binding.
        assert _infer_ch_type(True) == "UInt8"
        assert _infer_ch_type(False) == "UInt8"

    def test_int(self):
        assert _infer_ch_type(0) == "Int64"
        assert _infer_ch_type(42) == "Int64"
        assert _infer_ch_type(-1) == "Int64"

    def test_float(self):
        assert _infer_ch_type(0.0) == "Float64"
        assert _infer_ch_type(3.14) == "Float64"

    def test_datetime(self):
        assert _infer_ch_type(datetime.datetime(2026, 1, 1, 12, 0, 0)) == "DateTime"

    def test_date(self):
        # date check must NOT match datetime (datetime is a subclass of date).
        assert _infer_ch_type(datetime.date(2026, 1, 1)) == "Date"

    def test_string(self):
        assert _infer_ch_type("hello") == "String"
        assert _infer_ch_type("") == "String"

    def test_empty_list(self):
        # An empty IN clause must still produce a typed Array placeholder
        # so CH can parse it. String inner is the safe default.
        assert _infer_ch_type([]) == "Array(String)"
        assert _infer_ch_type(()) == "Array(String)"

    def test_list_of_strings(self):
        assert _infer_ch_type(["AR", "TX", "CA"]) == "Array(String)"

    def test_list_of_ints(self):
        assert _infer_ch_type([1, 2, 3]) == "Array(Int64)"

    def test_list_of_floats(self):
        assert _infer_ch_type([1.5, 2.5]) == "Array(Float64)"

    def test_list_of_bools(self):
        assert _infer_ch_type([True, False]) == "Array(UInt8)"

    def test_list_of_dates(self):
        assert _infer_ch_type([datetime.date(2026, 1, 1)]) == "Array(Date)"

    def test_list_with_leading_none(self):
        # Inner type must be inferred from the first non-None element.
        assert _infer_ch_type([None, "AR", "TX"]) == "Array(String)"
        assert _infer_ch_type([None, 1, 2]) == "Array(Int64)"


# ── translate_params ────────────────────────────────────────────────────────

class TestTranslateParams:
    def test_simple_equality(self):
        sql = "SELECT * FROM t WHERE state = %(state)s"
        out = translate_params(sql, {"state": "AR"})
        assert out == "SELECT * FROM t WHERE state = {state:String}"

    def test_in_clause_with_list(self):
        sql = "SELECT * FROM t WHERE ccn IN %(ccns)s"
        out = translate_params(sql, {"ccns": ["017014", "047114"]})
        assert out == "SELECT * FROM t WHERE ccn IN {ccns:Array(String)}"

    def test_multiple_placeholders(self):
        sql = (
            "SELECT * FROM t "
            "WHERE state = %(state)s AND year = %(year)s AND ccn IN %(ccns)s"
        )
        out = translate_params(sql, {
            "state": "AR",
            "year": 2024,
            "ccns": ["017014"],
        })
        assert "{state:String}" in out
        assert "{year:Int64}" in out
        assert "{ccns:Array(String)}" in out

    def test_repeated_placeholder(self):
        # The same placeholder used twice should translate twice.
        sql = "SELECT * FROM t WHERE a = %(p)s OR b = %(p)s"
        out = translate_params(sql, {"p": "x"})
        assert out.count("{p:String}") == 2

    def test_unknown_placeholder_defaults_to_string(self):
        # A placeholder whose name isn't in params should still render —
        # binding will set NULL, but parse must succeed.
        sql = "SELECT * FROM t WHERE col = %(missing)s"
        out = translate_params(sql, {})
        assert out == "SELECT * FROM t WHERE col = {missing:String}"

    def test_no_placeholders(self):
        sql = "SELECT 1"
        assert translate_params(sql, {}) == "SELECT 1"

    def test_none_value_yields_nullable(self):
        sql = "SELECT * FROM t WHERE col = %(c)s"
        out = translate_params(sql, {"c": None})
        assert out == "SELECT * FROM t WHERE col = {c:Nullable(String)}"

    def test_datetime_value(self):
        sql = "SELECT * FROM t WHERE created_at >= %(since)s"
        out = translate_params(sql, {"since": datetime.datetime(2026, 1, 1)})
        assert out == "SELECT * FROM t WHERE created_at >= {since:DateTime}"
