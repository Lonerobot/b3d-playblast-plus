"""FFmpeg encode helpers — standalone, no external dependencies.

The ffmpeg executable path is always passed in explicitly so this module has
zero dependency on the parent playblast_plus package or its settings.
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path


def _shell_quote(path: str) -> str:
    """Return a safely shell-quoted path for use in a ``shell=True`` command.

    On POSIX, :func:`shlex.quote` is used so that spaces and shell
    metacharacters in the path cannot be interpreted by the shell.

    On Windows, the path is wrapped in double-quotes after stripping any
    embedded double-quote characters.  Double-quotes are not legal in Windows
    file or directory names and cannot appear in user-supplied paths through
    normal means.

    Args:
        path (str): Filesystem path to quote.

    Returns:
        str: Shell-safe quoted path string.
    """
    if sys.platform == "win32":
        return '"' + path.replace('"', '') + '"'
    return shlex.quote(path)


# Default encode settings — can be overridden per call
DEFAULT_INPUT_ARGS = "-c:v libx264 -crf 21 -preset ultrafast -pix_fmt yuv420p"


def open_media_file(filepath: str) -> None:
    """Open *filepath* in the OS default viewer.

    Args:
        filepath (str): Path to a video or image file.
    """
    path = Path(filepath)
    if not path.is_file():
        print(f"[PlayblastPlus] open_media_file: file not found: {filepath}")
        return

    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def mp4_from_image_sequence(
    ffmpeg_path: str,
    image_seq_path: str,
    output_path: str,
    framerate: int = 24,
    start_frame: int = 0,
    end_frame: int = 0,
    audio_path: str = None,
    post_open: bool = False,
    add_burnin: bool = False,
    burnin_text: str = "",
    burnin_font_size: int = 24,
    input_args: str = DEFAULT_INPUT_ARGS,
) -> bool:
    """Encode a PNG image sequence to MP4 using FFmpeg.

    Args:
        ffmpeg_path (str): Absolute path to the ffmpeg executable.
        image_seq_path (str): ffmpeg-style input path, e.g.
                              ``/tmp/shot_%04d.png``.
        output_path (str): Destination MP4 path.
        framerate (int): Output frame rate.
        start_frame (int): First frame number in the sequence.
        end_frame (int): Total number of frames to encode.
        audio_path (str): Optional path to an audio file to mux in.
        post_open (bool): Open the output file after encoding.
        add_burnin (bool): Draw a timecode / name burnin overlay.
        burnin_text (str): Text to render in the burnin.
        burnin_font_size (int): Font size for the burnin.
        input_args (str): FFmpeg video codec arguments string.

    Returns:
        bool: True if the output file was created.
    """
    if not ffmpeg_path or not Path(ffmpeg_path).is_file():
        print(f"[PlayblastPlus] ffmpeg not found at: {ffmpeg_path!r}")
        return False

    burnin = ""
    if add_burnin:
        burnin = (
            f'-vf "drawtext=font=Consolas: fontsize={burnin_font_size}: '
            f"fontcolor=white@0.5: text='{burnin_text} | %{{eif\\:n\\:d\\:4}}': "
            f"start_number={start_frame}: r=24: x=(w-tw-20): y=h-lh-20: "
            f'box=1: boxcolor=black@0.5: boxborderw=2"'
        )

    audio_input = f' -i {_shell_quote(audio_path)} ' if audio_path else ""
    audio_params = (
        ' -c:a aac -filter_complex "[1:0] apad" -shortest '
        if audio_path
        else ""
    )

    cmd = (
        f'{_shell_quote(ffmpeg_path)} '
        f"-framerate {framerate} "
        f"-y "
        f"-start_number {start_frame} "
        f"-loglevel quiet "
        f'-i {_shell_quote(image_seq_path)} '
        f"{burnin} "
        f"{audio_input}"
        f"{input_args} "
        f"{audio_params}"
        f"-frames:v {end_frame} "
        f'{_shell_quote(output_path)}'
    )

    print(f"[PlayblastPlus] encode: {cmd}")
    subprocess.call(cmd, shell=True)

    output = Path(output_path)
    if output.is_file():
        if post_open:
            open_media_file(output_path)
        return True

    print(f"[PlayblastPlus] encode failed — output not found: {output_path}")
    return False


def apng_from_image_sequence(
    apngasm_path: str,
    frame_files: list,
    output_path: str,
    framerate: int = 24,
    loop: int = 0,
    post_open: bool = False,
    timeout: int = 300,
) -> bool:
    """Assemble a sorted PNG frame list into an Animated PNG using apngasm.

    Args:
        apngasm_path (str): Absolute path to the apngasm executable.
        frame_files (list[str]): Sorted list of absolute PNG frame paths.
        output_path (str): Destination .png path for the APNG.
        framerate (int): Frame rate — used to derive per-frame delay as 1/framerate.
        loop (int): Loop count. 0 = infinite.
        post_open (bool): Open the output file after assembly.

    Returns:
        bool: True if the output file was created.
    """
    if not apngasm_path or not Path(apngasm_path).is_file():
        print(f"[PlayblastPlus] apngasm not found at: {apngasm_path!r}")
        return False

    if not frame_files:
        print("[PlayblastPlus] apng_from_image_sequence: no frame files provided")
        return False

    rate = max(int(round(framerate)), 1)
    cmd = (
        [apngasm_path, output_path]
        + frame_files
        + ["1", str(rate), f"-l{loop}"]
    )

    print(f"[PlayblastPlus] apng encode: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        e.process.kill()
        print(f"[PlayblastPlus] apng encode timed out after {timeout}s — increase 'APNG Encode Timeout' in add-on preferences")
        return False

    output = Path(output_path)
    if output.is_file():
        if post_open:
            open_media_file(output_path)
        return True

    print(f"[PlayblastPlus] apng encode failed — output not found: {output_path}")
    return False
