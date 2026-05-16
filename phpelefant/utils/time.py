from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re

_DURATION_RE = re.compile(r"^(?P<amount>[1-9][0-9]{0,5})(?P<unit>[mhdw])$")
_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def parse_duration(value: str) -> timedelta:
    match = _DURATION_RE.fullmatch(value.strip().lower())
    if not match:
        raise ValueError("Use a duration like 10m, 1h, 1d, or 7d.")
    seconds = int(match.group("amount")) * _SECONDS[match.group("unit")]
    return timedelta(seconds=seconds)


def human_timedelta(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    for unit, size in (("week", 604800), ("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            value = seconds // size
            return f"{value} {unit}{'' if value == 1 else 's'}"
    return f"{seconds} seconds"

