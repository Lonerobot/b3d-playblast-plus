# SPDX-License-Identifier: GPL-3.0-or-later

"""UI panels for B3D Playblast Plus."""

import bpy
from bpy.types import Panel


class PLAYBLAST_PT_main(Panel):
    """Main Playblast panel in the 3D Viewport sidebar."""

    bl_label = "Playblast Plus"
    bl_idname = "PLAYBLAST_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Playblast"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        col = layout.column(align=True)

        # TODO: add playblast settings and controls here
        col.operator("playblast.render", icon="RENDER_ANIMATION")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_classes = (
    PLAYBLAST_PT_main,
)


def register() -> None:
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
