"""
Manual terminal test for the AYON creator probe subprocess.

Run this from a terminal that has the AYON environment active
(i.e. launched from the AYON tray, or with env vars set manually):

    python test_ayon_probe.py

It simulates exactly what the Blender operator does:
  1. Resolves AYON_EXECUTABLE and AYON_PROJECT_NAME from the environment.
  2. Runs ayon_probe_creators.py as a subprocess with the same command.
  3. Prints stdout/stderr and the resulting JSON.

You can also override via CLI:
    python test_ayon_probe.py --exe "C:/path/to/ayon_console.exe" --project myproject
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Test ayon_probe_creators.py subprocess.")
    parser.add_argument("--exe",     default=None, help="Override AYON_EXECUTABLE path.")
    parser.add_argument("--project", default=None, help="Override AYON_PROJECT_NAME.")
    args = parser.parse_args()

    ayon_exe = args.exe or os.environ.get("AYON_EXECUTABLE", "")
    project_name = args.project or os.environ.get("AYON_PROJECT_NAME", "")

    # Simulate what the AYON launcher does: inject context into the environment
    # so the probe subprocess inherits it via os.environ.
    if project_name:
        os.environ["AYON_PROJECT_NAME"] = project_name
    if args.exe:
        os.environ["AYON_EXECUTABLE"] = args.exe

    print("=" * 60)
    print("PlayblastPlus — AYON probe test")
    print("=" * 60)
    print(f"AYON_EXECUTABLE   : {ayon_exe or '(not set)'}")
    print(f"AYON_PROJECT_NAME : {project_name or '(not set)'}")
    print(f"AYON_FOLDER_PATH  : {os.environ.get('AYON_FOLDER_PATH', '(not set)')}")
    print(f"AYON_TASK_NAME    : {os.environ.get('AYON_TASK_NAME', '(not set)')}")
    print()

    if not ayon_exe:
        print("ERROR: AYON_EXECUTABLE is not set.")
        print("       Either set the env var or pass --exe path/to/ayon_console.exe")
        sys.exit(1)
    if not Path(ayon_exe).is_file():
        print(f"ERROR: AYON_EXECUTABLE path does not exist: {ayon_exe}")
        sys.exit(1)
    if not project_name:
        print("ERROR: AYON_PROJECT_NAME is not set.")
        print("       Either set the env var or pass --project myproject")
        sys.exit(1)

    script_path = Path(__file__).parent / "lib" / "ayon_probe_creators.py"
    if not script_path.is_file():
        print(f"ERROR: probe script not found: {script_path}")
        sys.exit(1)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, prefix="pbp_probe_test_") as fh:
        output_path = fh.name

    cmd = [ayon_exe, "run", str(script_path), "--", "--output", output_path]

    print(f"Command: {' '.join(cmd)}")
    print(f"Output : {output_path}")
    print()
    print("--- subprocess output ---")

    result = subprocess.run(cmd, capture_output=False, text=True, timeout=60)

    print("--- end subprocess output ---")
    print()
    print(f"Exit code: {result.returncode}")
    print()

    if result.returncode != 0:
        print("FAILED — probe exited with non-zero code.")
        sys.exit(result.returncode)

    try:
        with open(output_path, "r", encoding="utf-8") as fh:
            creators = json.load(fh)
        print(f"Creators found: {len(creators)}")
        for c in creators:
            print(f"  [{c['id']}]  label={c['label']}  family={c['family']}")
    except Exception as e:
        print(f"ERROR reading output JSON: {e}")
        sys.exit(1)
    finally:
        Path(output_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
