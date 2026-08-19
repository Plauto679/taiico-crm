from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.client_folders import (
    FOLDER_MIME_TYPE,
    build_client_folder_drive_service,
    client_folders_parent_id,
    list_folder_children,
    normalize_rfc,
    valid_client_rfc,
)


def build_cleanup_plan(service) -> dict:
    folders = list_folder_children(service, client_folders_parent_id())
    by_rfc = defaultdict(list)
    for folder in folders:
        rfc = normalize_rfc(str(folder.get("name") or "").split(" - ", 1)[0])
        if folder.get("mimeType") == FOLDER_MIME_TYPE and valid_client_rfc(rfc):
            by_rfc[rfc].append(folder)

    safe_to_trash = []
    requires_review = []
    for rfc, matches in sorted(by_rfc.items()):
        if len(matches) < 2:
            continue
        inspected = []
        for folder in matches:
            children = list_folder_children(service, folder["id"])
            inspected.append({**folder, "child_count": len(children)})
        populated = [folder for folder in inspected if folder["child_count"] > 0]
        empty = [folder for folder in inspected if folder["child_count"] == 0]
        item = {"rfc": rfc, "folders": inspected}
        if len(populated) == 1 and empty:
            item["keep"] = populated[0]
            item["trash"] = empty
            safe_to_trash.append(item)
        else:
            requires_review.append(item)
    return {
        "summary": {
            "duplicate_rfcs": len(safe_to_trash) + len(requires_review),
            "safe_empty_folders": sum(len(item["trash"]) for item in safe_to_trash),
            "requires_review": len(requires_review),
        },
        "safe_to_trash": safe_to_trash,
        "requires_review": requires_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Identifica y opcionalmente envía a papelera carpetas RFC duplicadas vacías."
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    service = build_client_folder_drive_service()
    plan = build_cleanup_plan(service)
    result = {"dry_run": not args.apply, **plan}
    if args.apply:
        trashed = []
        for item in plan["safe_to_trash"]:
            for folder in item["trash"]:
                updated = service.files().update(
                    fileId=folder["id"],
                    body={"trashed": True},
                    fields="id,name,trashed",
                    supportsAllDrives=True,
                ).execute()
                trashed.append({"rfc": item["rfc"], **updated})
        result["trashed"] = trashed
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
