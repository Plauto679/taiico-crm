"""Keep assigned modules reachable from both navigation and home cards."""
import re
import unittest
from pathlib import Path

from services.auth import MODULES
from services.home_widgets import allowed_widgets, selected_widgets
from test_home_widgets import profile


class ModuleCatalogTests(unittest.TestCase):
    def test_every_assignable_module_has_one_catalog_entry_and_page(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "src/lib/module-catalog.ts").read_text()
        entries = re.findall(r"\['([^']+)', '[^']+', '([^']+)'", source)
        self.assertEqual(len(entries), len(MODULES))
        self.assertEqual({key for key, _ in entries}, set(MODULES))
        for key, href in entries:
            with self.subTest(module=key):
                self.assertTrue((root / "src/app" / href.lstrip("/") / "page.tsx").exists())

    def test_each_module_card_respects_read_operation_and_denied_access(self):
        for module in MODULES:
            if module == "inicio":
                continue
            for permission in ("lectura", "operacion", "ninguno"):
                with self.subTest(module=module, permission=permission):
                    user = profile("catalog@example.com", {module: permission})
                    expected = [] if permission == "ninguno" else [module]
                    self.assertEqual(allowed_widgets(user), expected)
                    self.assertEqual(selected_widgets(user, None), expected)


if __name__ == "__main__":
    unittest.main()
