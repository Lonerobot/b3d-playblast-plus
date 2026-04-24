import subprocess
from pathlib import Path as _Path


def _load_env() -> dict:
    """Parse a simple KEY=VALUE .env file from the repo root."""
    env_file = _Path(__file__).parent / ".env"
    values = {}
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


_env = _load_env()

DEPLOY = _env.get("DEPLOY_PATH", "")
if not DEPLOY:
    raise EnvironmentError(
        "DEPLOY_PATH not set. Copy .env.example to .env and set DEPLOY_PATH."
    )

ADDON_NAME = "playblast_plus"
IGNORE = [
    ".git",
    ".github",
    "logs",
    "__pycache__",
    ".gitignore",
    "README.md",
    "_deploy.py",
    ".env",
    ".env.example",
    "tinify.key",
]


def bump_version(level="patch"):
    import re
    from pathlib import Path

    if level not in ("major", "minor", "patch", "skip"):
        raise ValueError(f"Invalid level: '{level}'. Must be 'major', 'minor', 'patch', or 'skip'.")

    root = Path(__file__).parent
    manifest_file = root / "blender_manifest.toml"

    if level == "skip":
        # Read and return current version from manifest without modifying anything
        if manifest_file.is_file():
            manifest = manifest_file.read_text(encoding="utf-8")
            m = re.search(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', manifest, re.MULTILINE)
            if m:
                return m.group(1)
        return None

    # --- bl_info in __init__.py ---
    init_file = root / "__init__.py"
    content = init_file.read_text(encoding="utf-8")

    match = re.search(r'"version":\s*\((\d+),\s*(\d+),\s*(\d+)\)', content)
    if not match:
        raise ValueError("Could not find version in bl_info")

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        major, minor, patch = major, minor + 1, 0
    else:
        patch += 1

    new_version_tuple = f'"version": ({major}, {minor}, {patch})'
    init_file.write_text(content[:match.start()] + new_version_tuple + content[match.end():], encoding="utf-8")

    # --- version in blender_manifest.toml ---
    manifest = manifest_file.read_text(encoding="utf-8")
    manifest_match = re.search(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', manifest, re.MULTILINE)
    if not manifest_match:
        raise ValueError("Could not find version in blender_manifest.toml")
    new_version_str = f'version = "{major}.{minor}.{patch}"'
    manifest_file.write_text(manifest[:manifest_match.start()] + new_version_str + manifest[manifest_match.end():], encoding="utf-8")

    print(f"Version bumped ({level}): {int(match.group(1))}.{int(match.group(2))}.{int(match.group(3))} -> {major}.{minor}.{patch}")
    return f"{major}.{minor}.{patch}"


def build(level="skip"):
    """
    Build the Blender extension as a versioned zip using the Blender CLI.
    Bumps version first unless level='skip'.
    BLENDER_EXE must be set in .env if Blender is not on PATH.
    """
    import sys
    from pathlib import Path

    version = bump_version(level)

    # BLENDER_EXE can be set in .env, e.g.:
    #   BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 4.5\blender.exe
    blender_exe = _env.get("BLENDER_EXE") or "blender"

    root = Path(__file__).parent
    version_tag = f"-{version}" if version else ""
    output_zip = root / "releases" / f"{ADDON_NAME}{version_tag}.zip"
    output_zip.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(blender_exe),
        "--command", "extension", "build",
        "--source-dir", str(root),
        "--output-filepath", str(output_zip),
    ]
    print("[build] Running:", " ".join(f'"{c}"' if " " in c else c for c in cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[build] Blender build failed (exit {result.returncode})")
        sys.exit(result.returncode)

    print(f"[build] Extension built: {output_zip}")


def deploy(level="patch"):
    """Copy the addon to the Blender addons directory set in DEPLOY_PATH."""
    import shutil
    from pathlib import Path

    bump_version(level)

    src = Path(__file__).parent
    dst = Path(DEPLOY) / "addons" / ADDON_NAME

    if dst.exists():
        shutil.rmtree(dst)

    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*IGNORE))
    print(f"Deployed to: {dst}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Deploy or build the Blender extension.")
    parser.add_argument("cmd", nargs="?", default="deploy", choices=["deploy", "build"],
                        help="Command to run (default: deploy)")
    parser.add_argument("level", nargs="?", default="patch", choices=["major", "minor", "patch", "skip"],
                        help="Version bump level (default: patch)")
    args = parser.parse_args()

    if args.cmd == "deploy":
        deploy(args.level)
    elif args.cmd == "build":
        build("skip")
