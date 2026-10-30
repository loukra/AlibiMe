"""Stable sender identity + save-contact metadata."""
import uuid

from sqlalchemy import select

from app.db.models.enums import SenderBindingStatus, ServiceIdentityStatus
from app.db.models.request import Request
from app.db.models.service_identity import ServiceIdentity
from app.db.models.user_sender_binding import UserSenderBinding
from tests.conftest import get_template_id, signup


def _create_sms(client, headers, template, crid):
    tid = get_template_id(client, headers, template)
    return client.post(
        "/v1/requests",
        headers=headers,
        json={"client_request_id": crid, "template_id": tid, "channel": "sms", "delay_seconds": 0},
    )


def _cancel(client, headers, request_id):
    return client.post(f"/v1/requests/{request_id}/cancel", headers=headers)


def test_sms_create_returns_sender_identity(client):
    a = signup(client)
    resp = _create_sms(client, a["headers"], "boss_travel_assignment", "c1")
    assert resp.status_code == 201, resp.text
    sender = resp.json()["sender_identity"]
    assert sender is not None
    assert sender["sender_persona_key"] == "boss"
    assert sender["sender_display_name"] == "Boss"
    assert sender["sender_phone_e164"]  # the company's own sender number
    assert sender["contact_prompt_recommended"] is True
    assert uuid.UUID(sender["sender_binding_id"])  # parseable


def test_same_persona_reuses_one_binding_across_templates(client, db):
    """Two different templates with persona 'best_friend' must reuse the same
    binding (and therefore the same sender number)."""
    a = signup(client)
    first = _create_sms(client, a["headers"], "best_friend_need_you_outside", "c1").json()
    _cancel(client, a["headers"], first["request_id"])  # free the one-active slot
    second = _create_sms(client, a["headers"], "safety_checkin", "c2").json()

    assert first["sender_identity"]["sender_persona_key"] == "best_friend"
    assert second["sender_identity"]["sender_persona_key"] == "best_friend"
    assert (
        first["sender_identity"]["sender_binding_id"]
        == second["sender_identity"]["sender_binding_id"]
    )
    assert (
        first["sender_identity"]["sender_phone_e164"]
        == second["sender_identity"]["sender_phone_e164"]
    )

    bindings = db.execute(
        select(UserSenderBinding).where(
            UserSenderBinding.user_id == uuid.UUID(a["user_id"]),
            UserSenderBinding.sender_persona_key == "best_friend",
        )
    ).scalars().all()
    assert len(bindings) == 1


def test_different_personas_share_one_number_but_distinct_bindings(client):
    """With a single-number pool, distinct personas bind to the same line but get
    their own binding rows."""
    a = signup(client)
    boss = _create_sms(client, a["headers"], "boss_travel_assignment", "c1").json()
    _cancel(client, a["headers"], boss["request_id"])
    sibling = _create_sms(client, a["headers"], "sibling_family_checkin", "c2").json()

    assert (
        boss["sender_identity"]["sender_binding_id"]
        != sibling["sender_identity"]["sender_binding_id"]
    )
    assert (
        boss["sender_identity"]["sender_phone_e164"]
        == sibling["sender_identity"]["sender_phone_e164"]
    )


def test_request_persists_sender_snapshot(client, db):
    a = signup(client)
    resp = _create_sms(client, a["headers"], "boss_travel_assignment", "c1").json()
    req = db.get(Request, uuid.UUID(resp["request_id"]))
    assert req.sender_binding_id is not None
    assert req.sender_persona_key == "boss"
    assert req.sender_display_name_snapshot == "Boss"
    assert req.sender_phone_e164_snapshot == resp["sender_identity"]["sender_phone_e164"]


def test_history_exposes_sender_snapshot(client):
    a = signup(client)
    _create_sms(client, a["headers"], "boss_travel_assignment", "c1")
    items = client.get("/v1/history", headers=a["headers"]).json()["items"]
    assert items
    item = items[0]
    assert item["sender_persona_key"] == "boss"
    assert item["sender_display_name"] == "Boss"
    assert item["sender_phone_e164"]


def _create_call(client, headers, template, crid):
    tid = get_template_id(client, headers, template)
    return client.post(
        "/v1/requests",
        headers=headers,
        json={"client_request_id": crid, "template_id": tid, "channel": "call", "delay_seconds": 0},
    )


def _add_line(db, value, *, voice=True, sms=True):
    line = ServiceIdentity(
        provider="mock",
        identity_value=value,
        capability_outbound_voice=voice,
        capability_outbound_sms=sms,
        status=ServiceIdentityStatus.active.value,
    )
    db.add(line)
    db.commit()
    return line


def test_call_request_returns_sender_identity(client):
    """Calls get a fixed sender number too, so a saved contact shows for them."""
    a = signup(client)
    resp = _create_call(client, a["headers"], "boss_travel_assignment", "c1").json()
    sender = resp["sender_identity"]
    assert sender is not None
    assert sender["sender_persona_key"] == "boss"
    assert sender["sender_phone_e164"]
    assert sender["contact_prompt_recommended"] is True


def test_call_and_text_from_one_persona_share_the_number(client, db):
    a = signup(client)
    _add_line(db, "+10000000201")
    _add_line(db, "+10000000202")
    text = _create_sms(client, a["headers"], "best_friend_need_you_outside", "c1").json()
    _cancel(client, a["headers"], text["request_id"])
    call = _create_call(client, a["headers"], "best_friend_need_you_outside", "c2").json()
    assert (
        call["sender_identity"]["sender_phone_e164"]
        == text["sender_identity"]["sender_phone_e164"]
    )


def test_personas_get_distinct_numbers_when_the_pool_allows(client, db):
    a = signup(client)
    _add_line(db, "+10000000301")
    boss = _create_call(client, a["headers"], "boss_travel_assignment", "c1").json()
    _cancel(client, a["headers"], boss["request_id"])
    sibling = _create_call(client, a["headers"], "sibling_family_checkin", "c2").json()
    assert (
        boss["sender_identity"]["sender_phone_e164"]
        != sibling["sender_identity"]["sender_phone_e164"]
    )


def test_allocation_prefers_lines_that_call_and_text(client, db):
    # Retire the seed line so only the two new lines compete.
    for line in db.execute(select(ServiceIdentity)).scalars().all():
        line.status = ServiceIdentityStatus.disabled.value
    db.commit()
    _add_line(db, "+10000000401", sms=False)  # older, voice only
    _add_line(db, "+10000000402")
    a = signup(client)
    call = _create_call(client, a["headers"], "boss_travel_assignment", "c1").json()
    assert call["sender_identity"]["sender_phone_e164"] == "+10000000402"


def test_orphaned_line_reallocates_on_next_send(client, db):
    """If the bound line is disabled, the binding is re-pointed to a replacement
    line without mutating prior history."""
    a = signup(client)
    first = _create_sms(client, a["headers"], "boss_travel_assignment", "c1").json()
    _cancel(client, a["headers"], first["request_id"])
    binding_id = uuid.UUID(first["sender_identity"]["sender_binding_id"])

    # Disable the currently-bound line and add a replacement.
    binding = db.get(UserSenderBinding, binding_id)
    old_line = db.get(ServiceIdentity, binding.sender_line_id)
    old_line.status = ServiceIdentityStatus.disabled.value
    replacement = ServiceIdentity(
        provider="mock",
        identity_value="+10000000999",
        capability_outbound_voice=True,
        capability_outbound_sms=True,
        status=ServiceIdentityStatus.active.value,
        display_label="replacement",
    )
    db.add(replacement)
    db.commit()

    second = _create_sms(client, a["headers"], "boss_travel_assignment", "c2").json()
    assert second["sender_identity"]["sender_binding_id"] == str(binding_id)  # same binding
    assert second["sender_identity"]["sender_phone_e164"] == "+10000000999"  # new line

    db.expire_all()
    binding = db.get(UserSenderBinding, binding_id)
    assert binding.status == SenderBindingStatus.active.value
    # Prior history snapshot is untouched.
    first_req = db.get(Request, uuid.UUID(first["request_id"]))
    assert first_req.sender_phone_e164_snapshot != "+10000000999"


def test_no_destination_number_in_request_body_still_rejected(client):
    """The own-number invariant is unaffected by sender identity."""
    a = signup(client)
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    resp = client.post(
        "/v1/requests",
        headers=a["headers"],
        json={
            "client_request_id": "c1",
            "template_id": tid,
            "channel": "sms",
            "delay_seconds": 0,
            "to": "+15551234567",
        },
    )
    assert resp.status_code == 422
