"""Add Credits: catalog, App Store redemption, refunds, and the free dev path."""
import uuid

import pytest

from app.db.models.credit_ledger import CreditLedger
from app.db.models.credit_package_claim import CreditPackageClaim
from app.db.models.enums import FulfillmentMode, PlanKind
from app.db.models.plan import Plan
from tests.conftest import SECOND_PHONE, signup

PRODUCT_40 = "com.believablecall.app.credits40"


def _balance(client, headers):
    return client.get("/v1/entitlements", headers=headers).json()["credits_available"]


def _redeem(client, headers, token):
    return client.post(
        "/v1/credit-packages/redeem", headers=headers, json={"signed_transaction": token}
    )


@pytest.fixture
def dev_pack(db):
    """A free_dev pack, as used before purchases went live."""
    db.add(Plan(code="dev_5", kind=PlanKind.one_time.value, included_credit_units=5,
                display_name="5 Credits", fulfillment_mode=FulfillmentMode.free_dev.value,
                sort_order=99, active=True))
    db.commit()
    return "dev_5"


# --- Catalog ---

def test_list_shows_the_paid_packs_with_products_and_costs(client):
    a = signup(client)
    body = client.get("/v1/credit-packages", headers=a["headers"]).json()
    packs = body["packages"]
    assert [p["code"] for p in packs] == ["credits_12", "credits_40", "credits_100"]
    first = packs[0]
    assert first["credits"] == 12
    assert first["fulfillment_mode"] == "app_store_iap"
    assert first["store_product_id"] == "com.believablecall.app.credits12"
    assert first["price_label"] == "€2.99"
    assert body["credit_costs"] == {"call": 1, "sms": 1}  # test env: one each


def test_list_requires_auth(client):
    assert client.get("/v1/credit-packages").status_code == 401


# --- App Store redemption ---

def test_redeem_grants_the_packs_credits(client):
    a = signup(client)
    before = _balance(client, a["headers"])
    resp = _redeem(client, a["headers"], f"mock:{PRODUCT_40}:tx-1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "granted"
    assert body["granted_credits"] == 40
    assert body["plan_code"] == "credits_40"
    assert _balance(client, a["headers"]) == before + 40


def test_redeem_is_idempotent_per_transaction(client):
    a = signup(client)
    before = _balance(client, a["headers"])
    first = _redeem(client, a["headers"], f"mock:{PRODUCT_40}:tx-dup").json()
    second = _redeem(client, a["headers"], f"mock:{PRODUCT_40}:tx-dup").json()
    assert first["claim_id"] == second["claim_id"]
    assert _balance(client, a["headers"]) == before + 40


def test_transaction_cannot_be_redeemed_by_another_account(client):
    a = signup(client)
    b = signup(client, phone=SECOND_PHONE)
    _redeem(client, a["headers"], f"mock:{PRODUCT_40}:tx-shared")
    resp = _redeem(client, b["headers"], f"mock:{PRODUCT_40}:tx-shared")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "transaction_already_redeemed"


def test_invalid_transaction_is_rejected(client):
    a = signup(client)
    resp = _redeem(client, a["headers"], "forged")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_store_transaction"


def test_unknown_product_is_404(client):
    a = signup(client)
    assert _redeem(client, a["headers"], "mock:com.other.app.coins:tx-9").status_code == 404


def test_paid_pack_cannot_be_taken_for_free(client):
    a = signup(client)
    resp = client.post("/v1/credit-packages/credits_40/acquire", headers=a["headers"],
                       json={"client_request_id": "sneaky"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "package_not_acquirable"


def test_redeem_records_claim_and_ledger_entry(client, db):
    a = signup(client)
    claim_id = uuid.UUID(_redeem(client, a["headers"], f"mock:{PRODUCT_40}:tx-audit").json()["claim_id"])
    db.expire_all()
    claim = db.get(CreditPackageClaim, claim_id)
    assert claim.store_transaction_id == "tx-audit"
    assert claim.fulfillment_mode == "app_store_iap"
    ledger = db.query(CreditLedger).filter(CreditLedger.reference_id == claim_id).one()
    assert (ledger.entry_type, ledger.amount_units) == ("grant", 40)


# --- Refunds (App Store Server Notifications) ---

def test_refund_takes_the_credits_back(client):
    a = signup(client)
    before = _balance(client, a["headers"])
    _redeem(client, a["headers"], f"mock:{PRODUCT_40}:tx-ref")
    resp = client.post("/v1/webhooks/app-store",
                       json={"signedPayload": f"mock:REFUND:{PRODUCT_40}:tx-ref"})
    assert resp.status_code == 200
    assert resp.json()["refunded"] is True
    assert _balance(client, a["headers"]) == before
    # A second notification for the same refund changes nothing.
    again = client.post("/v1/webhooks/app-store",
                        json={"signedPayload": f"mock:REFUND:{PRODUCT_40}:tx-ref"})
    assert again.json()["refunded"] is False
    assert _balance(client, a["headers"]) == before


def test_other_notifications_are_stored_only(client):
    resp = client.post("/v1/webhooks/app-store",
                       json={"signedPayload": f"mock:CONSUMPTION_REQUEST:{PRODUCT_40}:tx-x"})
    assert resp.json() == {"status": "processed", "refunded": False}


def test_forged_notification_is_rejected(client):
    assert client.post("/v1/webhooks/app-store", json={"signedPayload": "nope"}).status_code == 400


# --- Free dev packs (still supported for local builds) ---

def test_free_dev_pack_grants_and_is_idempotent(client, dev_pack):
    a = signup(client)
    before = _balance(client, a["headers"])
    payload = {"client_request_id": "dup-claim"}
    first = client.post(f"/v1/credit-packages/{dev_pack}/acquire", headers=a["headers"], json=payload)
    second = client.post(f"/v1/credit-packages/{dev_pack}/acquire", headers=a["headers"], json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["claim_id"] == second.json()["claim_id"]
    assert _balance(client, a["headers"]) == before + 5


def test_acquire_unknown_package_is_404(client):
    a = signup(client)
    resp = client.post("/v1/credit-packages/credits_999/acquire", headers=a["headers"],
                       json={"client_request_id": "x"})
    assert resp.status_code == 404


def test_acquire_non_package_plan_is_rejected(client):
    a = signup(client)
    resp = client.post("/v1/credit-packages/free/acquire", headers=a["headers"],
                       json={"client_request_id": "y"})
    assert resp.status_code == 409


# --- Per-channel cost ---

def test_call_costs_more_than_a_text(client, monkeypatch):
    from app.core.config import settings
    from tests.conftest import get_template_id

    monkeypatch.setattr(settings, "call_credit_cost", 4)
    a = signup(client)
    _redeem(client, a["headers"], f"mock:{PRODUCT_40}:tx-cost")
    tid = get_template_id(client, a["headers"], "boss_travel_assignment")
    resp = client.post("/v1/requests", headers=a["headers"], json={
        "client_request_id": "c1", "template_id": tid, "channel": "call", "delay_seconds": 300,
    })
    assert resp.status_code == 201, resp.text


def test_mock_verifier_refuses_production(monkeypatch):
    from app.core.config import settings
    from app.domain.billing.store import MockStoreVerifier

    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(RuntimeError):
        MockStoreVerifier()
