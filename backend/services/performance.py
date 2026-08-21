from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class RequestMetrics:
    request_id: str
    started_at: float
    timings_ms: dict[str, float] = field(default_factory=dict)
    cache: dict[str, str] = field(default_factory=dict)


_metrics: ContextVar[RequestMetrics | None] = ContextVar("request_metrics", default=None)


def begin_request() -> tuple[object, RequestMetrics]:
    metrics = RequestMetrics(uuid.uuid4().hex[:12], time.perf_counter())
    return _metrics.set(metrics), metrics


def end_request(token: object) -> None:
    _metrics.reset(token)


def add_timing(name: str, duration_ms: float) -> None:
    metrics = _metrics.get()
    if metrics is not None:
        metrics.timings_ms[name] = metrics.timings_ms.get(name, 0.0) + duration_ms


@contextmanager
def timed(name: str) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        add_timing(name, (time.perf_counter() - started) * 1000)


def mark_cache(source: str, state: str) -> None:
    metrics = _metrics.get()
    if metrics is not None:
        metrics.cache[source] = state


def server_timing(metrics: RequestMetrics, total_ms: float) -> str:
    entries = [f'total;dur={total_ms:.1f}']
    labels = {
        "auth": "Authentication",
        "db": "Database",
        "drive": "Google Drive",
        "excel": "Excel processing",
    }
    for name, duration in sorted(metrics.timings_ms.items()):
        safe_name = "".join(character for character in name if character.isalnum() or character in "_-" )
        entries.append(f'{safe_name};dur={duration:.1f};desc="{labels.get(name, name)}"')
    for source, state in sorted(metrics.cache.items()):
        safe_source = "".join(character for character in source if character.isalnum() or character in "_-" )
        entries.append(f'cache_{safe_source};desc="{state}"')
    return ", ".join(entries)


def log_request(*, metrics: RequestMetrics, method: str, path: str, status: int, total_ms: float) -> None:
    threshold_ms = max(0, int(os.getenv("PERFORMANCE_LOG_THRESHOLD_MS", "250")))
    if total_ms < threshold_ms and status < 400:
        return
    print("PERFORMANCE " + json.dumps({
        "request_id": metrics.request_id,
        "method": method,
        "path": path,
        "status": status,
        "total_ms": round(total_ms, 1),
        "timings_ms": {key: round(value, 1) for key, value in metrics.timings_ms.items()},
        "cache": metrics.cache,
    }, ensure_ascii=False, sort_keys=True), flush=True)


def install_sqlalchemy_timing(engine) -> None:
    if getattr(engine, "_taiico_performance_installed", False):
        return
    from sqlalchemy import event

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(_connection, _cursor, _statement, _parameters, context, _executemany):
        context._taiico_query_started_at = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(_connection, _cursor, _statement, _parameters, context, _executemany):
        started = getattr(context, "_taiico_query_started_at", None)
        if started is not None:
            add_timing("db", (time.perf_counter() - started) * 1000)

    engine._taiico_performance_installed = True
