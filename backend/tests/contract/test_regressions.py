"""Critical regression tests (spec: "Critical regression tests").

These prove the load-bearing invariants hold.
"""
import uuid

import pytest
from sqlalchemy import select

from app.core.errors import PhoneNotVerified
from app.db.models.template import Template
from app.db.models.user import User
from app.domain.requests import service as requests_service
from tests.conftest import get_template_id, signup


def test_api_rejects_client_supplied_target_number(client):
    """The API must reject any attempt to specify a different target number."""
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    for forbidden_field in ("phone_number", "to", "target", "destination"):
        resp = client.post(
            "/v1/requests",
            headers=a["headers"],
            json={
                "client_request_id": "c1",
                "template_id": tid,
                "channel": "call",
                "delay_seconds": 0,
                forbidden_field: "+1999999999",
            },
        )
        assert resp.status_code == 422, f"{forbidden_field} should be rejected"
        assert resp.json()["error"]["code"] == "validation_failed"


def test_cannot_create_request_without_verified_primary_number(db):
    """A user with no verified primary number cannot create a request."""
    user = User(locale="en")
    db.add(user)
    db.commit()
    template = db.execute(
        select(Template).where(Template.code == "boss_travel_assignment")
    ).scalar_one()
    with pytest.raises(PhoneNotVerified):
        requests_service.create_request(
            db,
            user.id,
            client_request_id="c1",
            template_id=template.id,
            channel="call",
            delay_seconds=0,
            scheduled_at=None,
            user_locale="en",
        )


def test_pending_jobs_capped(client):
    """Multiple pending jobs are allowed up to the cap; one more is rejected."""
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    for i in range(3):
        r = client.post(
            "/v1/requests",
            headers=a["headers"],
            json={"client_request_id": f"c{i}", "template_id": tid, "channel": "call", "delay_seconds": 300},
        )
        assert r.status_code == 201, r.text
    over = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c4", "template_id": tid, "channel": "call", "delay_seconds": 300},
    )
    assert over.status_code == 409
    assert over.json()["error"]["code"] == "active_request_exists"


def test_template_cannot_be_used_on_unsupported_channel(client):
    a = signup(client)
    tid = get_template_id(client, a["headers"], "safety_checkin")  # sms-only
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={"client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 0},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "template_channel_not_supported"
