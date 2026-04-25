"""tests/test_register_tokens.py — tests for the AYON token registration guard.

Each test reloads ``lib.register_tokens`` with a fresh token state and
different environment variable combinations to verify that the guard behaves
correctly.

These tests run without Blender; a minimal ``bpy`` stub is installed into
``sys.modules`` before the relevant lib modules are imported.

Design note
-----------
Token lambdas read ``os.getenv()`` at *call* time, so env vars must remain
set while the lambda is invoked.  We use pytest's ``monkeypatch`` fixture for
clean env setup/teardown instead of a manual try/finally.
"""

import os
import sys
import types

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bpy_stub() -> types.ModuleType:
    """Return a minimal bpy stub sufficient for lib.blender_scene to import."""
    bpy = types.ModuleType("bpy")
    bpy.context = types.SimpleNamespace(
        view_layer=types.SimpleNamespace(name="ViewLayer")
    )
    return bpy



# lib module names to clear on each reload (including the parent package so
# its cached submodule attributes are also dropped).
_LIB_RELOAD_PREFIXES = (
    "lib.tokens",
    "lib.register_tokens",
    "lib.blender_scene",
    "lib",
)


def _reload_modules(monkeypatch, env: dict):
    """Patch env vars and reload token modules with clean state.

    Args:
        monkeypatch: pytest monkeypatch fixture for env isolation.
        env: Env vars to expose to the reloaded modules.

    Returns:
        The freshly-imported ``lib.tokens`` module.
    """
    sys.modules["bpy"] = _make_bpy_stub()

    # Drop cached lib modules so the guard re-evaluates with the new env.
    # The lib package itself must also be cleared; deleting only the sub-module
    # keys leaves a stale attribute on the package object and causes subsequent
    # `from lib import tokens` to return the old instance.
    for key in list(sys.modules):
        if any(key == p or key.startswith(p + ".") for p in _LIB_RELOAD_PREFIXES):
            del sys.modules[key]

    # monkeypatch clears *all* env vars and sets exactly what we provide.
    monkeypatch.delenv("AYON_PROJECT_NAME", raising=False)
    monkeypatch.delenv("AYON_WORKDIR",      raising=False)
    monkeypatch.delenv("AYON_FOLDER_PATH",  raising=False)
    monkeypatch.delenv("AYON_ASSET",        raising=False)
    monkeypatch.delenv("AYON_TASK_NAME",    raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    from lib import tokens as t
    from lib import register_tokens  # noqa: F401 — side-effects only
    return t


# ---------------------------------------------------------------------------
# Guard behaviour
# ---------------------------------------------------------------------------

def test_ayon_tokens_registered_when_project_set(monkeypatch):
    """All four AYON tokens are registered when AYON_PROJECT_NAME is present."""
    t = _reload_modules(monkeypatch, {"AYON_PROJECT_NAME": "my_project"})
    assert "<ayon_project>" in t._registered_tokens
    assert "<ayon_workdir>" in t._registered_tokens
    assert "<ayon_asset>"   in t._registered_tokens
    assert "<ayon_task>"    in t._registered_tokens


def test_ayon_tokens_not_registered_without_project(monkeypatch):
    """No AYON tokens should be registered when AYON_PROJECT_NAME is absent."""
    t = _reload_modules(monkeypatch, {})
    assert "<ayon_project>" not in t._registered_tokens
    assert "<ayon_workdir>" not in t._registered_tokens
    assert "<ayon_asset>"   not in t._registered_tokens
    assert "<ayon_task>"    not in t._registered_tokens


def test_ayon_tokens_registered_without_workdir(monkeypatch):
    """Registration must not require AYON_WORKDIR — only AYON_PROJECT_NAME."""
    t = _reload_modules(monkeypatch, {"AYON_PROJECT_NAME": "proj"})
    assert "<ayon_project>" in t._registered_tokens


# ---------------------------------------------------------------------------
# Token resolution — env must remain set while lambdas are called
# ---------------------------------------------------------------------------

def test_ayon_project_token_resolves(monkeypatch):
    t = _reload_modules(monkeypatch, {"AYON_PROJECT_NAME": "my_project"})
    resolved = t._registered_tokens["<ayon_project>"]["func"](None)
    assert resolved == "my_project"


def test_ayon_asset_token_prefers_folder_path(monkeypatch):
    """AYON_FOLDER_PATH takes precedence over the deprecated AYON_ASSET."""
    t = _reload_modules(monkeypatch, {
        "AYON_PROJECT_NAME": "p",
        "AYON_FOLDER_PATH":  "/shots/sh010",
        "AYON_ASSET":        "old_asset",
    })
    resolved = t._registered_tokens["<ayon_asset>"]["func"](None)
    assert resolved == "/shots/sh010"


def test_ayon_workdir_token_empty_when_missing(monkeypatch):
    """<ayon_workdir> resolves to an empty string when AYON_WORKDIR is absent."""
    t = _reload_modules(monkeypatch, {"AYON_PROJECT_NAME": "p"})
    resolved = t._registered_tokens["<ayon_workdir>"]["func"](None)
    assert resolved == ""


def test_ayon_task_token_resolves(monkeypatch):
    t = _reload_modules(monkeypatch, {
        "AYON_PROJECT_NAME": "p",
        "AYON_TASK_NAME": "animation",
    })
    resolved = t._registered_tokens["<ayon_task>"]["func"](None)
    assert resolved == "animation"


def test_ayon_task_token_empty_when_missing(monkeypatch):
    t = _reload_modules(monkeypatch, {"AYON_PROJECT_NAME": "p"})
    resolved = t._registered_tokens["<ayon_task>"]["func"](None)
    assert resolved == ""
