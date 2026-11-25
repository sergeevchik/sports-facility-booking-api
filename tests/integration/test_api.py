from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.conftest import TEST_KEY

pytestmark = pytest.mark.integration


def create(client, payload):
    response = client.post("/api/v1/bookings", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_booking_lifecycle_and_idempotent_cancellation(client, payload, clock):
    booking = create(client, payload)
    assert booking["status"] == "confirmed"
    assert booking["starts_at"].endswith("Z")
    assert client.get(f"/api/v1/bookings/{booking['id']}").json() == booking
    cancelled = client.post(f"/api/v1/bookings/{booking['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    clock["now"] = datetime(2030, 6, 3, tzinfo=UTC)
    assert client.post(f"/api/v1/bookings/{booking['id']}/cancel").json() == cancelled


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("10:00", "11:00"),
        ("09:30", "10:30"),
        ("10:30", "11:30"),
        ("09:00", "12:00"),
        ("10:00", "10:30"),
    ],
)
def test_overlap_variants_are_rejected(client, payload, start, end):
    create(client, payload)
    response = client.post(
        "/api/v1/bookings",
        json={
            **payload,
            "starts_at": f"2030-06-02T{start}:00+03:00",
            "ends_at": f"2030-06-02T{end}:00+03:00",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "booking_conflict"
    assert client.get("/api/v1/bookings").json()["total"] == 1


def test_adjacent_bookings_are_allowed(client, payload):
    create(client, payload)
    second = create(
        client, {**payload, "starts_at": payload["ends_at"], "ends_at": "2030-06-02T12:00:00+03:00"}
    )
    assert second["status"] == "confirmed"


def test_different_facilities_do_not_conflict(client, payload):
    create(client, payload)
    other = client.post(
        "/api/v1/facilities",
        json={
            "name": "Other court",
            "sport": "tennis",
            "capacity": 4,
        },
    ).json()
    create(client, {**payload, "facility_id": other["id"]})


def test_cancel_releases_interval(client, payload):
    booking = create(client, payload)
    client.post(f"/api/v1/bookings/{booking['id']}/cancel")
    create(client, payload)


def test_cannot_cancel_started_booking(client, payload, clock):
    booking = create(client, payload)
    clock["now"] = datetime(2030, 6, 2, 7, tzinfo=UTC)
    response = client.post(f"/api/v1/bookings/{booking['id']}/cancel")
    assert response.status_code == 409 and response.json()["code"] == "booking_started"


@pytest.mark.parametrize("participants", [0, -1, 5, 101])
def test_capacity_validation(client, payload, participants):
    assert (
        client.post("/api/v1/bookings", json={**payload, "participants": participants}).status_code
        == 422
    )


def test_full_capacity_is_accepted(client, payload, facility):
    booking = create(client, {**payload, "participants": facility["capacity"]})
    assert booking["participants"] == facility["capacity"]


def test_concurrent_cancellation_is_idempotent(application, client, payload):
    booking = create(client, payload)
    barrier = Barrier(2)

    def cancel(_):
        with TestClient(application, headers={"X-API-Key": TEST_KEY}) as concurrent:
            barrier.wait(timeout=10)
            response = concurrent.post(f"/api/v1/bookings/{booking['id']}/cancel")
            assert response.status_code == 200
            return response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(cancel, range(2)))
    assert first == second
    assert "bookings_cancelled_total 1.0" in client.get("/metrics").text


def test_timezone_required_and_unknown_fields_rejected(client, payload):
    assert (
        client.post(
            "/api/v1/bookings",
            json={
                **payload,
                "starts_at": "2030-06-02T10:00:00",
            },
        ).status_code
        == 422
    )
    assert client.post("/api/v1/bookings", json={**payload, "price": 1}).status_code == 422


def test_unauthorized_errors_do_not_echo_key(application):
    with TestClient(application) as public:
        assert public.get("/api/v1/facilities").status_code == 401
        response = public.get("/api/v1/facilities", headers={"X-API-Key": "invalid-private-value"})
        assert response.status_code == 401
        assert "invalid-private-value" not in response.text
        assert response.json()["request_id"] == response.headers["X-Request-ID"]


def test_missing_resources_and_bad_identifiers(client, payload):
    for path in [f"/api/v1/facilities/{uuid4()}", f"/api/v1/bookings/{uuid4()}"]:
        assert client.get(path).status_code == 404
    assert (
        client.post("/api/v1/bookings", json={**payload, "facility_id": str(uuid4())}).status_code
        == 404
    )
    assert client.post(f"/api/v1/bookings/{uuid4()}/cancel").status_code == 404
    assert client.get("/api/v1/bookings/not-a-uuid").status_code == 422


def test_facility_disable_and_reenable(client, facility, payload):
    endpoint = f"/api/v1/facilities/{facility['id']}/status"
    assert client.patch(endpoint, json={"is_active": False}).status_code == 200
    assert client.post("/api/v1/bookings", json=payload).json()["code"] == "facility_inactive"
    assert client.patch(endpoint, json={"is_active": True}).status_code == 200
    create(client, payload)
    assert (
        client.patch(endpoint, json={"is_active": False}).json()["code"] == "facility_has_bookings"
    )


def test_past_bookings_do_not_prevent_disable(client, facility, payload, clock):
    create(client, payload)
    clock["now"] = datetime(2030, 6, 3, tzinfo=UTC)
    assert (
        client.patch(
            f"/api/v1/facilities/{facility['id']}/status", json={"is_active": False}
        ).status_code
        == 200
    )


def test_unique_facility_names(client, facility):
    response = client.post(
        "/api/v1/facilities",
        json={
            "name": facility["name"],
            "sport": "tennis",
            "capacity": 4,
        },
    )
    assert response.status_code == 409
    assert client.get("/api/v1/facilities").json()["total"] == 1


def test_availability_and_filters(client, payload, facility):
    query = {"starts_at": payload["starts_at"], "ends_at": payload["ends_at"], "participants": 2}
    assert client.get("/api/v1/availability", params=query).json()["total"] == 1
    assert (
        client.get("/api/v1/availability", params={**query, "participants": 5}).json()["total"] == 0
    )
    assert (
        client.get("/api/v1/availability", params={**query, "sport": "football"}).json()["total"]
        == 0
    )
    booking = create(client, payload)
    assert client.get("/api/v1/availability", params=query).json()["total"] == 0
    client.post(f"/api/v1/bookings/{booking['id']}/cancel")
    assert client.get("/api/v1/availability", params=query).json()["total"] == 1
    client.patch(f"/api/v1/facilities/{facility['id']}/status", json={"is_active": False})
    assert client.get("/api/v1/availability", params=query).json()["total"] == 0


def test_lists_pagination_and_period_filters(client, payload):
    create(client, payload)
    assert client.get("/api/v1/bookings", params={"status": "confirmed"}).json()["total"] == 1
    assert client.get("/api/v1/bookings", params={"customer_ref": "other"}).json()["total"] == 0
    assert client.get("/api/v1/bookings", params={"facility_id": str(uuid4())}).json()["total"] == 0
    assert client.get("/api/v1/bookings", params={"offset": 1}).json()["items"] == []
    assert client.get("/api/v1/facilities", params={"sport": "football"}).json()["total"] == 0
    assert client.get("/api/v1/facilities", params={"is_active": False}).json()["total"] == 0
    assert client.get("/api/v1/facilities", params={"limit": 101}).status_code == 422
    assert (
        client.get("/api/v1/bookings", params={"starts_at": payload["ends_at"]}).json()["total"]
        == 0
    )
    assert (
        client.get("/api/v1/bookings", params={"ends_at": payload["starts_at"]}).json()["total"]
        == 0
    )
    assert (
        client.get(
            "/api/v1/bookings",
            params={"starts_at": payload["ends_at"], "ends_at": payload["starts_at"]},
        ).status_code
        == 422
    )
    assert (
        client.get("/api/v1/bookings", params={"starts_at": "2030-06-02T10:00"}).status_code == 422
    )


def test_concurrent_same_slot_has_exactly_one_winner(application, payload, client):
    barrier = Barrier(6)

    def reserve(_):
        with TestClient(application, headers={"X-API-Key": TEST_KEY}) as concurrent:
            barrier.wait(timeout=10)
            return concurrent.post("/api/v1/bookings", json=payload).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(reserve, range(6)))
    assert sorted(statuses) == [201, 409, 409, 409, 409, 409]
    assert client.get("/api/v1/bookings").json()["total"] == 1


def test_concurrent_disable_and_booking_preserve_invariant(application, payload, client):
    barrier = Barrier(2)

    def operation(disable):
        with TestClient(application, headers={"X-API-Key": TEST_KEY}) as concurrent:
            barrier.wait(timeout=10)
            if disable:
                return concurrent.patch(
                    f"/api/v1/facilities/{payload['facility_id']}/status", json={"is_active": False}
                ).status_code
            return concurrent.post("/api/v1/bookings", json=payload).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        disabled, booked = list(pool.map(operation, [True, False]))
    assert (disabled, booked) in [(200, 409), (409, 201)]


def test_database_constraint_rejects_overlap_without_service(engine, client, payload):
    booking = create(client, payload)
    with pytest.raises(IntegrityError) as error, engine.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO bookings
              (id,facility_id,customer_ref,participants,starts_at,ends_at,status,created_at)
            SELECT :id,facility_id,customer_ref,participants,starts_at,ends_at,status,created_at
            FROM bookings WHERE id=:source
        """),
            {"id": uuid4(), "source": booking["id"]},
        )
    assert error.value.orig.sqlstate == "23P01"


def test_health_metrics_and_low_cardinality(client, payload, application, monkeypatch):
    assert client.get("/health").status_code == 200
    booking = create(client, payload)
    client.get(f"/api/v1/bookings/{booking['id']}")
    client.get("/unmatched-private-identifier")
    metrics = client.get("/metrics").text
    assert "app_ready 1.0" in metrics
    assert 'route="/api/v1/bookings/{booking_id}"' in metrics
    assert booking["id"] not in metrics
    assert "unmatched-private-identifier" not in metrics
    monkeypatch.setattr(application.state.database, "ready", lambda: False)
    assert client.get("/health").status_code == 503
    assert "app_ready 0.0" in client.get("/metrics").text


def test_cancellation_metric_counts_state_changes_only(client, payload):
    booking = create(client, payload)
    client.post(f"/api/v1/bookings/{booking['id']}/cancel")
    client.post(f"/api/v1/bookings/{booking['id']}/cancel")
    assert "bookings_cancelled_total 1.0" in client.get("/metrics").text
