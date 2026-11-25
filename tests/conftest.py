import os
import secrets
from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.config import Settings, get_settings
from app.main import create_app

TEST_KEY = secrets.token_urlsafe(32)
TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://booking@127.0.0.1:55432/booking_test"
)


@pytest.fixture
def settings():
    return Settings(database_url=TEST_URL, api_key=TEST_KEY, _env_file=None)


@pytest.fixture(scope="session")
def engine():
    if make_url(TEST_URL).database != "booking_test":
        pytest.fail("Refusing to run destructive tests against a database other than booking_test")
    os.environ["DATABASE_URL"] = TEST_URL
    os.environ["API_KEY"] = TEST_KEY
    get_settings.cache_clear()
    command.downgrade(Config("alembic.ini"), "base")
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(TEST_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def clock():
    return {"now": datetime(2030, 6, 1, 5, tzinfo=UTC)}


@pytest.fixture
def application(engine, settings, clock):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE bookings, facilities CASCADE"))
    return create_app(settings, clock=lambda: clock["now"])


@pytest.fixture
def client(application):
    with TestClient(application, headers={"X-API-Key": TEST_KEY}) as client:
        yield client


@pytest.fixture
def facility(client):
    response = client.post(
        "/api/v1/facilities",
        json={
            "name": "Test tennis court",
            "sport": "tennis",
            "capacity": 4,
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def payload(facility):
    return {
        "facility_id": facility["id"],
        "customer_ref": "test-customer",
        "participants": 2,
        "starts_at": "2030-06-02T10:00:00+03:00",
        "ends_at": "2030-06-02T11:00:00+03:00",
    }
