from __future__ import annotations

import fcntl
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_DIR = Path(
    "/Users/albertoalfaromendoza/Desktop/Taiico Antigravity AI OS/"
    "Taiico Local - Antigravity CRM/taiico-crm"
)
RUNTIME_DIR = REPO_DIR / ".runtime"
LOG_FILE = RUNTIME_DIR / "logs" / "auto-update.log"
LOCK_FILE = RUNTIME_DIR / "auto-update.lock"
BRANCH = "taiico-os"
ENV = {
    **os.environ,
    "HOME": "/Users/albertoalfaromendoza",
    "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
}


def log(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as stream:
        stream.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_DIR,
        env=ENV,
        text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
        check=False,
    )


def output(*args: str) -> str:
    result = run(*args, capture=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "comando fallido")
    return result.stdout.strip()


def changed(old_sha: str, new_sha: str, *paths: str) -> bool:
    return bool(output("git", "diff", "--name-only", old_sha, new_sha, "--", *paths))


def main() -> int:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0

        try:
            if output("git", "branch", "--show-current") != BRANCH:
                log(f"OMITIDO: la rama activa no es {BRANCH}")
                return 0

            if run("git", "fetch", "--quiet", "origin", BRANCH).returncode:
                log("ERROR: git fetch falló")
                return 1

            local_sha = output("git", "rev-parse", "HEAD")
            remote_sha = output("git", "rev-parse", f"origin/{BRANCH}")
            if local_sha == remote_sha:
                return 0

            if run("git", "merge-base", "--is-ancestor", local_sha, remote_sha).returncode:
                log(f"BLOQUEADO: la rama local y origin/{BRANCH} divergieron")
                return 1

            log(f"ACTUALIZANDO: {local_sha} -> {remote_sha}")
            if run("git", "pull", "--ff-only", "origin", BRANCH).returncode:
                log("BLOQUEADO: git pull no pudo preservar los cambios locales")
                return 1

            if changed(local_sha, remote_sha, "package.json", "package-lock.json"):
                log("Instalando dependencias de frontend")
                if run("npm", "ci").returncode:
                    log("ERROR: npm ci falló")
                    return 1

            if changed(local_sha, remote_sha, "backend/requirements.txt"):
                log("Instalando dependencias de backend")
                if run(str(REPO_DIR / ".venv/bin/python"), "-m", "pip", "install", "-r", "backend/requirements.txt").returncode:
                    log("ERROR: instalación de dependencias de backend falló")
                    return 1

            log("Compilando frontend")
            if run("npm", "run", "build").returncode:
                log("ERROR: la compilación del frontend falló")
                return 1

            domain = f"gui/{os.getuid()}"
            run("launchctl", "kickstart", "-k", f"{domain}/com.taiico.crm.backend")
            run("launchctl", "kickstart", "-k", f"{domain}/com.taiico.crm.frontend")
            log(f"COMPLETADO: servicios actualizados en {remote_sha}")
            return 0
        except Exception as exc:
            log(f"ERROR: {exc}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
