# SPDX-License-Identifier: GPL-3.0-or-later

"""
B3D Playblast Plus
==================
Maya/3ds Max style playblast rendering for Blender.

Metadata is defined in blender_manifest.toml (Blender 4.2+ extension platform).
The bl_info dict below is retained for backwards-compatibility with older Blender
versions that do not yet support the extensions platform.
"""

bl_info = {
    "name": "B3D Playblast Plus",
    "author": "Lonerobot",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Playblast",
    "description": "Maya/3ds Max style playblast rendering for Blender",
    "category": "Render",
    "doc_url": "https://github.com/Lonerobot/b3d-playblast-plus",
    "tracker_url": "https://github.com/Lonerobot/b3d-playblast-plus/issues",
}

import bpy  # noqa: E402  (imported after bl_info intentionally)

from . import operators, panels, preferences


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register() -> None:
    preferences.register()
    operators.register()
    panels.register()


def unregister() -> None:
    panels.unregister()
    operators.unregister()
    preferences.unregister()


if __name__ == "__main__":
    register()
