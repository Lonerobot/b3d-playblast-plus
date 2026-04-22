"""
Standalone AYON playblast publisher.

Reads project/folder/task context from AYON environment variables (set by the
AYON launcher).  Accepts a filepath via CLI or direct instantiation.

Usage (from an AYON-launched terminal, with AYON env vars set):
    python ayon_publish.py --filepath "P:/path/to/playblast.mp4"
    python ayon_publish.py --filepath "P:/path/to/playblast.mp4" --variant "Main"
"""

import os
import argparse


class AyonPlayblastPublisher:
    """Publish a playblast MP4 to AYON via TrayPublisher."""

    def __init__(
        self,
        filepath: str,
        variant: str = "Main",
        project_name: str = None,
        folder_path: str = None,
        task_name: str = None,
        creator_id: str = "settings_review",
    ) -> None:
        self.filepath = filepath
        self.variant = variant
        self.creator_id = creator_id or "settings_review"

        # Prefer explicitly passed args; fall back to environment variables.
        # Explicit args are required when called from the Blender operator
        # because ayon_console.exe does not inherit Blender's env vars.
        self.project_name = project_name or os.getenv("AYON_PROJECT_NAME")
        self.folder_path  = folder_path  or os.getenv("AYON_FOLDER_PATH")
        self.task_name    = task_name    or os.getenv("AYON_TASK_NAME")

    def _validate(self):
        missing = []
        if not self.project_name:
            missing.append("project_name (AYON_PROJECT_NAME)")
        if not self.folder_path:
            missing.append("folder_path (AYON_FOLDER_PATH)")
        if not self.task_name:
            missing.append("task_name (AYON_TASK_NAME)")
        if missing:
            raise EnvironmentError(
                f"Missing required AYON context: {missing}\n"
                "Pass as CLI args (--project / --folder-path / --task) or "
                "ensure Blender was launched via the AYON launcher."
            )
        if not os.path.isfile(self.filepath):
            raise FileNotFoundError(f"Filepath does not exist: {self.filepath}")

    def publish(self):
        self._validate()

        print(f"[ayon_publish] Project  : {self.project_name}")
        print(f"[ayon_publish] Folder   : {self.folder_path}")
        print(f"[ayon_publish] Task     : {self.task_name}")
        print(f"[ayon_publish] Variant  : {self.variant}")
        print(f"[ayon_publish] Filepath : {self.filepath}")

        import ayon_api
        from ayon_core.lib.attribute_definitions import FileDefItem
        from ayon_core.pipeline import install_host
        from ayon_core.pipeline.create import CreateContext
        from ayon_traypublisher.api import TrayPublisherHost
        import pyblish.api
        from pyblish.util import publish

        folder_entity = ayon_api.get_folder_by_path(self.project_name, self.folder_path)
        if not folder_entity:
            raise RuntimeError(
                f"Folder '{self.folder_path}' not found in project '{self.project_name}'"
            )

        task_entity = ayon_api.get_task_by_name(
            self.project_name, folder_entity["id"], self.task_name
        )
        if not task_entity:
            raise RuntimeError(
                f"Task '{self.task_name}' not found on folder '{self.folder_path}'"
            )

        file_items = FileDefItem.from_paths([self.filepath], allow_sequences=False)
        file_item_dict = file_items[0].to_dict()
        pre_create_data = {
            "representation_files": [file_item_dict],
            "reviewable": file_item_dict,
        }

        host = TrayPublisherHost()
        host.set_project_name(self.project_name)
        install_host(host)

        create_context = CreateContext(host, headless=True)

        # -- Validate creator is available ----------------------------------
        available_creators = list(create_context.creators.keys())
        print(f"[ayon_publish] Available creators: {available_creators}")
        if self.creator_id not in available_creators:
            raise RuntimeError(
                f"Creator '{self.creator_id}' was not found in the AYON create context.\n"
                f"Available creators: {available_creators}\n"
                "Use 'Refresh Creators' in the Blender panel to pick a valid one."
            )

        create_context.create(
            self.creator_id,
            self.variant,
            folder_entity,
            task_entity,
            pre_create_data,
        )

        create_context.save_changes()

        publish_context = pyblish.api.Context()
        publish_context.data["create_context"] = create_context
        publish(publish_context, create_context.publish_plugins)

        print("[ayon_publish] Publish complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Publish a playblast MP4 to AYON via TrayPublisher."
    )
    parser.add_argument("--filepath",    required=True,  help="Absolute path to the MP4.")
    parser.add_argument("--variant",     default="Main", help="AYON product variant (default: Main).")
    # Context args — passed explicitly from the Blender operator so the
    # script does not depend on env vars being inherited by ayon_console.
    parser.add_argument("--project",     default=None,   help="AYON project name.")
    parser.add_argument("--folder-path", default=None,   dest="folder_path", help="AYON folder path.")
    parser.add_argument("--task",        default=None,   help="AYON task name.")
    parser.add_argument("--creator",     default="settings_review", help="AYON creator identifier (default: settings_review).")
    args = parser.parse_args()

    AyonPlayblastPublisher(
        filepath=args.filepath,
        variant=args.variant,
        project_name=args.project,
        folder_path=args.folder_path,
        task_name=args.task,
        creator_id=args.creator,
    ).publish()


if __name__ == "__main__":
    main()