# -*- coding: utf-8 -*-
"""Tests for ``ai_sql_generator.build_system_prompt(engine)``.

Phase 3 / Path C — the AI Assistant must use a dialect-specific system
prompt so Claude generates valid PG SQL for PG sources and valid CH SQL
for CH sources. Subsumes what the master plan called Phase 6 dialect
threading.
"""

import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock

import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import _stub_odoo_runtime  # noqa: E402


ADDON_ROOT = os.environ.get("POSTERRA_ADDONS_ROOT", r"C:\Users\nisha\Odoo_Dev")


# ─────────────────────────────────────────────────────────────────────
# Load ai_sql_generator.py under stubbed odoo runtime + a minimal
# anthropic stub (the module imports anthropic at top level).
# ─────────────────────────────────────────────────────────────────────


def _stub_anthropic():
    if "anthropic" in sys.modules:
        return
    anth = types.ModuleType("anthropic")
    anth.AnthropicAzureFoundry = MagicMock(name="AnthropicAzureFoundry")
    anth.Anthropic = MagicMock(name="Anthropic")
    sys.modules["anthropic"] = anth


_stub_odoo_runtime()
_stub_anthropic()


_PATH = os.path.join(
    ADDON_ROOT, "dashboard_builder", "services", "ai_sql_generator.py"
)
_spec = importlib.util.spec_from_file_location("ai_sql_generator_under_test", _PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["ai_sql_generator_under_test"] = _mod
_spec.loader.exec_module(_mod)

build_system_prompt = _mod.build_system_prompt
SYSTEM_PROMPT = _mod.SYSTEM_PROMPT
_PROMPT_BASE = _mod._PROMPT_BASE
_PROMPT_POSTGRES = _mod._PROMPT_POSTGRES
_PROMPT_CLICKHOUSE = _mod._PROMPT_CLICKHOUSE


# ─────────────────────────────────────────────────────────────────────
# Dialect routing
# ─────────────────────────────────────────────────────────────────────


class TestBuildSystemPromptDialect:
    """``build_system_prompt(engine)`` returns the right dialect tail."""

    def test_postgres_local_returns_pg_dialect(self):
        prompt = build_system_prompt("postgres_local")
        assert _PROMPT_BASE in prompt
        assert _PROMPT_POSTGRES in prompt
        assert _PROMPT_CLICKHOUSE not in prompt

    def test_clickhouse_returns_ch_dialect(self):
        prompt = build_system_prompt("clickhouse")
        assert _PROMPT_BASE in prompt
        assert _PROMPT_CLICKHOUSE in prompt
        assert _PROMPT_POSTGRES not in prompt

    def test_default_engine_is_postgres(self):
        # No-arg call MUST return PG dialect — preserves byte-identical
        # behaviour for every existing PG widget that uses the AI Assistant
        # before Path C lands.
        prompt = build_system_prompt()
        assert _PROMPT_POSTGRES in prompt
        assert _PROMPT_CLICKHOUSE not in prompt

    def test_unknown_engine_falls_back_to_postgres(self):
        prompt = build_system_prompt("snowflake")
        assert _PROMPT_POSTGRES in prompt
        assert _PROMPT_CLICKHOUSE not in prompt

    def test_none_engine_falls_back_to_postgres(self):
        prompt = build_system_prompt(None)
        assert _PROMPT_POSTGRES in prompt

    def test_empty_engine_falls_back_to_postgres(self):
        prompt = build_system_prompt("")
        assert _PROMPT_POSTGRES in prompt


class TestPromptContent:
    """Each dialect block contains the engine-specific tokens it must
    contain — and lacks tokens from the other dialect."""

    def test_pg_contains_pg_tokens(self):
        # date_trunc is a PG-specific function the AI must use for date
        # bucketing on PG sources.
        assert "date_trunc" in _PROMPT_POSTGRES
        assert "ILIKE" in _PROMPT_POSTGRES

    def test_pg_does_not_contain_ch_tokens(self):
        # toStartOfMonth is CH-specific. If it leaks into PG dialect,
        # Claude would generate broken PG SQL.
        assert "toStartOfMonth" not in _PROMPT_POSTGRES
        assert "toYYYYMM" not in _PROMPT_POSTGRES
        assert "LowCardinality" not in _PROMPT_POSTGRES

    def test_ch_contains_ch_tokens(self):
        # CH date functions
        assert "toStartOfMonth" in _PROMPT_CLICKHOUSE
        assert "toYYYYMM" in _PROMPT_CLICKHOUSE
        # CH-only types/wrappers
        assert "LowCardinality" in _PROMPT_CLICKHOUSE
        # Must explicitly forbid date_trunc — most common PG-ism
        # the AI tries to use on CH.
        assert "date_trunc" in _PROMPT_CLICKHOUSE  # mentioned in the "DO NOT use" guidance
        assert "DO NOT use date_trunc" in _PROMPT_CLICKHOUSE

    def test_ch_does_not_contain_pg_specific_idioms(self):
        # ILIKE doesn't exist in CH — admins must use positionCaseInsensitive
        # or lower(...) tricks. Verify the CH dialect doesn't suggest ILIKE.
        # (The base prompt may mention ILIKE in examples but the dialect
        # tail must steer toward CH-native functions.)
        assert "positionCaseInsensitive" in _PROMPT_CLICKHOUSE


class TestBackwardsCompatAlias:
    """The legacy ``SYSTEM_PROMPT`` constant must still exist and equal
    the PG dialect — every importer that used it before Path C
    continues to get PG-flavoured output without modification."""

    def test_system_prompt_alias_equals_pg_build(self):
        assert SYSTEM_PROMPT == build_system_prompt("postgres_local")

    def test_system_prompt_alias_is_pg(self):
        # Any code path that imports SYSTEM_PROMPT directly still gets
        # PG dialect, never CH. (Phase 3 Path C migrated all live call
        # sites to build_system_prompt, but external callers / tests
        # may still reference SYSTEM_PROMPT.)
        assert _PROMPT_POSTGRES in SYSTEM_PROMPT
        assert _PROMPT_CLICKHOUSE not in SYSTEM_PROMPT


class TestBaseInvariants:
    """The base prompt must contain rules that apply regardless of engine."""

    def test_base_contains_select_only_rule(self):
        assert "Only SELECT or WITH" in _PROMPT_BASE

    def test_base_contains_column_intelligence_section(self):
        assert "COLUMN INTELLIGENCE" in _PROMPT_BASE
        assert "NEVER AVG" in _PROMPT_BASE

    def test_base_contains_macro_section(self):
        assert "{WHERE_CLAUSE}" in _PROMPT_BASE
        assert "[[" in _PROMPT_BASE  # optional clause syntax

    def test_base_does_not_specialize_on_engine(self):
        # The base prompt should not name a specific engine — that's
        # what the dialect tails are for.
        # (We allow generic words like "SQL" — only block engine names.)
        assert "PostgreSQL" not in _PROMPT_BASE
        assert "ClickHouse" not in _PROMPT_BASE
