"""Exercise a deployed service; never print credentials or personal data."""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv


def check(response, status):
    if response.status_code != status:
        raise AssertionError(f"Expected HTTP {status}; got {response.status_code}: {response.text}")
    return response.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output")
    args = parser.parse_args()
    load_dotenv()
    start = (datetime.now(UTC) + timedelta(days=2)).replace(
        hour=7, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=1)
    with httpx.Client(
        base_url=args.base_url,
        headers={"X-API-Key": os.environ["API_KEY"]},
        trust_env=False,
    ) as client:
        health = check(client.get("/health"), 200)
        facility = check(
            client.post(
                "/api/v1/facilities",
                json={
                    "name": f"Smoke-{uuid4().hex[:12]}",
                    "sport": "tennis",
                    "capacity": 4,
                },
            ),
            201,
        )
        payload = {
            "facility_id": facility["id"],
            "customer_ref": "smoke-customer",
            "participants": 2,
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
        }
        booking = check(client.post("/api/v1/bookings", json=payload), 201)
        check(client.post("/api/v1/bookings", json=payload), 409)
        check(client.get(f"/api/v1/bookings/{booking['id']}"), 200)
        cancelled = check(client.post(f"/api/v1/bookings/{booking['id']}/cancel"), 200)
        repeat = check(client.post(f"/api/v1/bookings/{booking['id']}/cancel"), 200)
        assert cancelled["cancelled_at"] == repeat["cancelled_at"]
        replacement = check(client.post("/api/v1/bookings", json=payload), 201)
        check(client.post(f"/api/v1/bookings/{replacement['id']}/cancel"), 200)
        check(
            client.patch(f"/api/v1/facilities/{facility['id']}/status", json={"is_active": False}),
            200,
        )
        metrics = client.get("/metrics")
        assert metrics.status_code == 200 and "bookings_created_total" in metrics.text
    result = {
        "health": health,
        "checks_passed": [
            "create_facility",
            "create_booking",
            "conflict_409",
            "read_booking",
            "cancel",
            "idempotent_cancel",
            "rebook_released_interval",
            "deactivate",
            "metrics",
        ],
    }
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as output:
            json.dump(result, output, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
