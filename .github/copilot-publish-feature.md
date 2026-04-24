# .copilot-publish-feature.md

## Blender Playblast Addon --- Publish Feature Augmentation

---

## 1. Context

This feature **augments the existing publishing system** used for AYON
integration.

- The current system is functional and must remain intact.
- This implementation introduces **granular control over media
  selection**.
- No destructive refactors --- only extend existing logic where
  necessary.

---

## 2. Feature Overview

Introduce a **media-driven publishing workflow** allowing the user to
explicitly choose what to publish.

### Supported Media Modes

- `MP4 Video`
- `Image Sequence`
- `Still Image`

Each mode determines: - File discovery location - Allowed product
types - Available variant options

---

## 3. UI Requirements

### 3.1 Media Type Switch

Add an enum property:

```python
media_type: EnumProperty(
    name="Media Type",
    items=[
        ("MP4", "MP4 Video", ""),
        ("SEQUENCE", "Image Sequence", ""),
        ("IMAGE", "Still Image", "")
    ]
)
```

---

### 3.2 File Selection Dropdown

A dynamic enum that updates based on `media_type`.

#### Behaviour:

---

  Mode        Directory             Filter                           Notes

---

  MP4         playblast root        `.mp4`                           Direct file
                                                                     listing

  SEQUENCE    `frames/`             `.png` (RGBA with transparency)  Group into
                                                                     sequences

IMAGE       `captures/`           `.png` (RGBA with transparency)  Single
                                                                     frame
                                                                     selection
------------------------------------------------------------------------------

---

### 3.3 Product Type Filtering

- Use existing product enum
- Dynamically filter based on `media_type`

#### Rules:

- `MP4` / `SEQUENCE`:
  - Allow: `review`, `render`
  - Disallow: image-only products
- `IMAGE`:
  - Allow: `review`, `image`

---

### 3.4 Variant Enum

- Populate dynamically from config
- Overrides any static variant list

---

## 4. File Discovery Logic

### 4.1 MP4

Scan: `<playblast_root>`{=html}/\*.mp4

---

### 4.2 Still Images

Scan: `<playblast_root>`{=html}/captures/\*.png

Notes: - Files are always `.png` - May contain transparency depending on
capture mode

---

### 4.3 Image Sequences

Scan: `<playblast_root>`{=html}/frames/\*.png

Notes: - Frames are always `.png` - May include alpha channel (RGBA)

Group files into sequences (not individual frames)

Example: shotA_0001.png shotA_0002.png → shotA\_\[####\].png

---

## 5. Sequence Parsing

Detect and group sequences based on: - Filename pattern - Frame
numbering - Padding

Preferred libraries: - clique - fileseq

this was run inside Blender, so it appears clique is loaded and availible to the interpreter. 

```
>>> import clique
>>> clique
<module 'clique' from 'C:\\Users\\pete\\AppData\\Local\\Ynput\\AYON\\dependency_packages\\ayon_2602231726_windows.zip\\dependencies\\clique\\__init__.py'>
```

Fallback: - Regex grouping

Sequence parsing must occur inside blender for the addon UI, and then be passed to the publish script in the correct format.

TThis script was previously used in Maya to publish frame sequences. Ensure the sequence extraction is similar - 

```
import pyblish.api
from pyblish.util import publish

# from openpype.client import get_asset_by_name
# from openpype.lib.attribute_definitions import FileDefItem
# from openpype.pipeline import install_host
# from openpype.pipeline.create import CreateContext
# from openpype.hosts.traypublisher.api import TrayPublisherHost

# from openpype.pipeline import context_tools

##################
# AYON REFACTOR 
##################
from ayon_core.lib.attribute_definitions import FileDefItem
from ayon_core.pipeline import install_host
from ayon_core.pipeline.create import CreateContext
from ayon_traypublisher.api import TrayPublisherHost 
from ayon_core.pipeline import context_tools 
import ayon_api

from pathlib import Path
import json

class PlayblastPublisher():
    def __init__(self, root_folder) -> None:
        self.root_folder = Path(root_folder)

        """
        There seems to be some nuances about executing this class 
        as a supbrocess. 

        I tried numerous ways to have global constants for the 
        publishing naming conventions, but having the process 
        aware of the relative imports needed was troublesome

        So I am reverting to having a JSON settings file and 
        loading it where needed.   
        """
        settings_file = Path(__file__).parent.absolute() / 'settings.json'
        with open(settings_file) as f:
            settings = json.load(f)

        self.reviewable = settings["review_prefix"]
        self.representation = settings["representation_prefix"]
        self.variant = settings["variant"]

    def globData(self,pattern, ext):
        file_names = []
        for f in self.root_folder.glob(f'{pattern}*{ext}'):
            file_names.append(str(f))
        return file_names

    def get_reviewable(self, ext='.mp4'):
        return self.globData(self.reviewable, ext)

    def get_representation(self, ext='.png'):
        return self.globData(self.representation, ext)

    def publish_review(self):
        context = context_tools.get_current_context()
        project_name = context["project_name"]
        folder_path = context["folder_path"]
        task_name = context["task_name"]
        variant = self.variant
        sequence_paths = self.get_representation()
        review_paths = self.get_reviewable()
        # Based on which create plugin should be used
        create_identifier = "settings_review"

        folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
        task_entity = ayon_api.get_task_by_name(
            project_name, folder_entity["id"], task_name
        )

        representation_files = FileDefItem.from_value(sequence_paths, True)
        if len(representation_files) != 1:
            raise ValueError(
                "Couldn't figure out single representation item from paths."
            )

        reviewable = FileDefItem.from_value(review_paths, True)
        if len(reviewable) > 1:
            raise ValueError(
                "Couldn't figure out single reviewable item from paths."
            )

        representation_item = representation_files[0].to_dict()
        reviewable_item = reviewable[0].to_dict()

        pre_create_data = {
            "representation_files": representation_item,
            "reviewable": reviewable_item
        }

        host = TrayPublisherHost()
        host.set_project_name(project_name)
        install_host(host)

        create_context = CreateContext(host, headless=True)
        create_context.create(
            create_identifier,
            variant,
            folder_entity,
            task_entity,
            pre_create_data
        )

        create_context.save_changes()

        publish_context = pyblish.api.Context()
        publish_context.data["create_context"] = create_context
        publish(publish_context, create_context.publish_plugins)

if __name__ == "__main__":
  
    import sys
    args = sys.argv[1:] 
  
    if args and args[0]:
        print(f'Publishing review media from {args[0]}')
        pub = PlayblastPublisher(args[0])  
        pub.publish_review()
```

---

## 6. Config System

Replace: apng_settings.json

With: config.json

### Structure

{ "MP4": { "products": \["review", "render"\], "variants": \["Main",
"Turnaround"\] }, "SEQUENCE": { "products": \["review", "render"\],
"variants": \["Main", "Turnaround"\] }, "IMAGE": { "products":
\["review", "image"\], "variants": \["Main", "Wire", "Chalk"\] } }

---

## 7. Publisher Integration

Do not replace existing publisher.

### Behaviour:

- MP4 → pass file path
- IMAGE → pass file path
- SEQUENCE → pass pattern + frame range

---

## 8. Preferences Dependency

- SEQUENCE depends on `keep_images`
- Disable or warn if not enabled

---

## 9. Error Handling

- No files → UI warning
- Invalid selection → block publish
- Missing folders → fail gracefully

---

## 10. Design Constraints

- Non-destructive
- Modular logic
- No hardcoded product/variant rules
- need to move the refresh creators button so it mimicks the layout of the token dialog - currently it's full width and looks clunky. it should be an icon button at the end of the creators list.

---

## 11. Expected Outcome

User selects: - media type - file / sequence - product - variant

System publishes exactly that media.

---

## 12. Notes

- All preview frames are `.png`
- Transparency must be preserved
