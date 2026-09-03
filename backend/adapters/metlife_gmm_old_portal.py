from __future__ import annotations

import os
import re
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from adapters.metlife_gmm_portal import (
    AdapterStepResult,
    MetLifeGmmPortalAdapter,
    MetLifeGmmPortalResult,
    MetLifeGmmPortalTask,
    MetLifePortalAdapterError,
    build_drive_service,
    chrome_cdp_url,
    ensure_persistent_chrome,
    ensure_credentials,
    now_iso,
    portal_page,
    policy_digits,
    sanitize_drive_name,
)
from services.client_folders import (
    FOLDER_MIME_TYPE,
    client_folder_creation_lock,
    client_folders_parent_id,
    normalize_client_name,
    normalize_rfc,
    safe_folder_component,
    valid_client_rfc,
)
from services.drive_folder_naming import is_process_folder_for, process_folder_name


METLIFE_OLD_PORTAL_URL = (
    "https://servicios.metlife.com.mx/wps/portal/agentes/!ut/p/a1/"
    "04_Sj9CPykssy0xPLMnMz0vM0Q_0yU9PT03xLy3RL0hXVAQAEl7pog!!/"
)
OLD_PORTAL_ADAPTER_NAME = "metlife_gmm_old_portal"
CLIENT_FOLDERS_PARENT_ID_ENV = "GOOGLE_DRIVE_CLIENT_FOLDERS_PARENT_ID"

OldPortalStopAfter = Literal[
    "login",
    "open_contractual_search",
    "search_rfc",
    "search_policy",
    "search_name",
    "confirm_policy_match",
    "download_documents",
    "upload_to_client_folder",
]


RFC_PATTERN = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b", re.I)
SEARCH_RESULT_TIMEOUT_MS = 10_000


def canonical_policy_number(value: object) -> str:
    digits = policy_digits(str(value or ""))
    return (digits.lstrip("0") or "0") if digits else ""


def portal_policy_number(task: MetLifeGmmPortalTask) -> str:
    """The old portal indexes renewals by POLORIG, not by the renewed NPOLIZA."""
    return canonical_policy_number(task.original_policy_number or task.policy_number)


def policy_row_matches(row_text: str, task: MetLifeGmmPortalTask) -> bool:
    wanted = portal_policy_number(task)
    if not wanted:
        return False
    tokens = re.findall(r"\d+", row_text or "")
    return any(canonical_policy_number(token) == wanted for token in tokens)


def client_folder_name(task: MetLifeGmmPortalTask) -> str:
    rfc = normalize_rfc(task.rfc)
    if not valid_client_rfc(rfc):
        raise MetLifePortalAdapterError(f"RFC inválido para carpeta de cliente: {task.rfc}")
    name = normalize_client_name(task.client_name, rfc)
    if not name:
        raise MetLifePortalAdapterError("No hay nombre de cliente para crear su carpeta")
    return f"{rfc} - {safe_folder_component(name)}"


def _drive_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def find_or_create_client_folder(service, task: MetLifeGmmPortalTask) -> dict[str, Any]:
    parent_id = os.getenv(CLIENT_FOLDERS_PARENT_ID_ENV, "").strip() or client_folders_parent_id()
    rfc = normalize_rfc(task.rfc)
    with client_folder_creation_lock(rfc):
        response = service.files().list(
            q=(
                f"'{_drive_literal(parent_id)}' in parents and "
                f"mimeType = '{FOLDER_MIME_TYPE}' and trashed = false"
            ),
            fields="files(id,name,webViewLink)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1000,
        ).execute()
        matches = [
            item for item in response.get("files", [])
            if normalize_rfc(str(item.get("name", "")).split(" - ", 1)[0]) == rfc
        ]
        if len(matches) > 1:
            raise MetLifePortalAdapterError(f"Hay múltiples carpetas de cliente para el RFC {rfc}")
        if matches:
            return matches[0]
        return service.files().create(
            body={
                "name": client_folder_name(task),
                "mimeType": FOLDER_MIME_TYPE,
                "parents": [parent_id],
            },
            fields="id,name,webViewLink",
            supportsAllDrives=True,
        ).execute()


def renewal_folder_descriptor(task: MetLifeGmmPortalTask) -> str:
    deadline = task.renewal_deadline
    year = deadline.year if hasattr(deadline, "year") else int(str(deadline)[:4])
    return f"Renovacion póliza {task.policy_number} {year} - {year + 1}"


def renewal_folder_name(
    task: MetLifeGmmPortalTask,
    *,
    created_at: datetime | None = None,
) -> str:
    return process_folder_name(
        renewal_folder_descriptor(task),
        occurred_at=created_at,
    )


def find_or_create_renewal_folder(
    service,
    client_folder_id: str,
    task: MetLifeGmmPortalTask,
) -> dict[str, Any]:
    descriptor = renewal_folder_descriptor(task)
    response = service.files().list(
        q=(
            f"'{_drive_literal(client_folder_id)}' in parents and "
            f"mimeType = '{FOLDER_MIME_TYPE}' and trashed = false"
        ),
        fields="files(id,name,webViewLink,createdTime)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        pageSize=1000,
    ).execute()
    matches = [
        folder for folder in response.get("files", [])
        if is_process_folder_for(str(folder.get("name") or ""), descriptor)
    ]
    if matches:
        matches.sort(key=lambda folder: str(folder.get("createdTime") or ""))
        return matches[0]
    name = renewal_folder_name(task)
    return service.files().create(
        body={
            "name": name,
            "mimeType": FOLDER_MIME_TYPE,
            "parents": [client_folder_id],
        },
        fields="id,name,webViewLink",
        supportsAllDrives=True,
    ).execute()


def upload_files_idempotently(service, local_folder: Path, drive_folder_id: str) -> list[dict[str, Any]]:
    from googleapiclient.http import MediaFileUpload

    existing = service.files().list(
        q=f"'{_drive_literal(drive_folder_id)}' in parents and trashed = false",
        fields="files(id,name,mimeType,webViewLink)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        pageSize=1000,
    ).execute().get("files", [])
    by_name = {item["name"]: item for item in existing if item.get("name")}
    uploaded: list[dict[str, Any]] = []
    for path in sorted(item for item in local_folder.rglob("*") if item.is_file()):
        media = MediaFileUpload(str(path), resumable=False)
        if path.name in by_name:
            result = service.files().update(
                fileId=by_name[path.name]["id"],
                media_body=media,
                fields="id,name,mimeType,webViewLink",
                supportsAllDrives=True,
            ).execute()
        else:
            result = service.files().create(
                body={"name": path.name, "parents": [drive_folder_id]},
                media_body=media,
                fields="id,name,mimeType,webViewLink",
                supportsAllDrives=True,
            ).execute()
        uploaded.append(result)
    return uploaded


class MetLifeGmmOldPortalAdapter(MetLifeGmmPortalAdapter):
    """Adapter for Consultas > Doc. Contractual in the legacy agent portal."""

    def run(
        self,
        task: MetLifeGmmPortalTask,
        *,
        stop_after: OldPortalStopAfter | None = "confirm_policy_match",
        upload_to_drive: bool = False,
    ) -> MetLifeGmmPortalResult:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise MetLifePortalAdapterError("Playwright no está instalado") from exc

        self.steps = []
        self.download_root.mkdir(parents=True, exist_ok=True)
        downloaded: Path | None = None
        extracted: Path | None = None
        drive_folder: dict[str, Any] | None = None
        try:
            with sync_playwright() as playwright:
                ensure_persistent_chrome(self.session_profile_dir)
                browser = playwright.chromium.connect_over_cdp(chrome_cdp_url())
                context = browser.contexts[0]
                page = portal_page(context, METLIFE_OLD_PORTAL_URL)

                step = self.record_step("open_old_portal", url=METLIFE_OLD_PORTAL_URL)
                reused_session = self.contractual_search_ready(page)
                if not reused_session:
                    page.goto(METLIFE_OLD_PORTAL_URL, wait_until="domcontentloaded", timeout=90_000)
                self.complete_step(step, current_url=page.url, reused_session=reused_session)

                step = self.record_step("authenticate_old_portal")
                if not reused_session:
                    self.login_old_portal(page)
                self.complete_step(step, current_url=page.url, reused_session=reused_session)
                if stop_after == "login":
                    raise StopIteration(stop_after)

                step = self.record_step("open_contractual_search")
                if not reused_session:
                    self.open_contractual_search(page)
                self.complete_step(step, current_url=page.url, reused_session=reused_session)
                if stop_after == "open_contractual_search":
                    raise StopIteration(stop_after)

                self.search_with_fallbacks(page, task, stop_after=stop_after)

                step = self.record_step(
                    "confirm_policy_match",
                    renewed_policy_number=task.policy_number,
                    original_policy_number=task.original_policy_number,
                    portal_policy_number=portal_policy_number(task),
                )
                self.open_policy_documents(page, task)
                self.complete_step(step, current_url=page.url)
                if stop_after == "confirm_policy_match":
                    raise StopIteration(stop_after)

                step = self.record_step("download_documents")
                downloaded = self.download_all_documents(page, task)
                extracted = self.extract_download_safely(downloaded, task)
                self.complete_step(
                    step,
                    downloaded_zip_path=str(downloaded),
                    extracted_folder_path=str(extracted),
                )
                if stop_after == "download_documents":
                    raise StopIteration(stop_after)

                if upload_to_drive:
                    step = self.record_step("upload_to_client_folder")
                    service = build_drive_service()
                    client_folder = find_or_create_client_folder(service, task)
                    drive_folder = find_or_create_renewal_folder(
                        service,
                        client_folder["id"],
                        task,
                    )
                    uploads = upload_files_idempotently(service, extracted, drive_folder["id"])
                    self.complete_step(
                        step,
                        client_folder=client_folder,
                        drive_folder=drive_folder,
                        uploaded_files=uploads,
                    )
                    if stop_after == "upload_to_client_folder":
                        raise StopIteration(stop_after)

            return self._result("completed", task, downloaded, extracted, drive_folder)
        except StopIteration as stop:
            return self._result(f"stopped_after_{stop}", task, downloaded, extracted, drive_folder)
        except Exception as exc:
            if self.steps and self.steps[-1].status == "started":
                self.fail_step(self.steps[-1], exc)
            return self._result("failed", task, downloaded, extracted, drive_folder, str(exc))

    def _result(
        self,
        status: str,
        task: MetLifeGmmPortalTask,
        downloaded: Path | None,
        extracted: Path | None,
        drive_folder: dict[str, Any] | None,
        error: str | None = None,
    ) -> MetLifeGmmPortalResult:
        return MetLifeGmmPortalResult(
            status=status,
            task_id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            steps=self.steps,
            downloaded_zip_path=str(downloaded) if downloaded else None,
            extracted_folder_path=str(extracted) if extracted else None,
            drive_folder_id=drive_folder.get("id") if drive_folder else None,
            drive_folder_link=drive_folder.get("webViewLink") if drive_folder else None,
            error_message=error,
        )

    def login_old_portal(self, page) -> None:
        self.username, self.password = ensure_credentials(
            self.username, self.password
        )
        body = page.locator("body")
        for _ in range(90):
            text = body.inner_text(timeout=10_000)
            if "Consultas" in text and "Admon. de Cartera" in text:
                return
            visible_inputs = page.locator("input:visible")
            if visible_inputs.count() >= 2 and "Ingresar" in text:
                break
            time.sleep(1)
        else:
            raise MetLifePortalAdapterError(f"Estado de acceso desconocido en {page.url}")

        inputs = page.locator("input:visible")
        password = page.locator("input[type='password']:visible").first
        user = page.locator("input[type='text']:visible").first
        if user.count() == 0:
            user = inputs.first
        user.fill(self.username)
        password.fill(self.password)
        page.get_by_role("button", name="Ingresar", exact=True).click()
        page.get_by_text("Consultas", exact=True).wait_for(state="visible", timeout=90_000)

    def open_contractual_search(self, page) -> None:
        consultas = page.get_by_text("Consultas", exact=True).first
        consultas.hover()
        contractual = page.get_by_text(re.compile(r"^Doc\.\s*Contractual$", re.I)).first
        contractual.wait_for(state="visible", timeout=15_000)
        contractual.hover()
        contractual.click()
        page.get_by_text(
            re.compile(r"B[uú]squeda de documentaci[oó]n contractual", re.I)
        ).wait_for(state="visible", timeout=90_000)

    @staticmethod
    def contractual_search_ready(page) -> bool:
        try:
            return page.locator("#rfc").is_visible()
        except Exception:
            return False

    def search_rfc(self, page, rfc: str) -> None:
        normalized = normalize_rfc(rfc)
        if not valid_client_rfc(normalized):
            raise MetLifePortalAdapterError(f"RFC inválido para búsqueda: {rfc}")
        rfc_input = page.locator("#rfc")
        rfc_input.wait_for(state="visible", timeout=15_000)
        self.clear_search_fields(page)
        rfc_input.fill(normalized)
        page.get_by_role("button", name="Consultar", exact=True).click()

    def search_policy(self, page, policy_number: str) -> None:
        normalized = canonical_policy_number(policy_number)
        if not normalized:
            raise MetLifePortalAdapterError("No hay número de póliza para la búsqueda")
        candidates = (
            "#pol",
            "#poliza",
            "#policy",
            "input[placeholder*='Póliza' i]",
            "input[placeholder*='Poliza' i]",
            "input[name='pol']",
            "input[name='poliza']",
            "input[name*='poliza' i]",
        )
        policy_input = None
        for selector in candidates:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                policy_input = locator
                break
        if policy_input is None:
            try:
                labelled = page.get_by_label(re.compile(r"^P[oó]liza$", re.I)).first
                if labelled.count() and labelled.is_visible():
                    policy_input = labelled
            except Exception:
                policy_input = None
        if policy_input is None:
            raise MetLifePortalAdapterError("No se encontró el campo Póliza en el portal viejo")
        self.clear_search_fields(page)
        policy_input.fill(normalized)
        page.get_by_role("button", name="Consultar", exact=True).click()

    def search_name(self, page, client_name: str | None) -> None:
        normalized = " ".join(str(client_name or "").split())
        if not normalized:
            raise MetLifePortalAdapterError("No hay nombre de contratante para la búsqueda")
        candidates = (
            "#nombre",
            "#contratante",
            "input[placeholder*='Nombre/Contr' i]",
            "input[name*='nombre' i]",
            "input[name*='contratante' i]",
        )
        name_input = None
        for selector in candidates:
            locator = page.locator(selector).first
            if locator.count() and locator.is_visible():
                name_input = locator
                break
        if name_input is None:
            try:
                labelled = page.get_by_label(
                    re.compile(r"Nombre\s*/?\s*Contr|Contratante", re.I)
                ).first
                if labelled.count() and labelled.is_visible():
                    name_input = labelled
            except Exception:
                name_input = None
        if name_input is None:
            raise MetLifePortalAdapterError(
                "No se encontró el campo Nombre/Contratante en el portal viejo"
            )
        self.clear_search_fields(page)
        name_input.fill(normalized)
        page.get_by_role("button", name="Consultar", exact=True).click()

    @staticmethod
    def clear_search_fields(page) -> None:
        for index in range(page.locator("input:visible").count()):
            field = page.locator("input:visible").nth(index)
            try:
                if field.is_editable():
                    field.fill("")
            except Exception:
                continue

    def matching_policy_rows(
        self,
        page,
        task: MetLifeGmmPortalTask,
        *,
        require_task_rfc: bool = True,
    ):
        rows = page.locator("table tbody tr[role='row']")
        matches: list[tuple[Any, str]] = []
        expected_rfc = normalize_rfc(task.rfc)
        require_rfc_match = require_task_rfc and valid_client_rfc(expected_rfc)
        for index in range(rows.count()):
            row = rows.nth(index)
            text = row.inner_text(timeout=5_000)
            if not policy_row_matches(text, task):
                continue
            row_rfcs = [normalize_rfc(item) for item in RFC_PATTERN.findall(text)]
            if require_rfc_match and expected_rfc not in row_rfcs:
                continue
            matches.append((row, row_rfcs[0] if len(set(row_rfcs)) == 1 else ""))
        return matches

    def wait_for_matching_policy_rows(
        self,
        page,
        task: MetLifeGmmPortalTask,
        *,
        require_task_rfc: bool,
    ):
        deadline = time.monotonic() + (SEARCH_RESULT_TIMEOUT_MS / 1000)
        matches = []
        while time.monotonic() < deadline:
            matches = self.matching_policy_rows(
                page,
                task,
                require_task_rfc=require_task_rfc,
            )
            if len(matches) == 1:
                return matches
            if len(matches) > 1:
                break
            time.sleep(0.25)
        return matches

    def search_with_fallbacks(
        self,
        page,
        task: MetLifeGmmPortalTask,
        *,
        stop_after: OldPortalStopAfter | None,
    ) -> None:
        attempts = []
        if valid_client_rfc(normalize_rfc(task.rfc)):
            attempts.append(("search_rfc", task.rfc, self.search_rfc))
        attempts.extend(
            [
                ("search_policy", portal_policy_number(task), self.search_policy),
                ("search_name", task.client_name, self.search_name),
            ]
        )
        errors: list[str] = []
        for step_name, value, search in attempts:
            step = self.record_step(step_name, query=value)
            try:
                search(page, value)
                matches = self.wait_for_matching_policy_rows(
                    page,
                    task,
                    require_task_rfc=step_name == "search_rfc",
                )
                if len(matches) != 1:
                    raise MetLifePortalAdapterError(
                        f"la búsqueda produjo {len(matches)} coincidencias exactas de póliza"
                    )
                recovered_rfc = matches[0][1]
                if step_name != "search_rfc" and valid_client_rfc(recovered_rfc):
                    task.rfc = recovered_rfc
                self.complete_step(
                    step,
                    current_url=page.url,
                    exact_policy_match=True,
                    recovered_rfc=recovered_rfc or None,
                )
                if stop_after == step_name:
                    raise StopIteration(stop_after)
                return
            except StopIteration:
                raise
            except Exception as exc:
                self.fail_step(step, exc)
                errors.append(f"{step_name}: {exc}")
        raise MetLifePortalAdapterError(
            "No se localizó la póliza en el portal antiguo tras RFC, póliza y nombre: "
            + " | ".join(errors)
        )

    def open_policy_documents(self, page, task: MetLifeGmmPortalTask) -> None:
        # DataTables nests the result table inside layout tables whose parent
        # rows repeat the complete result text. Only role="row" entries are
        # actual policy records and may be used for an exact match.
        matches = self.matching_policy_rows(page, task)
        require_rfc_match = valid_client_rfc(normalize_rfc(task.rfc))
        if len(matches) != 1:
            raise MetLifePortalAdapterError(
                f"Se esperó una póliza original {portal_policy_number(task)} para {task.rfc}; "
                f"se encontraron {len(matches)} coincidencias"
            )
        row, recovered_rfc = matches[0]
        if not require_rfc_match:
            if not valid_client_rfc(recovered_rfc):
                raise MetLifePortalAdapterError(
                    f"Se encontró la póliza original {portal_policy_number(task)}, "
                    "pero no fue posible recuperar un RFC único"
                )
            task.rfc = recovered_rfc
        links = row.locator("a")
        if links.count():
            links.last.click()
        else:
            row.locator("img, [role='button'], input[type='image']").last.click()
        page.get_by_text(
            re.compile(r"Informaci[oó]n de P[oó]liza y Documentos Digitales", re.I)
        ).wait_for(state="visible", timeout=90_000)

    def download_all_documents(self, page, task: MetLifeGmmPortalTask) -> Path:
        checkboxes = page.locator("input[type='checkbox']:visible")
        if checkboxes.count() == 0:
            raise MetLifePortalAdapterError("No se encontraron documentos seleccionables")
        for index in range(checkboxes.count()):
            checkbox = checkboxes.nth(index)
            if checkbox.is_enabled() and not checkbox.is_checked():
                checkbox.check(force=True)

        download_dir = self.download_root / sanitize_drive_name(
            f"old_portal_{normalize_rfc(task.rfc)}_{task.policy_number}_{int(time.time())}"
        )
        download_dir.mkdir(parents=True, exist_ok=True)
        cdp = page.context.new_cdp_session(page)
        cdp.send(
            "Page.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir)},
        )
        before = {item.name for item in download_dir.iterdir()}
        page.get_by_role("button", name="Descargar", exact=True).click(no_wait_after=True)

        deadline = time.monotonic() + 120
        downloaded: Path | None = None
        while time.monotonic() < deadline:
            candidates = [
                item
                for item in download_dir.iterdir()
                if item.is_file()
                and item.name not in before
                and not item.name.endswith(".crdownload")
            ]
            if candidates:
                downloaded = max(candidates, key=lambda item: item.stat().st_mtime)
                if downloaded.stat().st_size > 0:
                    break
            time.sleep(1)
        if downloaded is None:
            raise MetLifePortalAdapterError("No se recibió la descarga del portal antiguo")
        filename = sanitize_drive_name(downloaded.name or f"{normalize_rfc(task.rfc)}_{task.policy_number}.zip")
        destination = self.download_root / filename
        if destination.exists():
            destination = self.download_root / sanitize_drive_name(
                f"{destination.stem}_{int(time.time())}{destination.suffix}"
            )
        shutil.move(str(downloaded), str(destination))
        return destination

    def extract_download_safely(self, archive: Path, task: MetLifeGmmPortalTask) -> Path:
        if not archive.exists() or archive.stat().st_size == 0:
            raise MetLifePortalAdapterError("La descarga está vacía")
        destination = self.download_root / sanitize_drive_name(
            f"{normalize_rfc(task.rfc)}_{task.policy_number}_{task.renewal_deadline}"
        )
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        if not zipfile.is_zipfile(archive):
            shutil.copy2(archive, destination / archive.name)
            return destination
        with zipfile.ZipFile(archive) as bundle:
            root = destination.resolve()
            for member in bundle.infolist():
                target = (destination / member.filename).resolve()
                if root not in target.parents and target != root:
                    raise MetLifePortalAdapterError("El ZIP contiene una ruta insegura")
            bundle.extractall(destination)
        return destination
