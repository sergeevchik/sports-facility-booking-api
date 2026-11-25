from datetime import datetime
from enum import StrEnum
from typing import Annotated, TypeVar
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
CustomerRef = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^[\w.-]+$")
]


class Sport(StrEnum):
    tennis = "tennis"
    football = "football"
    basketball = "basketball"
    badminton = "badminton"


class BookingStatus(StrEnum):
    confirmed = "confirmed"
    cancelled = "cancelled"


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FacilityCreate(InputModel):
    name: Name
    sport: Sport
    capacity: int = Field(ge=1, le=100)


class FacilityStatusUpdate(InputModel):
    is_active: bool


class FacilityRead(FacilityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime


class BookingCreate(InputModel):
    facility_id: UUID
    customer_ref: CustomerRef
    participants: int = Field(ge=1, le=100)
    starts_at: AwareDatetime
    ends_at: AwareDatetime


class BookingRead(BookingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: BookingStatus
    created_at: datetime
    cancelled_at: datetime | None


T = TypeVar("T")


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int
