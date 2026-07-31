# -*- coding: utf-8 -*-
"""Test that ``_get_api_user`` sets ``request.tenant_id`` before
returning. This is the single point of tenant-context wiring for all
JWT API routes; if it breaks, every CH-backed filter cascade and
widget data endpoint silently loses isolation.

The test loads ``widget_api.py`` with stubbed Odoo + JWT helpers and
asserts the side-effect on the request object.
"""

import os
import sys
import types
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import _stub_odoo_runtime, ADDON_ROOT  # noqa: E402


def _load_get_api_user():
    """Surgically load ``_get_api_user`` from widget_api.py.

    Pre-stubs ``odoo.http`` (for the ``request`` global) and the
    sibling ``auth_api`` module (for ``_verify_token``,
    ``_json_error``, ``_json_response``) so the import succeeds
    without an Odoo runtime.
    """
    _stub_odoo_runtime()

    # Stub odoo.http with a request placeholder we can mutate per test.
    if "odoo.http" not in sys.modules or not getattr(
        sys.modules["odoo.http"], "_is_stub", False
    ):
        http_stub = types.ModuleType("odoo.http")
        http_stub._is_stub = True

        class _RequestProxy:
            """Per-test mutable container — the test sets attributes
            on this object and asserts them after _get_api_user returns."""

            httprequest = SimpleNamespace(headers={})
            env = None
            tenant_id = None

        http_stub.request = _RequestProxy()

        def _route(*_a, **_k):
            return lambda f: f

        http_stub.route = _route

        # widget_api defines a Controller subclass at module level —
        # provide a no-op base class so the import succeeds.
        class _Controller(object):
            pass

        http_stub.Controller = _Controller
        sys.modules["odoo.http"] = http_stub

        odoo = sys.modules["odoo"]
        odoo.http = http_stub

    # Stub the sibling controllers package + auth_api module so the
    # ``from .auth_api import ...`` resolves without loading the rest
    # of posterra_portal.
    pkg_name = "posterra_portal_under_test_controllers"
    if pkg_name not in sys.modules:
        pkg = types.ModuleType(pkg_name)
        pkg.__path__ = [os.path.join(ADDON_ROOT, "posterra_portal", "controllers")]
        sys.modules[pkg_name] = pkg

    auth_stub = types.ModuleType(pkg_name + ".auth_api")

    def _verify_token(token):
        # Stub: anything starting with "valid:" is accepted; anything
        # else raises. Returns a payload dict the controller expects.
        if not token.startswith("valid:"):
            raise ValueError("invalid token")
        # Encode user_id and app_id in the token: "valid:<user>:<app>"
        _, uid, aid = token.split(":")
        return {"type": "access", "user_id": int(uid), "app_id": int(aid)}

    def _json_error(*_a, **_k):
        return None

    def _json_response(*_a, **_k):
        return None

    auth_stub._verify_token = _verify_token
    auth_stub._json_error = _json_error
    auth_stub._json_response = _json_response
    sys.modules[pkg_name + ".auth_api"] = auth_stub

    # And stub the sibling portal module for the
    # ``from .portal import _get_providers_for_user`` line.
    portal_stub = types.ModuleType(pkg_name + ".portal")
    portal_stub._get_providers_for_user = lambda u: []
    sys.modules[pkg_name + ".portal"] = portal_stub

    # Now load widget_api.py as a member of our fake controllers pkg.
    import importlib.util
    src = os.path.join(ADDON_ROOT, "posterra_portal", "controllers", "widget_api.py")
    spec = importlib.util.spec_from_file_location(
        pkg_name + ".widget_api", src
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[pkg_name + ".widget_api"] = module
    spec.loader.exec_module(module)
    return module


_widget_api = _load_get_api_user()
_get_api_user = _widget_api._get_api_user


# ── Fakes for the env / records ─────────────────────────────────────────────

class _FakeRecord(SimpleNamespace):
    def exists(self):
        return getattr(self, "_exists", True)


class _FakeRecordset:
    def __init__(self, record):
        self._record = record

    def browse(self, _id):
        return self._record

    def sudo(self):
        return self


class _FakeEnv(dict):
    def __init__(self, user, app):
        super().__init__()
        self["res.users"] = _FakeRecordset(user)
        self["saas.app"] = _FakeRecordset(app)


# ── Tests ───────────────────────────────────────────────────────────────────

class TestGetApiUserSetsTenantId:
    def setup_method(self):
        # Reset the fake request before each test.
        from odoo.http import request
        request.httprequest = SimpleNamespace(headers={})
        request.tenant_id = None
        self.request = request

    def test_valid_token_sets_tenant_id_to_app_id(self):
        from odoo.http import request

        user = _FakeRecord(id=5, login="admin")
        app = _FakeRecord(id=42, app_key="posterra")
        request.env = _FakeEnv(user, app)
        request.httprequest.headers = {"Authorization": "Bearer valid:5:42"}

        u, a = _get_api_user()
        assert u is user
        assert a is app
        assert request.tenant_id == 42, (
            "request.tenant_id must be set so downstream CH-backed "
            "endpoints have tenant context"
        )

    def test_missing_auth_header_raises_before_setting_tenant_id(self):
        from odoo.http import request

        user = _FakeRecord(id=5, login="admin")
        app = _FakeRecord(id=42, app_key="posterra")
        request.env = _FakeEnv(user, app)
        request.httprequest.headers = {}

        with pytest.raises(ValueError, match="Authorization header"):
            _get_api_user()
        assert request.tenant_id is None  # never assigned on auth failure

    def test_invalid_token_raises_before_setting_tenant_id(self):
        from odoo.http import request

        user = _FakeRecord(id=5, login="admin")
        app = _FakeRecord(id=42, app_key="posterra")
        request.env = _FakeEnv(user, app)
        request.httprequest.headers = {"Authorization": "Bearer garbage"}

        with pytest.raises(ValueError):
            _get_api_user()
        assert request.tenant_id is None

    def test_missing_app_raises_before_setting_tenant_id(self):
        from odoo.http import request

        user = _FakeRecord(id=5, login="admin")
        app = _FakeRecord(id=42, app_key="posterra", _exists=False)
        request.env = _FakeEnv(user, app)
        request.httprequest.headers = {"Authorization": "Bearer valid:5:42"}

        with pytest.raises(ValueError, match="app that no longer exists"):
            _get_api_user()
        assert request.tenant_id is None
