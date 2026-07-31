# -*- coding: utf-8 -*-
"""Integration tests for ``dashboard.connection``.

Run via Odoo's test runner (so the Odoo registry is available):

    python odoo-bin --test-enable -d <db> -i posterra_portal --stop-after-init

The tests register themselves as a Phase 1 ``post_install`` suite.
They live outside the addon (per user preference), so to actually
execute them inside Odoo you'd typically:

    1. Symlink (or copy) this file into ``posterra_portal/tests/``, or
    2. Add ``posterra_portal/tests/`` as a separate path on the Odoo
       --addons-path so this directory is also picked up.

The assertions themselves are addon-agnostic — they operate on the
``dashboard.connection`` model via the env.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "clickhouse_integration")
class TestDashboardConnection(TransactionCase):
    """CRUD + Test Connection button + cache invalidation."""

    def setUp(self):
        super().setUp()
        self.Connection = self.env["dashboard.connection"]

    def test_create_connection_with_defaults(self):
        rec = self.Connection.create({
            "name": "Test CH",
            "engine": "clickhouse",
            "host": "ch.example.com",
            "database": "analytics",
            "username": "app_user",
            "password_param_key": "test.ch.password",
        })
        self.assertEqual(rec.engine, "clickhouse")
        self.assertTrue(rec.is_active)
        self.assertTrue(rec.requires_tenant_filter)
        self.assertEqual(rec.query_timeout_seconds, 30)
        self.assertEqual(rec.port, 8443)
        self.assertTrue(rec.use_tls)

    def test_unique_name(self):
        self.Connection.create({
            "name": "Duplicate",
            "engine": "clickhouse",
        })
        with self.assertRaises(Exception):
            self.Connection.create({
                "name": "Duplicate",
                "engine": "clickhouse",
            })

    def test_test_connection_failure_surfaces_user_error(self):
        # Unreachable host → action_test_connection should raise UserError.
        rec = self.Connection.create({
            "name": "Unreachable",
            "engine": "clickhouse",
            "host": "definitely-not-a-real-host.invalid",
            "port": 8443,
            "database": "x",
            "username": "x",
            "password_param_key": "test.bogus.password",
        })
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            rec.action_test_connection()
        self.assertTrue(rec.last_test_result.startswith("FAIL"))
        self.assertIsNotNone(rec.last_test_at)

    def test_write_invalidates_cached_client(self):
        # Direct test of the invalidation hook — populate the cache
        # with a sentinel and confirm write() clears it.
        rec = self.Connection.create({
            "name": "CacheInvalidation",
            "engine": "clickhouse",
            "host": "ch.example.com",
            "database": "x",
        })
        try:
            from posterra_portal.utils.query_executors.clickhouse import (
                _clients,
            )
        except ImportError:
            self.skipTest("clickhouse-connect not installed")
            return

        _clients[rec.id] = object()  # sentinel "cached client"
        self.assertIn(rec.id, _clients)

        rec.write({"name": "RenamedAfterCache"})
        self.assertNotIn(rec.id, _clients)

    def test_unlink_invalidates_cached_client(self):
        rec = self.Connection.create({
            "name": "UnlinkInvalidation",
            "engine": "clickhouse",
            "host": "ch.example.com",
            "database": "x",
        })
        try:
            from posterra_portal.utils.query_executors.clickhouse import (
                _clients,
            )
        except ImportError:
            self.skipTest("clickhouse-connect not installed")
            return

        rid = rec.id
        _clients[rid] = object()
        self.assertIn(rid, _clients)

        rec.unlink()
        self.assertNotIn(rid, _clients)

    def test_action_invalidate_cache_drops_cached_client(self):
        """Explicit Invalidate Cache button — used after rotating the
        password under password_param_key (which doesn't trigger
        connection.write and so the regular invalidation hook misses)."""
        rec = self.Connection.create({
            "name": "ManualInvalidation",
            "engine": "clickhouse",
            "host": "ch.example.com",
            "database": "x",
        })
        try:
            from posterra_portal.utils.query_executors.clickhouse import (
                _clients,
            )
        except ImportError:
            self.skipTest("clickhouse-connect not installed")
            return

        _clients[rec.id] = object()
        self.assertIn(rec.id, _clients)

        rec.action_invalidate_cache()
        self.assertNotIn(rec.id, _clients)

    def test_inactive_connection_blocks_executor_creation(self):
        """Disabled connections must refuse to build an executor —
        otherwise admins disable a connection and queries silently
        keep running."""
        from odoo.addons.posterra_portal.utils.query_executors import (
            get_executor_for_connection,
        )

        rec = self.Connection.create({
            "name": "InactiveConn",
            "engine": "clickhouse",
            "host": "ch.example.com",
            "database": "x",
            "is_active": False,
        })
        with self.assertRaisesRegex(ValueError, "inactive"):
            get_executor_for_connection(self.env, rec)


@tagged("post_install", "-at_install", "clickhouse_integration")
class TestSchemaSourceUniqueness(TransactionCase):
    """Per-connection schema source uniqueness — the same physical
    table name may exist on multiple backends but not twice on one."""

    def test_same_table_allowed_on_different_connections(self):
        Connection = self.env["dashboard.connection"]
        Source = self.env["dashboard.schema.source"]

        ch_a = Connection.create({"name": "CH-A", "engine": "clickhouse",
                                   "host": "a.example.com"})
        ch_b = Connection.create({"name": "CH-B", "engine": "clickhouse",
                                   "host": "b.example.com"})

        # Same table_name on different connections — both allowed.
        Source.create({
            "name": "Facts on A",
            "table_name": "fact_referrals",
            "connection_id": ch_a.id,
        })
        Source.create({
            "name": "Facts on B",
            "table_name": "fact_referrals",
            "connection_id": ch_b.id,
        })

    def test_duplicate_table_on_same_connection_rejected(self):
        from odoo.exceptions import ValidationError

        Connection = self.env["dashboard.connection"]
        Source = self.env["dashboard.schema.source"]

        ch = Connection.create({"name": "CH-Single", "engine": "clickhouse",
                                "host": "x.example.com"})
        Source.create({
            "name": "Facts",
            "table_name": "fact_referrals",
            "connection_id": ch.id,
        })
        with self.assertRaises(ValidationError):
            Source.create({
                "name": "Facts Duplicate",
                "table_name": "fact_referrals",
                "connection_id": ch.id,
            })

    def test_duplicate_local_postgres_table_still_rejected(self):
        """NULL connection_id (local Postgres) should still be unique
        per table — backward compat with pre-CH behaviour."""
        from odoo.exceptions import ValidationError

        Source = self.env["dashboard.schema.source"]
        # The platform is likely to have created a record for an
        # existing MV during install; pick a fresh table name.
        Source.create({
            "name": "Local Test",
            "table_name": "test_local_pg_uniq",
        })
        with self.assertRaises(ValidationError):
            Source.create({
                "name": "Local Test Dup",
                "table_name": "test_local_pg_uniq",
            })

    def test_dotted_table_name_accepted(self):
        """ClickHouse db.table form must save without rejection."""
        Connection = self.env["dashboard.connection"]
        Source = self.env["dashboard.schema.source"]
        ch = Connection.create({"name": "CH-Dotted", "engine": "clickhouse",
                                "host": "d.example.com"})
        rec = Source.create({
            "name": "Cross-tenant Geo",
            "table_name": "shared.dim_geo",
            "connection_id": ch.id,
        })
        self.assertEqual(rec.table_name, "shared.dim_geo")
        self.assertEqual(rec.engine, "clickhouse")


@tagged("post_install", "-at_install", "clickhouse_integration")
class TestSchemaSourceConnection(TransactionCase):
    """``dashboard.schema.source.connection_id`` + engine compute."""

    def test_engine_defaults_to_postgres_local_without_connection(self):
        src = self.env["dashboard.schema.source"].create({
            "name": "Test PG Source",
            "table_name": "hha_provider",
        })
        self.assertEqual(src.engine, "postgres_local")
        self.assertFalse(src.connection_id)

    def test_engine_reflects_connection_engine(self):
        conn = self.env["dashboard.connection"].create({
            "name": "Test CH for Source",
            "engine": "clickhouse",
            "host": "ch.example.com",
        })
        src = self.env["dashboard.schema.source"].create({
            "name": "Test CH Source",
            "table_name": "fact_referrals",
            "connection_id": conn.id,
        })
        self.assertEqual(src.engine, "clickhouse")
