"""
Diagnostic probe for AYON version streams.

Shows exactly what product names our publisher generates for each task,
what versions currently exist in AYON, and what version would be assigned
on the next publish -- revealing whether the version counter is shared or
per-task.

Run via ayon_console so AYON modules are available:

    ayon_console.exe run test_ayon_version_stream.py -- \\
        --project 00000_VertexApe_DevTest \\
        --folder assets/test \\
        --tasks Rigging Modeling Lookdev Animation FX \\
        --variant Main \\
        --creator settings_review

Or if running from a terminal with AYON env vars already set:

    ayon_console.exe run test_ayon_version_stream.py
"""

import argparse
import os
import sys


def get_product_name_for_creator(create_context, creator_id, variant,
                                  folder_entity, task_entity):
    """Ask the creator what product name it would generate for this context."""
    if creator_id not in create_context.creators:
        return f"<creator '{creator_id}' not found>"
    creator = create_context.creators[creator_id]
    project_name = create_context.project_name
    try:
        # Current AYON API: (project_name, folder_entity, task_entity, variant)
        name = creator.get_product_name(
            project_name,
            folder_entity,
            task_entity,
            variant,
        )
        return name
    except Exception as exc:
        return f"<error: {exc}>"


def main():
    parser = argparse.ArgumentParser(
        description="Probe AYON version streams per task."
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("AYON_PROJECT_NAME", ""),
        help="AYON project name (default: AYON_PROJECT_NAME env var).",
    )
    parser.add_argument(
        "--folder",
        default=os.environ.get("AYON_FOLDER_PATH", "assets/test"),
        help="Folder path within the project (default: AYON_FOLDER_PATH or 'assets/test').",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        default=["Rigging", "Modeling", "Lookdev", "Animation", "FX"],
        help="Task names to probe (space-separated).",
    )
    parser.add_argument(
        "--variant",
        default="Main",
        help="Product variant (default: Main).",
    )
    parser.add_argument(
        "--creator",
        default="settings_review",
        help="Creator identifier (default: settings_review).",
    )

    argv = [a for a in sys.argv[1:] if a != "--"]
    args = parser.parse_args(argv)

    if not args.project:
        print("ERROR: --project is required (or set AYON_PROJECT_NAME).")
        sys.exit(1)

    # -- Ensure AYON env vars are set so AYON modules initialise correctly --
    os.environ.setdefault("AYON_PROJECT_NAME", args.project)

    import ayon_api
    from ayon_core.pipeline import install_host
    from ayon_core.pipeline.create import CreateContext
    from ayon_traypublisher.api import TrayPublisherHost

    project_name = args.project
    folder_path  = args.folder
    task_names   = args.tasks
    variant      = args.variant
    creator_id   = args.creator

    print("=" * 70)
    print("PlayblastPlus -- AYON version-stream probe")
    print("=" * 70)
    print(f"  Project   : {project_name}")
    print(f"  Folder    : {folder_path}")
    print(f"  Tasks     : {task_names}")
    print(f"  Variant   : {variant}")
    print(f"  Creator   : {creator_id}")
    print()

    # -- 1. Fetch folder entity ---------------------------------------------
    folder_entity = ayon_api.get_folder_by_path(project_name, folder_path)
    if not folder_entity:
        print(f"ERROR: folder '{folder_path}' not found in project '{project_name}'.")
        sys.exit(1)

    folder_id = folder_entity["id"]
    print(f"Folder entity : {folder_entity['name']}  (id: {folder_id})")
    print()

    # -- 2. Fetch all existing products under this folder ------------------
    print("-" * 70)
    print("STEP 1 -- All products currently published under this folder")
    print("-" * 70)
    all_products = list(ayon_api.get_products(
        project_name,
        folder_ids=[folder_id],
        fields={"id", "name", "productType"},
    ))
    if not all_products:
        print("  (none -- no products have been published to this folder yet)")
    else:
        # Fetch last versions for all products
        product_ids = {p["id"] for p in all_products}
        last_versions = dict(ayon_api.get_last_versions(
            project_name,
            product_ids,
            fields={"version", "productId"},
        ))
        for product in sorted(all_products, key=lambda p: p["name"]):
            lv = last_versions.get(product["id"])
            ver_str = f"v{lv['version']:03d}" if lv else "(no versions)"
            print(f"  {product['name']:<30} type={product['productType']:<12} latest={ver_str}")
    print()

    # -- 3. List actual tasks on this folder ------------------------------
    print("-" * 70)
    print("STEP 2 -- Actual tasks on this folder (from AYON database)")
    print("-" * 70)
    actual_tasks = list(ayon_api.get_tasks(
        project_name,
        folder_ids=[folder_id],
        fields={"id", "name", "taskType"},
    ))
    task_map = {t["name"]: t for t in actual_tasks}
    if not actual_tasks:
        print("  (no tasks found on this folder)")
    else:
        for t in sorted(actual_tasks, key=lambda x: x["name"]):
            print(f"  name={t['name']:<20} taskType={t.get('taskType','?')}")
    print()

    # Reconcile requested task names (case-insensitive fallback)
    def resolve_task_name(name):
        if name in task_map:
            return name
        for actual in task_map:
            if actual.lower() == name.lower():
                return actual
        return None

    # -- 4. Build CreateContext to ask what product name it would generate --
    print("-" * 70)
    print("STEP 3 -- Initialise CreateContext (reads AYON creator settings)")
    print("-" * 70)
    host = TrayPublisherHost()
    host.set_project_name(project_name)
    install_host(host)
    create_context = CreateContext(host, headless=True)

    available_creators = list(create_context.creators.keys())
    print(f"  Available creators : {available_creators}")
    if creator_id not in available_creators:
        print(f"  WARNING: '{creator_id}' is not available in this project.")
    print()

    # -- 5. Per-task analysis -----------------------------------------------
    print("-" * 70)
    print("STEP 4 -- Per-task version stream analysis")
    print("-" * 70)
    print("  Mode A = raw variant (what old code does):      variant=%r" % variant)
    print("  Mode B = task-prefixed variant (fixed code):    {task_name}_%s" % variant)
    print()

    rows = []
    for task_name in task_names:
        resolved = resolve_task_name(task_name)
        if resolved is None:
            rows.append({
                "task": task_name,
                "status": "NOT FOUND IN AYON",
                "task_type": "?",
                "product_name_A": "?",
                "product_name_B": "?",
                "latest_A": "?",
                "next_A": "?",
                "latest_B": "?",
                "next_B": "?",
            })
            continue

        task_entity = task_map[resolved]
        task_type = task_entity.get("taskType", "?")
        task_name_slug = task_entity.get("name", "")

        # Mode A: old code -- raw variant, same product for all tasks
        product_name_A = get_product_name_for_creator(
            create_context, creator_id, variant, folder_entity, task_entity
        )

        # Mode B: fixed code -- {task_name}_{variant} gives per-task product stream
        # Matches the existing naming convention: review_3d_anim_Main, etc.
        effective_variant = f"{task_name_slug}_{variant}" if task_name_slug else variant
        product_name_B = get_product_name_for_creator(
            create_context, creator_id, effective_variant, folder_entity, task_entity
        )

        def lookup_version(product_name):
            products = list(ayon_api.get_products(
                project_name,
                folder_ids=[folder_id],
                product_names=[product_name],
                fields={"id", "name"},
            ))
            if not products:
                return "(no product yet)", 1
            pid = products[0]["id"]
            lv_map = dict(ayon_api.get_last_versions(
                project_name, [pid], fields={"version", "productId"}
            ))
            lv = lv_map.get(pid)
            if lv:
                return f"v{lv['version']:03d}", lv["version"] + 1
            return "(no versions)", 1

        latest_A, next_A = lookup_version(product_name_A)
        latest_B, next_B = lookup_version(product_name_B)

        rows.append({
            "task": task_name,
            "status": "OK",
            "task_type": task_type,
            "product_name_A": product_name_A,
            "product_name_B": product_name_B,
            "latest_A": latest_A,
            "next_A": f"v{next_A:03d}",
            "latest_B": latest_B,
            "next_B": f"v{next_B:03d}",
        })

    # Print Mode A table (old behaviour)
    print("  --- MODE A: Old code (raw variant=%r) ---" % variant)
    col_w = {
        "task":     max(len("Task"),     max(len(r["task"])          for r in rows)),
        "ttype":    max(len("TaskType"), max(len(r["task_type"])     for r in rows)),
        "prod":     max(len("ProductName"), max(len(r["product_name_A"]) for r in rows)),
        "latest":   max(len("LatestVer"), max(len(r["latest_A"])    for r in rows)),
        "next":     max(len("NextVer"),  max(len(r["next_A"])        for r in rows)),
    }

    def row_fmt(task, ttype, prod, latest, nxt):
        return (
            f"  {task:<{col_w['task']}}  {ttype:<{col_w['ttype']}}  "
            f"{prod:<{col_w['prod']}}  {latest:<{col_w['latest']}}  {nxt}"
        )

    hdr = row_fmt("Task", "TaskType", "ProductName", "LatestVer", "NextVer")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for r in rows:
        print(row_fmt(r["task"], r["task_type"], r["product_name_A"], r["latest_A"], r["next_A"]))
    print()

    # Print Mode B table (fixed behaviour)
    print("  --- MODE B: Fixed code (variant={task_name}_%s) ---" % variant)
    col_w2 = {
        "task":   max(len("Task"),     max(len(r["task"])          for r in rows)),
        "ttype":  max(len("TaskType"), max(len(r["task_type"])     for r in rows)),
        "prod":   max(len("ProductName"), max(len(r["product_name_B"]) for r in rows)),
        "latest": max(len("LatestVer"), max(len(r["latest_B"])    for r in rows)),
        "next":   max(len("NextVer"),  max(len(r["next_B"])        for r in rows)),
    }

    def row_fmt2(task, ttype, prod, latest, nxt):
        return (
            f"  {task:<{col_w2['task']}}  {ttype:<{col_w2['ttype']}}  "
            f"{prod:<{col_w2['prod']}}  {latest:<{col_w2['latest']}}  {nxt}"
        )

    hdr2 = row_fmt2("Task", "TaskType", "ProductName", "LatestVer", "NextVer")
    print(hdr2)
    print("  " + "-" * (len(hdr2) - 2))
    for r in rows:
        print(row_fmt2(r["task"], r["task_type"], r["product_name_B"], r["latest_B"], r["next_B"]))
    print()

    # -- 5. Diagnosis ------------------------------------------------------
    print("-" * 70)
    print("STEP 5 -- Diagnosis")
    print("-" * 70)

    ok_rows = [r for r in rows if r["status"] == "OK"]
    unique_A = {r["product_name_A"] for r in ok_rows}
    unique_B = {r["product_name_B"] for r in ok_rows}

    if len(unique_A) == 1:
        (shared_name,) = unique_A
        print(f"  [!] MODE A -- ALL tasks share product name: '{shared_name}'")
        print("       Version counter is SHARED -- switching tasks continues the same stream.")
    else:
        print(f"  [OK] MODE A -- Tasks have DISTINCT products: {sorted(unique_A)}")

    print()

    if len(unique_B) == 1:
        (shared_name,) = unique_B
        print(f"  [!] MODE B -- ALL tasks still share product name: '{shared_name}'")
        print("       Fix did not work as expected.")
    else:
        print(f"  [OK] MODE B -- Tasks have DISTINCT products: {sorted(unique_B)}")
        print("       Each task gets its own version stream -- v001 resets correctly on task switch.")

    print()

    # Check whether our publisher actually passes the right task to subprocess
    print("-" * 70)
    print("STEP 6 -- Environment variable check (task context propagation)")
    print("-" * 70)
    env_project = os.environ.get("AYON_PROJECT_NAME", "(not set)")
    env_folder  = os.environ.get("AYON_FOLDER_PATH",  "(not set)")
    env_task    = os.environ.get("AYON_TASK_NAME",    "(not set)")
    print(f"  AYON_PROJECT_NAME = {env_project}")
    print(f"  AYON_FOLDER_PATH  = {env_folder}")
    print(f"  AYON_TASK_NAME    = {env_task}")
    print()
    if env_task == "(not set)":
        print("  [!]  AYON_TASK_NAME is not set -- the publisher subprocess would fail")
        print("     unless the env var is set by the AYON launcher before Blender starts.")
    else:
        print(f"  The publisher subprocess would use task '{env_task}' from env vars.")
        print("  If you switch tasks in Blender WITHOUT restarting, this env var")
        print("  must be updated by the task-switch mechanism for the correct task")
        print("  to be passed to the publish subprocess.")
    print()
    print("=" * 70)
    print("Probe complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
