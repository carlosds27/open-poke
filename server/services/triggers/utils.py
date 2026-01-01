from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from dateutil.rrule import rrulestr
from zoneinfo import ZoneInfo

from ...logging_config import logger
DEFAULT_STATUS = "active"
VALID_STATUSES = {"active", "paused", "completed"}


def normalize_status(status: Optional[str]) -> str:
    """Clamp trigger status to the known set."""

    if not status:
        return DEFAULT_STATUS
    normalized = status.lower()
    if normalized not in VALID_STATUSES:
        logger.warning(
            "invalid status supplied; defaulting to active",
            extra={"status": status},
        )
        return DEFAULT_STATUS
    return normalized


def build_recurrence(
    recurrence_rule: Optional[str],
    start_dt_local: datetime,
    tz: ZoneInfo,
) -> Optional[str]:
    """Embed DTSTART metadata into the supplied RRULE text."""

    if not recurrence_rule:
        return None

    if start_dt_local.tzinfo is None:
        localized_start = start_dt_local.replace(tzinfo=tz)
    else:
        localized_start = start_dt_local.astimezone(tz)

    if localized_start.utcoffset() == timedelta(0):
        dt_line = f"DTSTART:{localized_start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    else:
        tz_name = getattr(tz, "key", "UTC")
        dt_line = f"DTSTART;TZID={tz_name}:{localized_start.strftime('%Y%m%dT%H%M%S')}"

    lines = [segment.strip() for segment in recurrence_rule.strip().splitlines() if segment.strip()]
    filtered = [segment for segment in lines if not segment.upper().startswith("DTSTART")]
    if not filtered:
        raise ValueError("recurrence_rule must contain an RRULE definition")

    if not filtered[0].upper().startswith("RRULE"):
        filtered[0] = f"RRULE:{filtered[0]}"

    return "\n".join([dt_line, *filtered])


def load_rrule(recurrence_text: str):
    """Parse a stored recurrence string into a dateutil rule instance."""

    return rrulestr(recurrence_text)


__all__ = [
    "DEFAULT_STATUS",
    "VALID_STATUSES",
    "build_recurrence",
    "load_rrule",
    "normalize_status",
]
