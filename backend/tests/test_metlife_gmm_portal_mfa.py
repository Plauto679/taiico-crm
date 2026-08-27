import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.metlife_gmm_portal import (
    MetLifeGmmPortalAdapter,
    MetLifeGmmPortalTask,
    policy_candidate_match_score,
    portal_page,
)
from adapters.metlife_gmm_collection import parse_paid_until


class MetLifeGmmMfaContinuationTests(unittest.TestCase):
    def test_policy_match_ignores_ramo_and_zero_padding(self):
        self.assertEqual(
            policy_candidate_match_score(
                "02006 0000560034 MEDICALIFE FAMILIAR", "560034", "60034"
            ),
            3,
        )
        self.assertEqual(
            policy_candidate_match_score(
                "06001 0001359180 MEDICALIFE FAMILIAR", "1359180", "874437"
            ),
            3,
        )

    def test_policy_match_accepts_changed_renewal_consecutive_by_original_suffix(self):
        self.assertEqual(
            policy_candidate_match_score(
                "02006 0001132476 MEDICALIFE FAMILIAR", "1032476", "32476"
            ),
            1,
        )
        self.assertEqual(
            policy_candidate_match_score(
                "02006 0001035883 MEDICALIFE FAMILIAR", "935883", "35883"
            ),
            1,
        )

    def test_policy_match_rejects_a_different_policy(self):
        self.assertEqual(
            policy_candidate_match_score(
                "06001 0001455902 MEDICALIFE FAMILIAR", "1337172", "516069"
            ),
            0,
        )

    def test_portal_page_keeps_old_and_new_portals_in_separate_tabs(self):
        old_page = MagicMock()
        old_page.url = "https://servicios.metlife.com.mx/wps/portal/agentes/"
        new_page = MagicMock()
        new_page.url = "https://agentes.metlife.mx/app/graph-clients"
        context = MagicMock()
        context.pages = [old_page, new_page]

        selected = portal_page(context, "https://agentes.metlife.mx/")

        self.assertIs(selected, new_page)
        context.new_page.assert_not_called()

    def test_paid_until_parser_accepts_portal_format(self):
        self.assertEqual(
            str(parse_paid_until("PAGADO HASTA\n10.09.2026")),
            "2026-09-10",
        )

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

    def test_open_clientes_beta_uses_first_matching_button(self):
        adapter = self.make_adapter()
        page = MagicMock()
        buttons = page.get_by_role.return_value
        buttons.count.return_value = 1
        first_button = buttons.first
        first_button.is_visible.return_value = True

        adapter.open_clientes_beta(page)

        page.get_by_role.assert_called_once_with(
            "button", name="Clientes Beta", exact=True
        )
        first_button.click.assert_called_once_with()

    def test_download_waits_for_rows_and_uses_dom_click_for_unchecked_boxes(self):
        with tempfile.TemporaryDirectory() as download_root:
            adapter = MetLifeGmmPortalAdapter(
                username="operator",
                password="secret",
                session_profile_dir="/tmp/taiico-metlife-mfa-test",
                download_root=download_root,
            )
            page = MagicMock()
            checkboxes = MagicMock()
            checked = MagicMock()
            unchecked = MagicMock()
            checked.is_visible.return_value = True
            checked.is_checked.return_value = True
            unchecked.is_visible.return_value = True
            unchecked.is_checked.return_value = False
            checkboxes.count.return_value = 2
            checkboxes.nth.side_effect = [checked, unchecked]
            page.locator.return_value = checkboxes
            download = page.expect_download.return_value.__enter__.return_value.value
            download.suggested_filename = "documents.zip"

            adapter.download_documents(
                page,
                MetLifeGmmPortalTask(id="task", policy_number="123", rfc="RFC123"),
            )

            page.wait_for_selector.assert_called_once_with(
                "input[type='checkbox']", state="visible", timeout=60_000
            )
            checked.evaluate.assert_not_called()
            unchecked.evaluate.assert_called_once_with("element => element.click()")
            download.save_as.assert_called_once()


if __name__ == "__main__":
    unittest.main()
