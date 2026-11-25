from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.errors import DomainError
from app.policy import validate_interval

NOW = datetime(2030, 6, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [
        ("2030-05-31T10:00+03:00", "2030-05-31T11:00+03:00", "booking_in_past"),
        ("2030-06-02T10:00+03:00", "2030-06-02T10:00+03:00", "invalid_duration"),
        ("2030-06-02T11:00+03:00", "2030-06-02T10:00+03:00", "invalid_duration"),
        ("2030-06-02T10:00+03:00", "2030-06-02T10:15+03:00", "invalid_duration"),
        ("2030-06-02T10:00+03:00", "2030-06-02T14:00+03:00", "invalid_duration"),
        ("2030-06-02T10:15+03:00", "2030-06-02T11:15+03:00", "invalid_time_grid"),
        ("2030-06-02T10:00:01+03:00", "2030-06-02T11:00:01+03:00", "invalid_time_grid"),
        ("2030-06-02T07:30+03:00", "2030-06-02T08:30+03:00", "outside_opening_hours"),
        ("2030-06-02T21:30+03:00", "2030-06-02T22:30+03:00", "outside_opening_hours"),
        ("2030-06-02T23:00+03:00", "2030-06-03T00:00+03:00", "outside_opening_hours"),
        ("2030-06-02T10:00", "2030-06-02T11:00", "timezone_required"),
    ],
)
def test_invalid_intervals(settings, start, end, code):
    with pytest.raises(DomainError) as error:
        validate_interval(datetime.fromisoformat(start), datetime.fromisoformat(end), NOW, settings)
    assert error.value.code == code


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2030-06-02T08:00+03:00", "2030-06-02T08:30+03:00"),
        ("2030-06-02T19:00+03:00", "2030-06-02T22:00+03:00"),
        ("2030-06-02T07:00Z", "2030-06-02T08:00Z"),
        ("2030-06-02T09:00+02:00", "2030-06-02T10:00+02:00"),
    ],
)
def test_valid_intervals_are_normalized_to_utc(settings, start, end):
    lower, upper = validate_interval(
        datetime.fromisoformat(start),
        datetime.fromisoformat(end),
        NOW,
        settings,
    )
    assert lower.tzinfo == UTC and upper.tzinfo == UTC and lower < upper


@pytest.mark.parametrize(
    "overrides",
    [
        {"opening_hour": 22, "closing_hour": 8},
        {"min_booking_minutes": 180, "max_booking_minutes": 30},
        {"min_booking_minutes": 45},
    ],
)
def test_reject_invalid_policy_configuration(settings, overrides):
    with pytest.raises(ValidationError):
        Settings(**{**settings.model_dump(), **overrides}, _env_file=None)
