from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.config import Settings
from app.errors import DomainError


def validate_interval(
    starts_at: datetime, ends_at: datetime, now: datetime, settings: Settings
) -> tuple[datetime, datetime]:
    if starts_at.utcoffset() is None or ends_at.utcoffset() is None:
        raise DomainError("timezone_required", "Specify an explicit UTC offset", 422)
    starts_at, ends_at = starts_at.astimezone(UTC), ends_at.astimezone(UTC)
    if starts_at <= now:
        raise DomainError("booking_in_past", "Booking must start in the future", 422)
    minutes = (ends_at - starts_at).total_seconds() / 60
    if not settings.min_booking_minutes <= minutes <= settings.max_booking_minutes:
        raise DomainError("invalid_duration", "Booking duration is outside policy limits", 422)
    zone = ZoneInfo(settings.app_timezone)
    start, end = starts_at.astimezone(zone), ends_at.astimezone(zone)
    if any(t.minute % 30 or t.second or t.microsecond for t in (start, end)):
        raise DomainError("invalid_time_grid", "Times must align to a 30-minute grid", 422)
    end_minutes = end.hour * 60 + end.minute
    if (
        start.date() != end.date()
        or start.hour < settings.opening_hour
        or end_minutes > settings.closing_hour * 60
    ):
        raise DomainError("outside_opening_hours", "Interval is outside opening hours", 422)
    return starts_at, ends_at
