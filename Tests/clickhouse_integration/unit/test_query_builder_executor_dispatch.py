# -*- coding: utf-8 -*-
"""Tests for ``QueryBuilder.execute_preview()`` executor dispatch.

Phase 3 / Path B fix — the wizard's preview path was always running
against local Postgres regardless of the schema source's
``connection_id``. ``execute_preview()`` now dispatches via
``get_executor()`` when the source has a non-null connection, while
keeping the local-PG path byte-for-byte identical when ``schema_source``
is None or has a NULL connection (zero regression on existing PG widgets).
"""

import importlib.util
import os
import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import _stub_odoo_runtime  # noqa: E402

ADDON_ROOT = os.environ.get("POSTERRA_ADDONS_ROOT", r"C:\Users\nisha\Odoo_Dev")


# ─────────────────────────────────────────────────────────────────────
# Stub the executor + filter_builder modules under the
# ``odoo.addons.posterra_portal.utils`` namespace so query_builder's
# late imports resolve to mocks we can introspect from the tests.
# ─────────────────────────────────────────────────────────────────────


def _install_addon_stubs():
    _stub_odoo_runtime()

    if "odoo.addons" not in sys.modules:
        sys.modules["odoo.addons"] = types.ModuleType("odoo.addons")
    if "odoo.addons.posterra_portal" not in sys.modules:
        sys.modules["odoo.addons.posterra_portal"] = types.ModuleType(
            "odoo.addons.posterra_portal"
        )
    if "odoo.addons.posterra_portal.utils" not in sys.modules:
        sys.modules["odoo.addons.posterra_portal.utils"] = types.ModuleType(
            "odoo.addons.posterra_portal.utils"
        )

    qe_mod = types.ModuleType(
        "odoo.addons.posterra_portal.utils.query_executors"
    )
    qe_mod.get_executor = MagicMock(name="get_executor")
    sys.modules["odoo.addons.posterra_portal.utils.query_executors"] = qe_mod

    fb_mod = types.ModuleType(
        "odoo.addons.posterra_portal.utils.filter_builder"
    )

    def _resolve_optional_clauses(sql, params):
        # Trivial passthrough — strip [[ ]] markers, preserve content.
        return sql.replace("[[", "").replace("]]", "")

    fb_mod.resolve_optional_clauses = _resolve_optional_clauses
    sys.modules["odoo.addons.posterra_portal.utils.filter_builder"] = fb_mod

    return qe_mod, fb_mod


_qe_mod, _fb_mod = _install_addon_stubs()


# Load the SUT (system under test) — query_builder.py — bypassing the
# package ``__init__`` so we don't drag in the rest of dashboard_builder.
_qb_path = os.path.join(
    ADDON_ROOT, "dashboard_builder", "services", "query_builder.py"
)
_spec = importlib.util.spec_from_file_location(
    "query_builder_under_test", _qb_path
)
_qb_module = importlib.util.module_from_spec(_spec)
sys.modules["query_builder_under_test"] = _qb_module
_spec.loader.exec_module(_qb_module)
QueryBuilder = _qb_module.QueryBuilder


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _make_cursor(rows=None, columns=None):
    """Mock cursor with predictable description/fetchall."""
    cr = MagicMock(name="cr")
    cr.description = [(c,) for c in (columns or ["value"])]
    cr.fetchall.return_value = rows or [(123,)]
    return cr


def _make_env(cursor):
    return SimpleNamespace(cr=cursor)


def _make_source(connection=None):
    return SimpleNamespace(connection_id=connection)


def _make_connection(engine="clickhouse", name="ch-conn", is_active=True):
    return SimpleNamespace(engine=engine, name=name, is_active=is_active, id=42)


@pytest.fixture(autouse=True)
def _reset_executor_mock():
    """Each test starts with a fresh mock so call counts don't bleed."""
    _qe_mod.get_executor.reset_mock()
    yield
    _qe_mod.get_executor.reset_mock()


# ─────────────────────────────────────────────────────────────────────
# Local PG path — zero-regression cases
# ─────────────────────────────────────────────────────────────────────


class TestExecutePreviewLocalPG:
    """When ``schema_source`` is None or has no connection, the call
    still runs against ``env.cr`` (the pre-Phase-3 path). The factory
    must NEVER be invoked in this branch."""

    def test_no_schema_source_uses_env_cr(self):
        cr = _make_cursor(rows=[(99,)], columns=["value"])
        qb = QueryBuilder(_make_env(cr))
        cols, rows = qb.execute_preview("SELECT 1", {})
        assert cols == ["value"]
        assert rows == [(99,)]
        # SAVEPOINT, SET LOCAL statement_timeout, the query, RELEASE SAVEPOINT
        sqls = [c.args[0] for c in cr.execute.call_args_list]
        assert any("SAVEPOINT preview_exec" in s for s in sqls)
        assert any("SET LOCAL statement_timeout" in s for s in sqls)
        assert any("SELECT 1" in s for s in sqls)
        assert any("RELEASE SAVEPOINT preview_exec" in s for s in sqls)
        _qe_mod.get_executor.assert_not_called()

    def test_schema_source_with_null_connection_uses_env_cr(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        source = _make_source(connection=None)
        cols, rows = qb.execute_preview("SELECT 1", {}, schema_source=source)
        assert cols == ["value"]
        _qe_mod.get_executor.assert_not_called()
        # cr.execute should have been called for the savepoint dance
        assert cr.execute.called

    def test_local_pg_path_preserves_savepoint_on_error(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))

        # First three execute() calls succeed (SAVEPOINT, SET LOCAL,
        # the actual SELECT) — make the SELECT raise.
        call_log = []

        def execute_side_effect(sql, *args, **kwargs):
            call_log.append(sql)
            if "SAVEPOINT" in sql or "SET LOCAL" in sql or "ROLLBACK" in sql:
                return None
            raise Exception("simulated PG error")

        cr.execute.side_effect = execute_side_effect

        with pytest.raises(ValueError, match="Query execution failed"):
            qb.execute_preview("SELECT 1", {})

        # Verify rollback happened
        assert any("ROLLBACK TO SAVEPOINT" in s for s in call_log)


# ─────────────────────────────────────────────────────────────────────
# Remote engine path — CH dispatch
# ─────────────────────────────────────────────────────────────────────


class TestExecutePreviewRemoteEngine:
    """When ``schema_source`` has a non-null connection, the call must
    route through ``get_executor()`` and NEVER touch ``env.cr``."""

    def test_clickhouse_source_dispatches_via_executor(self):
        cr = _make_cursor()
        env = _make_env(cr)
        qb = QueryBuilder(env)

        executor = MagicMock(name="executor")
        executor.execute.return_value = (["value"], [(456,)])
        _qe_mod.get_executor.return_value = executor

        source = _make_source(connection=_make_connection("clickhouse"))
        cols, rows = qb.execute_preview("SELECT 1", {}, schema_source=source)

        _qe_mod.get_executor.assert_called_once_with(env, source)
        executor.execute.assert_called_once()
        # cr.execute MUST NOT be called when dispatching to remote
        cr.execute.assert_not_called()
        assert cols == ["value"]
        assert rows == [(456,)]

    def test_remote_executor_failure_raised_as_value_error(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))

        executor = MagicMock()
        executor.execute.side_effect = Exception("CH connection refused")
        _qe_mod.get_executor.return_value = executor

        source = _make_source(connection=_make_connection("clickhouse"))
        with pytest.raises(ValueError, match="Query execution failed"):
            qb.execute_preview("SELECT 1", {}, schema_source=source)


# ─────────────────────────────────────────────────────────────────────
# Macro resolution and validation — engine-agnostic
# ─────────────────────────────────────────────────────────────────────


class TestMacroResolution:
    """``{where_clause}``, ``[[optional]]``, and ``LIMIT`` injection
    happen BEFORE engine dispatch, on both PG and remote paths."""

    def test_where_clause_macro_replaced(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        qb.execute_preview(
            "SELECT 1 FROM t WHERE {where_clause}",
            {"state": "TX"},
        )
        sqls = [c.args[0] for c in cr.execute.call_args_list]
        target = next(s for s in sqls if "FROM t" in s)
        assert "{where_clause}" not in target
        assert "state = %(state)s" in target

    def test_where_clause_falls_back_to_1eq1_when_no_params(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        qb.execute_preview("SELECT 1 FROM t WHERE {where_clause}", {})
        sqls = [c.args[0] for c in cr.execute.call_args_list]
        target = next(s for s in sqls if "FROM t" in s)
        assert "1=1" in target

    def test_limit_appended_when_missing(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        qb.execute_preview("SELECT 1 FROM t", {}, limit=10)
        sqls = [c.args[0] for c in cr.execute.call_args_list]
        target = next(s for s in sqls if "FROM t" in s)
        assert "LIMIT 10" in target

    def test_existing_limit_not_duplicated(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        qb.execute_preview("SELECT 1 FROM t LIMIT 5", {}, limit=10)
        sqls = [c.args[0] for c in cr.execute.call_args_list]
        target = next(s for s in sqls if "FROM t" in s)
        # Only one LIMIT (the user-provided one), not appended again
        assert target.count("LIMIT") == 1

    def test_remote_path_also_resolves_macros_before_dispatch(self):
        executor = MagicMock()
        executor.execute.return_value = (["value"], [(1,)])
        _qe_mod.get_executor.return_value = executor

        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        source = _make_source(connection=_make_connection("clickhouse"))
        qb.execute_preview(
            "SELECT 1 FROM t WHERE {where_clause}",
            {"state": "TX"},
            schema_source=source,
        )
        # The SQL passed to the executor must already have the macro resolved
        executed_sql = executor.execute.call_args.args[0]
        assert "{where_clause}" not in executed_sql
        assert "state = %(state)s" in executed_sql


class TestValidation:
    """Validation gate runs BEFORE dispatch on both paths. The exact
    error message varies by failure mode (first-word vs blocked keyword
    vs semicolon); what matters is that no SQL leaves the gate."""

    def test_non_select_first_word_rejected_before_local_dispatch(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        with pytest.raises(ValueError, match="SELECT or WITH"):
            qb.execute_preview("DELETE FROM t", {})
        # cr.execute MUST NOT be called for an invalid query
        cr.execute.assert_not_called()

    def test_non_select_first_word_rejected_before_remote_dispatch(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        source = _make_source(connection=_make_connection("clickhouse"))
        with pytest.raises(ValueError, match="SELECT or WITH"):
            qb.execute_preview("DROP TABLE t", {}, schema_source=source)
        _qe_mod.get_executor.assert_not_called()

    def test_blocked_keyword_in_body_rejected(self):
        # First word is SELECT (passes first-word check) but body
        # contains DROP at a word boundary — hits blocked-keyword gate.
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        source = _make_source(connection=_make_connection("clickhouse"))
        with pytest.raises(ValueError, match="blocked keyword"):
            qb.execute_preview(
                "SELECT col FROM t WHERE col = DROP", {},
                schema_source=source,
            )
        _qe_mod.get_executor.assert_not_called()
        cr.execute.assert_not_called()

    def test_semicolon_rejected(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        with pytest.raises(ValueError, match="Semicolons not allowed"):
            qb.execute_preview("SELECT 1; SELECT 2", {})

    def test_non_select_rejected(self):
        cr = _make_cursor()
        qb = QueryBuilder(_make_env(cr))
        with pytest.raises(ValueError, match="SELECT or WITH"):
            qb.execute_preview("UPDATE t SET x=1", {})
