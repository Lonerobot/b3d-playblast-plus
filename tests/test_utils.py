"""tests/test_utils.py — unit tests for ``lib/utils.py``.

These tests run without Blender.  ``lib/utils.py`` has no ``bpy`` dependency.

Negative-frame sequences
------------------------
Blender renders negative frame numbers with a leading minus sign, always
zero-padding the digit portion to 4 places:

    frame -1   →  shot.-0001.png   (5 characters: minus + 4 digits)
    frame -100 →  shot.-0100.png   (5 characters)

FFmpeg's printf-style ``%0Nd`` format mirrors this behaviour: ``%05d`` with
value ``-1`` produces ``-0001``.  The tests below confirm that
``create_ffmpeg_input`` returns a ``%05d`` pattern for any filename whose
frame field starts with a minus sign.
"""

import pytest

from lib.utils import Parsing


# ---------------------------------------------------------------------------
# Positive frame numbers
# ---------------------------------------------------------------------------

def test_four_digit_frame_number():
    result = Parsing.create_ffmpeg_input("/tmp/shot.0001.png")
    assert result == "/tmp/shot.%04d.png"


def test_three_digit_padding():
    result = Parsing.create_ffmpeg_input("/tmp/take.001.png")
    assert result == "/tmp/take.%03d.png"


def test_five_digit_frame_number():
    result = Parsing.create_ffmpeg_input("/tmp/long.10001.png")
    assert result == "/tmp/long.%05d.png"


def test_path_with_spaces():
    result = Parsing.create_ffmpeg_input("/my renders/shot A.0010.png")
    assert result == "/my renders/shot A.%04d.png"


def test_blender_version_suffix_not_confused():
    """Blender appends .001/.002 to object names; only the rightmost run before .png matters."""
    result = Parsing.create_ffmpeg_input("/tmp/cube.001.0023.png")
    assert result == "/tmp/cube.001.%04d.png"


def test_case_insensitive_extension():
    result = Parsing.create_ffmpeg_input("/tmp/shot.0001.PNG")
    assert result == "/tmp/shot.%04d.PNG"


def test_frame_zero():
    result = Parsing.create_ffmpeg_input("/tmp/shot.0000.png")
    assert result == "/tmp/shot.%04d.png"


# ---------------------------------------------------------------------------
# Negative frame numbers
# ---------------------------------------------------------------------------

def test_negative_frame_minus_0001():
    """Frame -1: Blender outputs shot.-0001.png → %05d pattern."""
    result = Parsing.create_ffmpeg_input("/tmp/shot.-0001.png")
    assert result == "/tmp/shot.%05d.png"


def test_negative_frame_minus_0005():
    """Frame -5: shot.-0005.png → %05d pattern."""
    result = Parsing.create_ffmpeg_input("/tmp/shot.-0005.png")
    assert result == "/tmp/shot.%05d.png"


def test_negative_frame_minus_0100():
    """Frame -100: shot.-0100.png → %05d pattern."""
    result = Parsing.create_ffmpeg_input("/tmp/seq.-0100.png")
    assert result == "/tmp/seq.%05d.png"


def test_negative_frame_with_spaces_in_path():
    result = Parsing.create_ffmpeg_input("/my renders/anim.-0010.png")
    assert result == "/my renders/anim.%05d.png"


def test_negative_frame_deep_path():
    result = Parsing.create_ffmpeg_input("/a/b/c/scene.object.-0042.png")
    assert result == "/a/b/c/scene.object.%05d.png"


def test_negative_five_digit_frame():
    """Very large negative frame: shot.-10000.png → %06d."""
    result = Parsing.create_ffmpeg_input("/tmp/shot.-10000.png")
    assert result == "/tmp/shot.%06d.png"


# ---------------------------------------------------------------------------
# Edge cases — no frame number
# ---------------------------------------------------------------------------

def test_no_frame_number_returns_none():
    result = Parsing.create_ffmpeg_input("/tmp/image.png")
    assert result is None


def test_none_input_returns_none():
    result = Parsing.create_ffmpeg_input(None)
    assert result is None


def test_empty_string_returns_none():
    result = Parsing.create_ffmpeg_input("")
    assert result is None


def test_path_with_no_extension_returns_none():
    result = Parsing.create_ffmpeg_input("/tmp/shot_0001")
    assert result is None
