import os

import bpy
from bpy.types import Panel, Menu

from . import bl_info
from .lib.tokens import list_tokens
from .lib.custom_icons import get_icon_id


def _panel_title() -> str:
    v = bl_info["version"]
    title = f"Playblast Plus  v{v[0]}.{v[1]}.{v[2]}"
    ayon = os.getenv("AYON_PROJECT_NAME")
    if ayon:
        title += f"  -  {ayon}"
    return title


# ---------------------------------------------------------------------------
# Token insert menu
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_MT_token_menu(Menu):
    bl_label = "Insert Token"
    bl_idname = "PLAYBLASTPLUS_MT_token_menu"

    def draw(self, context):
        layout = self.layout
        for token, info in list_tokens().items():
            op = layout.operator(
                "playblastplus.insert_token",
                text=f"{info['label']}  {token}",
                icon='ADD',
            )
            op.token = token


# ---------------------------------------------------------------------------
# 3D viewport header menu
# ---------------------------------------------------------------------------

class VIEW3D_MT_playblastplus(Menu):
    bl_label = "Playblast Plus"
    bl_idname = "VIEW3D_MT_playblastplus"

    def draw(self, context):
        layout = self.layout
        layout.operator("playblastplus.run",      text="Playblast",    icon='RENDER_ANIMATION')
        layout.operator("playblastplus.snapshot", text="Snapshot",     icon='IMAGE')
        layout.separator()
        layout.operator("playblastplus.open_output", text="Open Folder", icon='FILE_FOLDER')
        layout.operator("playblastplus.open_last",   text="Open Last",   icon='FILE_MOVIE')


def _menu_func_view3d(self, context):
    self.layout.menu(VIEW3D_MT_playblastplus.bl_idname)


# ---------------------------------------------------------------------------
# Main (flat) panel — no sub-panels, all content in boxes
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_PT_main(Panel):
    bl_label = _panel_title()
    bl_idname = "PLAYBLASTPLUS_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Playblast Plus'

    def draw(self, context):
        layout = self.layout
        props = context.scene.playblast_plus

        # ── Header / description box (Shotput pattern) ──────────────────
        box = layout.box()
        col = box.column(align=True)
        ayon = os.getenv("AYON_PROJECT_NAME")
        if ayon:
            icon = get_icon_id("ayon")
            col.label(text="Playblast Plus — Animation Review", **icon)
        else:
            col.label(text="Playblast Plus — Animation Review", icon='RENDER_ANIMATION')
        col.separator(factor=0.4)
        sub = col.column(align=True)
        sub.scale_y = 0.75
        sub.label(text="Capture and encode the viewport frame range")

        # ── Tool guard (format-aware) ─────────────────────────────────────
        prefs = context.preferences.addons[__package__].preferences
        from .lib.ffmpeg_utils import dl_state, find_apngasm, find_ffmpeg

        if prefs.output_format == 'MP4':
            if dl_state["running"]:
                box = layout.box()
                col = box.column(align=True)
                col.label(text="Downloading FFmpeg…", icon='IMPORT')
                col.progress(
                    factor=dl_state["progress"],
                    text=f"{int(dl_state['progress'] * 100)} %",
                )
                return
            if dl_state["error"]:
                box = layout.box()
                col = box.column(align=True)
                col.alert = True
                col.label(text="Download failed", icon='ERROR')
                col.label(text=dl_state["error"])
                col.separator(factor=0.3)
                col.operator("playblastplus.install_ffmpeg", text="Retry", icon='FILE_REFRESH')
                return
            if not find_ffmpeg(prefs.ffmpeg_path):
                warn = layout.box().column(align=True)
                warn.alert = True
                warn.label(text="FFmpeg not found", icon='ERROR')
                warn.label(text="Playblast Plus needs this to convert to mp4")
                warn.separator(factor=0.3)
                warn.operator("playblastplus.install_ffmpeg", icon='IMPORT')
                return
        else:  # APNG
            if not find_apngasm():
                warn = layout.box().column(align=True)
                warn.alert = True
                warn.label(text="apngasm not found", icon='ERROR')
                warn.label(text="Place apngasm.exe in the add-on bin/ folder")
                return
            info = layout.box().column(align=True)
            info.alert = True
            info.label(text="APNG conversion can take some time at higher resolutions", icon='INFO')

            # ── APNG Preset ────────────────────────────────────────────
            from .lib.apng_presets import get_preset
            pbox = layout.box()
            pcol = pbox.column(align=True)
            pcol.label(text="Preset", icon='PRESET')
            pcol.prop(prefs, "apng_preset", text="")
            preset_data = get_preset(prefs.apng_preset)
            if preset_data:
                info_row = pcol.row(align=True)
                info_row.enabled = False
                info_row.label(
                    text=f"Resolution:  {preset_data['width']} \u00d7 {preset_data['height']}  @  {preset_data.get('framerate', '?')} fps"
                )
            pcol.operator("playblastplus.apply_apng_preset", icon='SCENE_DATA')

        # ── Camera ──────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Camera", icon='CAMERA_DATA')
        col.prop(props, "camera", text="")

        # ── Output name ─────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Output Name", icon='FILE_TEXT')
        row = col.row(align=True)
        row.prop(props, "output_token", text="")
        row.menu("PLAYBLASTPLUS_MT_token_menu", text="", icon='ADD')

        # ── Shading (icon-only) ──────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Shading", icon='SHADING_SOLID')
        row = col.row(align=True)
        row.prop_enum(props, "shading_mode", 'WIREFRAME', text="Wire",     icon='SHADING_WIRE')
        row.prop_enum(props, "shading_mode", 'SOLID',     text="Solid",    icon='SHADING_SOLID')
        row.prop_enum(props, "shading_mode", 'MATERIAL',  text="Material", icon='SHADING_TEXTURE')
        row.prop_enum(props, "shading_mode", 'RENDERED',  text="Render",   icon='SHADING_RENDERED')

        # ── Options (3 rows × 2 cols) ────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Overrides", icon='OVERLAY')

        grid = col.column(align=True)

        # Row 1: overlay mode
        row = grid.row(align=True)
        row.prop_enum(props, "overlay_mode", 'ON',  text="Overlays On")
        row.prop_enum(props, "overlay_mode", 'OFF', text="Overlays Off")

        # Row 2: bg only | wireframe
        row = grid.row(align=True)
        row.prop_enum(props, "overlay_mode", 'BACKGROUND', text="Bg Only")
        row.prop(props, "show_wireframe_overlay", toggle=True)

        # Row 3: cavity | outline — only shown in SOLID shading
        if props.shading_mode == 'SOLID':
            row = grid.row(align=True)
            row.prop(props, "show_cavity",  toggle=True)
            row.prop(props, "show_outline", toggle=True)

        # ── Output ───────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Output", icon='OUTPUT')
        row = col.row(align=True)
        row.prop(props, "half_res", toggle=True)
        if prefs.output_format == 'MP4':
            row.prop(props, "add_burnin", toggle=True)
        row = col.row(align=True)
        row.operator("playblastplus.open_output", text="Open Folder", icon='FILE_FOLDER')
        row.operator("playblastplus.open_last",   text="Open Last",   icon='FILE_MOVIE')

        # ── Capture ──────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Capture", icon='CAMERA_DATA')
        row = col.row(align=True)
        row.scale_y = 2.0
        if prefs.output_format == 'APNG':            
            row.alert = True
            row.operator("playblastplus.run", text="Create APNG", icon='RENDER_ANIMATION')
            row.alert = False        
        else:
            row.operator("playblastplus.run", text="Playblast", icon='RENDER_ANIMATION')

        row.operator("playblastplus.snapshot", text="Snap",      icon='IMAGE')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_CLASSES = [
    PLAYBLASTPLUS_MT_token_menu,
    VIEW3D_MT_playblastplus,
    PLAYBLASTPLUS_PT_main,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_HT_header.append(_menu_func_view3d)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(_menu_func_view3d)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


