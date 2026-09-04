from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Literal

from services.drive_folder_naming import is_process_folder_for, process_folder_descriptor, process_folder_name
from services.client_folders import normalize_rfc, valid_client_rfc


METLIFE_PORTAL_URL = "https://agentes.metlife.mx/"
METLIFE_CLIENTES_BETA_URL = "https://agentes.metlife.mx/app/graph-clients"
TARGET_DRIVE_FOLDER_ID_ENV = "GOOGLE_DRIVE_RENEWALS_METLIFE_GMM_FOLDER_ID"
USERNAME_ENV = "METLIFE_AGENT_PORTAL_USERNAME"
PASSWORD_ENV = "METLIFE_AGENT_PORTAL_PASSWORD"
CHROME_PROFILE_ENV = "METLIFE_CHROME_PROFILE_DIR"
CHROME_CDP_PORT_ENV = "METLIFE_CHROME_CDP_PORT"
DEFAULT_CHROME_CDP_PORT = 9223
DEFAULT_CHROME_PATH = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

AdapterStopAfter = Literal[
    "login",
    "clientes_beta",
    "search_rfc",
    "search_policy",
    "search_name",
    "confirm_policy_match",
    "download_policy_document",
    "upload_to_drive",
]
SEARCH_RESULT_TIMEOUT_MS = 10_000
SEARCH_MENU_SELECTOR = "div.MuiPopover-root[role='presentation']"
SEARCH_MENU_CLOSE_TIMEOUT_MS = 5_000


@dataclass
class AdapterStepResult:
    step_name: str
    status: str
    started_at: str
    completed_at: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetLifeGmmPortalTask:
    id: str
    policy_number: str
    rfc: str
    client_name: str | None = None
    renewal_deadline: Any | None = None
    original_policy_number: str | None = None


@dataclass
class MetLifeGmmPortalResult:
    status: str
    task_id: str
    policy_number: str
    rfc: str
    steps: list[AdapterStepResult]
    downloaded_zip_path: str | None = None
    extracted_folder_path: str | None = None
    drive_folder_id: str | None = None
    drive_folder_link: str | None = None
    error_message: str | None = None


class MetLifePortalAdapterError(RuntimeError):
    pass


class MetLifePortalMfaRequired(MetLifePortalAdapterError):
    pass


def stable_chrome_profile_dir() -> Path:
    configured = os.getenv(CHROME_PROFILE_ENV)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Library/Application Support/Taiico/MetLife GMM Chrome"


def chrome_cdp_port() -> int:
    return int(os.getenv(CHROME_CDP_PORT_ENV, str(DEFAULT_CHROME_CDP_PORT)))


def chrome_cdp_url() -> str:
    return f"http://127.0.0.1:{chrome_cdp_port()}"


def chrome_server_ready() -> bool:
    try:
        with urllib.request.urlopen(f"{chrome_cdp_url()}/json/version", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def portal_page(context, target_url: str):
    """Reuse one persistent tab per portal host, creating it when absent."""
    target_host = urlparse(target_url).netloc.casefold()
    for page in context.pages:
        if urlparse(page.url or "").netloc.casefold() == target_host:
            return page
    page = context.new_page()
    page.goto(target_url, wait_until="domcontentloaded", timeout=90_000)
    return page


def ensure_persistent_chrome(profile_dir: Path) -> None:
    if chrome_server_ready():
        return
    if not DEFAULT_CHROME_PATH.exists():
        raise MetLifePortalAdapterError(f"Google Chrome was not found at {DEFAULT_CHROME_PATH}")
    profile_dir.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(DEFAULT_CHROME_PATH),
            f"--remote-debugging-port={chrome_cdp_port()}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={profile_dir}",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            METLIFE_PORTAL_URL,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(30):
        if chrome_server_ready():
            return
        time.sleep(0.5)
    raise MetLifePortalAdapterError("Persistent Chrome did not expose its local debugging endpoint")


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def sanitize_drive_name(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:180]


def renewal_folder_name(
    task: MetLifeGmmPortalTask,
    *,
    created_at: datetime | None = None,
) -> str:
    deadline = task.renewal_deadline
    year = deadline.year if hasattr(deadline, "year") else int(str(deadline or datetime.now().year)[:4])
    descriptor = sanitize_drive_name(
        f"Renovacion póliza {task.policy_number} {year} - {year + 1}"
    )
    return process_folder_name(descriptor, occurred_at=created_at)


def policy_digits(policy_number: str) -> str:
    return re.sub(r"\D+", "", str(policy_number or ""))


def policy_matches_text(policy_number: str, text: str) -> bool:
    wanted = policy_digits(policy_number)
    found = policy_digits(text)
    return bool(wanted and wanted in found)


def policy_candidate_match_score(
    candidate_text: str,
    current_policy_number: str,
    *original_policy_numbers: str,
) -> int:
    """Rank a Clientes Beta policy label without treating the ramo as policy data.

    MetLife renders labels such as ``02006 0000560034 MEDICALIFE``.  The first
    number is the ramo and the second is the policy.  On some renewals MetLife
    also replaces the leading renewal/consecutive digit, so the stable original
    policy is used as a suffix only when it contains at least five digits.
    """
    candidate_tokens = [
        token.lstrip("0") or "0"
        for token in re.findall(r"\d+", candidate_text or "")
    ]
    current = policy_digits(current_policy_number).lstrip("0") or "0"
    if current in candidate_tokens:
        return 3

    originals = {
        policy_digits(value).lstrip("0") or "0"
        for value in original_policy_numbers
        if policy_digits(value)
    }
    if any(original in candidate_tokens for original in originals):
        return 2
    if any(
        len(original) >= 5
        and len(token) > len(original)
        and token.endswith(original)
        for original in originals
        for token in candidate_tokens
    ):
        return 1
    return 0


def ensure_credentials(username: str | None = None, password: str | None = None) -> tuple[str, str]:
    username = username or os.getenv(USERNAME_ENV)
    password = password or os.getenv(PASSWORD_ENV)
    if not username or not password:
        raise MetLifePortalAdapterError(
            f"Missing MetLife credentials. Set {USERNAME_ENV} and {PASSWORD_ENV}."
        )
    return username, password


def create_drive_folder(service, parent_folder_id: str, name: str) -> dict[str, Any]:
    descriptor = process_folder_descriptor(name)
    existing = service.files().list(
        q=f"'{parent_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id,name,webViewLink,createdTime)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        pageSize=1000,
    ).execute().get("files", [])
    matches = [
        folder for folder in existing
        if is_process_folder_for(str(folder.get("name") or ""), descriptor)
    ]
    if matches:
        matches.sort(key=lambda folder: str(folder.get("createdTime") or ""))
        return matches[0]

    return service.files().create(
        body={
            "name": name,
            "parents": [parent_folder_id],
            "mimeType": "application/vnd.google-apps.folder",
        },
        fields="id,name,webViewLink",
        supportsAllDrives=True,
    ).execute()


def upload_folder_files_to_drive(service, local_folder: Path, drive_folder_id: str) -> list[dict[str, Any]]:
    from googleapiclient.http import MediaFileUpload

    uploaded = []
    for file_path in sorted(path for path in local_folder.rglob("*") if path.is_file()):
        media = MediaFileUpload(str(file_path), resumable=False)
        created = service.files().create(
            body={"name": file_path.name, "parents": [drive_folder_id]},
            media_body=media,
            fields="id,name,mimeType,webViewLink",
            supportsAllDrives=True,
        ).execute()
        uploaded.append(created)
    return uploaded


def build_drive_service():
    from google.auth import default
    from googleapiclient.discovery import build

    credentials, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


class MetLifeGmmPortalAdapter:
    def __init__(
        self,
        *,
        headless: bool = False,
        download_root: str | Path | None = None,
        username: str | None = None,
        password: str | None = None,
        session_profile_dir: str | Path | None = None,
    ):
        self.headless = headless
        self.download_root = Path(download_root or tempfile.mkdtemp(prefix="taiico-metlife-downloads-"))
        # Credentials are only required when the persistent browser is not
        # already authenticated. This lets scheduled runs reuse a valid portal
        # session without triggering a new login/MFA challenge.
        self.username = username or os.getenv(USERNAME_ENV)
        self.password = password or os.getenv(PASSWORD_ENV)
        self.session_profile_dir = Path(session_profile_dir or stable_chrome_profile_dir())
        self.steps: list[AdapterStepResult] = []

    def record_step(self, step_name: str, status: str = "started", **metadata):
        step = AdapterStepResult(step_name=step_name, status=status, started_at=now_iso(), metadata=metadata)
        self.steps.append(step)
        return step

    def complete_step(self, step: AdapterStepResult, status: str = "completed", **metadata):
        step.status = status
        step.completed_at = now_iso()
        step.metadata.update(metadata)

    def fail_step(self, step: AdapterStepResult, error: Exception | str):
        step.status = "failed"
        step.completed_at = now_iso()
        step.error_message = str(error)

    def maybe_stop(self, stop_after: AdapterStopAfter, step_name: str):
        if stop_after == step_name:
            raise StopIteration(step_name)

    @staticmethod
    def authenticated_app_session(page) -> bool:
        current_url = page.url if isinstance(page.url, str) else ""
        parsed = urlparse(current_url)
        return parsed.netloc.casefold() == "agentes.metlife.mx" and parsed.path.startswith("/app/")

    def prepare_clientes_beta(self, page) -> bool:
        """Open Clientes Beta while preserving an already authenticated SPA session."""
        reused_session = self.authenticated_app_session(page)
        if reused_session:
            if "/graph-clients" not in urlparse(page.url).path:
                page.goto(
                    METLIFE_CLIENTES_BETA_URL,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
            page.locator("#searchName").wait_for(state="visible", timeout=60_000)
            return True

        page.goto(METLIFE_PORTAL_URL, wait_until="domcontentloaded", timeout=60_000)
        self.login(page)
        self.open_clientes_beta(page)
        return False

    def run(
        self,
        task: MetLifeGmmPortalTask,
        *,
        stop_after: AdapterStopAfter | None = "confirm_policy_match",
        upload_to_drive: bool = False,
        target_drive_folder_id: str | None = None,
        resume_mfa: bool = False,
        mfa_code: str | None = None,
    ) -> MetLifeGmmPortalResult:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise MetLifePortalAdapterError("Playwright is not installed. Run pip install -r backend/requirements.txt.") from exc

        self.download_root.mkdir(parents=True, exist_ok=True)
        downloaded_zip_path: Path | None = None
        extracted_folder_path: Path | None = None
        drive_folder = None

        try:
            with sync_playwright() as p:
                ensure_persistent_chrome(self.session_profile_dir)
                browser = p.chromium.connect_over_cdp(chrome_cdp_url())
                context = browser.contexts[0]
                page = portal_page(context, METLIFE_PORTAL_URL)

                if resume_mfa:
                    step = self.record_step("continue_mfa", code_supplied=bool(mfa_code))
                    self.continue_mfa(page, mfa_code)
                    self.complete_step(step, current_url=page.url)
                else:
                    step = self.record_step("open_browser", url=METLIFE_PORTAL_URL)
                    reused_session = self.prepare_clientes_beta(page)
                    self.complete_step(step, current_url=page.url, reused_session=reused_session)
                    self.maybe_stop(stop_after, "open_browser")

                    step = self.record_step("authenticate_portal")
                    self.complete_step(step, current_url=page.url, reused_session=reused_session)
                    self.maybe_stop(stop_after, "login")

                step = self.record_step("clientes_beta")
                if resume_mfa:
                    self.open_clientes_beta(page)
                self.complete_step(step, current_url=page.url)
                self.maybe_stop(stop_after, "clientes_beta")

                self.search_with_fallbacks(page, task, stop_after=stop_after)

                step = self.record_step("confirm_policy_match", rfc=task.rfc, policy_number=task.policy_number)
                self.open_policy_documents(page)
                self.complete_step(step, current_url=page.url)
                self.maybe_stop(stop_after, "confirm_policy_match")

                step = self.record_step("download_policy_document")
                downloaded_zip_path = self.download_documents(page, task)
                self.complete_step(step, downloaded_zip_path=str(downloaded_zip_path))
                self.maybe_stop(stop_after, "download_policy_document")

                step = self.record_step("validate_download")
                extracted_folder_path = self.extract_download(downloaded_zip_path, task)
                self.complete_step(step, extracted_folder_path=str(extracted_folder_path))

                if upload_to_drive:
                    step = self.record_step("upload_to_drive")
                    parent_id = target_drive_folder_id or os.getenv(TARGET_DRIVE_FOLDER_ID_ENV)
                    if not parent_id:
                        raise MetLifePortalAdapterError(f"Missing target Drive folder id. Set {TARGET_DRIVE_FOLDER_ID_ENV}.")
                    service = build_drive_service()
                    drive_folder = create_drive_folder(service, parent_id, extracted_folder_path.name)
                    uploaded = upload_folder_files_to_drive(service, extracted_folder_path, drive_folder["id"])
                    self.complete_step(step, drive_folder=drive_folder, uploaded_files=uploaded)
                    self.maybe_stop(stop_after, "upload_to_drive")

            return MetLifeGmmPortalResult(
                status="completed" if downloaded_zip_path else "matched",
                task_id=task.id,
                policy_number=task.policy_number,
                rfc=task.rfc,
                steps=self.steps,
                downloaded_zip_path=str(downloaded_zip_path) if downloaded_zip_path else None,
                extracted_folder_path=str(extracted_folder_path) if extracted_folder_path else None,
                drive_folder_id=drive_folder["id"] if drive_folder else None,
                drive_folder_link=drive_folder.get("webViewLink") if drive_folder else None,
            )
        except StopIteration as stop:
            return MetLifeGmmPortalResult(
                status=f"stopped_after_{stop}",
                task_id=task.id,
                policy_number=task.policy_number,
                rfc=task.rfc,
                steps=self.steps,
                downloaded_zip_path=str(downloaded_zip_path) if downloaded_zip_path else None,
                extracted_folder_path=str(extracted_folder_path) if extracted_folder_path else None,
            )
        except MetLifePortalMfaRequired as exc:
            if self.steps and self.steps[-1].status == "started":
                self.complete_step(
                    self.steps[-1],
                    status="waiting_for_operator",
                    session_preserved=True,
                    current_url=page.url,
                )
                self.steps[-1].error_message = str(exc)
            return MetLifeGmmPortalResult(
                status="mfa_required",
                task_id=task.id,
                policy_number=task.policy_number,
                rfc=task.rfc,
                steps=self.steps,
                error_message=str(exc),
            )
        except Exception as exc:
            if self.steps and self.steps[-1].status == "started":
                self.fail_step(self.steps[-1], exc)
            return MetLifeGmmPortalResult(
                status="failed",
                task_id=task.id,
                policy_number=task.policy_number,
                rfc=task.rfc,
                steps=self.steps,
                downloaded_zip_path=str(downloaded_zip_path) if downloaded_zip_path else None,
                extracted_folder_path=str(extracted_folder_path) if extracted_folder_path else None,
                error_message=str(exc),
            )

    def login(self, page):
        self.username, self.password = ensure_credentials(
            self.username, self.password
        )
        for _ in range(60):
            body_text = page.locator("body").inner_text(timeout=10_000)
            if "Clientes Beta" in body_text:
                return
            if page.locator("#username").is_visible():
                break
            if "términos" in body_text.lower() or "terms and conditions" in body_text.lower():
                raise MetLifePortalMfaRequired(
                    "OPERATOR_ACTION_REQUIRED: accept the visible MetLife terms in the persistent Chrome window."
                )
            time.sleep(1)
        else:
            raise MetLifePortalAdapterError(f"Unknown MetLife login state at {page.url}")

        page.locator("#username").fill(self.username)
        page.locator("#password").fill(self.password)
        page.locator("#signOnButtonSpan").click()
        page.wait_for_load_state("networkidle", timeout=60_000)
        for _ in range(18):
            body_text = page.locator("body").inner_text(timeout=10_000)
            if "Clientes Beta" in body_text:
                return
            if "código" in body_text.lower() and "correo electrónico" in body_text.lower():
                raise MetLifePortalMfaRequired(
                    "MFA_REQUIRED: MetLife requested an email verification code before the portal dashboard."
                )
            time.sleep(5)
        page.wait_for_selector("text=Clientes Beta", timeout=5_000)

    def continue_mfa(self, page, mfa_code: str | None = None):
        """Continue the persisted portal session after the operator receives MFA."""
        if mfa_code:
            code_input = page.locator(
                "input[autocomplete='one-time-code'], input[name*='code' i], "
                "input[id*='code' i], input[type='tel']"
            ).first
            code_input.wait_for(state="visible", timeout=15_000)
            code_input.fill(mfa_code.strip())
            submit = page.get_by_role(
                "button", name=re.compile("verificar|validar|continuar|confirmar|enviar", re.I)
            ).first
            submit.click()

        # With no code, the operator may have completed MFA in the headed browser.
        page.wait_for_selector("text=Clientes Beta", timeout=120_000)

    def open_clientes_beta(self, page):
        buttons = page.get_by_role("button", name="Clientes Beta", exact=True)
        if buttons.count() and buttons.first.is_visible():
            buttons.first.click()
        else:
            page.get_by_text("Clientes Beta", exact=True).last.click()
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.wait_for_url(re.compile(r".*/graph-clients.*|.*/clients.*"), timeout=60_000)

    @staticmethod
    def _visible_locators(locator) -> list[Any]:
        visible = []
        for index in range(locator.count()):
            candidate = locator.nth(index)
            if candidate.is_visible():
                visible.append(candidate)
        return visible

    def close_residual_search_menu(self, page) -> None:
        """Dismiss any open Material UI search menu left by a prior attempt."""
        menus = self._visible_locators(page.locator(SEARCH_MENU_SELECTOR))
        for menu in menus:
            page.keyboard.press("Escape")
            try:
                menu.wait_for(state="hidden", timeout=SEARCH_MENU_CLOSE_TIMEOUT_MS)
            except Exception as exc:
                raise MetLifePortalAdapterError(
                    "El menú residual de 'Buscar por' no se pudo cerrar"
                ) from exc

        if self._visible_locators(page.locator(SEARCH_MENU_SELECTOR)):
            raise MetLifePortalAdapterError(
                "El menú residual de 'Buscar por' continúa visible"
            )

    def select_search_option(self, page, search_label: str) -> None:
        """Select exactly one visible option and wait until its menu is gone."""
        menu_locator = page.locator(SEARCH_MENU_SELECTOR)
        try:
            menu_locator.last.wait_for(
                state="visible", timeout=SEARCH_MENU_CLOSE_TIMEOUT_MS
            )
        except Exception as exc:
            raise MetLifePortalAdapterError(
                "El menú de 'Buscar por' no apareció"
            ) from exc

        visible_menus = self._visible_locators(menu_locator)
        if len(visible_menus) != 1:
            raise MetLifePortalAdapterError(
                "Se esperaba un único menú visible de 'Buscar por'; "
                f"se encontraron {len(visible_menus)}"
            )

        visible_options = self._visible_locators(
            page.get_by_role("option", name=search_label, exact=True)
        )
        if len(visible_options) != 1:
            raise MetLifePortalAdapterError(
                f"Se esperaba una única opción visible '{search_label}'; "
                f"se encontraron {len(visible_options)}"
            )

        visible_options[0].click()
        try:
            visible_menus[0].wait_for(
                state="hidden", timeout=SEARCH_MENU_CLOSE_TIMEOUT_MS
            )
        except Exception as exc:
            raise MetLifePortalAdapterError(
                f"El menú de 'Buscar por' no desapareció tras seleccionar "
                f"'{search_label}'"
            ) from exc

        if self._visible_locators(page.locator(SEARCH_MENU_SELECTOR)):
            raise MetLifePortalAdapterError(
                f"El menú de 'Buscar por' continúa visible tras seleccionar "
                f"'{search_label}'"
            )

    def search(self, page, search_label: str, value: str) -> None:
        value = " ".join(str(value or "").split())
        if not value:
            raise MetLifePortalAdapterError(
                f"No hay valor para buscar por {search_label}"
            )
        self.close_residual_search_menu(page)
        buscar = page.get_by_text("Buscar por", exact=True).first.locator("..")
        buscar.click()
        self.select_search_option(page, search_label)

        search_input = page.locator("#searchName")
        search_input.wait_for(state="visible", timeout=15_000)
        try:
            search_input.fill("")
            search_input.fill(value)
        except Exception:
            page.keyboard.press("Meta+A")
            page.keyboard.insert_text(value)
        page.get_by_test_id("searchIconId").click()

    def search_by_rfc(self, page, rfc: str):
        self.search(page, "RFC Contratante", rfc)

    def search_by_policy(self, page, policy_number: str):
        self.search(page, "No. de Póliza", policy_number)

    def search_by_name(self, page, client_name: str):
        self.search(page, "Contratante", client_name)

    def matching_policy_labels(self, page, *policy_numbers: str):
        supplied = [value for value in policy_numbers if policy_digits(value)]
        labels = page.locator("span").filter(has_text=re.compile("MEDICALIFE", re.I))
        candidates: list[tuple[int, Any]] = []
        for index in range(labels.count()):
            label = labels.nth(index)
            if not label.is_visible():
                continue
            text = label.inner_text(timeout=5_000)
            score = policy_candidate_match_score(text, supplied[0], *supplied[1:])
            if score:
                candidates.append((score, label))
        best_score = max((score for score, _ in candidates), default=0)
        return [label for score, label in candidates if score == best_score]

    def wait_for_matching_policy(self, page, *policy_numbers: str):
        deadline = time.monotonic() + (SEARCH_RESULT_TIMEOUT_MS / 1000)
        while time.monotonic() < deadline:
            best = self.matching_policy_labels(page, *policy_numbers)
            if len(best) == 1:
                return best[0]
            if len(best) > 1:
                break
            time.sleep(0.25)
        wanted = ", ".join(
            policy_digits(value).lstrip("0") or "0"
            for value in policy_numbers
            if policy_digits(value)
        )
        raise MetLifePortalAdapterError(
            f"Expected one matching GMM policy label for {wanted}; "
            f"found {len(self.matching_policy_labels(page, *policy_numbers))} matches."
        )

    def search_with_fallbacks(
        self,
        page,
        task: MetLifeGmmPortalTask,
        *,
        stop_after: AdapterStopAfter | None,
    ) -> None:
        attempts = []
        if valid_client_rfc(normalize_rfc(task.rfc)):
            attempts.append(("search_rfc", task.rfc, self.search_by_rfc))
        attempts.extend(
            [
                ("search_policy", task.policy_number, self.search_by_policy),
                ("search_name", task.client_name, self.search_by_name),
            ]
        )
        policy_numbers = (task.policy_number, task.original_policy_number or "")
        errors: list[str] = []
        for step_name, value, search in attempts:
            step = self.record_step(step_name, query=value)
            try:
                search(page, value)
                label = self.wait_for_matching_policy(page, *policy_numbers)
                label.click()
                page.get_by_text("Cobranza", exact=True).last.wait_for(
                    state="visible", timeout=SEARCH_RESULT_TIMEOUT_MS
                )
                self.complete_step(step, current_url=page.url, exact_policy_match=True)
                self.maybe_stop(stop_after, step_name)
                return
            except StopIteration:
                raise
            except Exception as exc:
                self.fail_step(step, exc)
                errors.append(f"{step_name}: {exc}")
        raise MetLifePortalAdapterError(
            "No se localizó la póliza en Clientes Beta tras RFC, póliza y nombre: "
            + " | ".join(errors)
        )

    def select_matching_policy(self, page, *policy_numbers: str):
        supplied = [value for value in policy_numbers if policy_digits(value)]
        if not supplied:
            raise MetLifePortalAdapterError("No policy number was supplied for the portal search.")
        self.wait_for_matching_policy(page, *supplied).click()
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.get_by_text("Cobranza", exact=True).last.wait_for(
            state="visible", timeout=60_000
        )

    def open_matching_policy(self, page, policy_number: str):
        self.select_matching_policy(page, policy_number)
        self.open_policy_documents(page)

    def open_policy_documents(self, page):
        page.get_by_text("Documentos de la póliza", exact=True).click()
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.get_by_text(re.compile(r"^Nombre del documento$", re.I)).last.wait_for(
            state="visible", timeout=60_000
        )

    def download_documents(self, page, task: MetLifeGmmPortalTask) -> Path:
        page.wait_for_selector("input[type='checkbox']", state="visible", timeout=60_000)
        checkboxes = page.locator("input[type='checkbox']")
        count = checkboxes.count()
        if count == 0:
            # Angular Material checkboxes often hide the input, so click visible checkbox boxes.
            boxes = page.locator(".mat-checkbox, mat-checkbox, [role='checkbox']")
            count = boxes.count()
            for index in range(count):
                boxes.nth(index).click()
        else:
            for index in range(count):
                checkbox = checkboxes.nth(index)
                if checkbox.is_visible() and not checkbox.is_checked():
                    checkbox.evaluate("element => element.click()")

        if count == 0:
            raise MetLifePortalAdapterError("No downloadable policy document checkboxes were found.")

        with page.expect_download(timeout=90_000) as download_info:
            page.get_by_role("button", name=re.compile("DESCARGAR|Descargar", re.I)).click()
        download = download_info.value
        suggested = sanitize_drive_name(download.suggested_filename or f"{task.rfc}_{task.policy_number}.zip")
        destination = self.download_root / suggested
        download.save_as(str(destination))
        return destination

    def extract_download(self, zip_path: Path, task: MetLifeGmmPortalTask) -> Path:
        if not zip_path.exists() or zip_path.stat().st_size == 0:
            raise MetLifePortalAdapterError(f"Downloaded file is missing or empty: {zip_path}")
        folder = self.download_root / renewal_folder_name(task)
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)

        if zipfile.is_zipfile(zip_path):
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(folder)
        else:
            shutil.copy2(zip_path, folder / zip_path.name)
        return folder


def result_to_dict(result: MetLifeGmmPortalResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "task_id": result.task_id,
        "policy_number": result.policy_number,
        "rfc": result.rfc,
        "steps": [step.__dict__ for step in result.steps],
        "downloaded_zip_path": result.downloaded_zip_path,
        "extracted_folder_path": result.extracted_folder_path,
        "drive_folder_id": result.drive_folder_id,
        "drive_folder_link": result.drive_folder_link,
        "error_message": result.error_message,
    }
