"""Add Credits feature: catalog listing + idempotent acquisition."""
from tests.conftest import signup


def test_list_credit_packages_returns_active_packs_sorted(client):
    a = signup(client)
    resp = client.get("/v1/credit-packages", headers=a["headers"])
    assert resp.status_code == 200, resp.text
    packages = resp.json()["packages"]
    codes = [p["code"] for p in packages]

    # The four seeded credit packs, in sort order. `free` and the subscription
    # stub are not credit packages and must not appear.
    assert codes == ["credits_5", "credits_15", "credits_30", "credits_60"]
    first = packages[0]
    assert first["display_name"] == "5 Credits"
    assert first["credits"] == 5
    assert first["fulfillment_mode"] == "free_dev"
    assert first["price_label"] == "Free for now"
    assert first["badge_text"] == "Free"
    assert first["active"] is True


def test_list_credit_packages_requires_auth(client):
    assert client.get("/v1/credit-packages").status_code == 401


def test_acquire_grants_credits_and_updates_balance(client):
    a = signup(client)
    before = client.get("/v1/entitlements", headers=a["headers"]).json()["credits_available"]

    resp = client.post(
        "/v1/credit-packages/credits_15/acquire",
        headers=a["headers"],
        json={"client_request_id": "claim-1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "granted"
    assert body["granted_credits"] == 15
    assert body["plan_code"] == "credits_15"
    assert body["credits_available"] == before + 15
    assert body["claim_id"]

    # Entitlements endpoint reflects the new balance (backend source of truth).
    after = client.get("/v1/entitlements", headers=a["headers"]).json()["credits_available"]
    assert after == before + 15


def test_acquire_is_idempotent_on_client_request_id(client):
    a = signup(client)
    before = client.get("/v1/entitlements", headers=a["headers"]).json()["credits_available"]

    payload = {"client_request_id": "dup-claim"}
    first = client.post("/v1/credit-packages/credits_5/acquire", headers=a["headers"], json=payload)
    second = client.post("/v1/credit-packages/credits_5/acquire", headers=a["headers"], json=payload)

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["claim_id"] == second.json()["claim_id"]
    # Credited exactly once despite two calls.
    after = client.get("/v1/entitlements", headers=a["headers"]).json()["credits_available"]
    assert after == before + 5


def test_acquire_unknown_package_is_404(client):
    a = signup(client)
    resp = client.post(
        "/v1/credit-packages/credits_999/acquire",
        headers=a["headers"],
        json={"client_request_id": "x"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_acquire_non_package_plan_is_rejected(client):
    a = signup(client)
    # `free` is an active one-time plan but grants 0 credits -> not a package.
    resp = client.post(
        "/v1/credit-packages/free/acquire",
        headers=a["headers"],
        json={"client_request_id": "y"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "package_not_acquirable"


def test_acquire_records_claim_and_ledger_entry(client, db):
    import uuid

    from app.db.models.credit_ledger import CreditLedger
    from app.db.models.credit_package_claim import CreditPackageClaim

    a = signup(client)
    resp = client.post(
        "/v1/credit-packages/credits_30/acquire",
        headers=a["headers"],
        json={"client_request_id": "audit-1"},
    )
    claim_id = uuid.UUID(resp.json()["claim_id"])

    db.expire_all()
    claim = db.get(CreditPackageClaim, claim_id)
    assert claim is not None
    assert claim.status == "granted"
    assert claim.credits_granted == 30
    assert claim.granted_at is not None

    # The grant references the claim via the ledger (entry_type=grant).
    ledger = (
        db.query(CreditLedger)
        .filter(CreditLedger.reference_id == claim_id)
        .one()
    )
    assert ledger.entry_type == "grant"
    assert ledger.reference_type == "purchase"
    assert ledger.amount_units == 30
