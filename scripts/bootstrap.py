"""Generate local-only credentials; never overwrite an existing environment."""

import os
import secrets
from pathlib import Path


def main():
    path = Path(__file__).resolve().parents[1] / ".env"
    password = secrets.token_hex(24)
    content = (
        f"POSTGRES_PASSWORD={password}\nAPI_KEY={secrets.token_urlsafe(32)}\n"
        f"GRAFANA_ADMIN_PASSWORD={secrets.token_urlsafe(32)}\n"
        f"DATABASE_URL=postgresql+psycopg://booking:{password}@localhost:5432/booking\n"
        "APP_VERSION=1.0.0\nAPP_TIMEZONE=Europe/Moscow\n"
    )
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Existing .env preserved.")
        return
    with os.fdopen(descriptor, "w") as output:
        output.write(content)
    print("Created .env with local credentials (mode 600). Values were not printed.")


if __name__ == "__main__":
    main()
