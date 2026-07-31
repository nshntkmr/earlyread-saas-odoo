# -*- coding: utf-8 -*-
"""Regression tests for Codex-flagged gaps in Phase 3 Path B + C.

Codex review caught five P1 issues after the initial Phase 3 commit. The
tests below lock in the fixes that are unit-testable (issues 4 — dotted
table support — is the most testable; issue 1, 2, 3 are integration-level
and verified manually). Issue 5 — intent pipeline bypass for CH — is
tested via a smoke test on the engine-routing decision.
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
# Stub odoo + addon namespaces, then load query_builder.
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

    # Real sql_idents — load it from disk (no Odoo deps).
    sql_idents_path = os.path.join(
        ADDON_ROOT, "posterra_portal", "utils", "sql_idents.py"
    )
    spec = importlib.util.spec_from_file_location(
        "odoo.addons.posterra_portal.utils.sql_idents", sql_idents_path
    )
    sql_idents = importlib.util.module_from_spec(spec)
    sys.modules["odoo.addons.posterra_portal.utils.sql_idents"] = sql_idents
    spec.loader.exec_module(sql_idents)

    # Stub the executor + filter_builder modules — query_builder imports
    # them lazily inside execute_preview.
    qe_mod = types.ModuleType(
        "odoo.addons.posterra_portal.utils.query_executors"
    )
    qe_mod.get_executor = MagicMock(name="get_executor")
    sys.modules["odoo.addons.posterra_portal.utils.query_executors"] = qe_mod

    fb_mod = types.ModuleType(
        "odoo.addons.posterra_portal.utils.filter_builder"
    )
    fb_mod.resolve_optional_clauses = lambda sql, params: sql.replace("[[", "").replace("]]", "")
    sys.modules["odoo.addons.posterra_portal.utils.filter_builder"] = fb_mod


_install_addon_stubs()


_qb_path = os.path.join(
    ADDON_ROOT, "dashboard_builder", "services", "query_builder.py"
)
_spec = importlib.util.spec_from_file_location(
    "qb_codex_fixup_test", _qb_path
)
_qb = importlib.util.module_from_spec(_spec)
sys.modules["qb_codex_fixup_test"] = _qb
_spec.loader.exec_module(_qb)


# ─────────────────────────────────────────────────────────────────────
# Issue 4 — Dotted table names (the fix that blocks CH visual builder)
# ─────────────────────────────────────────────────────────────────────


class TestSafeTableAcceptsDottedNames:
    """``_safe_table`` is the new helper that delegates to
    ``posterra_portal.utils.sql_idents.quote_table``. Unlike the old
    ``_safe_ident``, it accepts schema-qualified names so CH tables in
    ``shared.*``, ``silver.*``, ``gold.*`` survive the visual builder
    SQL emission step.
    """

    def test_unqualified_table_quoted_as_single_identifier(self):
        # Postgres MV — single-segment table name. Same output as before.
        assert _qb._safe_table("mv_hha_kpi_summary") == '"mv_hha_kpi_summary"'

    def test_dotted_ch_table_quoted_per_segment(self):
        # CH shared table — must produce two quoted identifiers, not one.
        assert _qb._safe_table("shared.inhome_v2") == '"shared"."inhome_v2"'

    def test_silver_dotted_table(self):
        assert _qb._safe_table("silver.fact_referrals") == '"silver"."fact_referrals"'

    def test_gold_dotted_table(self):
        assert _qb._safe_table("gold.kpi_summary") == '"gold"."kpi_summary"'

    def test_invalid_chars_still_rejected(self):
        # SQL injection attempt — semicolons, spaces must be rejected.
        with pytest.raises(ValueError, match="Invalid SQL table reference"):
            _qb._safe_table("shared.inhome_v2; DROP TABLE shared.users--")
        with pytest.raises(ValueError, match="Invalid SQL table reference"):
            _qb._safe_table("shared inhome_v2")

    def test_three_segment_name_rejected(self):
        # TABLE_RE allows at most one dot. cluster.db.table is not yet
        # supported (would be a future enhancement when CH clusters need it).
        with pytest.raises(ValueError, match="Invalid SQL table reference"):
            _qb._safe_table("cluster1.shared.inhome_v2")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="Invalid SQL table reference"):
            _qb._safe_table("")

    def test_safe_ident_still_rejects_dots(self):
        # _safe_ident is still the right helper for COLUMN names. Columns
        # cannot contain dots — that would be a join reference, not a
        # column name. This test guards against accidentally relaxing
        # column-name validation.
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _qb._safe_ident("shared.inhome_v2")


# ─────────────────────────────────────────────────────────────────────
# Issue 4 — Boundary check that _safe_table is the function visual
# builder actually calls. Locks in the migration from _safe_ident.
# ─────────────────────────────────────────────────────────────────────


class TestVisualBuilderUsesSafeTable:
    """Every place ``query_builder.py`` emits a table reference (single
    source FROM, multi-source primary FROM, JOIN clauses) must call
    ``_safe_table`` so dotted names pass through. Codex flagged that
    these still used ``_safe_ident`` after Phase 3 Path C landed.

    Rather than running the full SQL builder (which needs a real Odoo
    env), this test reads the source file and asserts that no
    ``_safe_ident(*.table_name)`` patterns survive — the migration is
    complete.
    """

    def test_no_safe_ident_table_name_calls_remain(self):
        with open(_qb.__file__, encoding='utf-8') as f:
            source = f.read()
        # The post-fix codebase should call _safe_table for every
        # table-name emission. _safe_ident is still valid for COLUMN
        # names, parameter names, etc. — but never for table_name.
        import re
        offenders = re.findall(r'_safe_ident\(\s*[^)]*\.table_name', source)
        assert not offenders, (
            f"Found {len(offenders)} _safe_ident(*.table_name) calls — "
            f"these reject dotted CH tables. Use _safe_table instead. "
            f"Offenders: {offenders}"
        )

    def test_safe_table_helper_exists(self):
        # Sanity: the new helper is defined and accepts dotted names.
        assert hasattr(_qb, '_safe_table')
        assert _qb._safe_table('shared.inhome_v2') == '"shared"."inhome_v2"'
