from pathlib import Path

import bpy
from bpy.types import Operator

from .lib.blender_scene import Blender_Scene
from .lib.blender_preview import BlenderPreview
from .lib import encode, tokens, utils
from .lib.ffmpeg_utils import dl_state, find_apngasm, find_ffmpeg, start_install


def _ffmpeg_path(context) -> str | None:
    """Return the ffmpeg executable path using the 3-step discovery order."""
    prefs = context.preferences.addons[__package__].preferences
    return find_ffmpeg(prefs.ffmpeg_path)


# ---------------------------------------------------------------------------
# Main viewport render
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_run(Operator):
    """Render the active viewport frame range and encode to MP4"""
    bl_idname = "playblastplus.run"
    bl_label = "Viewport Render"
    bl_description = "Capture the viewport frame range and encode to MP4"

    def execute(self, context):
        props = context.scene.playblast_plus
        prefs = context.preferences.addons[__package__].preferences

        ffmpeg = None
        if prefs.output_format != 'APNG':
            ffmpeg = _ffmpeg_path(context)
            if not ffmpeg:
                self.report(
                    {'ERROR'},
                    "FFmpeg not found. Set a path in Preferences → Add-ons → Playblast Plus "
                    "or use Install FFmpeg.",
                )
                return {'CANCELLED'}

        # ------------------------------------------------------------------
        # Paths
        # ------------------------------------------------------------------
        output_dir = Blender_Scene.get_output_dir()
        temp_dir   = Blender_Scene.get_temp_capture_dir()
        output_name = tokens.format_tokens(props.output_token, None) or "playblast"

        # ------------------------------------------------------------------
        # Capture
        # ------------------------------------------------------------------
        renderer = BlenderPreview()
        renderer.pre_process()
        renderer.set_override_properties(
            camera=props.camera,
            shading_mode=props.shading_mode,
            overlay_mode=props.overlay_mode,
            show_wireframe_overlay=props.show_wireframe_overlay,
            show_cavity=props.show_cavity,
            show_outline=props.show_outline,
            half_res=props.half_res,
        )

        # Apply transparency override for APNG if requested
        _orig_film_transparent = context.scene.render.film_transparent
        if prefs.output_format == 'APNG' and prefs.apng_transparent:
            context.scene.render.film_transparent = True
            context.scene.render.image_settings.color_mode = 'RGBA'

        ffmpeg_input = renderer.create(filename=str(Path(temp_dir) / output_name))
        renderer.post_process()
        context.scene.render.film_transparent = _orig_film_transparent

        if not ffmpeg_input:
            self.report({'ERROR'}, "PlayblastPlus: capture produced no frames.")
            return {'CANCELLED'}

        # ------------------------------------------------------------------
        # Encode
        # ------------------------------------------------------------------
        framerate   = Blender_Scene.getFrameRate()
        frame_start, frame_end = Blender_Scene.getFrameRange()
        frame_count = int(frame_end - frame_start + 1)

        if prefs.output_format == 'APNG':
            apngasm = find_apngasm()
            if not apngasm:
                self.report({'ERROR'}, "PlayblastPlus: apngasm not found.")
                return {'CANCELLED'}
            output_path = str(Path(output_dir) / f"{output_name}.png")
            frame_files = sorted(
                f for f in Path(temp_dir).iterdir()
                if f.suffix == '.png' and f.name.startswith(output_name + '.')
            )
            print(
                f"[PlayblastPlus] APNG encode: {len(frame_files)} frames "
                f"@ {int(round(framerate))} fps → {output_path}"
            )
            import time as _time
            _t_encode = _time.monotonic()
            ok = encode.apng_from_image_sequence(
                apngasm_path=apngasm,
                frame_files=[str(f) for f in frame_files],
                output_path=output_path,
                framerate=int(round(framerate)),
                post_open=not (prefs.apng_tinify and prefs.apng_tinify_key),
                timeout=prefs.apng_timeout,
            )
            if not ok and not Path(output_path).is_file():
                self.report({'ERROR'}, "PlayblastPlus: APNG encode timed out. Increase 'APNG Encode Timeout' in add-on preferences.")
            if ok:
                _encode_secs = _time.monotonic() - _t_encode
                _apng_mb = Path(output_path).stat().st_size / (1024 * 1024)
                print(
                    f"[PlayblastPlus] APNG encode done in {_encode_secs:.1f}s  "
                    f"— output size: {_apng_mb:.2f} MB"
                )
            if ok and prefs.apng_tinify:
                if not prefs.apng_tinify_key:
                    print("[PlayblastPlus] Tinify: skipped — API key not set")
                    self.report({'WARNING'}, "PlayblastPlus: Tinify key is not set in preferences")
                else:
                    from .lib.tinify_client import compress_file
                    print(f"[PlayblastPlus] Tinify: uploading {_apng_mb:.2f} MB to api.tinify.com…")
                    tinify_ok, tinify_info = compress_file(prefs.apng_tinify_key, output_path, output_path)
                    if tinify_ok:
                        print(
                            f"[PlayblastPlus] Tinify: \u2713 compressed in {tinify_info['elapsed_s']:.1f}s  "
                            f"{tinify_info['size_before_mb']:.2f} MB \u2192 {tinify_info['size_after_mb']:.2f} MB  "
                            f"({tinify_info['saved_pct']:.1f}% saved)  "
                            f"[{tinify_info['compressions_this_month']} compressions this month]"
                        )
                    else:
                        print(f"[PlayblastPlus] Tinify: \u2717 {tinify_info['message']}")
                        self.report({'WARNING'}, f"PlayblastPlus: Tinify failed — {tinify_info['message']}")
                    if tinify_ok:
                        import bpy as _bpy
                        _bpy.ops.wm.path_open(filepath=output_path)
        else:
            output_path = str(Path(output_dir) / f"{output_name}.mp4")
            ok = encode.mp4_from_image_sequence(
                ffmpeg_path=ffmpeg,
                image_seq_path=ffmpeg_input,
                output_path=output_path,
                framerate=framerate,
                start_frame=int(frame_start),
                end_frame=frame_count,
                add_burnin=props.add_burnin,
                burnin_text=output_name,
                post_open=True,
                input_args=prefs.encode_args,
            )

        if not ok:
            self.report({'ERROR'}, "PlayblastPlus: encode failed.")
            return {'CANCELLED'}

        props.last_playblast = output_path
        props.last_output_dir = output_dir
        props.last_temp_dir = temp_dir

        # ------------------------------------------------------------------
        # Frame cleanup
        # ------------------------------------------------------------------
        if prefs.keep_images:
            frames_dir = Path(output_dir) / 'frames' / output_name
            frames_dir.mkdir(parents=True, exist_ok=True)
            moved = 0
            for f in Path(temp_dir).iterdir():
                if f.suffix == '.png' and f.name.startswith(output_name + '.'):
                    f.replace(frames_dir / f.name)
                    moved += 1
            self.report(
                {'INFO'},
                f"PlayblastPlus: saved \u2192 {output_path}  |  {moved} frames \u2192 {frames_dir}",
            )
        else:
            utils.FolderOps.purge_contents(temp_dir, ext='.png')
            self.report({'INFO'}, f"PlayblastPlus: saved → {output_path}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_snapshot(Operator):
    """Capture a single frame from the active viewport"""
    bl_idname = "playblastplus.snapshot"
    bl_label = "Snap"
    bl_description = "Capture a single viewport frame as PNG"

    def execute(self, context):
        props = context.scene.playblast_plus

        output_dir  = Blender_Scene.get_output_dir()
        captures_dir = Path(output_dir) / 'captures'
        captures_dir.mkdir(exist_ok=True)

        output_name = tokens.format_tokens(props.output_token, None) or "playblast"
        frame_str   = str(Blender_Scene.current_frame()).zfill(4)

        renderer = BlenderPreview()
        renderer.pre_process()
        renderer.set_override_properties(
            shading_mode=props.shading_mode,
            overlay_mode=props.overlay_mode,
            show_wireframe_overlay=props.show_wireframe_overlay,
            show_cavity=props.show_cavity,
            show_outline=props.show_outline,
        )

        snap_path = renderer.snapshot(
            filename=str(captures_dir / f'{output_name}_{frame_str}')
        )
        renderer.post_process()

        props.last_playblast = snap_path or ""
        self.report({'INFO'}, f"PlayblastPlus: snapshot → {snap_path}")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Token helper
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_insert_token(Operator):
    """Append a token to the output name field"""
    bl_idname = "playblastplus.insert_token"
    bl_label = "Insert Token"
    bl_description = "Append this token to the Output Name field"

    token: bpy.props.StringProperty(name="Token")

    def execute(self, context):
        props = context.scene.playblast_plus
        props.output_token = props.output_token + self.token
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

class PLAYBLASTPLUS_OT_open_output(Operator):
    """Open the playblast output folder in the system file explorer"""
    bl_idname = "playblastplus.open_output"
    bl_label = "Open Output Folder"
    bl_description = "Open the output folder in the system file explorer"

    def execute(self, context):
        utils.FolderOps.explore(Blender_Scene.get_output_dir())
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_open_last(Operator):
    """Open the most recently created playblast in the system viewer"""
    bl_idname = "playblastplus.open_last"
    bl_label = "Open Last"
    bl_description = "Open the most recently created playblast file"

    def execute(self, context):
        last = context.scene.playblast_plus.last_playblast
        if last and Path(last).is_file():
            encode.open_media_file(last)
        else:
            self.report({'WARNING'}, "PlayblastPlus: no playblast file found.")
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_apply_apng_preset(Operator):
    """Apply the selected APNG preset to the scene resolution and frame rate"""
    bl_idname = "playblastplus.apply_apng_preset"
    bl_label = "Apply to Scene"
    bl_description = "Set scene resolution and frame rate to match the selected APNG preset"

    def execute(self, context):
        from .lib.apng_presets import get_preset
        prefs = context.preferences.addons[__package__].preferences
        preset = get_preset(prefs.apng_preset)
        if not preset:
            self.report({'WARNING'}, "PlayblastPlus: preset not found.")
            return {'CANCELLED'}

        render = context.scene.render
        render.resolution_x = preset["width"]
        render.resolution_y = preset["height"]
        render.resolution_percentage = 100
        context.scene.render.fps = preset.get("framerate", 24)

        label = preset.get("label", preset["name"])
        w, h, fps = preset["width"], preset["height"], preset.get("framerate", 24)
        self.report({'INFO'}, f"PlayblastPlus: applied '{label}' — {w}×{h} @ {fps} fps")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# FFmpeg installer (modal — download runs in a background thread)
# ---------------------------------------------------------------------------

def _redraw_areas() -> float | None:
    """Timer callback: tag VIEW_3D and PREFERENCES areas for redraw while install runs."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in ('VIEW_3D', 'PREFERENCES'):
                    area.tag_redraw()
    except Exception:
        pass
    return 0.1 if dl_state["running"] else None


class PLAYBLASTPLUS_OT_install_ffmpeg(Operator):
    """Download and install FFmpeg to the add-on's local bin/ folder"""
    bl_idname = "playblastplus.install_ffmpeg"
    bl_label = "Install FFmpeg"
    bl_description = "Download FFmpeg from the internet and install it to the add-on bin/ folder"

    def execute(self, context):
        if dl_state["running"]:
            self.report({'WARNING'}, "FFmpeg install already in progress.")
            return {'CANCELLED'}

        prefs = context.preferences.addons[__package__].preferences
        start_install(url=prefs.download_url)

        if not bpy.app.timers.is_registered(_redraw_areas):
            bpy.app.timers.register(_redraw_areas, first_interval=0.1)

        def _on_complete():
            if dl_state["running"]:
                return 0.25
            if dl_state["done"]:
                installed = find_ffmpeg()
                if installed:
                    try:
                        bpy.context.preferences.addons[__package__].preferences.ffmpeg_path = installed
                    except Exception:
                        pass
            return None

        bpy.app.timers.register(_on_complete, first_interval=0.25)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_CLASSES = [
    PLAYBLASTPLUS_OT_run,
    PLAYBLASTPLUS_OT_snapshot,
    PLAYBLASTPLUS_OT_insert_token,
    PLAYBLASTPLUS_OT_open_output,
    PLAYBLASTPLUS_OT_open_last,
    PLAYBLASTPLUS_OT_apply_apng_preset,
    PLAYBLASTPLUS_OT_install_ffmpeg,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
