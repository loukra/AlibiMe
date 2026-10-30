"""Unit tests for the Twilio sender-line sync (DB upsert logic, no network)."""
from sqlalchemy import select

from app.admin.sync_sender_lines import TwilioNumber, link_vapi_numbers, sync_sender_lines
from app.db.models.enums import ServiceIdentityStatus
from app.db.models.service_identity import ServiceIdentity


def _twilio(sid="PN1", e164="+14155550111", sms=True, voice=False):
    return TwilioNumber(sid=sid, e164=e164, sms=sms, voice=voice)


def test_sync_imports_twilio_number_and_demotes_mock_sms(db):
    # The seed leaves one mock SMS-capable line in the pool.
    mock = db.execute(
        select(ServiceIdentity).where(ServiceIdentity.provider == "mock")
    ).scalars().first()
    assert mock is not None and mock.capability_outbound_sms is True

    result = sync_sender_lines(db, [_twilio()], messaging_service_sid="MG_test")
    assert result["created"] == 1
    assert result["sms_demoted"] == 1

    db.expire_all()
    row = db.execute(
        select(ServiceIdentity).where(ServiceIdentity.external_identity_id == "PN1")
    ).scalars().first()
    assert row.provider == "twilio"
    assert row.identity_value == "+14155550111"
    assert row.capability_outbound_sms is True
    assert row.status == ServiceIdentityStatus.active.value
    assert row.twilio_messaging_service_sid == "MG_test"

    # Mock line keeps voice but no longer offers SMS, so SMS allocation uses the
    # real Twilio number.
    mock = db.get(ServiceIdentity, mock.id)
    assert mock.capability_outbound_sms is False
    assert mock.capability_outbound_voice is True


def test_sync_is_idempotent(db):
    sync_sender_lines(db, [_twilio()], messaging_service_sid="MG_test")
    result = sync_sender_lines(db, [_twilio()], messaging_service_sid="MG_test")
    assert result["created"] == 0
    assert result["updated"] == 1
    rows = db.execute(
        select(ServiceIdentity).where(ServiceIdentity.external_identity_id == "PN1")
    ).scalars().all()
    assert len(rows) == 1  # no duplicate


def test_sync_disables_vanished_numbers(db):
    sync_sender_lines(db, [_twilio(sid="PN1"), _twilio(sid="PN2", e164="+14155550222")],
                      messaging_service_sid="MG_test")
    # PN2 disappears from Twilio on the next sync.
    result = sync_sender_lines(db, [_twilio(sid="PN1")], messaging_service_sid="MG_test")
    assert result["disabled"] == 1
    gone = db.execute(
        select(ServiceIdentity).where(ServiceIdentity.external_identity_id == "PN2")
    ).scalars().first()
    assert gone.status == ServiceIdentityStatus.disabled.value


def test_sync_adopts_existing_number_row(db):
    # A pre-existing row with the same E.164 (manual seed) gets adopted, not
    # duplicated, and upgraded to a real twilio row keyed by SID.
    db.add(ServiceIdentity(provider="manual", identity_value="+14155550111",
                           capability_outbound_sms=True, capability_outbound_voice=False,
                           status=ServiceIdentityStatus.active.value))
    db.commit()
    sync_sender_lines(db, [_twilio(sid="PN9", e164="+14155550111")],
                      messaging_service_sid="MG_test")
    rows = db.execute(
        select(ServiceIdentity).where(ServiceIdentity.identity_value == "+14155550111")
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].provider == "twilio"
    assert rows[0].external_identity_id == "PN9"


def test_link_vapi_numbers_stores_known_ids_and_imports_the_rest(db):
    sync_sender_lines(
        db,
        [
            _twilio(sid="PN1", e164="+14155550111", voice=True),
            _twilio(sid="PN2", e164="+14155550222", voice=True),
            _twilio(sid="PN3", e164="+14155550333", voice=False),  # sms only
        ],
        messaging_service_sid="MG_test",
    )
    imported = []

    def fake_import(e164):
        imported.append(e164)
        return "vapi_new"

    result = link_vapi_numbers(db, {"+14155550111": "vapi_1"}, fake_import)
    assert result == {"linked": 2, "imported": 1, "missing": 0}
    assert imported == ["+14155550222"]

    by_sid = {
        r.external_identity_id: r.vapi_phone_number_id
        for r in db.execute(
            select(ServiceIdentity).where(ServiceIdentity.provider == "twilio")
        ).scalars()
    }
    assert by_sid == {"PN1": "vapi_1", "PN2": "vapi_new", "PN3": None}


def test_link_vapi_numbers_without_import_leaves_unknown_lines(db):
    sync_sender_lines(db, [_twilio(voice=True)], messaging_service_sid="MG_test")
    assert link_vapi_numbers(db, {}) == {"linked": 0, "imported": 0, "missing": 1}
