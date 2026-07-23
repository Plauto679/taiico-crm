from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def secure_cookie_for(request: Request) -> bool:
    configured = os.getenv("AUTH_COOKIE_SECURE")
    if configured is not None and configured.strip():
        return env_flag("AUTH_COOKIE_SECURE")
    if os.getenv("TAIICO_ENV", "development").strip().casefold() == "production":
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    return request.url.scheme == "https" or forwarded_proto == "https"


def client_address(request: Request) -> str:
    direct_address = request.client.host if request.client else "unknown"
    if direct_address not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return direct_address

    # FastAPI only listens on loopback in production. Forwarded headers are
    # therefore accepted only from the local Next.js reverse proxy.
    cloudflare_address = request.headers.get("cf-connecting-ip", "").strip()
    if cloudflare_address:
        return cloudflare_address
    forwarded_address = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded_address or direct_address


class LoginRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _max_attempts() -> int:
        return max(1, int(os.getenv("AUTH_LOGIN_MAX_ATTEMPTS", "5")))

    @staticmethod
    def _window_seconds() -> int:
        return max(1, int(os.getenv("AUTH_LOGIN_WINDOW_SECONDS", "900")))

    @staticmethod
    def key(request: Request, username: str) -> str:
        return f"{client_address(request)}:{username.strip().casefold()}"

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self._window_seconds()
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= cutoff:
                attempts.popleft()
            if len(attempts) >= self._max_attempts():
                retry_after = max(1, int(attempts[0] + self._window_seconds() - now))
                raise HTTPException(
                    status_code=429,
                    detail="Too many login attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._attempts[key].append(time.monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = LoginRateLimiter()
