from __future__ import annotations

import os
import re
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


METLIFE_PORTAL_URL = "https://agentes.metlife.mx/"
TARGET_DRIVE_FOLDER_ID_ENV = "GOOGLE_DRIVE_RENEWALS_METLIFE_GMM_FOLDER_ID"
USERNAME_ENV = "METLIFE_AGENT_PORTAL_USERNAME"
PASSWORD_ENV = "METLIFE_AGENT_PORTAL_PASSWORD"

AdapterStopAfter = Literal[
    "login",
    "clientes_beta",
    "search_policy",
    "confirm_policy_match",
    "download_policy_document",
    "upload_to_drive",
]


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


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def sanitize_drive_name(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:180]


def renewal_folder_name(task: MetLifeGmmPortalTask) -> str:
    deadline = task.renewal_deadline.isoformat() if hasattr(task.renewal_deadline, "isoformat") else str(task.renewal_deadline or "unknown-period")
    return sanitize_drive_name(f"{task.rfc}_{task.policy_number}_{deadline}")


def policy_digits(policy_number: str) -> str:
    return re.sub(r"\D+", "", str(policy_number or ""))


def policy_matches_text(policy_number: str, text: str) -> bool:
    wanted = policy_digits(policy_number)
    found = policy_digits(text)
    return bool(wanted and wanted in found)


def ensure_credentials(username: str | None = None, password: str | None = None) -> tuple[str, str]:
    username = username or os.getenv(USERNAME_ENV)
    password = password or os.getenv(PASSWORD_ENV)
    if not username or not password:
        raise MetLifePortalAdapterError(
            f"Missing MetLife credentials. Set {USERNAME_ENV} and {PASSWORD_ENV}."
        )
    return username, password


def create_drive_folder(service, parent_folder_id: str, name: str) -> dict[str, Any]:
    existing = service.files().list(
        q=f"'{parent_folder_id}' in parents and name = '{name.replace(chr(39), chr(92) + chr(39))}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
        fields="files(id,name,webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        pageSize=10,
    ).execute().get("files", [])
    if existing:
        return existing[0]

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
    ):
        self.headless = headless
        self.download_root = Path(download_root or tempfile.mkdtemp(prefix="taiico-metlife-downloads-"))
        self.username, self.password = ensure_credentials(username, password)
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

    def run(
        self,
        task: MetLifeGmmPortalTask,
        *,
        stop_after: AdapterStopAfter = "confirm_policy_match",
        upload_to_drive: bool = False,
        target_drive_folder_id: str | None = None,
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
                browser = p.chromium.launch(channel="chrome", headless=self.headless)
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()

                step = self.record_step("open_browser", url=METLIFE_PORTAL_URL)
                page.goto(METLIFE_PORTAL_URL, wait_until="domcontentloaded", timeout=60_000)
                self.complete_step(step, current_url=page.url)
                self.maybe_stop(stop_after, "open_browser")

                step = self.record_step("authenticate_portal")
                self.login(page)
                self.complete_step(step, current_url=page.url)
                self.maybe_stop(stop_after, "login")

                step = self.record_step("clientes_beta")
                self.open_clientes_beta(page)
                self.complete_step(step, current_url=page.url)
                self.maybe_stop(stop_after, "clientes_beta")

                step = self.record_step("search_policy", rfc=task.rfc, policy_number=task.policy_number)
                self.search_by_rfc(page, task.rfc)
                self.complete_step(step, current_url=page.url)
                self.maybe_stop(stop_after, "search_policy")

                step = self.record_step("confirm_policy_match", rfc=task.rfc, policy_number=task.policy_number)
                self.open_matching_policy(page, task.policy_number)
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

                context.close()
                browser.close()

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
        page.wait_for_selector("#username", timeout=60_000)
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

    def open_clientes_beta(self, page):
        page.get_by_text("Clientes Beta", exact=True).click()
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.wait_for_url(re.compile(r".*/graph-clients.*|.*/clients.*"), timeout=60_000)

    def search_by_rfc(self, page, rfc: str):
        buscar = page.get_by_text(re.compile("Buscar por", re.I)).locator("..")
        buscar.click()
        page.get_by_text("RFC Contratante", exact=True).click()

        search_input = page.locator("input").filter(has_not_text="").last
        try:
            search_input.fill(rfc)
        except Exception:
            page.keyboard.insert_text(rfc)
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.wait_for_selector(f"text={rfc}", timeout=60_000)

    def open_matching_policy(self, page, policy_number: str):
        wanted = policy_digits(policy_number)
        cards = page.locator("text=/PÓLIZAS|POLIZAS/i").locator("xpath=ancestor::*[contains(@class, 'card') or contains(@class, 'mat-card') or self::div][1]")
        count = cards.count()
        candidates = []
        for index in range(count):
            card = cards.nth(index)
            text = card.inner_text(timeout=5_000)
            if policy_matches_text(wanted, text):
                candidates.append((index, text))
        if not candidates:
            # Fallback: find any visible text containing policy digits and click its nearest card/container.
            match = page.get_by_text(re.compile(wanted)).first
            match.wait_for(timeout=15_000)
            match.click()
        else:
            cards.nth(candidates[0][0]).click()

        page.wait_for_load_state("networkidle", timeout=60_000)
        page.get_by_text("Documentos de la póliza", exact=True).click()
        page.wait_for_load_state("networkidle", timeout=60_000)
        page.wait_for_selector("text=Nombre del documento", timeout=60_000)

    def download_documents(self, page, task: MetLifeGmmPortalTask) -> Path:
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
                if checkbox.is_visible():
                    checkbox.check()

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
