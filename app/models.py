from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.clock import utc_now


class Base(DeclarativeBase):
    pass


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="positive_capacity"),
        CheckConstraint(
            "sport IN ('tennis','football','basketball','badminton')", name="valid_sport"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    sport: Mapped[str] = mapped_column(String(24))
    capacity: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("participants > 0", name="positive_participants"),
        CheckConstraint("ends_at > starts_at", name="valid_interval"),
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="valid_status"),
        CheckConstraint(
            "(status = 'cancelled') = (cancelled_at IS NOT NULL)", name="consistent_cancellation"
        ),
        Index("ix_bookings_facility_start", "facility_id", "starts_at"),
        Index("ix_bookings_customer", "customer_ref"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    facility_id: Mapped[UUID] = mapped_column(ForeignKey("facilities.id", ondelete="RESTRICT"))
    customer_ref: Mapped[str] = mapped_column(String(64))
    participants: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
