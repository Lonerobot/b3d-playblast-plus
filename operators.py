import shutil
from pathlib import Path

import bpy
from bpy.types import Operator

from .lib.blender_scene import Blender_Scene
from .lib.blender_preview import BlenderPreview
from .lib import encode, tokens, utils
from .lib.ffmpeg_utils import dl_state, find_ffmpeg, start_install


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
            output_path = str(Path(output_dir) / f"{output_name}.apng")
            print(
                f"[PlayblastPlus] APNG encode: {ffmpeg_input} "
                f"@ {int(round(framerate))} fps → {output_path}"
            )
            import time as _time
            _t_encode = _time.monotonic()
            ok = encode.apng_from_image_sequence(
                ffmpeg_path=ffmpeg,
                image_seq_path=ffmpeg_input,
                output_path=output_path,
                framerate=framerate,
                start_frame=int(frame_start),
                end_frame=frame_count,
                post_open=not (prefs.apng_tinify and prefs.apng_tinify_key),
                timeout=prefs.apng_timeout,
            )
            if not ok and not Path(output_path).is_file():
                self.report({'ERROR'}, "PlayblastPlus: APNG encode failed or timed out. Increase 'APNG Encode Timeout' in add-on preferences if needed.")
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
                    shutil.move(str(f), str(frames_dir / f.name))
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


# Module-level registry of active publish processes so the timer can reference them.
_ayon_publish_procs: list = []

# Last publish result — shown in the panel until the next publish starts.
# Keys: "label" (str), "success" (bool), "log_path" (str)
_ayon_last_publish_result: dict = {}

# Cache of (identifier, label) tuples fetched from traypublisher inside Blender.
# Populated by PLAYBLASTPLUS_OT_refresh_ayon_creators.
_ayon_creator_cache: list = []  # list of dicts: {"id": str, "label": str, "family": str}


class PLAYBLASTPLUS_OT_refresh_ayon_creators(Operator):
    """Query AYON traypublisher inside Blender to list available review creators"""
    bl_idname = "playblastplus.refresh_ayon_creators"
    bl_label = "Refresh Creators"
    bl_description = "Fetch available AYON publish creators from the traypublisher addon"

    def execute(self, context):
        import os as _os

        project_name = _os.getenv("AYON_PROJECT_NAME", "")
        if not project_name:
            self.report({'ERROR'}, "PlayblastPlus: AYON_PROJECT_NAME is not set.")
            return {'CANCELLED'}

        try:
            from ayon_core.pipeline import install_host
            from ayon_core.pipeline.create import CreateContext
            from ayon_traypublisher.api import TrayPublisherHost
        except ImportError as e:
            self.report({'ERROR'}, f"PlayblastPlus: Could not import AYON modules: {e}")
            return {'CANCELLED'}

        try:
            host = TrayPublisherHost()
            host.set_project_name(project_name)
            install_host(host)
            create_context = CreateContext(host, headless=True)
        except Exception as e:
            self.report({'ERROR'}, f"PlayblastPlus: Failed to initialise AYON create context: {e}")
            return {'CANCELLED'}

        # Only the three settings-based creators that TrayPublisher exposes for
        # playblast publishing. Derive a human-readable label by stripping the
        # "settings_" prefix and capitalising: settings_review → "Review".
        _VALID_IDS = {"settings_review", "settings_render", "settings_image"}
        _ayon_creator_cache.clear()
        for cid, creator in create_context.creators.items():
            if cid not in _VALID_IDS:
                continue
            product_type = cid[len("settings_"):]
            label = product_type.capitalize()
            _ayon_creator_cache.append({"id": cid, "label": label, "family": product_type})

        _ayon_creator_cache.sort(key=lambda x: x["label"])

        # If the scene's current creator_id is no longer valid, reset to first entry.
        props = context.scene.playblast_plus
        known_ids = {c["id"] for c in _ayon_creator_cache}
        if props.ayon_creator_id not in known_ids and _ayon_creator_cache:
            props.ayon_creator_id = _ayon_creator_cache[0]["id"]

        self.report(
            {'INFO'},
            f"PlayblastPlus: found {len(_ayon_creator_cache)} AYON creators.",
        )
        return {'FINISHED'}


class PLAYBLASTPLUS_OT_set_ayon_creator(bpy.types.Operator):
    """Select this AYON creator for the review publish"""
    bl_idname = "playblastplus.set_ayon_creator"
    bl_label = "Select Creator"
    bl_description = "Use this AYON creator for the publish"

    creator_id: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.playblast_plus.ayon_creator_id = self.creator_id
        return {'FINISHED'}


def _ayon_publish_poll() -> float | None:
    """Timer callback: poll active AYON publish subprocesses and log their output."""
    import sys as _sys

    def _redraw_all():
        try:
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        except Exception:
            pass

    still_running = []
    for entry in _ayon_publish_procs:
        proc   = entry["proc"]
        log_fh = entry["log_fh"]
        label  = entry["label"]

        ret = proc.poll()
        if ret is None:
            still_running.append(entry)
        else:
            # Drain any remaining output
            try:
                remainder = proc.stdout.read()
                if remainder:
                    log_fh.write(remainder)
            except Exception:
                pass
            log_fh.flush()
            log_fh.close()
            log_path = entry["log_path"]
            if ret == 0:
                print(f"[PlayblastPlus] AYON publish succeeded: {label}  log → {log_path}")
                _ayon_last_publish_result.update(
                    {"label": label, "success": True, "log_path": log_path}
                )
                try:
                    _lbl, _lp = label, log_path
                    def _popup_ok(self, context, _l=_lbl, _lp=_lp):
                        col = self.layout.column(align=True)
                        col.label(text=f"'{_l}' published successfully.", icon='CHECKMARK')
                        col.separator(factor=0.3)
                        col.label(text=_lp, icon='FILE_TEXT')
                    bpy.context.window_manager.popup_menu(
                        _popup_ok, title="AYON Publish Complete", icon='INFO'
                    )
                except Exception:
                    pass
            else:
                print(
                    f"[PlayblastPlus] AYON publish FAILED (exit {ret}): {label}\n"
                    f"  See log: {log_path}"
                )
                _ayon_last_publish_result.update(
                    {"label": label, "success": False, "log_path": log_path}
                )
                # Print the last 40 lines of the log to the Blender console
                try:
                    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                    tail = lines[-40:] if len(lines) > 40 else lines
                    print("[PlayblastPlus] --- publish log tail ---")
                    print("".join(tail))
                    print("[PlayblastPlus] --- end log ---")
                except Exception as e:
                    print(f"[PlayblastPlus] Could not read log: {e}")
                try:
                    _lbl, _lp = label, log_path
                    def _popup_err(self, context, _l=_lbl, _lp=_lp):
                        col = self.layout.column(align=True)
                        col.label(text=f"Publish FAILED for '{_l}'.", icon='ERROR')
                        col.separator(factor=0.3)
                        col.label(text="See log for details:", icon='FILE_TEXT')
                        col.label(text=_lp)
                    bpy.context.window_manager.popup_menu(
                        _popup_err, title="AYON Publish Failed", icon='ERROR'
                    )
                except Exception:
                    pass
            _redraw_all()

    _ayon_publish_procs[:] = still_running
    # Redraw on every tick while publishing so the "Publishing…" indicator updates
    if still_running:
        _redraw_all()
        return 1.0
    return None


class PLAYBLASTPLUS_OT_ayon_publish(Operator):
    """Publish the last playblast to AYON via TrayPublisher"""
    bl_idname = "playblastplus.ayon_publish"
    bl_label = "Publish to AYON"
    bl_description = "Send the last rendered playblast to AYON for review"

    def execute(self, context):
        import os as _os
        import sys as _sys
        import subprocess
        import tempfile
        import datetime
        from pathlib import Path as _Path

        props = context.scene.playblast_plus

        # ── AYON executable ───────────────────────────────────────────────
        ayon_exe = _os.getenv("AYON_EXECUTABLE", "")
        if not ayon_exe:
            self.report(
                {'ERROR'},
                "PlayblastPlus: AYON_EXECUTABLE is not set. "
                "Launch Blender from the AYON launcher.",
            )
            return {'CANCELLED'}
        if not _Path(ayon_exe).is_file():
            self.report(
                {'ERROR'},
                f"PlayblastPlus: AYON_EXECUTABLE path does not exist: {ayon_exe}",
            )
            return {'CANCELLED'}

        # ── AYON context — read from Blender's own env vars ───────────────
        project_name = _os.getenv("AYON_PROJECT_NAME", "")
        folder_path  = _os.getenv("AYON_FOLDER_PATH", "")
        task_name    = _os.getenv("AYON_TASK_NAME", "")

        missing = []
        if not project_name: missing.append("AYON_PROJECT_NAME")
        if not folder_path:  missing.append("AYON_FOLDER_PATH")
        if not task_name:    missing.append("AYON_TASK_NAME")
        if missing:
            self.report(
                {'ERROR'},
                f"PlayblastPlus: Missing AYON context variables: {', '.join(missing)}. "
                "Launch Blender from the AYON launcher with a task context active.",
            )
            return {'CANCELLED'}

        # ── Variant & creator ─────────────────────────────────────────────
        variant = props.ayon_variant.strip()
        if not variant:
            self.report({'ERROR'}, "PlayblastPlus: AYON variant cannot be empty.")
            return {'CANCELLED'}

        creator_id = props.ayon_creator_id.strip()
        if not creator_id:
            self.report({'ERROR'}, "PlayblastPlus: No AYON creator selected — use 'Refresh Creators'.")
            return {'CANCELLED'}

        # ── Last playblast ────────────────────────────────────────────────
        last = props.last_playblast
        if not last:
            self.report(
                {'ERROR'},
                "PlayblastPlus: No playblast path recorded — run a playblast first.",
            )
            return {'CANCELLED'}
        if not _Path(last).is_file():
            self.report(
                {'ERROR'},
                f"PlayblastPlus: Playblast file not found on disk: {last}",
            )
            return {'CANCELLED'}

        # ── Publish script ────────────────────────────────────────────────
        script_path = _Path(__file__).parent / "lib" / "ayon_publish.py"
        if not script_path.is_file():
            self.report(
                {'ERROR'},
                f"PlayblastPlus: Publish script missing: {script_path}",
            )
            return {'CANCELLED'}

        # ── Log file ──────────────────────────────────────────────────────
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir  = _Path(tempfile.gettempdir()) / "playblast_plus_publish_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"ayon_publish_{ts}.log"
        log_fh   = open(log_path, "w", encoding="utf-8")
        log_fh.write(
            f"[PlayblastPlus] AYON publish started {ts}\n"
            f"  project : {project_name}\n"
            f"  folder  : {folder_path}\n"
            f"  task    : {task_name}\n"
            f"  variant : {variant}\n"
            f"  file    : {last}\n\n"
        )
        log_fh.flush()
        print(f"[PlayblastPlus] AYON publish log → {log_path}")

        # ── Launch — pass context explicitly so ayon_console inherits it ──
        cmd = [
            ayon_exe, "run", str(script_path),
            "--filepath",    last,
            "--variant",     variant,
            "--project",     project_name,
            "--folder-path", folder_path,
            "--task",        task_name,
            "--creator",     creator_id,
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            # No CREATE_NEW_CONSOLE — we capture stdout instead
        )

        _ayon_publish_procs.append({
            "proc":     proc,
            "log_fh":   log_fh,
            "log_path": str(log_path),
            "label":    _Path(last).name,
        })

        if not bpy.app.timers.is_registered(_ayon_publish_poll):
            bpy.app.timers.register(_ayon_publish_poll, first_interval=1.0)

        self.report(
            {'INFO'},
            f"PlayblastPlus: publishing '{_Path(last).name}' (variant: {variant}) — "
            f"log → {log_path}",
        )
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
    PLAYBLASTPLUS_OT_refresh_ayon_creators,
    PLAYBLASTPLUS_OT_set_ayon_creator,
    PLAYBLASTPLUS_OT_ayon_publish,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
