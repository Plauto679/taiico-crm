from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from adapters.metlife_gmm_portal import (
    AdapterStepResult,
    METLIFE_PORTAL_URL,
    MetLifeGmmPortalAdapter,
    MetLifeGmmPortalTask,
    MetLifePortalMfaRequired,
    chrome_cdp_url,
    ensure_persistent_chrome,
    portal_page,
)


COLLECTION_FAILURE_DATE = date(2000, 1, 1)


@dataclass
class MetLifeGmmCollectionResult:
    status: str
    task_id: str
    policy_number: str
    rfc: str
    paid_until: date | None
    steps: list[AdapterStepResult]
    error_message: str | None = None


def parse_paid_until(value: str) -> date:
    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", value or "")
    if match:
        day, month, year = (int(item) for item in match.groups())
        return date(year, month, day)
    match = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", value or "")
    if match:
        year, month, day = (int(item) for item in match.groups())
        return date(year, month, day)
    raise ValueError(f"No se pudo interpretar Pagado Hasta: {value!r}")


class MetLifeGmmCollectionAdapter(MetLifeGmmPortalAdapter):
    """Independent read-only collector for the new MetLife agent portal."""

    def check(self, task: MetLifeGmmPortalTask) -> MetLifeGmmCollectionResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed") from exc

        self.steps = []
        paid_until: date | None = None
        page = None
        try:
            with sync_playwright() as playwright:
                ensure_persistent_chrome(self.session_profile_dir)
                browser = playwright.chromium.connect_over_cdp(chrome_cdp_url())
                context = browser.contexts[0]
                page = portal_page(context, METLIFE_PORTAL_URL)

                step = self.record_step("collection_open_new_portal", url=METLIFE_PORTAL_URL)
                page.goto(METLIFE_PORTAL_URL, wait_until="domcontentloaded", timeout=90_000)
                self.complete_step(step, current_url=page.url)

                step = self.record_step("collection_authenticate")
                self.login(page)
                self.complete_step(step, current_url=page.url)

                step = self.record_step("collection_open_clientes_beta")
                self.open_clientes_beta(page)
                self.complete_step(step, current_url=page.url)

                step = self.record_step("collection_search_rfc", rfc=task.rfc)
                self.search_by_rfc(page, task.rfc)
                self.complete_step(step, current_url=page.url)

                step = self.record_step(
                    "collection_select_policy",
                    policy_number=task.policy_number,
                    original_policy_number=task.original_policy_number,
                )
                self.select_matching_policy(
                    page,
                    task.policy_number,
                    task.original_policy_number or "",
                )
                self.complete_step(step, current_url=page.url)

                step = self.record_step("collection_read_paid_until")
                paid_until = self.read_paid_until(page)
                self.complete_step(step, paid_until=paid_until.isoformat())

            return MetLifeGmmCollectionResult(
                status="completed",
                task_id=task.id,
                policy_number=task.policy_number,
                rfc=task.rfc,
                paid_until=paid_until,
                steps=self.steps,
            )
        except MetLifePortalMfaRequired as exc:
            if self.steps and self.steps[-1].status == "started":
                self.complete_step(
                    self.steps[-1],
                    status="waiting_for_operator",
                    current_url=page.url if page else None,
                )
                self.steps[-1].error_message = str(exc)
            return self._failed_result(task, exc)
        except Exception as exc:
            if self.steps and self.steps[-1].status == "started":
                self.fail_step(self.steps[-1], exc)
            return self._failed_result(task, exc)

    def _failed_result(
        self,
        task: MetLifeGmmPortalTask,
        error: Exception,
    ) -> MetLifeGmmCollectionResult:
        return MetLifeGmmCollectionResult(
            status="failed",
            task_id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            paid_until=None,
            steps=self.steps,
            error_message=str(error),
        )

    def read_paid_until(self, page) -> date:
        cobranza = page.get_by_text("Cobranza", exact=True).last
        cobranza.click()
        page.wait_for_load_state("networkidle", timeout=60_000)

        label = page.get_by_text(re.compile(r"^PAGADO\s+HASTA$", re.I)).last
        label.wait_for(state="visible", timeout=60_000)
        label.scroll_into_view_if_needed()
        for parent_path in ("..", "../..", "../../.."):
            text = label.locator(f"xpath={parent_path}").inner_text(timeout=5_000)
            try:
                return parse_paid_until(text)
            except ValueError:
                continue
        raise ValueError("La sección Cobranza no mostró una fecha Pagado Hasta válida")


def collection_result_to_dict(result: MetLifeGmmCollectionResult) -> dict:
    return {
        "status": result.status,
        "task_id": result.task_id,
        "policy_number": result.policy_number,
        "rfc": result.rfc,
        "paid_until": result.paid_until.isoformat() if result.paid_until else None,
        "steps": [step.__dict__ for step in result.steps],
        "error_message": result.error_message,
        "checked_at": datetime.now(UTC).isoformat(),
    }


def check_metlife_gmm_collection(
    task: MetLifeGmmPortalTask,
    **adapter_options,
) -> MetLifeGmmCollectionResult:
    """Reusable entry point for any module that needs MetLife GMM collection data."""
    return MetLifeGmmCollectionAdapter(**adapter_options).check(task)
