from __future__ import annotations

import datetime as dt
import os
import re
from zoneinfo import ZoneInfo


DEFAULT_BUSINESS_TIMEZONE = "America/Mexico_City"
PROCESS_FOLDER_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}(?: \d{2}-\d{2})?\s+")


def business_now() -> dt.datetime:
    timezone_name = os.getenv("TAIICO_BUSINESS_TIMEZONE", DEFAULT_BUSINESS_TIMEZONE).strip()
    try:
        timezone = ZoneInfo(timezone_name)
    except Exception:
        timezone = ZoneInfo(DEFAULT_BUSINESS_TIMEZONE)
    return dt.datetime.now(timezone)


def process_folder_name(
    descriptor: str,
    *,
    occurred_at: dt.date | dt.datetime | None = None,
    include_time: bool = True,
    max_length: int = 180,
) -> str:
    cleaned = re.sub(r"\s+", " ", str(descriptor or "")).strip()
    if not cleaned:
        raise ValueError("La descripción de la carpeta de proceso es obligatoria")
    value = occurred_at or business_now()
    if isinstance(value, dt.datetime) and value.tzinfo is not None:
        timezone_name = os.getenv("TAIICO_BUSINESS_TIMEZONE", DEFAULT_BUSINESS_TIMEZONE).strip()
        try:
            value = value.astimezone(ZoneInfo(timezone_name))
        except Exception:
            value = value.astimezone(ZoneInfo(DEFAULT_BUSINESS_TIMEZONE))
    prefix = value.strftime("%Y-%m-%d %H-%M" if include_time and isinstance(value, dt.datetime) else "%Y-%m-%d")
    return f"{prefix} {cleaned}"[:max_length]


def process_folder_descriptor(name: str) -> str:
    return PROCESS_FOLDER_PREFIX.sub("", str(name or "").strip(), count=1)


def is_process_folder_for(name: str, descriptor: str) -> bool:
    return process_folder_descriptor(name).casefold() == str(descriptor or "").strip().casefold()
