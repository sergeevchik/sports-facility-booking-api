import logging
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import exists, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as DatabaseTimeout
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import services
from app.clock import utc_now
from app.config import Settings, get_settings
from app.database import Database
from app.errors import DomainError
from app.metrics import Metrics
from app.middleware import RequestMetricsMiddleware
from app.models import Booking, Facility
from app.policy import validate_interval
from app.schemas import (
    BookingCreate,
    BookingRead,
    BookingStatus,
    FacilityCreate,
    FacilityRead,
    FacilityStatusUpdate,
    Page,
    Sport,
)

logger = logging.getLogger("booking.errors")
key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def require_key(request: Request, key: str | None = Depends(key_header)):
    expected = request.app.state.settings.api_key.get_secret_value()
    if key is None or not secrets.compare_digest(key.encode(), expected.encode()):
        raise DomainError("unauthorized", "A valid X-API-Key is required", 401)


def session_dependency(request: Request):
    with request.app.state.database.sessions() as session:
        yield session


def aware(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise DomainError("timezone_required", "Specify an explicit UTC offset", 422)
    return value


def create_app(settings: Settings | None = None, clock: Callable = utc_now) -> FastAPI:
    settings = settings or get_settings()
    database, metrics = Database(settings), Metrics()

    @asynccontextmanager
    async def lifespan(app):
        yield
        database.engine.dispose()

    app = FastAPI(
        title="Sports Facility Booking API",
        version=settings.app_version,
        description="Operator API for a sports complex. Business routes require X-API-Key.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.metrics = metrics
    app.add_middleware(RequestMetricsMiddleware, metrics=metrics)

    def error_response(request, code, message, status_code, details=None):
        payload = {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
        }
        if details is not None:
            payload["details"] = details
        return JSONResponse(payload, status_code=status_code)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        if exc.code == "booking_conflict":
            metrics.conflicts.inc()
        return error_response(request, exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        details = [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return error_response(request, "validation_error", "Invalid request", 422, details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return error_response(request, "http_error", str(exc.detail), exc.status_code)

    @app.exception_handler(OperationalError)
    @app.exception_handler(DatabaseTimeout)
    async def database_error(request, exc):
        metrics.ready.set(0)
        return error_response(
            request, "database_unavailable", "Database temporarily unavailable", 503
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error(
            "unhandled_exception type=%s request_id=%s",
            type(exc).__name__,
            getattr(request.state, "request_id", None),
        )
        return error_response(request, "internal_error", "Unexpected internal error", 500)

    @app.get(
        "/health", tags=["operations"], responses={503: {"description": "Database unavailable"}}
    )
    def health():
        ready = database.ready()
        metrics.ready.set(int(ready))
        return JSONResponse(
            {
                "status": "ok" if ready else "unavailable",
                "version": settings.app_version,
                "database": "ready" if ready else "unavailable",
            },
            status_code=200 if ready else 503,
        )

    @app.get("/metrics", include_in_schema=False)
    def prometheus_metrics():
        metrics.ready.set(int(database.ready()))
        return Response(
            generate_latest(metrics.registry), headers={"Content-Type": CONTENT_TYPE_LATEST}
        )

    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_key)])

    @router.post("/facilities", response_model=FacilityRead, status_code=201, tags=["facilities"])
    def create_facility(data: FacilityCreate, session=Depends(session_dependency)):
        return services.create_facility(session, data)

    @router.get("/facilities", response_model=Page[FacilityRead], tags=["facilities"])
    def list_facilities(
        sport: Sport | None = None,
        is_active: bool | None = None,
        limit: Limit = 20,
        offset: Offset = 0,
        session=Depends(session_dependency),
    ):
        query = select(Facility).order_by(Facility.name, Facility.id)
        if sport is not None:
            query = query.where(Facility.sport == sport)
        if is_active is not None:
            query = query.where(Facility.is_active == is_active)
        return services.paginate(session, query, limit, offset)

    @router.get("/facilities/{facility_id}", response_model=FacilityRead, tags=["facilities"])
    def read_facility(facility_id: UUID, session=Depends(session_dependency)):
        return services.get_facility(session, facility_id)

    @router.patch(
        "/facilities/{facility_id}/status", response_model=FacilityRead, tags=["facilities"]
    )
    def facility_status(
        facility_id: UUID,
        data: FacilityStatusUpdate,
        session=Depends(session_dependency),
    ):
        return services.change_facility_status(session, facility_id, data.is_active, clock())

    @router.get("/availability", response_model=Page[FacilityRead], tags=["availability"])
    def availability(
        starts_at: datetime,
        ends_at: datetime,
        participants: Annotated[int, Query(ge=1, le=100)],
        sport: Sport | None = None,
        limit: Limit = 20,
        offset: Offset = 0,
        session=Depends(session_dependency),
    ):
        start, end = validate_interval(aware(starts_at), aware(ends_at), clock(), settings)
        conflict = exists().where(
            Booking.facility_id == Facility.id,
            Booking.status == "confirmed",
            Booking.starts_at < end,
            Booking.ends_at > start,
        )
        query = (
            select(Facility)
            .where(
                Facility.is_active.is_(True),
                Facility.capacity >= participants,
                ~conflict,
            )
            .order_by(Facility.name, Facility.id)
        )
        if sport is not None:
            query = query.where(Facility.sport == sport)
        return services.paginate(session, query, limit, offset)

    @router.post("/bookings", response_model=BookingRead, status_code=201, tags=["bookings"])
    def create_booking(data: BookingCreate, session=Depends(session_dependency)):
        booking = services.create_booking(session, data, clock(), settings)
        metrics.created.inc()
        return booking

    @router.get("/bookings", response_model=Page[BookingRead], tags=["bookings"])
    def list_bookings(
        facility_id: UUID | None = None,
        status: BookingStatus | None = None,
        customer_ref: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        limit: Limit = 20,
        offset: Offset = 0,
        session=Depends(session_dependency),
    ):
        if starts_at is not None:
            starts_at = aware(starts_at)
        if ends_at is not None:
            ends_at = aware(ends_at)
        if starts_at is not None and ends_at is not None and ends_at <= starts_at:
            raise DomainError("invalid_interval", "ends_at must be later than starts_at", 422)
        query = select(Booking).order_by(Booking.starts_at, Booking.id)
        for column, value in (
            (Booking.facility_id, facility_id),
            (Booking.status, status),
            (Booking.customer_ref, customer_ref),
        ):
            if value is not None:
                query = query.where(column == value)
        if starts_at is not None:
            query = query.where(Booking.ends_at > starts_at)
        if ends_at is not None:
            query = query.where(Booking.starts_at < ends_at)
        return services.paginate(session, query, limit, offset)

    @router.get("/bookings/{booking_id}", response_model=BookingRead, tags=["bookings"])
    def read_booking(booking_id: UUID, session=Depends(session_dependency)):
        return services.get_booking(session, booking_id)

    @router.post("/bookings/{booking_id}/cancel", response_model=BookingRead, tags=["bookings"])
    def cancel_booking(booking_id: UUID, session=Depends(session_dependency)):
        booking, changed = services.cancel_booking(session, booking_id, clock())
        if changed:
            metrics.cancelled.inc()
        return booking

    app.include_router(router)
    return app
