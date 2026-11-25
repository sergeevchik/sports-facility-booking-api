"""Normal traffic: availability, lists and create/cancel cycles on per-user facilities."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from locust import HttpUser, between, task


class BookingUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.client.trust_env = False
        self.client.headers["X-API-Key"] = os.environ["API_KEY"]
        start = (datetime.now(UTC) + timedelta(days=7)).replace(
            hour=7,
            minute=0,
            second=0,
            microsecond=0,
        )
        self.interval = {
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=1)).isoformat(),
        }
        response = self.client.post(
            "/api/v1/facilities",
            json={
                "name": f"Load-{uuid4().hex}",
                "sport": "tennis",
                "capacity": 4,
            },
            name="create load facility",
        )
        response.raise_for_status()
        self.facility_id = response.json()["id"]

    @task(3)
    def availability(self):
        self.client.get(
            "/api/v1/availability",
            params={**self.interval, "participants": 2},
            name="GET availability",
        )

    @task
    def bookings(self):
        self.client.get(
            "/api/v1/bookings", params={"facility_id": self.facility_id}, name="GET bookings"
        )

    @task
    def booking_cycle(self):
        with self.client.post(
            "/api/v1/bookings",
            json={
                **self.interval,
                "facility_id": self.facility_id,
                "customer_ref": "load-customer",
                "participants": 2,
            },
            name="POST booking",
            catch_response=True,
        ) as response:
            if response.status_code != 201:
                response.failure(f"Unexpected status {response.status_code}")
                return
            booking_id = response.json()["id"]
        self.client.post(f"/api/v1/bookings/{booking_id}/cancel", name="POST cancel")

    def on_stop(self):
        if hasattr(self, "facility_id"):
            response = self.client.get(
                "/api/v1/bookings",
                params={"facility_id": self.facility_id, "status": "confirmed"},
                name="cleanup bookings",
            )
            if response.status_code == 200:
                for booking in response.json()["items"]:
                    self.client.post(
                        f"/api/v1/bookings/{booking['id']}/cancel", name="cleanup cancel"
                    )
            self.client.patch(
                f"/api/v1/facilities/{self.facility_id}/status",
                json={"is_active": False},
                name="deactivate load facility",
            )
