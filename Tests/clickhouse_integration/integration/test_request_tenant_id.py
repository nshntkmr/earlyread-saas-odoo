# -*- coding: utf-8 -*-
"""Integration test: ``request.tenant_id`` is set after app resolution.

Hits ``/my/<app_key>/`` as an authenticated user and asserts that
``request.tenant_id`` was populated. We can't read ``request`` from
outside the request lifecycle, so this test runs an HTTP request
against a running Odoo and reads back through a probe endpoint.

For Phase 1 this test is skipped automatically until a probe endpoint
is added (kept as a placeholder so the gap is visible). The same
behaviour is exercised by the manual smoke test in
``manual/phase1_smoke_test.md``.
"""

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "clickhouse_integration")
class TestRequestTenantId(HttpCase):

    def test_tenant_id_set_on_app_dashboard(self):
        # The Phase 1 deliverable sets ``request.tenant_id`` in
        # ``app_dashboard`` and ``_build_portal_ctx``. There is no
        # debug endpoint that exposes ``request.tenant_id`` to the
        # outside world (and adding one is out of scope), so this
        # automated assertion is deferred to Phase 2.
        #
        # The manual checklist at ``manual/phase1_smoke_test.md``
        # covers the equivalent verification: load /my/posterra,
        # confirm widgets render correctly, confirm the request log
        # shows tenant_id resolution. Re-enable this test in Phase 2
        # once a debug header or telemetry endpoint exists.
        self.skipTest(
            "Deferred to Phase 2: needs a probe endpoint that echoes "
            "request.tenant_id back to the client. Manual coverage "
            "in manual/phase1_smoke_test.md."
        )
