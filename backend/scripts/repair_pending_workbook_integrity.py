from __future__ import annotations

import argparse
import io
from pathlib import Path
import sys
import zipfile


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.xlsx_integrity import repair_workbook_integrity


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Repair Taiico XLSX row spans and table revision identifiers in place."
    )
    parser.add_argument("workbooks", nargs="+", type=Path)
    args = parser.parse_args()

    for path in args.workbooks:
        original = path.read_bytes()
        repaired = repair_workbook_integrity(original)
        with zipfile.ZipFile(io.BytesIO(repaired), "r") as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise ValueError(f"{path.name}: CRC inválido en {bad_member}")
        path.write_bytes(repaired)
        print(f"Reparado: {path}")


if __name__ == "__main__":
    main()
