from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, TypeVar

from services.performance import mark_cache


T = TypeVar("T")
CACHE_VERSION = 1
DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / ".runtime" / "data-cache"


@dataclass(frozen=True)
class CacheResult(Generic[T]):
    value: T
    state: str
    stored_at: float


class PersistentDataCache:
    """Process-safe-enough local cache with stale-while-revalidate semantics.

    Values must be JSON serializable. Writes are atomic, stale values remain
    available after restarts, and only one refresh thread runs per key inside
    the backend process.
    """

    def __init__(self, directory: Path | None = None):
        configured = os.getenv("DATA_CACHE_DIR", "").strip()
        self.directory = directory or (Path(configured) if configured else DEFAULT_CACHE_DIR)
        self._lock = threading.RLock()
        self._entries: dict[str, tuple[float, object]] = {}
        self._refreshing: set[str] = set()
        self._load_locks: dict[str, threading.Lock] = {}

    def _load_lock(self, key: str) -> threading.Lock:
        with self._lock:
            return self._load_locks.setdefault(key, threading.Lock())

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self.directory / f"{digest}.json"

    def _read(self, key: str) -> tuple[float, object] | None:
        with self._lock:
            if key in self._entries:
                return self._entries[key]
        path = self._path(key)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("version") != CACHE_VERSION or document.get("key") != key:
                return None
            entry = (float(document["stored_at"]), document["value"])
        except (FileNotFoundError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        with self._lock:
            self._entries[key] = entry
        return entry

    def set(self, key: str, value: T) -> CacheResult[T]:
        stored_at = time.time()
        document = {"version": CACHE_VERSION, "key": key, "stored_at": stored_at, "value": value}
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary, path)
        with self._lock:
            self._entries[key] = (stored_at, value)
        return CacheResult(value, "refreshed", stored_at)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass

    def invalidate_prefix(self, prefix: str) -> None:
        # Known in-memory entries are enough for current usage; persistent keys
        # are invalidated explicitly by each module to avoid scanning payloads.
        with self._lock:
            keys = [key for key in self._entries if key.startswith(prefix)]
        for key in keys:
            self.invalidate(key)

    def get_or_load(
        self,
        key: str,
        loader: Callable[[], T],
        *,
        ttl_seconds: int,
        background_refresh: bool = True,
    ) -> CacheResult[T]:
        entry = self._read(key)
        now = time.time()
        if entry is not None:
            stored_at, value = entry
            if now - stored_at <= max(0, ttl_seconds):
                mark_cache(key, "hit")
                return CacheResult(value, "hit", stored_at)  # type: ignore[arg-type]
            if background_refresh:
                self._start_refresh(key, loader)
                mark_cache(key, "stale")
                return CacheResult(value, "stale", stored_at)  # type: ignore[arg-type]

        with self._load_lock(key):
            # Another request may have populated the key while this request
            # waited for the single-flight lock.
            current = self._read(key)
            if current is not None:
                stored_at, value = current
                if time.time() - stored_at <= max(0, ttl_seconds):
                    mark_cache(key, "hit")
                    return CacheResult(value, "hit", stored_at)  # type: ignore[arg-type]
            mark_cache(key, "miss")
            try:
                return self.set(key, loader())
            except Exception:
                # A last-known-good value wins over a transient Drive outage,
                # even when synchronous refresh was explicitly requested.
                fallback = current or entry
                if fallback is not None:
                    stored_at, value = fallback
                    mark_cache(key, "stale-error")
                    return CacheResult(value, "stale-error", stored_at)  # type: ignore[arg-type]
                raise

    def _start_refresh(self, key: str, loader: Callable[[], T]) -> None:
        with self._lock:
            if key in self._refreshing:
                return
            self._refreshing.add(key)

        def refresh() -> None:
            try:
                self.set(key, loader())
            except Exception as exc:
                print(f"CACHE_REFRESH_FAILED key={key} error={type(exc).__name__}: {exc}", flush=True)
            finally:
                with self._lock:
                    self._refreshing.discard(key)

        threading.Thread(target=refresh, name=f"cache-refresh-{key}", daemon=True).start()


data_cache = PersistentDataCache()
