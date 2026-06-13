"""Test harness.

Runs the full suite on a throwaway SQLite database so the project is verifiable
locally with zero external services. The DATABASE_URL is set *before* importing
any app module so the app engine binds to the test DB.
"""
from __future__ import annotations

import os
import tempfile

# --- Configure environment BEFORE importing the app ---
_db_fd, _db_path = tempfile.mkstemp(suffix="-test.db")
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_db_path}"
os.environ["APP_SECRET_KEY"] = "test-secret-key-for-pytest-0123456789"
os.environ["PHONE_ENCRYPTION_KEY"] = ""  # derived from secret in dev/test
os.environ["OTP_PROVIDER"] = "mock"
os.environ["VOICE_PROVIDER"] = "mock"
os.environ["MESSAGE_PROVIDER"] = "mock"
os.environ["FEATURE_FREE_TEST_REQUEST"] = "true"
os.environ["FREE_TEST_CREDITS"] = "3"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.otp.mock import MOCK_OTP_CODE  # noqa: E402
from app.seeds.seed import seed_all  # noqa: E402

DEFAULT_PHONE = "+491701234567"
SECOND_PHONE = "+491701239999"


@pytest.fixture(autouse=True)
def fresh_db():
    """Recreate + seed the schema before every test for isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """A session for direct DB assertions. Always expire before reading."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def signup(client: TestClient, phone: str = DEFAULT_PHONE, locale: str = "en") -> dict:
    """Run the OTP start+confirm flow and return {token, user_id, headers}."""
    start = client.post(
        "/v1/auth/phone/start",
        json={"phone_number": phone, "device_id": "test-device", "locale": locale},
    )
    assert start.status_code == 200, start.text
    verification_id = start.json()["verification_id"]
    confirm = client.post(
        "/v1/auth/phone/confirm",
        json={"verification_id": verification_id, "code": MOCK_OTP_CODE, "device_id": "test-device"},
    )
    assert confirm.status_code == 200, confirm.text
    token = confirm.json()["session_token"]
    return {
        "token": token,
        "user_id": confirm.json()["user"]["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def auth(client):
    return signup(client)


def get_template_id(client: TestClient, headers: dict, code: str) -> str:
    resp = client.get("/v1/templates", headers=headers)
    assert resp.status_code == 200, resp.text
    for t in resp.json()["templates"]:
        if t["code"] == code:
            return t["id"]
    raise AssertionError(f"template {code} not found in catalog")
