import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.metlife_gmm_portal import MetLifeGmmPortalAdapter


class MetLifeGmmMfaContinuationTests(unittest.TestCase):
    def make_adapter(self):
        return MetLifeGmmPortalAdapter(
            username="operator",
            password="secret",
            session_profile_dir="/tmp/taiico-metlife-mfa-test",
        )

    def test_continue_mfa_submits_operator_code_and_waits_for_dashboard(self):
        adapter = self.make_adapter()
        page = MagicMock()
        code_input = page.locator.return_value.first
        submit = page.get_by_role.return_value.first

        adapter.continue_mfa(page, " 123456 ")

        code_input.wait_for.assert_called_once_with(state="visible", timeout=15_000)
        code_input.fill.assert_called_once_with("123456")
        submit.click.assert_called_once_with()
        page.wait_for_selector.assert_called_once_with("text=Clientes Beta", timeout=120_000)

    def test_continue_mfa_can_confirm_code_entered_in_headed_browser(self):
        adapter = self.make_adapter()
        page = MagicMock()

        adapter.continue_mfa(page)

        page.locator.assert_not_called()
        page.get_by_role.assert_not_called()
        page.wait_for_selector.assert_called_once_with("text=Clientes Beta", timeout=120_000)


if __name__ == "__main__":
    unittest.main()
