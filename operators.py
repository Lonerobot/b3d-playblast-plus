# SPDX-License-Identifier: GPL-3.0-or-later

"""Operators for B3D Playblast Plus."""

import bpy
from bpy.types import Operator


class PLAYBLAST_OT_render(Operator):
    """Render a viewport playblast"""

    bl_idname = "playblast.render"
    bl_label = "Render Playblast"
    bl_description = "Render a viewport playblast to disk"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        # TODO: replace with playblast render logic
        self.report({"INFO"}, "Playblast render complete")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    PLAYBLAST_OT_render,
)


def register() -> None:
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
