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
        from .lib.ffmpeg_utils import dl_state, find_ffmpeg

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
            warn.label(text="Playblast Plus needs this to convert to mp4/APNG")
            warn.separator(factor=0.3)
            warn.operator("playblastplus.install_ffmpeg", icon='IMPORT')
            return

        if prefs.output_format == 'APNG':
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

        # ── AYON Publish (only shown when running inside AYON) ────────────
        if os.getenv("AYON_PROJECT_NAME"):
            layout.separator(factor=0.5)
            ayon_box = layout.box()
            ayon_col = ayon_box.column(align=True)

            # Section header
            header_row = ayon_col.row(align=True)
            ayon_icon = get_icon_id("ayon")
            header_row.label(text="Publish to AYON", **ayon_icon)

            ayon_col.separator(factor=0.5)

            # Context info
            folder_path = os.getenv("AYON_FOLDER_PATH", "—")
            task_name   = os.getenv("AYON_TASK_NAME",   "—")
            ctx_col = ayon_col.column(align=True)
            ctx_col.scale_y = 0.8
            ctx_col.enabled = False
            ctx_col.label(text=f"Folder:  {folder_path}", icon='FILE_FOLDER')
            ctx_col.label(text=f"Task:    {task_name}",   icon='ARMATURE_DATA')

            ayon_col.separator(factor=0.5)

            # Last playblast path
            last = props.last_playblast
            has_last = bool(last and __import__('pathlib').Path(last).is_file())
            path_col = ayon_col.column(align=True)
            path_col.scale_y = 0.8
            if has_last:
                path_col.enabled = False
                path_col.label(
                    text=__import__('pathlib').Path(last).name,
                    icon='FILE_MOVIE',
                )
            else:
                path_col.alert = True
                path_col.label(text="No playblast yet — run one first", icon='ERROR')

            ayon_col.separator(factor=0.5)

            # Creator picker
            from .operators import _ayon_creator_cache
            creator_row = ayon_col.row(align=True)
            if _ayon_creator_cache:
                # Show a plain text field labelled with current selection's label
                current = next(
                    (c for c in _ayon_creator_cache if c["id"] == props.ayon_creator_id),
                    None,
                )
                display = current["label"] if current else props.ayon_creator_id
                creator_row.label(text=f"Creator:  {display}", icon='SHADERFX')
            else:
                creator_row.alert = True
                creator_row.label(text="No creators — press Refresh", icon='ERROR')
            ayon_col.operator(
                "playblastplus.refresh_ayon_creators",
                text="Refresh Creators",
                icon='FILE_REFRESH',
            )
            if _ayon_creator_cache:
                creator_box = ayon_col.box()
                creator_col = creator_box.column(align=True)
                for entry in _ayon_creator_cache:
                    row = creator_col.row(align=True)
                    is_selected = props.ayon_creator_id == entry["id"]
                    op = row.operator(
                        "playblastplus.set_ayon_creator",
                        text=entry["label"],
                        icon='CHECKMARK' if is_selected else 'LAYER_USED',
                        depress=is_selected,
                    )
                    op.creator_id = entry["id"]

            ayon_col.separator(factor=0.5)

            # Variant field
            ayon_col.prop(props, "ayon_variant", text="Variant")

            ayon_col.separator(factor=0.3)

            # Publish button
            pub_row = ayon_col.row(align=True)
            pub_row.scale_y = 1.6
            pub_row.enabled = has_last and bool(props.ayon_creator_id)
            pub_row.operator(
                "playblastplus.ayon_publish",
                text="Publish Review",
                **get_icon_id("ayon"),
            )


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


