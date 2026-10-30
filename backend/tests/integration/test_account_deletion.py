"""DELETE /v1/me removes the account and its data (App Store requirement)."""
import uuid

from sqlalchemy import func, select

from app.db.models import (
    CreditLedger,
    PhoneNumber,
    Request,
    User,
    UserSenderBinding,
    UserSession,
)
from tests.conftest import SECOND_PHONE, get_template_id, signup


def _send(client, headers, channel="sms", crid="c1"):
    tid = get_template_id(client, headers, "boss_travel_assignment")
    resp = client.post(
        "/v1/requests",
        headers=headers,
        json={"client_request_id": crid, "template_id": tid, "channel": channel, "delay_seconds": 300},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _count(db, model, user_id):
    return db.execute(
        select(func.count()).select_from(model).where(model.user_id == user_id)
    ).scalar_one()


def test_delete_removes_user_and_data(client, db):
    a = signup(client)
    _send(client, a["headers"])
    user_id = uuid.UUID(a["user_id"])

    resp = client.delete("/v1/me", headers=a["headers"])
    assert resp.status_code == 204

    db.expire_all()
    assert db.get(User, user_id) is None
    for model in (PhoneNumber, Request, UserSenderBinding, UserSession, CreditLedger):
        assert _count(db, model, user_id) == 0, model.__name__


def test_token_stops_working(client):
    a = signup(client)
    client.delete("/v1/me", headers=a["headers"])
    assert client.get("/v1/me", headers=a["headers"]).status_code == 401


def test_other_users_untouched(client):
    a = signup(client)
    b = signup(client, phone=SECOND_PHONE)
    _send(client, b["headers"], channel="call")
    client.delete("/v1/me", headers=a["headers"])
    assert client.get("/v1/me", headers=b["headers"]).status_code == 200
    assert client.get("/v1/history", headers=b["headers"]).json()["items"]


def test_signing_up_again_gives_no_second_free_allowance(client):
    a = signup(client)
    assert client.get("/v1/me", headers=a["headers"]).json()["credits_available"] == 3
    client.delete("/v1/me", headers=a["headers"])

    again = signup(client)
    assert again["user_id"] != a["user_id"]
    assert client.get("/v1/me", headers=again["headers"]).json()["credits_available"] == 0


def test_requires_auth(client):
    assert client.delete("/v1/me").status_code == 401
