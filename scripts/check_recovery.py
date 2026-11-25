"""Verify persistence and a reversible database outage on the dedicated Compose project."""

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv


def main():
    load_dotenv()
    docker = shutil.which("docker") or "/Applications/Docker.app/Contents/Resources/bin/docker"
    command = [docker, "compose"]
    with httpx.Client(
        base_url="http://127.0.0.1:8000",
        timeout=15,
        trust_env=False,
        headers={"X-API-Key": os.environ["API_KEY"]},
    ) as client:
        facility = client.post(
            "/api/v1/facilities",
            json={
                "name": f"Recovery-{uuid4().hex[:12]}",
                "sport": "tennis",
                "capacity": 4,
            },
        )
        assert facility.status_code == 201
        start = (datetime.now(UTC) + timedelta(days=3)).replace(
            hour=7, minute=0, second=0, microsecond=0
        )
        booking = client.post(
            "/api/v1/bookings",
            json={
                "facility_id": facility.json()["id"],
                "customer_ref": "recovery-customer",
                "participants": 2,
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(hours=1)).isoformat(),
            },
        )
        assert booking.status_code == 201
        identifier = booking.json()["id"]
        subprocess.run([*command, "restart", "api"], check=True)
        wait_healthy(client)
        assert client.get(f"/api/v1/bookings/{identifier}").json()["id"] == identifier
        try:
            subprocess.run([*command, "stop", "db"], check=True)
            health = client.get("/health")
            assert health.status_code == 503
            business = client.get("/api/v1/facilities")
            assert business.status_code == 503
            metrics = client.get("/metrics")
            assert metrics.status_code == 200 and "app_ready 0.0" in metrics.text
        finally:
            subprocess.run([*command, "start", "db"], check=True)
        wait_healthy(client)
        assert client.get(f"/api/v1/bookings/{identifier}").json()["id"] == identifier
        assert client.post(f"/api/v1/bookings/{identifier}/cancel").status_code == 200
        assert (
            client.patch(
                f"/api/v1/facilities/{facility.json()['id']}/status", json={"is_active": False}
            ).status_code
            == 200
        )
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "persistence_after_api_restart": True,
        "health_during_database_outage": 503,
        "business_during_database_outage": 503,
        "metrics_during_database_outage": 200,
        "recovery_without_api_restart": True,
        "data_preserved": True,
    }
    Path("artifacts/recovery.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


def wait_healthy(client):
    for _ in range(40):
        try:
            if client.get("/health").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise AssertionError("API did not become healthy within 40 attempts")


if __name__ == "__main__":
    main()
