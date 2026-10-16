"""Date rules (spec section 0.8): store UTC, show DD/MM/YYYY in the workspace timezone."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

DISPLAY_DATE_FORMAT = "%d/%m/%Y"
DISPLAY_DATETIME_FORMAT = "%d/%m/%Y %H:%M"
META_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2026-06-29T17:58:13+0000


def parse_meta_time(value: str) -> datetime:
    """Parse Meta's `created_time` and return an aware UTC datetime."""
    return datetime.strptime(value, META_TIME_FORMAT).astimezone(UTC)


def to_workspace_tz(value: datetime, timezone: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Naive datetimes are not allowed; store UTC.")
    return value.astimezone(ZoneInfo(timezone))


def format_date(value: date | datetime, timezone: str | None = None) -> str:
    if isinstance(value, datetime) and timezone:
        value = to_workspace_tz(value, timezone)
    return value.strftime(DISPLAY_DATE_FORMAT)


def format_datetime(value: datetime, timezone: str) -> str:
    return to_workspace_tz(value, timezone).strftime(DISPLAY_DATETIME_FORMAT)


def parse_display_date(value: str) -> date:
    """Parse DD/MM/YYYY (used by imports and filters). Raises ValueError."""
    return datetime.strptime(value.strip(), DISPLAY_DATE_FORMAT).date()
