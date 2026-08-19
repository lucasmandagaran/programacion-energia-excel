from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .config import LOCAL_TZ


def local_today() -> date:
    return datetime.now(LOCAL_TZ).date()


def local_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(LOCAL_TZ)
    except Exception:
        return None


def advance_date(value: Any) -> str:
    if not value:
        return ""
    parsed = local_datetime(value)
    if parsed:
        return parsed.strftime("%d/%m/%Y")
    return str(value)[:10]


def advance_time(value: Any) -> str:
    if not value:
        return ""
    parsed = local_datetime(value)
    if parsed:
        return parsed.strftime("%H:%M")
    return ""


def format_date(value: Any) -> str:
    if not value:
        return ""
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except Exception:
        return str(value)


def format_datetime(value: Any) -> str:
    if not value:
        return ""
    parsed = local_datetime(value)
    if parsed:
        return parsed.strftime("%d/%m/%Y %H:%M")
    return str(value)
