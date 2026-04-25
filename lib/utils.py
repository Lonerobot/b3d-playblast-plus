"""Utility helpers bundled with the Blender extension.

Subset of playblast_plus.lib.utils — no Qt, no DCC dependencies.
"""

import re
import subprocess
import sys
from pathlib import Path


class Parsing:

    @staticmethod
    def create_ffmpeg_input(img_start: str) -> str:
        """Convert the path of the first frame in a numeric PNG sequence to an
        ffmpeg ``%0Nd`` pattern string.

        e.g. ``/tmp/shot_0001.png`` → ``/tmp/shot_%04d.png``

        Args:
            img_start (str): Path to the first frame of the sequence.

        Returns:
            str: ffmpeg-compatible input path, or None if no numeric run found.
        """
        if not img_start:
            return None
        img_start = Path(img_start)
        file_name = img_start.name
        # Anchor to end: match an optional leading minus and the frame-number
        # digits immediately before .png.  The minus is included in the capture
        # group so that the width of the %0Nd replacement mirrors the full field
        # width (sign + digits) that Blender and FFmpeg both use.
        m = re.search(r"(-?\d+)\.png$", file_name, re.IGNORECASE)
        if m:
            frame_str = m.group(1)
            is_negative = frame_str.startswith('-')
            digits = frame_str.lstrip('-')
            # For negative frames Blender outputs e.g. shot.-0005.png (minus +
            # 4 zero-padded digits = 5 chars total).  printf/FFmpeg %05d for -5
            # also produces "-0005", so pad_len must include the sign character.
            pad_len = len(digits) + (1 if is_negative else 0)
            # Preserve the original extension case (.png, .PNG, etc.)
            ext = file_name[m.end(1):]
            ffmpeg_input = file_name[:m.start(1)] + f"%0{pad_len}d" + ext
            return str(img_start.parent / ffmpeg_input)
        return None


class FolderOps:

    @staticmethod
    def explore(dir: str) -> None:
        """Open *dir* in the OS file explorer."""
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{dir}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", dir])
        else:
            subprocess.Popen(["xdg-open", dir])

    @staticmethod
    def purge_contents(root: str, ext: str = ".*", skip_folder: str = "") -> None:
        """Delete files in *root* that match *ext*.

        Args:
            root (str): Directory to clean.
            ext (str): File extension to target, e.g. ``'.png'``. Defaults to
                       all files (``'.*'``).
            skip_folder (str): Name of an immediate subfolder to leave
                               untouched.
        """
        for f in Path(root).rglob(f"*{ext}"):
            try:
                if f.parent.name != skip_folder:
                    f.unlink()
            except OSError as e:
                print(f"[PlayblastPlus] error removing {f}: {e.strerror}")
