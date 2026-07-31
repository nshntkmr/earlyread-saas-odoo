# -*- coding: utf-8 -*-
"""pytest config — exposes a ``load_module`` helper that imports a
specific source file from the addon worktree, bypassing the package
``__init__`` chain (which would otherwise pull in the Odoo runtime).

Override the addon root via ``POSTERRA_ADDONS_ROOT`` when the tests run
against a different worktree.
"""

import importlib.util
import os
import sys
import types


_DEFAULT_ROOT = r"C:\Users\nisha\Odoo_Dev"
ADDON_ROOT = os.environ.get("POSTERRA_ADDONS_ROOT", _DEFAULT_ROOT)


def _stub_odoo_runtime():
    """Install a minimal ``odoo`` module stub so model files that say
    ``from odoo import api, fields, models`` can import without a real
    Odoo install.

    The stubs exist for *parsing*, not for runtime behaviour — every
    descriptor (Char, Many2one, etc.) returns the same sentinel object.
    Tests that need real Odoo behaviour must run via odoo-bin --test-enable.
    """
    if "odoo" in sys.modules and getattr(sys.modules["odoo"], "_is_stub", False):
        return

    odoo = types.ModuleType("odoo")
    odoo._is_stub = True

    # ── odoo.fields — every descriptor accepts (*args, **kwargs) and
    #     returns a placeholder ────────────────────────────────────────
    fields_mod = types.ModuleType("odoo.fields")

    def _field_factory(*_a, **_k):
        return None

    for name in (
        "Char", "Text", "Boolean", "Integer", "Float", "Date", "Datetime",
        "Selection", "Binary", "Many2one", "One2many", "Many2many",
        "Json", "Html", "Reference",
    ):
        setattr(fields_mod, name, _field_factory)

    class _Datetime:
        @staticmethod
        def now():
            import datetime
            return datetime.datetime.utcnow()

    fields_mod.Datetime = _Datetime
    odoo.fields = fields_mod

    # ── odoo.models — Model is a base class that does nothing ──────────
    models_mod = types.ModuleType("odoo.models")

    class _ModelMeta(type):
        def __new__(mcls, name, bases, attrs):
            return super().__new__(mcls, name, bases, attrs)

    class Model(metaclass=_ModelMeta):
        _name = ""
        _inherit = []
        _description = ""

    models_mod.Model = Model
    odoo.models = models_mod

    # ── odoo.api — decorators are pass-throughs ─────────────────────────
    api_mod = types.ModuleType("odoo.api")

    def _passthrough(*_a, **_k):
        # Used as both ``@api.depends('x')`` and ``@api.model`` —
        # detect by signature shape.
        if len(_a) == 1 and callable(_a[0]):
            return _a[0]
        return lambda f: f

    api_mod.depends = _passthrough
    api_mod.model = _passthrough
    api_mod.model_create_multi = _passthrough
    api_mod.constrains = _passthrough
    api_mod.onchange = _passthrough
    api_mod.returns = _passthrough
    api_mod.multi = _passthrough
    odoo.api = api_mod

    # ── odoo.exceptions — make the common ones plain Exceptions ────────
    exc_mod = types.ModuleType("odoo.exceptions")

    class _OdooError(Exception):
        pass

    exc_mod.UserError = _OdooError
    exc_mod.ValidationError = _OdooError
    exc_mod.AccessError = _OdooError
    odoo.exceptions = exc_mod

    sys.modules["odoo"] = odoo
    sys.modules["odoo.fields"] = fields_mod
    sys.modules["odoo.models"] = models_mod
    sys.modules["odoo.api"] = api_mod
    sys.modules["odoo.exceptions"] = exc_mod


def load_package(relative_dir, package_name):
    """Register a directory as an importable package without running
    its ``__init__.py``.

    This lets the loaded modules use relative imports
    (``from .base import X``) without dragging in the package's real
    ``__init__`` (which often pulls in Odoo).
    """
    _stub_odoo_runtime()
    full_path = os.path.join(ADDON_ROOT, relative_dir)
    if not os.path.isdir(full_path):
        raise FileNotFoundError(full_path)
    if package_name in sys.modules:
        return sys.modules[package_name]
    pkg = types.ModuleType(package_name)
    pkg.__path__ = [full_path]
    sys.modules[package_name] = pkg
    return pkg


def load_source(relative_path, module_name=None, package=None):
    """Import a single .py file from the addon worktree.

    Bypasses the package ``__init__.py`` to avoid pulling in Odoo. If
    the file under test uses relative imports
    (``from .base import X``), pass ``package=`` matching the package
    its siblings share — and call ``load_package(...)`` first to
    register that package name.
    """
    _stub_odoo_runtime()
    full_path = os.path.join(ADDON_ROOT, relative_path)
    if not os.path.isfile(full_path):
        raise FileNotFoundError(full_path)

    name = module_name or (
        "loaded_" + relative_path.replace(os.sep, "_").replace(".py", "")
    )
    if package:
        # Register under ``<package>.<leaf>`` so the relative imports
        # resolve to siblings already loaded into sys.modules.
        leaf = os.path.splitext(os.path.basename(relative_path))[0]
        full_name = f"{package}.{leaf}"
        spec = importlib.util.spec_from_file_location(full_name, full_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        # Also alias under the test-friendly name.
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    spec = importlib.util.spec_from_file_location(name, full_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
