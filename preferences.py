import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from .lib.ffmpeg_utils import default_download_url, find_ffmpeg
from .lib import apng_presets


class PlayblastPlusPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    ffmpeg_path: StringProperty(
        name="FFmpeg Path",
        description=(
            "Absolute path to the ffmpeg executable. "
            "Leave blank to use the system PATH or the add-on's local bin/ folder."
        ),
        default="",
        subtype='FILE_PATH',
    )

    default_output_token: StringProperty(
        name="Default Output Token",
        description="Default token string used for output filenames",
        default="<scene>_<camera>",
    )

    encode_args: StringProperty(
        name="Encode Arguments",
        description="FFmpeg video codec arguments inserted between input and output",
        default="-c:v libx264 -crf 21 -preset ultrafast -pix_fmt yuv420p",
    )

    keep_images: BoolProperty(
        name="Keep Intermediate Images",
        description="Keep the raw PNG frame sequence after encoding to MP4",
        default=False,
    )

    download_url: StringProperty(
        name="FFmpeg Download URL",
        description="URL to download FFmpeg from. Defaults to gyan.dev essentials (Windows), BtbN (Linux), evermeet.cx (macOS)",
        default="",
    )

    output_format: EnumProperty(
        name="Output Format",
        description="Output format for the encoded playblast",
        items=[
            ('MP4',  "MP4",             "Encode to H.264 MP4 via FFmpeg (default)", 'FILE_MOVIE',  0),
            ('APNG', "APNG",            "Encode to Animated PNG via FFmpeg", 'IMAGE_DATA', 1),
        ],
        default='MP4',
    )

    apng_transparent: BoolProperty(
        name="Use Transparency",
        description=(
            "Capture frames with an alpha channel for transparent backgrounds. "
            "Automatically sets film_transparent on the scene during capture."
        ),
        default=True,
    )

    apng_tinify: BoolProperty(
        name="Optimise with Tinify",
        description="Upload the finished APNG to the Tinify API to reduce file size",
        default=False,
    )

    apng_tinify_key: StringProperty(
        name="Tinify API Key",
        description="Your Tinify API key (https://tinify.com)",
        default="",
        subtype='PASSWORD',
    )

    apng_timeout: IntProperty(
        name="APNG Encode Timeout",
        description="Maximum seconds to wait for APNG FFmpeg encoding to finish. Increase for long sequences at high resolution",
        default=300,
        min=30,
        soft_max=1800,
        subtype='TIME',
    )

    apng_preset: EnumProperty(
        name="APNG Preset",
        description="Preset resolution and frame rate. Apply to scene via the button in the panel",
        items=apng_presets.enum_items,
    )

    def draw(self, context):
        layout = self.layout

        # ── FFmpeg ────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="FFmpeg", icon='FILE_MOVIE')

        found = find_ffmpeg(self.ffmpeg_path)
        if found:
            row = col.row()
            row.label(text="Found:", icon='CHECKMARK')
            row.label(text=found)
        else:
            warn = col.row()
            warn.alert = True
            warn.label(text="FFmpeg not found", icon='ERROR')

        col.prop(self, "ffmpeg_path")
        col.separator(factor=0.3)
        sub = col.column(align=True)
        sub.scale_y = 0.75
        sub.label(text="Download URL (leave blank for platform default):")
        col.prop(self, "download_url", text="")
        if not self.download_url:
            hint = col.row()
            hint.enabled = False
            hint.label(text=default_download_url())
        col.separator(factor=0.5)
        col.operator("playblastplus.install_ffmpeg", icon='IMPORT')
        col.separator()
        col.prop(self, "encode_args")

        # ── Output ────────────────────────────────────────────────────
        box = layout.box()
        col = box.column(align=True)
        col.label(text="Output", icon='OUTPUT')
        col.prop(self, "default_output_token")
        col.prop(self, "keep_images")
        col.separator(factor=0.5)
        col.prop(self, "output_format")
        if self.output_format == 'APNG':
            box2 = box.box()
            col2 = box2.column(align=True)
            col2.label(text="APNG Options (Experimental)", icon='EXPERIMENTAL')                  
            col2.label(text="Increase this value if you get timeout errors in this mode")
            col2.prop(self, "apng_transparent")
            col2.prop(self, "apng_tinify")
            if self.apng_tinify:
                col2.label(text="Tinify compresses the APNG file using the Tinify API key")       
                col2.label(text="Register to get your free key and add it to the box below")      
                col2.label(text="https://tinify.com/developers", icon='URL') 
                col2.prop(self, "apng_tinify_key")
            col2.prop(self, "apng_timeout")


def register():
    bpy.utils.register_class(PlayblastPlusPreferences)


def unregister():
    bpy.utils.unregister_class(PlayblastPlusPreferences)
