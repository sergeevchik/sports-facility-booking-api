"""Run a bounded, reproducible workload against this local development environment."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--seconds", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.users <= 50 or not 1 <= args.seconds <= 1800:
        parser.error("Use 1–50 users and 1–1800 seconds for the local environment")
    load_dotenv()
    if not os.environ.get("API_KEY"):
        parser.error("API_KEY is required; run bootstrap first")
    Path("artifacts/load").mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "load/locustfile.py",
        "--headless",
        "--host",
        "http://127.0.0.1:8000",
        "--users",
        str(args.users),
        "--spawn-rate",
        "1",
        "--run-time",
        f"{args.seconds}s",
        "--only-summary",
        "--csv",
        "artifacts/load/booking",
        "--csv-full-history",
        "--html",
        "artifacts/load/report.html",
        "--exit-code-on-error",
        "1",
    ]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    main()
