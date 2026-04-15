# B3D Playblast Plus

Blender addon version of the Maya/3ds Max playblast plugin — render a quick,
un-rendered viewport animation (playblast) directly from Blender's 3D Viewport.

---

## Extension Platform (Blender 4.2+)

This addon is structured as a **Blender Extension** and can be installed via the
[Blender Extensions repository method](https://docs.blender.org/manual/en/latest/advanced/extensions/index.html).

### File structure

```
b3d-playblast-plus/
├── blender_manifest.toml  # Extension manifest (required by Blender 4.2+)
├── __init__.py            # Addon entry point — register / unregister
├── operators.py           # bpy.types.Operator subclasses
├── panels.py              # bpy.types.Panel subclasses (sidebar UI)
└── preferences.py         # AddonPreferences subclass
```

### `blender_manifest.toml`

The manifest file replaces the old `bl_info` dict as the canonical metadata
source for Blender 4.2+ extensions. A `bl_info` dict is still present in
`__init__.py` for backwards-compatibility with older Blender versions.

### Installing from a repository

1. In Blender, go to **Edit → Preferences → Get Extensions**.
2. Add this repository URL as a new remote repository.
3. Search for *B3D Playblast Plus* and install.

### Installing manually

Zip the repository folder and install via
**Edit → Preferences → Add-ons → Install from Disk**.

---

## Development

There is no build step — the Python files are loaded directly by Blender.
After editing any `.py` file, reload the addon with **F3 → Reload Scripts**
or restart Blender.

## License

GPL-3.0-or-later — see [SPDX:GPL-3.0-or-later](https://spdx.org/licenses/GPL-3.0-or-later.html).
