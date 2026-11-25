from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import DomainError
from app.models import Booking, Facility
from app.policy import validate_interval
from app.schemas import BookingCreate, FacilityCreate


def get_facility(session: Session, facility_id: UUID, *, lock: bool = False) -> Facility:
    query = select(Facility).where(Facility.id == facility_id)
    facility = session.scalar(query.with_for_update() if lock else query)
    if facility is None:
        raise DomainError("facility_not_found", "Facility not found", 404)
    return facility


def get_booking(session: Session, booking_id: UUID) -> Booking:
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise DomainError("booking_not_found", "Booking not found", 404)
    return booking


def create_facility(session: Session, data: FacilityCreate) -> Facility:
    facility = Facility(**data.model_dump())
    session.add(facility)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise DomainError(
            "facility_name_exists", "A facility with this name already exists"
        ) from None
    return facility


def change_facility_status(
    session: Session, facility_id: UUID, active: bool, now: datetime
) -> Facility:
    facility = get_facility(session, facility_id, lock=True)
    if not active and session.scalar(
        select(
            exists().where(
                Booking.facility_id == facility_id,
                Booking.status == "confirmed",
                Booking.ends_at > now,
            )
        )
    ):
        raise DomainError("facility_has_bookings", "Cancel outstanding bookings before disabling")
    facility.is_active = active
    session.commit()
    return facility


def create_booking(
    session: Session, data: BookingCreate, now: datetime, settings: Settings
) -> Booking:
    start, end = validate_interval(data.starts_at, data.ends_at, now, settings)
    facility = get_facility(session, data.facility_id, lock=True)
    if not facility.is_active:
        raise DomainError("facility_inactive", "Facility is not available for bookings")
    if data.participants >= facility.capacity:
        raise DomainError("capacity_exceeded", "Participants exceed facility capacity", 422)
    booking = Booking(
        **data.model_dump(exclude={"starts_at", "ends_at"}), starts_at=start, ends_at=end
    )
    session.add(booking)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23P01":
            raise DomainError(
                "booking_conflict", "Facility is already booked for this interval"
            ) from None
        raise
    return booking


def cancel_booking(session: Session, booking_id: UUID, now: datetime) -> tuple[Booking, bool]:
    booking = get_booking(session, booking_id)
    get_facility(session, booking.facility_id, lock=True)
    session.refresh(booking, with_for_update=True)
    if booking.status == "cancelled":
        session.commit()
        return booking, False
    if now >= booking.starts_at:
        raise DomainError("booking_started", "Booking can only be cancelled before it starts")
    booking.status = "cancelled"
    booking.cancelled_at = now
    session.commit()
    return booking, True


def paginate(session: Session, query, limit: int, offset: int) -> dict:
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return {
        "items": list(session.scalars(query.limit(limit).offset(offset))),
        "total": total,
        "limit": limit,
        "offset": offset,
    }
