# SPDX-License-Identifier: GPL-3.0-or-later

"""Addon preferences for B3D Playblast Plus."""

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, BoolProperty


class PlayblastPlusPreferences(AddonPreferences):
    """Persistent settings stored in Blender's user preferences."""

    # The bl_idname must match the package name (top-level directory / __init__.py)
    bl_idname = __package__

    output_path: StringProperty(  # type: ignore[valid-type]
        name="Default Output Path",
        description="Default directory for playblast output files",
        subtype="DIR_PATH",
        default="//playblasts/",
    )

    auto_open: BoolProperty(  # type: ignore[valid-type]
        name="Auto-open After Render",
        description="Automatically open the playblast in the system media player when done",
        default=False,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "output_path")
        layout.prop(self, "auto_open")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    PlayblastPlusPreferences,
)


def register() -> None:
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
