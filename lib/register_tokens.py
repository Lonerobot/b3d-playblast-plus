"""Register Blender-specific tokens with the bundled token system.

This module is kept for backwards compatibility. Tokens are also registered
directly in __init__.py when the extension loads.
"""
import os

from . import tokens
from .blender_scene import Blender_Scene


tokens.register_token(
    "<camera>",
    lambda options: Blender_Scene.get_current_camera() or "camera",
    label="Camera name",
)

tokens.register_token(
    "<scene>",
    lambda options: Blender_Scene.get_name() or "playblast",
    label="Current scene name",
)

tokens.register_token(
    "<blendfile>",
    lambda options: Blender_Scene.get_name() or "playblast",
    label="Blend file name without extension",
)

tokens.register_token(
    "<viewlayer>",
    lambda options: __import__('bpy').context.view_layer.name,
    label="Active view layer",
)

# ── AYON tokens — only registered when running inside an AYON pipeline ──────
if os.getenv("AYON_PROJECT_NAME") and os.getenv("AYON_WORKDIR"):
    tokens.register_token(
        "<ayon_project>",
        lambda options: os.getenv("AYON_PROJECT_NAME", ""),
        label="AYON project name",
    )
    tokens.register_token(
        "<ayon_workdir>",
        lambda options: os.getenv("AYON_WORKDIR", ""),
        label="AYON working directory",
    )
    tokens.register_token(
        "<ayon_asset>",
        lambda options: os.getenv("AYON_FOLDER_PATH", os.getenv("AYON_ASSET", "")),
        label="AYON asset / folder path",
    )
    tokens.register_token(
        "<ayon_task>",
        lambda options: os.getenv("AYON_TASK_NAME", ""),
        label="AYON task name",
    )
