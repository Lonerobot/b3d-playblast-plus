"""
APNG preset loader.

Presets are defined in apng-presets.json at the add-on root.
Edit that file manually to add, remove, or adjust presets.

Each preset entry:
  {
    "name":      str   — unique identifier used as EnumProperty value
    "label":     str   — human-readable name shown in the dropdown
    "width":     int   — render resolution X
    "height":    int   — render resolution Y
    "framerate": int   — scene frame rate
  }
"""

import json
from pathlib import Path

_PRESETS_FILE = Path(__file__).parent.parent / "apng-presets.json"

# Blender requires that EnumProperty items callbacks return a list whose
# strings stay alive (no GC). We keep a module-level cache for this.
_enum_cache: list = []


def load_presets() -> list:
    """Read presets from apng-presets.json. Returns an empty list on any error."""
    if not _PRESETS_FILE.is_file():
        return []
    try:
        data = json.loads(_PRESETS_FILE.read_text(encoding="utf-8"))
        return data.get("presets", [])
    except Exception as exc:
        print(f"[PlayblastPlus] Could not load apng-presets.json: {exc}")
        return []


def get_preset(name: str) -> dict | None:
    """Return the preset dict matching *name*, or None."""
    for preset in load_presets():
        if preset.get("name") == name:
            return preset
    return None


def enum_items(_self=None, _context=None) -> list:
    """Dynamic EnumProperty items callback.

    Returns a cached list of (identifier, label, description) tuples.
    Falls back to a single placeholder entry when the file is missing or empty.
    """
    global _enum_cache
    presets = load_presets()
    if not presets:
        _enum_cache = [
            ("NONE", "No presets", "Add presets to apng-presets.json in the add-on folder"),
        ]
        return _enum_cache

    _enum_cache = [
        (
            p["name"],
            p.get("label", p["name"]),
            f"{p.get('width', '?')}\u00d7{p.get('height', '?')} @ {p.get('framerate', '?')} fps",
        )
        for p in presets
    ]
    return _enum_cache
