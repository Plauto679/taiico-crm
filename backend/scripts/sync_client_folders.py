from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from services.client_folders import (  # noqa: E402
    build_client_folder_drive_service,
    build_client_folder_plan,
    client_folders_parent_id,
    create_client_folders,
    list_folder_children,
    load_metlife_client_records,
    rename_client_folders,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one Google Drive folder per canonical MetLife client RFC."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create missing folders. Without this flag the command is read-only.",
    )
    parser.add_argument(
        "--parent-id",
        default=client_folders_parent_id(),
        help="Destination Google Drive folder ID.",
    )
    parser.add_argument(
        "--preview-path",
        type=Path,
        default=REPOSITORY_DIR / ".runtime" / "client-folder-sync-preview.csv",
        help="CSV path for the complete plan.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Independent Drive connections used during --apply (default: 8).",
    )
    return parser.parse_args()


def write_preview(path: Path, plan: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=["action", "rfc", "client_name", "folder_name", "policy_count", "aliases"],
        )
        writer.writeheader()
        for candidate in plan["candidates"]:
            writer.writerow(
                {
                    "action": "create",
                    "rfc": candidate.rfc,
                    "client_name": candidate.client_name,
                    "folder_name": candidate.folder_name,
                    "policy_count": candidate.policy_count,
                    "aliases": " | ".join(candidate.aliases),
                }
            )
        mismatches_by_rfc = {item["rfc"]: item for item in plan["name_mismatches"]}
        for existing in plan["already_exists"]:
            mismatch = mismatches_by_rfc.get(existing["rfc"])
            writer.writerow(
                {
                    "action": "rename" if mismatch else "already_exists",
                    "rfc": existing["rfc"],
                    "client_name": "",
                    "folder_name": mismatch["expected_name"] if mismatch else " | ".join(folder["name"] for folder in existing["folders"]),
                    "policy_count": "",
                    "aliases": "",
                }
            )
        for rfc, count in plan["invalid_rfcs"].items():
            writer.writerow(
                {
                    "action": "invalid_rfc",
                    "rfc": rfc,
                    "client_name": "",
                    "folder_name": "",
                    "policy_count": count,
                    "aliases": "",
                }
            )
        for rfc in plan["missing_name_rfcs"]:
            writer.writerow(
                {
                    "action": "missing_name",
                    "rfc": rfc,
                    "client_name": "",
                    "folder_name": "",
                    "policy_count": "",
                    "aliases": "",
                }
            )


def main() -> int:
    args = parse_args()
    records, issues = load_metlife_client_records()
    service = build_client_folder_drive_service()
    existing_items = list_folder_children(service, args.parent_id)
    plan = build_client_folder_plan(records, existing_items)
    write_preview(args.preview_path, plan)

    print({
        "mode": "apply" if args.apply else "dry-run",
        "parent_id": args.parent_id,
        "source_rows": len(records),
        "parser_issues": len(issues),
        **plan["summary"],
        "preview_path": str(args.preview_path),
    }, flush=True)
    if not args.apply:
        return 0
    if not 1 <= args.workers <= 16:
        raise ValueError("--workers must be between 1 and 16")

    total = len(plan["candidates"])
    renamed = rename_client_folders(service, plan["name_mismatches"])
    if renamed:
        print({"renamed": len(renamed)}, flush=True)

    def report_progress(index, candidate, _folder):
        if index == 1 or index % 25 == 0 or index == total:
            print(
                f"created={index}/{total} rfc={candidate.rfc} name={candidate.client_name}",
                flush=True,
            )

    created = create_client_folders(
        service,
        args.parent_id,
        plan["candidates"],
        progress=report_progress,
        workers=args.workers,
        service_factory=build_client_folder_drive_service,
    )
    print({"created": len(created), "requested": total, "renamed": len(renamed)}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
