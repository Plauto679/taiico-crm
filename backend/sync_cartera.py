from __future__ import annotations

import argparse
import json

from services.cartera import sync_cartera_source


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincroniza una cartera canónica de Drive con SQL")
    parser.add_argument("--insurer", choices=("metlife", "sura"), required=True)
    args = parser.parse_args()
    print(json.dumps(sync_cartera_source(args.insurer), ensure_ascii=False))


if __name__ == "__main__":
    main()
