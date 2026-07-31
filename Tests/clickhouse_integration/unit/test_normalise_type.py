# -*- coding: utf-8 -*-
"""Tests for ``_normalise_type`` — engine-AWARE column type mapping.

Each backend uses ONLY its own type map (per the Snowflake-connector plan):
isolating dispatch fixes the cross-fallback bugs (Snowflake ``DECIMAL(10,0)``
being intercepted by Postgres ``decimal → float``; Postgres ``time`` picking up
Snowflake's ``date``). Every native type still collapses to one of
(text, integer, float, date, boolean). The call site passes ``source.engine``.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_source  # noqa: E402


_schema = load_source(
    os.path.join("dashboard_builder", "models", "dashboard_schema.py"),
    module_name="dashboard_schema_under_test",
)
_normalise_type = _schema._normalise_type


class TestPostgresTypes:
    @pytest.mark.parametrize("native,expected", [
        ("character varying", "text"),
        ("character varying(255)", "text"),
        ("text", "text"),
        ("uuid", "text"),
        ("integer", "integer"),
        ("bigint", "integer"),
        ("smallint", "integer"),
        ("numeric", "float"),
        ("numeric(10,2)", "float"),
        ("double precision", "float"),
        ("date", "date"),
        ("timestamp without time zone", "date"),
        ("timestamp with time zone", "date"),
        ("boolean", "boolean"),
    ])
    def test_known_types(self, native, expected):
        assert _normalise_type(native, "postgres_local") == expected

    def test_default_engine_is_postgres(self):
        # Back-compat: omitting the engine keeps the Postgres mapping.
        assert _normalise_type("integer") == "integer"

    def test_pg_time_stays_text(self):
        # Must NOT be intercepted by Snowflake's time → date.
        assert _normalise_type("time", "postgres_local") == "text"


class TestClickHouseTypes:
    @pytest.mark.parametrize("native,expected", [
        ("String", "text"),
        ("FixedString(10)", "text"),
        ("UUID", "text"),
        ("Enum8('a' = 1)", "text"),
        ("Int32", "integer"),
        ("Int64", "integer"),
        ("UInt32", "integer"),
        ("Float64", "float"),
        ("Decimal(10, 2)", "float"),
        ("Date", "date"),
        ("DateTime", "date"),
        ("DateTime64(3)", "date"),
        ("Bool", "boolean"),
    ])
    def test_known_types(self, native, expected):
        assert _normalise_type(native, "clickhouse") == expected


class TestClickHouseWrappers:
    @pytest.mark.parametrize("native,expected", [
        ("LowCardinality(String)", "text"),
        ("Nullable(Int64)", "integer"),
        ("Nullable(String)", "text"),
        ("Array(String)", "text"),
        ("LowCardinality(Nullable(String))", "text"),
        ("Nullable(LowCardinality(String))", "text"),
        ("Array(LowCardinality(String))", "text"),
    ])
    def test_wrappers_unwrap(self, native, expected):
        assert _normalise_type(native, "clickhouse") == expected


class TestSnowflakeTypes:
    @pytest.mark.parametrize("native,expected", [
        ("NUMBER(38,0)", "integer"),
        ("NUMBER", "integer"),            # bare = NUMBER(38,0)
        ("NUMBER(10,2)", "float"),
        ("DECIMAL(12,4)", "float"),
        ("DECIMAL(10,0)", "integer"),     # the bug Codex flagged
        ("TEXT", "text"),
        ("VARCHAR(255)", "text"),
        ("VARIANT", "text"),
        ("FLOAT", "float"),
        ("BOOLEAN", "boolean"),
        ("DATE", "date"),
        ("TIMESTAMP_NTZ", "date"),
        ("TIMESTAMP_LTZ", "date"),
        ("TIME", "date"),
    ])
    def test_known_types(self, native, expected):
        assert _normalise_type(native, "snowflake") == expected


class TestEdgeCases:
    def test_empty_returns_text(self):
        assert _normalise_type("", "postgres_local") == "text"
        assert _normalise_type(None, "clickhouse") == "text"
        assert _normalise_type(None, "snowflake") == "text"

    def test_unknown_falls_back_to_text(self):
        assert _normalise_type("PolygonZ", "postgres_local") == "text"
        assert _normalise_type("CustomType123", "snowflake") == "text"
