"""Verify live Prometheus samples and the provisioned Grafana dashboard."""

import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv


def main():
    load_dotenv()
    queries = [
        'up{job="sports-booking-api"}',
        "app_ready",
        "bookings_created_total",
        "sum(http_requests_total)",
        "sum(http_request_duration_seconds_count)",
    ]
    results = {}
    with httpx.Client(timeout=10, trust_env=False) as client:
        for query in queries:
            # A healthy API can precede its first Prometheus scrape after a restart.
            for _ in range(30):
                response = client.get("http://127.0.0.1:9090/api/v1/query", params={"query": query})
                response.raise_for_status()
                payload = response.json()
                samples = payload.get("data", {}).get("result", [])
                if (
                    payload["status"] == "success"
                    and samples
                    and all(float(sample["value"][1]) > 0 for sample in samples)
                ):
                    results[query] = samples
                    break
                time.sleep(1)
            else:
                raise AssertionError(f"No positive live samples after 30 attempts: {query}")
        dashboard = client.get(
            "http://127.0.0.1:3000/api/dashboards/uid/sports-booking",
            auth=("admin", os.environ["GRAFANA_ADMIN_PASSWORD"]),
        )
        dashboard.raise_for_status()
        data = dashboard.json()
        results["grafana"] = {
            "title": data["dashboard"]["title"],
            "panels": len(data["dashboard"]["panels"]),
        }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/monitoring.json").write_text(json.dumps(results, indent=2) + "\n")
    print("Verified live Prometheus samples and provisioned Grafana dashboard.")


if __name__ == "__main__":
    main()
