import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.metlife_gmm_portal import (
    SEARCH_RESULT_TIMEOUT_MS,
    MetLifeGmmPortalAdapter,
    MetLifePortalAdapterError,
    MetLifeGmmPortalTask,
    ensure_persistent_chrome,
    policy_candidate_match_score,
    portal_page,
)
from adapters.metlife_gmm_collection import parse_paid_until


class MetLifeGmmMfaContinuationTests(unittest.TestCase):
    def test_persistent_chrome_launches_once_and_waits_for_cdp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chrome_path = root / "Google Chrome"
            chrome_path.touch()
            profile = root / "profile"
            with patch(
                "adapters.metlife_gmm_portal.DEFAULT_CHROME_PATH",
                chrome_path,
            ), patch(
                "adapters.metlife_gmm_portal.chrome_server_ready",
                return_value=False,
            ), patch(
                "adapters.metlife_gmm_portal.wait_for_chrome_server",
                return_value=True,
            ) as wait_for_server, patch(
                "adapters.metlife_gmm_portal.subprocess.Popen",
            ) as popen:
                ensure_persistent_chrome(profile)

        popen.assert_called_once()
        wait_for_server.assert_called_once_with(30)

    def test_persistent_chrome_suppresses_launch_during_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chrome_path = root / "Google Chrome"
            chrome_path.touch()
            profile = root / "profile"
            profile.mkdir()
            lock_path = profile / ".taiico-chrome-start.lock"
            lock_path.write_text(str(__import__("time").time()))
            with patch(
                "adapters.metlife_gmm_portal.DEFAULT_CHROME_PATH",
                chrome_path,
            ), patch(
                "adapters.metlife_gmm_portal.chrome_server_ready",
                return_value=False,
            ), patch(
                "adapters.metlife_gmm_portal.wait_for_chrome_server",
                return_value=False,
            ) as wait_for_server, patch(
                "adapters.metlife_gmm_portal.subprocess.Popen",
            ) as popen, self.assertRaisesRegex(
                MetLifePortalAdapterError, "duplicate launch suppressed"
            ):
                ensure_persistent_chrome(profile)

        popen.assert_not_called()
        wait_for_server.assert_called_once_with(10)

    def test_clientes_beta_waits_up_to_thirty_seconds_for_search_results(self):
        self.assertEqual(SEARCH_RESULT_TIMEOUT_MS, 30_000)

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

    def test_expired_session_restarts_all_new_portal_tabs_and_preserves_old_portal(self):
        adapter = self.make_adapter()
        old_page = MagicMock()
        old_page.url = "https://servicios.metlife.com.mx/wps/portal/agentes/"
        app_page = MagicMock()
        app_page.url = "https://agentes.metlife.mx/app/graph-clients"
        expired_page = MagicMock()
        expired_page.url = (
            "https://federate.sso.metlife.com/as/example/resume/as/authorization.ping"
        )
        unrelated_page = MagicMock()
        unrelated_page.url = "https://mail.google.com/"
        fresh_page = MagicMock()
        context = MagicMock()
        context.pages = [old_page, app_page, expired_page, unrelated_page]
        context.new_page.return_value = fresh_page

        restarted = adapter.restart_new_portal(context)

        self.assertIs(restarted, fresh_page)
        app_page.close.assert_called_once_with()
        expired_page.close.assert_called_once_with()
        old_page.close.assert_not_called()
        unrelated_page.close.assert_not_called()
        fresh_page.goto.assert_called_once_with(
            "https://agentes.metlife.mx/",
            wait_until="domcontentloaded",
            timeout=90_000,
        )

    def test_prepare_clientes_beta_recovers_expired_sso_session(self):
        adapter = self.make_adapter()
        stale_page = MagicMock()
        stale_page.url = (
            "https://federate.sso.metlife.com/as/example/resume/as/authorization.ping"
        )
        fresh_page = MagicMock()
        context = MagicMock()
        context.pages = [stale_page]
        adapter.restart_new_portal = MagicMock(return_value=fresh_page)
        adapter.prepare_clientes_beta = MagicMock(return_value=False)

        page, reused, recovered = adapter.prepare_clientes_beta_with_recovery(
            context, stale_page
        )

        self.assertIs(page, fresh_page)
        self.assertFalse(reused)
        self.assertTrue(recovered)
        adapter.restart_new_portal.assert_called_once_with(context)
        adapter.prepare_clientes_beta.assert_called_once_with(fresh_page)

    def test_prepare_clientes_beta_restarts_when_stale_spa_never_becomes_ready(self):
        adapter = self.make_adapter()
        stale_page = MagicMock()
        stale_page.url = "https://agentes.metlife.mx/app/graph-clients"
        fresh_page = MagicMock()
        context = MagicMock()
        context.pages = [stale_page]
        adapter.context_has_expired_session = MagicMock(return_value=False)
        adapter.restart_new_portal = MagicMock(return_value=fresh_page)
        adapter.prepare_clientes_beta = MagicMock(
            side_effect=[TimeoutError("checkbox did not become visible"), False]
        )

        page, reused, recovered = adapter.prepare_clientes_beta_with_recovery(
            context, stale_page
        )

        self.assertIs(page, fresh_page)
        self.assertFalse(reused)
        self.assertTrue(recovered)
        adapter.restart_new_portal.assert_called_once_with(context)
        self.assertEqual(
            adapter.prepare_clientes_beta.call_args_list,
            [unittest.mock.call(stale_page), unittest.mock.call(fresh_page)],
        )

    def test_document_selection_uses_visible_material_checkbox_not_hidden_input(self):
        adapter = self.make_adapter()
        page = MagicMock()
        combined = MagicMock()
        boxes = MagicMock()
        box = MagicMock()
        hidden_inputs = MagicMock()
        boxes.count.return_value = 1
        boxes.nth.return_value = box
        box.is_visible.return_value = True
        box.get_attribute.return_value = "false"
        hidden_inputs.count.return_value = 1

        def locate(selector):
            if selector.startswith("input[type='checkbox'],"):
                return combined
            if selector == ".mat-checkbox, mat-checkbox, [role='checkbox']":
                return boxes
            if selector == "input[type='checkbox']":
                return hidden_inputs
            raise AssertionError(selector)

        page.locator.side_effect = locate

        count = adapter.select_document_checkboxes(page)

        self.assertEqual(count, 1)
        combined.first.wait_for.assert_called_once_with(
            state="attached", timeout=60_000
        )
        box.click.assert_called_once_with()
        hidden_inputs.nth.assert_not_called()

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

    def test_clientes_beta_search_falls_back_in_required_order(self):
        adapter = self.make_adapter()
        calls = []
        adapter.search_by_rfc = lambda _page, value: calls.append(("rfc", value))
        adapter.search_by_policy = lambda _page, value: calls.append(("policy", value))
        adapter.search_by_name = lambda _page, value: calls.append(("name", value))
        label = MagicMock()
        adapter.wait_for_matching_policy = MagicMock(
            side_effect=[
                RuntimeError("no RFC result"),
                RuntimeError("no policy result"),
                label,
            ]
        )
        page = MagicMock()
        page.url = "https://agentes.metlife.mx/app/graph-clients"

        adapter.search_with_fallbacks(
            page,
            MetLifeGmmPortalTask(
                id="task",
                policy_number="1353851",
                original_policy_number="1066235",
                rfc="SABM7809274J4",
                client_name="JOSE MIGUEL SANCHEZ BAUTISTA",
            ),
            stop_after=None,
        )

        self.assertEqual(
            calls,
            [
                ("rfc", "SABM7809274J4"),
                ("policy", "1353851"),
                ("name", "JOSE MIGUEL SANCHEZ BAUTISTA"),
            ],
        )
        label.click.assert_called_once_with()
        self.assertEqual(
            [step.status for step in adapter.steps],
            ["failed", "failed", "completed"],
        )

    def test_search_closes_residual_menu_selects_visible_option_and_waits_for_close(self):
        adapter = self.make_adapter()
        page = MagicMock()

        residual_menu = MagicMock()
        opened_menu = MagicMock()
        menu_locator = MagicMock()
        menu_locator.count.side_effect = [1, 0, 1, 0]
        menu_locator.nth.side_effect = [residual_menu, opened_menu]
        menu_locator.last = opened_menu
        residual_menu.is_visible.return_value = True
        opened_menu.is_visible.return_value = True

        options = MagicMock()
        hidden_option = MagicMock()
        visible_option = MagicMock()
        options.count.return_value = 2
        options.nth.side_effect = [hidden_option, visible_option]
        hidden_option.is_visible.return_value = False
        visible_option.is_visible.return_value = True

        search_input = MagicMock()

        def locator(selector):
            if selector == "div.MuiPopover-root[role='presentation']":
                return menu_locator
            if selector == "#searchName":
                return search_input
            raise AssertionError(f"Unexpected selector: {selector}")

        page.locator.side_effect = locator
        page.get_by_role.return_value = options

        adapter.search(page, "RFC Contratante", " SABM7809274J4 ")

        page.keyboard.press.assert_called_once_with("Escape")
        residual_menu.wait_for.assert_called_once_with(state="hidden", timeout=5_000)
        page.get_by_role.assert_called_once_with(
            "option", name="RFC Contratante", exact=True
        )
        hidden_option.click.assert_not_called()
        visible_option.click.assert_called_once_with()
        opened_menu.wait_for.assert_has_calls(
            [
                unittest.mock.call(state="visible", timeout=5_000),
                unittest.mock.call(state="hidden", timeout=5_000),
            ]
        )
        search_input.fill.assert_has_calls(
            [unittest.mock.call(""), unittest.mock.call("SABM7809274J4")]
        )
        page.get_by_test_id.assert_called_once_with("searchIconId")

    def test_search_rejects_duplicate_visible_options(self):
        adapter = self.make_adapter()
        page = MagicMock()
        menu = MagicMock()
        menu.is_visible.return_value = True
        menu_locator = MagicMock()
        menu_locator.count.side_effect = [0, 0, 1]
        menu_locator.nth.return_value = menu

        first_option = MagicMock()
        second_option = MagicMock()
        first_option.is_visible.return_value = True
        second_option.is_visible.return_value = True
        options = MagicMock()
        options.count.return_value = 2
        options.nth.side_effect = [first_option, second_option]

        page.locator.return_value = menu_locator
        page.get_by_role.return_value = options

        with self.assertRaisesRegex(
            Exception, "una única opción visible 'RFC Contratante'"
        ):
            adapter.search(page, "RFC Contratante", "SABM7809274J4")

        first_option.click.assert_not_called()
        second_option.click.assert_not_called()

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
            combined = MagicMock()
            boxes = MagicMock()
            boxes.count.return_value = 0

            def locate(selector):
                if selector.startswith("input[type='checkbox'],"):
                    return combined
                if selector == ".mat-checkbox, mat-checkbox, [role='checkbox']":
                    return boxes
                if selector == "input[type='checkbox']":
                    return checkboxes
                raise AssertionError(selector)

            page.locator.side_effect = locate
            download = page.expect_download.return_value.__enter__.return_value.value
            download.suggested_filename = "documents.zip"

            adapter.download_documents(
                page,
                MetLifeGmmPortalTask(id="task", policy_number="123", rfc="RFC123"),
            )

            combined.first.wait_for.assert_called_once_with(
                state="attached", timeout=60_000
            )
            checked.evaluate.assert_not_called()
            unchecked.evaluate.assert_called_once_with("element => element.click()")
            download.save_as.assert_called_once()


if __name__ == "__main__":
    unittest.main()
