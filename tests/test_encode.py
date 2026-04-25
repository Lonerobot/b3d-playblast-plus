"""tests/test_encode.py — unit tests for ``lib/encode.py``.

Covers:
- Path sanitisation via ``_shell_quote``
- Verification that ``mp4_from_image_sequence`` passes correctly-quoted paths
  to the shell command
- Error-path behaviour (missing binary, no frames, timeout)

These tests run without Blender.  ``lib/encode.py`` has no ``bpy`` dependency.
"""

import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.encode import _shell_quote, apng_from_image_sequence, mp4_from_image_sequence


# ---------------------------------------------------------------------------
# _shell_quote — path sanitisation unit tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shlex quoting only")
def test_shell_quote_posix_simple_path():
    assert _shell_quote("/tmp/output.mp4") == shlex.quote("/tmp/output.mp4")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shlex quoting only")
def test_shell_quote_posix_path_with_spaces():
    quoted = _shell_quote("/my renders/shot A.mp4")
    # shlex.split must reconstruct the exact path as a single token
    parts = shlex.split(quoted)
    assert len(parts) == 1
    assert parts[0] == "/my renders/shot A.mp4"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shlex quoting only")
def test_shell_quote_posix_path_with_shell_metacharacters():
    """A path containing $, (, ) etc. must not be shell-expanded."""
    dangerous = "/tmp/shot$(id).mp4"
    quoted = _shell_quote(dangerous)
    parts = shlex.split(quoted)
    assert len(parts) == 1
    assert parts[0] == dangerous


@pytest.mark.skipif(sys.platform != "win32", reason="Windows quoting only")
def test_shell_quote_windows_wraps_in_double_quotes():
    result = _shell_quote("C:\\My Renders\\output.mp4")
    assert result.startswith('"') and result.endswith('"')


@pytest.mark.skipif(sys.platform != "win32", reason="Windows quoting only")
def test_shell_quote_windows_strips_embedded_quotes():
    result = _shell_quote('C:\\bad"path\\file.mp4')
    inner = result.strip('"')
    assert '"' not in inner


# ---------------------------------------------------------------------------
# mp4_from_image_sequence — shell command quotes all paths
# ---------------------------------------------------------------------------

def test_mp4_shell_command_quotes_paths_with_spaces(tmp_path):
    """Paths containing spaces survive round-trip through the shell command."""
    spaced_dir = tmp_path / "my renders"
    spaced_dir.mkdir()
    fake_ffmpeg = spaced_dir / "ffmpeg"
    fake_ffmpeg.touch()

    output_path = str(spaced_dir / "output with spaces.mp4")
    image_seq   = str(spaced_dir / "shot with spaces.%04d.png")

    captured = []

    def fake_call(cmd, **kwargs):
        captured.append(cmd)
        Path(output_path).touch()  # simulate successful encode
        return 0

    with patch("subprocess.call", side_effect=fake_call):
        result = mp4_from_image_sequence(
            ffmpeg_path=str(fake_ffmpeg),
            image_seq_path=image_seq,
            output_path=output_path,
        )

    assert result is True
    assert captured, "subprocess.call was not called"
    cmd_str = captured[0]

    if sys.platform != "win32":
        # On POSIX, shlex.split must recover the exact paths
        parts = shlex.split(cmd_str)
        assert str(fake_ffmpeg) in parts
        assert image_seq in parts
        assert output_path in parts


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shlex quoting only")
def test_mp4_shell_command_quotes_audio_path(tmp_path):
    """Audio path with spaces is also safely quoted."""
    fake_ffmpeg = tmp_path / "ffmpeg"
    fake_ffmpeg.touch()
    audio_path  = str(tmp_path / "my audio track.wav")
    output_path = str(tmp_path / "out.mp4")
    image_seq   = str(tmp_path / "shot.%04d.png")

    # Create dummy audio file so it passes any existence check that may be added
    Path(audio_path).touch()

    captured = []

    def fake_call(cmd, **kwargs):
        captured.append(cmd)
        Path(output_path).touch()
        return 0

    with patch("subprocess.call", side_effect=fake_call):
        mp4_from_image_sequence(
            ffmpeg_path=str(fake_ffmpeg),
            image_seq_path=image_seq,
            output_path=output_path,
            audio_path=audio_path,
        )

    assert captured
    cmd_str = captured[0]
    parts = shlex.split(cmd_str)
    assert audio_path in parts


# ---------------------------------------------------------------------------
# Error-path behaviour
# ---------------------------------------------------------------------------

def test_mp4_missing_ffmpeg_path_returns_false():
    assert mp4_from_image_sequence("", "in_%04d.png", "/tmp/out.mp4") is False


def test_mp4_nonexistent_ffmpeg_returns_false():
    assert mp4_from_image_sequence(
        "/nonexistent/ffmpeg", "in_%04d.png", "/tmp/out.mp4"
    ) is False


def test_apng_no_frames_returns_false():
    assert apng_from_image_sequence("/fake/apngasm", [], "/tmp/out.png") is False


def test_apng_missing_binary_returns_false():
    assert apng_from_image_sequence(
        "/nonexistent/apngasm", ["f.png"], "/tmp/out.png"
    ) is False


def test_apng_empty_binary_path_returns_false():
    assert apng_from_image_sequence("", ["f.png"], "/tmp/out.png") is False


def test_apng_timeout_returns_false(tmp_path):
    """subprocess.TimeoutExpired during encoding must return False, not raise."""
    fake_apngasm = tmp_path / "apngasm"
    fake_apngasm.touch()
    fake_apngasm.chmod(0o755)

    exc = subprocess.TimeoutExpired(cmd=[], timeout=1)
    exc.process = MagicMock()  # apng_from_image_sequence calls e.process.kill()

    with patch("subprocess.run", side_effect=exc):
        result = apng_from_image_sequence(
            str(fake_apngasm), ["f1.png"], str(tmp_path / "out.png"), timeout=1
        )

    assert result is False
    exc.process.kill.assert_called_once()


def test_apng_returns_false_when_output_not_created(tmp_path):
    """apng returns False when apngasm runs but produces no output file."""
    fake_apngasm = tmp_path / "apngasm"
    fake_apngasm.touch()
    fake_apngasm.chmod(0o755)

    # subprocess.run returns normally but no output file is written
    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("subprocess.run", return_value=mock_result):
        result = apng_from_image_sequence(
            str(fake_apngasm),
            ["f1.png"],
            str(tmp_path / "out.png"),
        )

    assert result is False
