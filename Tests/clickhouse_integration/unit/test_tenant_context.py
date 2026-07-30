# -*- coding: utf-8 -*-
"""Tests for ``get_current_tenant_id``.

Tenant context flows: HTTP request → ``request.tenant_id`` (set by
controllers) → ``get_current_tenant_id`` reads it. Without a request,
the function falls back to the user's accessible apps; ambiguity
(multiple apps, or none) is treated as an error rather than silently
picking one — that's the failure mode this whole system exists to
prevent.
"""

import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import load_source  # noqa: E402

_tc = load_source(
    os.path.join("posterra_portal", "utils", "tenant_context.py"),
    module_name="tenant_context_under_test",
)
get_current_tenant_id = _tc.get_current_tenant_id


# ── Fakes ───────────────────────────────────────────────────────────────────

class _FakeRecordset:
    """Mimics what env['saas.app'].sudo().search() returns: iterable
    of records, ``.filtered(fn)``, ``.id`` on a singleton.
    """

    def __init__(self, records):
        self._records = list(records)

    def __iter__(self):
        return iter(self._records)

    def __len__(self):
        return len(self._records)

    def filtered(self, fn):
        return _FakeRecordset([r for r in self._records if fn(r)])

    def mapped(self, field):
        return [getattr(r, field, None) for r in self._records]

    @property
    def id(self):
        if len(self._records) != 1:
            raise ValueError("singleton expected")
        return self._records[0].id


class _FakeApp(SimpleNamespace):
    pass


class _FakeUser(SimpleNamespace):
    def _is_public(self):
        return getattr(self, "is_public", False)

    def has_group(self, _xmlid):
        return getattr(self, "_has_group", False)


class _FakeAppCollection:
    def __init__(self, apps):
        self._apps = apps

    def sudo(self):
        return self

    def search(self, _domain):
        # Active filter handled in real code by the [('is_active','=',True)] domain;
        # here we mimic by returning all and letting the function's
        # _user_has_access path filter inactive ones.
        return _FakeRecordset(self._apps)


class _FakeEnv:
    def __init__(self, apps, user):
        self._apps = apps
        self.user = user

    def __getitem__(self, model_name):
        if model_name == "saas.app":
            return _FakeAppCollection(self._apps)
        raise KeyError(model_name)


def _make_user(login="admin", is_public=False, hha_provider_id=None,
               hha_scope_group_id=None, has_group=False):
    partner = SimpleNamespace(
        hha_provider_id=hha_provider_id,
        hha_scope_group_id=hha_scope_group_id,
    )
    return _FakeUser(
        login=login,
        is_public=is_public,
        partner_id=partner,
        _has_group=has_group,
    )


def _make_app(id, app_key, access_mode="hha_provider", is_active=True,
              access_group_xmlid=None):
    return _FakeApp(
        id=id,
        app_key=app_key,
        access_mode=access_mode,
        is_active=is_active,
        access_group_xmlid=access_group_xmlid,
    )


# ── request.tenant_id wins ──────────────────────────────────────────────────

class TestRequestTenantId:
    def test_request_with_tenant_id_returns_it_as_string(self):
        req = SimpleNamespace(tenant_id=42)
        env = _FakeEnv(apps=[], user=_make_user())
        assert get_current_tenant_id(env, req) == "42"

    def test_request_without_tenant_id_falls_through_to_user(self):
        req = SimpleNamespace()
        provider = SimpleNamespace(id=1)
        user = _make_user(hha_provider_id=provider)
        app = _make_app(7, "posterra")
        env = _FakeEnv(apps=[app], user=user)
        assert get_current_tenant_id(env, req) == "7"


# ── Fallback to user's apps ────────────────────────────────────────────────

class TestUserFallback:
    def test_single_accessible_hha_provider_app(self):
        provider = SimpleNamespace(id=1)
        user = _make_user(hha_provider_id=provider)
        app = _make_app(7, "posterra")
        env = _FakeEnv(apps=[app], user=user)
        assert get_current_tenant_id(env, None) == "7"

    def test_single_accessible_group_app(self):
        user = _make_user(has_group=True)
        app = _make_app(11, "mssp", access_mode="group",
                       access_group_xmlid="x.group_mssp")
        env = _FakeEnv(apps=[app], user=user)
        assert get_current_tenant_id(env, None) == "11"

    def test_no_accessible_apps_raises(self):
        user = _make_user()
        app = _make_app(7, "posterra")
        env = _FakeEnv(apps=[app], user=user)
        with pytest.raises(ValueError, match="no accessible saas.app"):
            get_current_tenant_id(env, None)

    def test_multiple_accessible_apps_raises(self):
        provider = SimpleNamespace(id=1)
        user = _make_user(hha_provider_id=provider, has_group=True)
        app1 = _make_app(7, "posterra")
        app2 = _make_app(11, "mssp", access_mode="group",
                        access_group_xmlid="x.group_mssp")
        env = _FakeEnv(apps=[app1, app2], user=user)
        with pytest.raises(ValueError, match="multiple apps"):
            get_current_tenant_id(env, None)

    def test_public_user_raises(self):
        user = _make_user(is_public=True)
        env = _FakeEnv(apps=[], user=user)
        with pytest.raises(ValueError, match="no authenticated user"):
            get_current_tenant_id(env, None)

    def test_inactive_app_excluded(self):
        provider = SimpleNamespace(id=1)
        user = _make_user(hha_provider_id=provider)
        app1 = _make_app(7, "posterra", is_active=True)
        app2 = _make_app(8, "old", is_active=False)
        env = _FakeEnv(apps=[app1, app2], user=user)
        assert get_current_tenant_id(env, None) == "7"
