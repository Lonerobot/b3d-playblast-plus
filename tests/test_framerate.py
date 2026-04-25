"""tests/test_framerate.py — regression tests for getFrameRate() precision.

These tests verify that ``Blender_Scene.getFrameRate()`` returns the true
frame rate as ``fps / fps_base`` rather than the integer ``fps`` numerator,
which is incorrect for drop-frame / NTSC rates (23.976, 29.97, etc.).

A minimal ``bpy`` stub is installed before the lib module is imported so that
these tests run without a Blender installation.
"""

import sys
import types

import pytest

# ---------------------------------------------------------------------------
# bpy stub — install before importing lib.blender_scene
# ---------------------------------------------------------------------------

_render_stub  = types.SimpleNamespace(fps=24, fps_base=1.0)
_scene_stub   = types.SimpleNamespace(render=_render_stub)
_context_stub = types.SimpleNamespace(scene=_scene_stub)

bpy_stub = types.ModuleType("bpy")
bpy_stub.context = _context_stub
sys.modules["bpy"] = bpy_stub

from lib.blender_scene import Blender_Scene  # noqa: E402 — must come after stub


# ---------------------------------------------------------------------------
# Helper: set fps values on the stub
# ---------------------------------------------------------------------------

def _set_fps(fps: int, fps_base: float) -> None:
    _render_stub.fps      = fps
    _render_stub.fps_base = fps_base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_framerate_24_integer():
    _set_fps(24, 1.0)
    assert Blender_Scene.getFrameRate() == pytest.approx(24.0)


def test_framerate_25_pal():
    _set_fps(25, 1.0)
    assert Blender_Scene.getFrameRate() == pytest.approx(25.0)


def test_framerate_30():
    _set_fps(30, 1.0)
    assert Blender_Scene.getFrameRate() == pytest.approx(30.0)


def test_framerate_ntsc_23976():
    """23.976 fps — fps=24000, fps_base=1001 — must not return 24000."""
    _set_fps(24000, 1001.0)
    result = Blender_Scene.getFrameRate()
    assert abs(result - 23.976) < 0.001, f"Expected ~23.976, got {result}"


def test_framerate_ntsc_29970():
    """29.97 fps — fps=30000, fps_base=1001."""
    _set_fps(30000, 1001.0)
    result = Blender_Scene.getFrameRate()
    assert abs(result - 29.970) < 0.001, f"Expected ~29.970, got {result}"


def test_framerate_ntsc_5994():
    """59.94 fps — fps=60000, fps_base=1001."""
    _set_fps(60000, 1001.0)
    result = Blender_Scene.getFrameRate()
    assert abs(result - 59.940) < 0.001, f"Expected ~59.940, got {result}"


def test_framerate_returns_float_not_int():
    """Return type must be float (or at least a real number, not truncated int)."""
    _set_fps(24000, 1001.0)
    result = Blender_Scene.getFrameRate()
    # An int return of 24 would fail this check
    assert result != 24000
    assert result != 24
