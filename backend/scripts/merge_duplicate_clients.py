from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import SessionLocal
from services.client_merge import merge_duplicate_client


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolida dos clientes con el mismo RFC.")
    parser.add_argument("--canonical-id", required=True)
    parser.add_argument("--duplicate-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.apply:
        print(json.dumps({"dry_run": True, "canonical_id": args.canonical_id, "duplicate_id": args.duplicate_id}, indent=2))
        return 0

    db = SessionLocal()
    try:
        result = merge_duplicate_client(
            db,
            canonical_id=args.canonical_id,
            duplicate_id=args.duplicate_id,
        )
        db.commit()
        print(json.dumps({"success": True, **result}, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
