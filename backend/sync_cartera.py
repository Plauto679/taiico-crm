from __future__ import annotations

import argparse
import json

from services.cartera import sync_cartera_source, sync_cartera_sql_to_canonical


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza una cartera canónica de Drive con SQL")
    parser.add_argument("--insurer", choices=("metlife", "sura", "aarco_axa"), required=True)
    parser.add_argument("--direction", choices=("import", "export"), default="import")
    args = parser.parse_args()
    operation = sync_cartera_source if args.direction == "import" else sync_cartera_sql_to_canonical
    print(json.dumps(operation(args.insurer), ensure_ascii=False))


if __name__ == "__main__":
    main()
