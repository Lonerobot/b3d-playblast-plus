# Publish Code Validation — Playblast Plus (Blender)

> **Assessment Date:** 2026-04-24  
> **Reference:** [AYON Publish Developer Docs](https://docs.ayon.dev/docs/dev_publishing/)  
> **Scope:** All source files in the `b3d-playblast-plus` repository

---

## 1. Executive Summary

The current codebase provides **surface-level AYON awareness** — it reads AYON environment variables
to enrich output filenames with pipeline-aware tokens and shows a branded icon in the UI.
It does **not** implement an AYON publish pipeline.

There are no Creator, Collector, Validator, Extractor, or Integrator plugins.
Output files are written directly to a `playblasts/` folder next to the `.blend` file, completely outside
AYON's staging directory and version-management system.

The table below summarises conformance against each AYON publish principle:

| AYON Principle | Status | Notes |
|---|---|---|
| Creator plugin | ❌ Missing | No publish instance creation |
| Collector plugin | ❌ Missing | No pipeline context collection |
| Validator plugin | ❌ Missing | No pre-publish checks |
| Extractor plugin | ⚠️ Partial | `operators.py` performs extraction but outside the pyblish pipeline |
| Integrator plugin | ❌ Missing | No AYON version / review registration |
| Staging directory | ⚠️ Partial | Temp dir used for frames, but not AYON's `stagingDir` key |
| Product / family type | ❌ Missing | No `family` or `productType` declared |
| Version management | ❌ Missing | No AYON version increments |
| Review / reviewable | ❌ Missing | No `reviewable` flag or FTRACK/SG review creation |
| Token / context data | ⚠️ Partial | Env-var tokens for filenames only; no `instance.data` context |

> **Note on full pipeline integration:** AYON's `ayon_core` package imports OpenImageIO
> (OIIO), which is absent from Blender's bundled Python interpreter. Attempting to load
> `ayon_core` inside Blender causes a module conflict that crashes Blender. This is the
> primary architectural barrier to a complete in-process AYON publish integration and is
> discussed further in §4.1 and §5.

---

## 2. What the Current AYON Integration Does

The integration today is limited to three things.

### 2.1 AYON Token Registration (`lib/register_tokens.py`)

When both `AYON_PROJECT_NAME` **and** `AYON_WORKDIR` environment variables are present at
**import time**, four tokens are registered:

```
<ayon_project>  →  os.getenv("AYON_PROJECT_NAME")
<ayon_workdir>  →  os.getenv("AYON_WORKDIR")
<ayon_asset>    →  os.getenv("AYON_FOLDER_PATH") or os.getenv("AYON_ASSET")
<ayon_task>     →  os.getenv("AYON_TASK_NAME")
```

These tokens are substituted into the output filename string (e.g.
`<ayon_project>_<ayon_asset>_<ayon_task>`), which is a useful naming convention but is
not part of the AYON publish pipeline itself.

### 2.2 AYON Brand in the UI (`ui.py`)

When `AYON_PROJECT_NAME` is set, the panel header displays the project name and an AYON
icon, making it clear to artists that they are running inside a managed pipeline context.

### 2.3 No Publish Pipeline Calls

Neither `operators.py` nor any other module imports from `ayon_core`, calls
`pyblish.api`, or triggers any AYON publish event. The capture and encode steps run
entirely as standalone Blender operators.

---

## 3. Assessment Against AYON Publish Principles

The AYON publish pipeline is built on the **pyblish** framework and organises work into
five plugin types that run in a fixed order:
`Creator → Collector → Validator → Extractor → Integrator`.

### 3.1 Creator

**Purpose:** Mark content in the DCC scene as something to be published by creating a
structured instance (a container of metadata) that downstream plugins act on.

**Current state:** None. The addon has no Creator plugin. Artists trigger a capture
directly via the `PLAYBLASTPLUS_OT_run` operator. There is no publish instance,
no `family` / `productType`, and no `asset` binding stored in the scene.

**Impact:** Because no instance is created, none of the downstream AYON pipeline plugins
(validators, integrators) can act on the playblast output. Files are unknown to AYON.

---

### 3.2 Collector

**Purpose:** Harvest instances and pipeline context (project, asset, task, version,
staging directory) from the DCC environment and attach them to each instance's `data`
dictionary.

**Current state:** None. The AYON environment variables are read only to build a
filename string — they are never collected into a structured context object that the
publish pipeline could use.

**Impact:** Downstream plugins cannot rely on `instance.data["projectName"]`,
`instance.data["folderPath"]`, `instance.data["task"]`, etc.

---

### 3.3 Validator

**Purpose:** Inspect instances and the context for correctness without modifying the
scene or writing files. Fail the publish with a clear error message if checks do not pass.

**Current state:** None. There are no pre-publish checks for:

- Frame range validity (start < end, at least one frame)
- Camera existence and assignment
- Output directory writability
- AYON context consistency (e.g. `AYON_FOLDER_PATH` matches the open workfile)
- FFmpeg / apngasm availability (currently a hard runtime error in `execute()`)

The FFmpeg availability check in `PLAYBLASTPLUS_OT_run.execute()` is the closest thing
to a validator, but it runs mid-execution rather than before the pipeline begins.

---

### 3.4 Extractor

**Purpose:** Generate output files from the scene/instance into a **staging directory**,
a temporary location that is separate from the final publish destination.
The staging directory is managed by AYON (`instance.data["stagingDir"]`).

**Current state:** Partial. `operators.py` (`PLAYBLASTPLUS_OT_run`) performs the
extraction (capture PNG sequence → encode MP4/APNG), but:

- It does not use `instance.data["stagingDir"]`; it writes to
  `<blend_file_dir>/playblasts/` or the user extension directory.
- It runs as a Blender operator, not as a `pyblish.api.InstancePlugin`.
- It uses `subprocess.call(cmd, shell=True)` in `lib/encode.py`. This is an
  intentional architectural decision (see §4.1) but carries a path-sanitisation
  obligation.

---

### 3.5 Integrator

**Purpose:** Take files from the staging directory, move them to their final publish
location, register the version with the AYON server, and create review entries.

**Current state:** None. No AYON API calls are made, no version is created,
no review media is registered. The output file is simply placed on disk and (optionally)
opened in the OS viewer.

---

## 4. Code Issues Found

### 4.1 `shell=True` in `lib/encode.py` (`mp4_from_image_sequence`) — Architectural Context

The FFmpeg command is built by concatenating path strings and then executed with
`shell=True`:

```python
cmd = (
    f'"{ffmpeg_path}" '
    f'-i "{image_seq_path}" '
    ...
    f'"{output_path}"'
)
subprocess.call(cmd, shell=True)
```

**Why `shell=True` is intentional here.** Blender's bundled Python does not include
OpenImageIO (OIIO). AYON's Tray Publisher pipeline loads `ayon_core`, which in turn
imports OIIO. When this Python-level import is attempted inside Blender's interpreter it
creates a module conflict that crashes Blender. Extensive testing confirmed that the only
reliable way to invoke FFmpeg alongside an active AYON Tray Publisher session is via a
shell subprocess that runs entirely outside Blender's Python process. Switching to a
list-based `subprocess.run` (no shell) does **not** resolve this conflict because the
conflict is in the Python import chain, not the process model.

**Residual risk — path sanitisation.** While the architectural choice is sound, the
current implementation does no input validation before constructing the shell string.
An output path derived from user-controlled data (e.g. a token that expands to a string
containing shell metacharacters) could lead to unintended shell behaviour.

**Recommendation:** Add a path sanitisation step before building the command string.
On POSIX systems, `shlex.quote()` can be used to escape each path component. On Windows,
wrapping each path in double-quotes (as the code already does) is the correct approach,
but the path itself should be validated to contain no embedded double-quote characters:

```python
import shlex, sys

def _shell_quote(path: str) -> str:
    """Return a safely quoted path for use in shell=True subprocess calls."""
    if sys.platform == "win32":
        # Windows: strip any embedded quotes then re-wrap
        return '"' + path.replace('"', '') + '"'
    return shlex.quote(path)
```

The inputs `ffmpeg_path`, `image_seq_path`, and `output_path` should all pass through
`_shell_quote()` before being interpolated into `cmd`.

---

### 4.2 AYON Token Registration at Import Time (`lib/register_tokens.py`)

The AYON guard block runs at **module import time**, not inside a `register()` function:

```python
# runs unconditionally when the module is imported
if os.getenv("AYON_PROJECT_NAME") and os.getenv("AYON_WORKDIR"):
    tokens.register_token("<ayon_project>", ...)
    ...
```

This has two consequences:

1. If the user installs the addon, restarts Blender **with** AYON env vars, then removes
   those vars and reloads without a full restart, the tokens remain registered (stale).
2. Tokens cannot be unregistered when the addon is disabled via the normal `unregister()`
   path.

**Recommendation:** Move the guard block inside an explicit `register()` function and
add a paired `unregister()` function that removes the tokens from `_registered_tokens`.
Guard on `AYON_PROJECT_NAME` alone (see §4.3).

---

### 4.3 Over-Restrictive AYON Context Guard

The token registration guard requires **both** `AYON_PROJECT_NAME` and `AYON_WORKDIR`:

```python
if os.getenv("AYON_PROJECT_NAME") and os.getenv("AYON_WORKDIR"):
```

`AYON_WORKDIR` is not always present — for example in a batch / farm context or during
early pipeline bootstrapping where only the project and asset context are injected.
`AYON_PROJECT_NAME` is the canonical indicator that AYON is active.

**Recommendation:** Guard on `AYON_PROJECT_NAME` alone. Keep `<ayon_workdir>` resolving
to an empty string if the env var is absent (the lambda already handles this gracefully).

---

### 4.4 Deprecated `AYON_ASSET` Fallback (`lib/register_tokens.py`)

```python
lambda options: os.getenv("AYON_FOLDER_PATH", os.getenv("AYON_ASSET", "")),
```

`AYON_ASSET` is the old OpenPype variable name; in AYON it has been superseded by
`AYON_FOLDER_PATH`. Using the deprecated name as a silent fallback may silently return
wrong data in mixed OpenPype/AYON environments.

**Recommendation:** Remove the `AYON_ASSET` fallback or, if backward compatibility with
OpenPype is intentional, add a comment making this explicit.

---

### 4.5 `BlenderLogger` Is Defined but Never Used

`lib/blender_logger.py` exposes a `log` instance but no other module imports it.
All diagnostic output uses `print()` directly (e.g. `print("[PlayblastPlus] ...")`).

**Recommendation:** Either adopt the logger throughout (`log.info(...)`, `log.error(...)`)
or remove `blender_logger.py` to avoid dead code confusion.

---

### 4.6 Frame Range Validation Is Absent

`PLAYBLASTPLUS_OT_run.execute()` reads `frame_start` / `frame_end` from the scene but
never checks that `frame_start <= frame_end` or that the range is non-zero.
An inverted range (e.g. start=250, end=1) would silently produce zero or garbage output.

**Recommendation:** Add an early guard:

```python
if frame_start > frame_end:
    self.report({'ERROR'}, "PlayblastPlus: frame start is after frame end.")
    return {'CANCELLED'}
```

---

### 4.7 Temp Directory Is Not Cleaned Up on Failure

If the capture succeeds but encoding fails, the PNG frame sequence in `temp_dir` is
**not** removed. Files accumulate between failed runs.

**Recommendation:** Clean up `temp_dir` in all error return paths, or use a
`try/finally` block.

---

### 4.8 `getFrameRate` Returns an Integer, Not a Float (`lib/blender_scene.py`)

```python
@staticmethod
def getFrameRate() -> int:
    return bpy.context.scene.render.fps
```

`bpy.context.scene.render.fps` is an integer (frames per second numerator).
The true frame rate is `fps / fps_base`. For non-integer frame rates (e.g. 23.976 fps,
where `fps=24000` and `fps_base=1001`), this returns the wrong value.

**Recommendation:** Return `bpy.context.scene.render.fps / bpy.context.scene.render.fps_base`.

---

## 5. Recommended AYON Publish Architecture

> **Important constraint.** Full in-process AYON publish integration (via
> `ayon_core` / `pyblish`) requires OpenImageIO (OIIO), which is not bundled with
> Blender's Python interpreter. Importing `ayon_core` inside Blender therefore causes a
> module conflict that crashes Blender. Any publish integration must work around this
> by either (a) spawning AYON's Tray Publisher as a separate process that communicates
> with Blender, or (b) restricting in-process code to pure Python with no OIIO dependency.

The AYON publish pipeline is built on [pyblish](https://pyblish.com/) and AYON extends
it primarily with the `CreateContext` / `CreatedInstance` machinery described at
https://docs.ayon.dev/docs/dev_publishing/.

Key concepts from the docs that apply here:

- **`family`** on a `CreatedInstance` is **immutable** once set — it must be declared by
  the Creator plugin before the instance is handed to the pipeline.
- **`AutoCreator`** is the right base class for instances that should be created
  automatically without artist interaction (e.g. a workfile publish or a playblast that
  is always "ready to publish" when the addon is active).
- The Creator must implement `collect_instances`, `update_instances`, and
  `remove_instances` to keep scene metadata in sync with the pyblish context.
- Validation errors should raise `PublishValidationError` (not generic exceptions) so
  that AYON's UI can surface them with repair actions.

If full AYON pipeline integration is desired, the addon should be extended with a
`publish/` package containing the following plugins:

```
publish/
├── __init__.py
├── create_playblast.py          # AutoCreator — auto-registers a "review" instance
├── collect_ayon_context.py      # ContextPlugin — enriches context with pipeline vars
├── validate_frame_range.py      # InstancePlugin — start ≤ end, non-zero
├── validate_camera.py           # InstancePlugin — active camera exists
├── validate_output_dir.py       # InstancePlugin — output path is writable
├── extract_playblast.py         # InstancePlugin — captures PNG sequence + encodes
│                                #   (keeps shell=True for FFmpeg; writes to stagingDir)
└── integrate_review.py          # InstancePlugin — registers review media with AYON
```

### 5.1 AutoCreator Sketch

Per the AYON docs, `AutoCreator` is triggered on `CreateContext` reset and requires no
artist interaction — exactly the right pattern for a playblast that should always be
publishable when the addon is loaded.

```python
# publish/create_playblast.py
from ayon_core.pipeline.create import AutoCreator, CreatedInstance

class CreatePlayblast(AutoCreator):
    """Auto-create a review instance for the current Blender scene."""
    family     = "review"
    identifier = "playblast_review"
    label      = "Playblast Review"

    def collect_instances(self):
        # Re-collect any instance already stored in scene custom properties
        for stored in _read_scene_instances():
            if stored.get("creator_identifier") == self.identifier:
                instance = CreatedInstance.from_existing(stored, self)
                self._add_instance_to_context(instance)

    def create(self):
        # Called on reset if no existing instance found
        existing = next(
            (i for i in self.create_context.instances
             if i.creator_identifier == self.identifier),
            None,
        )
        if existing is not None:
            return
        instance_data = {
            "asset":   os.getenv("AYON_FOLDER_PATH", ""),
            "task":    os.getenv("AYON_TASK_NAME", ""),
            "variant": "Main",
        }
        instance = CreatedInstance(self.family, "playblastMain", instance_data, self)
        self._add_instance_to_context(instance)
        _store_scene_instance(instance.data_to_store())

    def update_instances(self, update_list):
        for instance, _ in update_list:
            _store_scene_instance(instance.data_to_store())

    def remove_instances(self, instances):
        pass  # AutoCreator — don't allow removal
```

### 5.2 Collector Sketch

```python
# publish/collect_ayon_context.py
import os
import pyblish.api

class CollectAyonContext(pyblish.api.ContextPlugin):
    """Collect AYON pipeline context into the publish context."""
    label = "Collect AYON Context"
    order = pyblish.api.CollectorOrder
    hosts = ["blender"]

    def process(self, context):
        context.data["projectName"]  = os.getenv("AYON_PROJECT_NAME", "")
        context.data["folderPath"]   = os.getenv("AYON_FOLDER_PATH", "")
        context.data["task"]         = os.getenv("AYON_TASK_NAME", "")
        context.data["workdir"]      = os.getenv("AYON_WORKDIR", "")
```

### 5.3 Validator Sketch (with `PublishValidationError`)

```python
# publish/validate_frame_range.py
import pyblish.api
from ayon_core.pipeline.publish import PublishValidationError

class ValidateFrameRange(pyblish.api.InstancePlugin):
    """Ensure frame start is not after frame end."""
    label    = "Validate Frame Range"
    order    = pyblish.api.ValidatorOrder
    families = ["review"]
    hosts    = ["blender"]

    def process(self, instance):
        import bpy
        scene = bpy.context.scene
        if scene.frame_start > scene.frame_end:
            raise PublishValidationError(
                message="Frame range is inverted",
                title="Invalid Frame Range",
                description=(
                    f"Frame start ({scene.frame_start}) is after "
                    f"frame end ({scene.frame_end}). "
                    "Fix the frame range in the Output Properties."
                ),
            )
```

### 5.4 Extractor Sketch

The extractor uses `shell=True` for FFmpeg (matching the current implementation) and
writes output into `instance.data["stagingDir"]` so the Integrator can pick it up.

```python
# publish/extract_playblast.py
import tempfile
import pyblish.api

class ExtractPlayblast(pyblish.api.InstancePlugin):
    """Capture the viewport and encode to the instance's staging directory."""
    label    = "Extract Playblast"
    order    = pyblish.api.ExtractorOrder
    families = ["review"]
    hosts    = ["blender"]

    def process(self, instance):
        staging_dir = instance.data.get("stagingDir") or tempfile.mkdtemp()
        instance.data["stagingDir"] = staging_dir

        # Run capture + encode using existing Blender operators / lib/encode.py
        # (shell=True subprocess is preserved to avoid OIIO/ayon_core conflict)
        output_file = _capture_and_encode(staging_dir)

        instance.data["representations"] = [{
            "name":       "mp4",
            "ext":        "mp4",
            "files":      output_file,
            "stagingDir": staging_dir,
            "reviewable": True,
        }]
```

---

## 6. Suggested Unit Tests

The tests below can be run with **pytest** from the repository root without Blender, by
isolating modules that do not import `bpy`.

### 6.1 Token System (`lib/tokens.py`)

```python
# tests/test_tokens.py
import importlib
import sys

# Stub bpy so register_tokens can be imported without Blender
sys.modules.setdefault("bpy", type(sys)("bpy"))

from lib import tokens


def setup_function():
    tokens._registered_tokens.clear()


def test_register_and_format():
    tokens.register_token("<foo>", lambda opts: "bar", label="Foo")
    assert tokens.format_tokens("<foo>_suffix", None) == "bar_suffix"


def test_format_with_no_tokens_unchanged():
    assert tokens.format_tokens("plain_name", None) == "plain_name"


def test_format_empty_string_returns_empty():
    assert tokens.format_tokens("", None) == ""


def test_format_none_returns_none():
    assert tokens.format_tokens(None, None) is None


def test_token_assertion_requires_angle_brackets():
    import pytest
    with pytest.raises(AssertionError):
        tokens.register_token("no_brackets", lambda o: "x")


def test_list_tokens_returns_copy():
    tokens.register_token("<x>", lambda o: "x")
    listed = tokens.list_tokens()
    listed.clear()
    assert "<x>" in tokens._registered_tokens
```

### 6.2 FFmpeg Input Path Generation (`lib/utils.py`)

```python
# tests/test_utils.py
from lib.utils import Parsing


def test_four_digit_frame_number():
    result = Parsing.create_ffmpeg_input("/tmp/shot.0001.png")
    assert result == "/tmp/shot.%04d.png"


def test_different_padding():
    result = Parsing.create_ffmpeg_input("/tmp/take.001.png")
    assert result == "/tmp/take.%03d.png"


def test_no_frame_number_returns_none():
    result = Parsing.create_ffmpeg_input("/tmp/image.png")
    assert result is None


def test_none_input_returns_none():
    result = Parsing.create_ffmpeg_input(None)
    assert result is None


def test_path_with_spaces():
    result = Parsing.create_ffmpeg_input("/my renders/shot A.0010.png")
    assert result == "/my renders/shot A.%04d.png"


def test_blender_version_suffix_not_confused():
    # Blender appends .001 / .002 to object names — the regex should match
    # only the rightmost numeric run before .png
    result = Parsing.create_ffmpeg_input("/tmp/cube.001.0023.png")
    assert result == "/tmp/cube.001.%04d.png"
```

### 6.3 AYON Token Registration Guard (`lib/register_tokens.py`)

```python
# tests/test_register_tokens.py
"""
These tests reload the register_tokens module with different environment variable
combinations to verify that the AYON guard behaves correctly.
"""
import importlib
import os
import sys
import types


def _make_bpy_stub():
    bpy = types.ModuleType("bpy")
    bpy.context = types.SimpleNamespace(
        view_layer=types.SimpleNamespace(name="ViewLayer")
    )
    return bpy


def _reload_with_env(env: dict):
    """Reload the token modules with a clean state and given env vars."""
    # Stub bpy
    sys.modules["bpy"] = _make_bpy_stub()

    # Clear token state
    for mod_name in list(sys.modules):
        if "tokens" in mod_name or "register_tokens" in mod_name or "blender_scene" in mod_name:
            del sys.modules[mod_name]

    old_env = os.environ.copy()
    os.environ.clear()
    os.environ.update(env)
    try:
        from lib import tokens as t
        from lib import register_tokens  # noqa: F401
        return t
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_ayon_tokens_registered_when_project_set():
    t = _reload_with_env({"AYON_PROJECT_NAME": "my_project"})
    assert "<ayon_project>" in t._registered_tokens


def test_ayon_tokens_not_registered_without_project():
    t = _reload_with_env({})
    assert "<ayon_project>" not in t._registered_tokens


def test_ayon_asset_token_prefers_folder_path():
    """AYON_FOLDER_PATH should take precedence over deprecated AYON_ASSET."""
    t = _reload_with_env({
        "AYON_PROJECT_NAME": "p",
        "AYON_FOLDER_PATH":  "/shots/sh010",
        "AYON_ASSET":        "old_asset",
    })
    resolved = t._registered_tokens["<ayon_asset>"]["func"](None)
    assert resolved == "/shots/sh010"


def test_ayon_workdir_token_empty_when_missing():
    t = _reload_with_env({"AYON_PROJECT_NAME": "p"})
    resolved = t._registered_tokens["<ayon_workdir>"]["func"](None)
    assert resolved == ""
```

### 6.4 Encode Module (`lib/encode.py`)

```python
# tests/test_encode.py
from pathlib import Path
import subprocess
import pytest
from unittest.mock import patch, MagicMock

from lib.encode import apng_from_image_sequence, mp4_from_image_sequence


def test_apng_no_frames_returns_false():
    assert apng_from_image_sequence("/fake/apngasm", [], "/tmp/out.png") is False


def test_apng_missing_binary_returns_false():
    assert apng_from_image_sequence("/nonexistent/apngasm", ["f.png"], "/tmp/out.png") is False


def test_mp4_missing_ffmpeg_returns_false():
    assert mp4_from_image_sequence("", "in_%04d.png", "/tmp/out.mp4") is False


def test_apng_timeout_returns_false(tmp_path):
    """A subprocess.TimeoutExpired during encoding should return False, not raise."""
    fake_apngasm = tmp_path / "apngasm"
    fake_apngasm.touch()
    fake_apngasm.chmod(0o755)

    mock_proc = MagicMock()
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=1, output=None)):
        with patch.object(subprocess.TimeoutExpired, "process", mock_proc, create=True):
            result = apng_from_image_sequence(
                str(fake_apngasm), ["f1.png"], str(tmp_path / "out.png"), timeout=1
            )
    assert result is False
```

### 6.5 Frame-Rate Precision (Regression for §4.8)

```python
# tests/test_framerate.py
"""
These tests require the fix described in §4.8 — getFrameRate() must return fps/fps_base.
Run after applying the fix.
"""
import types, sys

# Stub bpy with a non-integer frame rate (23.976 = 24000/1001)
bpy_stub = types.ModuleType("bpy")
render_stub = types.SimpleNamespace(fps=24000, fps_base=1001.0)
scene_stub  = types.SimpleNamespace(render=render_stub)
context_stub = types.SimpleNamespace(scene=scene_stub)
bpy_stub.context = context_stub
sys.modules["bpy"] = bpy_stub

from lib.blender_scene import Blender_Scene


def test_framerate_ntsc():
    fps = Blender_Scene.getFrameRate()
    assert abs(fps - 23.976) < 0.001


def test_framerate_24():
    bpy_stub.context.scene.render.fps      = 24
    bpy_stub.context.scene.render.fps_base = 1.0
    assert Blender_Scene.getFrameRate() == 24.0
```

---

## 7. Prioritised Action List

| Priority | Item | File | Section |
|---|---|---|---|
| 🔴 High | Path sanitisation for `shell=True` FFmpeg calls | `lib/encode.py` | §4.1 |
| 🔴 High | Validate frame range before capture | `operators.py` | §4.6 |
| 🟡 Medium | Fix `getFrameRate()` precision | `lib/blender_scene.py` | §4.8 |
| 🟡 Medium | Move AYON token guard into `register()` | `lib/register_tokens.py` | §4.2 |
| 🟡 Medium | Guard on `AYON_PROJECT_NAME` only | `lib/register_tokens.py` | §4.3 |
| 🟡 Medium | Remove deprecated `AYON_ASSET` fallback | `lib/register_tokens.py` | §4.4 |
| 🟢 Low | Adopt `BlenderLogger` or remove it | `lib/blender_logger.py` | §4.5 |
| 🟢 Low | Clean up temp dir on encode failure | `operators.py` | §4.7 |
| 🔵 Future | Implement AYON publish pipeline plugins (pending OIIO constraint resolution) | `publish/` | §5 |

---

## 8. Conclusion

Playblast Plus is a well-structured, self-contained Blender addon. Its AYON awareness is
a useful starting point. The use of `shell=True` for FFmpeg is a deliberate and
justified architectural decision driven by Blender's lack of OIIO and the resulting
`ayon_core` import conflicts — the recommendation is to harden it with path sanitisation
rather than remove it.

The most impactful near-term fixes are frame range validation and path sanitisation in
the FFmpeg command string. The AYON token registration lifecycle (§4.2–4.3) is a
moderate-effort improvement that makes the addon more robust in dynamic pipeline
environments.

Full AYON publish pipeline integration (Creator → Collector → Validator → Extractor →
Integrator) is architecturally feasible using `AutoCreator` and keeping all subprocess
calls (FFmpeg) out-of-process, but requires careful design around the OIIO/Blender
constraint. The sketch in §5 provides a path aligned with
https://docs.ayon.dev/docs/dev_publishing/.
