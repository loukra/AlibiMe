"""AppStoreVerifier in Xcode mode: StoreKit configuration purchases are
signed by Xcode, not Apple, so the library skips the signature check."""
from __future__ import annotations

import pytest

pytest.importorskip("appstoreserverlibrary")
import jwt  # noqa: E402  (installed with appstoreserverlibrary)

from app.core.config import settings  # noqa: E402
from app.domain.billing.store import AppStoreVerifier, InvalidStoreTransaction  # noqa: E402


def _xcode_transaction(**overrides) -> str:
    payload = {
        "transactionId": "2",
        "originalTransactionId": "2",
        "bundleId": settings.app_store_bundle_id,
        "productId": "com.believablecall.app.credits25",
        "type": "Consumable",
        "environment": "Xcode",
        "appAccountToken": "6f1c2a0e-1b2c-4d3e-8f90-123456789abc",
        "purchaseDate": 1793372220000,
        "signedDate": 1793372220000,
    }
    payload.update(overrides)
    return jwt.encode(payload, "xcode-local", algorithm="HS256")


@pytest.fixture
def xcode(monkeypatch):
    monkeypatch.setattr(settings, "app_store_environment", "Xcode")
    monkeypatch.setattr(settings, "app_store_root_certs_dir", None)


def test_xcode_mode_needs_no_certificates_and_reads_the_purchase(xcode):
    tx = AppStoreVerifier().verify_transaction(_xcode_transaction())
    assert tx.transaction_id == "2"
    assert tx.product_id == "com.believablecall.app.credits25"
    assert tx.app_account_token == "6f1c2a0e-1b2c-4d3e-8f90-123456789abc"
    assert not tx.revoked


def test_xcode_mode_rejects_other_environments_and_apps(xcode):
    verifier = AppStoreVerifier()
    with pytest.raises(InvalidStoreTransaction):
        verifier.verify_transaction(_xcode_transaction(environment="Sandbox"))
    with pytest.raises(InvalidStoreTransaction):
        verifier.verify_transaction(_xcode_transaction(bundleId="com.example.other"))


def test_xcode_mode_refuses_production(xcode, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    with pytest.raises(RuntimeError):
        AppStoreVerifier()
