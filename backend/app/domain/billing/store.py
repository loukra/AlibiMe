"""Verifying App Store purchases.

The app buys a consumable credit pack with StoreKit 2 and sends us the signed
transaction (a JWS). We only grant credits after checking Apple's signature, the
bundle id and the product, so a client can't invent purchases.

``AppStoreVerifier`` uses Apple's own app-store-server-library and needs Apple's
root certificates (https://www.apple.com/certificateauthority/) in
``APP_STORE_ROOT_CERTS_DIR``. ``MockStoreVerifier`` accepts ``mock:<product>:<id>``
tokens so purchases work end to end locally and in tests; it only runs with
``APP_ENV=local`` or ``test``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.errors import AppError


class InvalidStoreTransaction(AppError):
    code = "invalid_store_transaction"
    http_status = 400
    default_message = "The purchase couldn't be verified."


@dataclass(frozen=True)
class VerifiedTransaction:
    transaction_id: str
    product_id: str
    app_account_token: str | None = None
    revoked: bool = False


@dataclass(frozen=True)
class StoreNotification:
    type: str  # e.g. "REFUND", "CONSUMPTION_REQUEST"
    transaction: VerifiedTransaction | None


class StoreVerifier(Protocol):
    def verify_transaction(self, signed_transaction: str) -> VerifiedTransaction: ...

    def verify_notification(self, signed_payload: str) -> StoreNotification: ...


class MockStoreVerifier:
    """``mock:<product_id>:<transaction_id>`` for purchases and
    ``mock:<TYPE>:<product_id>:<transaction_id>`` for notifications."""

    def __init__(self) -> None:
        if not settings.is_dev:
            raise RuntimeError("The mock store verifier only runs with APP_ENV=local or test.")

    def verify_transaction(self, signed_transaction: str) -> VerifiedTransaction:
        parts = signed_transaction.split(":")
        if len(parts) != 3 or parts[0] != "mock" or not all(parts[1:]):
            raise InvalidStoreTransaction()
        return VerifiedTransaction(transaction_id=parts[2], product_id=parts[1])

    def verify_notification(self, signed_payload: str) -> StoreNotification:
        parts = signed_payload.split(":")
        if len(parts) != 4 or parts[0] != "mock":
            raise InvalidStoreTransaction()
        return StoreNotification(
            type=parts[1],
            transaction=VerifiedTransaction(transaction_id=parts[3], product_id=parts[2]),
        )


class AppStoreVerifier:  # pragma: no cover - needs Apple's certificates
    def __init__(self) -> None:
        from appstoreserverlibrary.models.Environment import Environment
        from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier

        environment = Environment(settings.app_store_environment)
        # Purchases from an Xcode StoreKit configuration are signed by Xcode,
        # not Apple: the library skips the signature, so never in production.
        if environment == Environment.XCODE:
            if not settings.is_dev:
                raise RuntimeError("APP_STORE_ENVIRONMENT=Xcode only runs with APP_ENV=local or test.")
            roots = []
        else:
            certs_dir = settings.app_store_root_certs_dir
            if not certs_dir:
                raise RuntimeError("Set APP_STORE_ROOT_CERTS_DIR to Apple's root certificates.")
            roots = [p.read_bytes() for p in sorted(Path(certs_dir).glob("*.cer"))]
            if not roots:
                raise RuntimeError(f"No .cer files in {certs_dir}.")
        self._verifier = SignedDataVerifier(
            roots,
            enable_online_checks=True,
            environment=environment,
            bundle_id=settings.app_store_bundle_id,
            app_apple_id=settings.app_store_app_apple_id,
        )

    def _wrap(self, payload) -> VerifiedTransaction:
        return VerifiedTransaction(
            transaction_id=payload.transactionId,
            product_id=payload.productId,
            app_account_token=payload.appAccountToken,
            revoked=payload.revocationDate is not None,
        )

    def verify_transaction(self, signed_transaction: str) -> VerifiedTransaction:
        from appstoreserverlibrary.signed_data_verifier import VerificationException

        try:
            return self._wrap(self._verifier.verify_and_decode_signed_transaction(signed_transaction))
        except VerificationException as exc:
            raise InvalidStoreTransaction() from exc

    def verify_notification(self, signed_payload: str) -> StoreNotification:
        from appstoreserverlibrary.signed_data_verifier import VerificationException

        try:
            note = self._verifier.verify_and_decode_notification(signed_payload)
            signed = note.data.signedTransactionInfo if note.data else None
            tx = (
                self._wrap(self._verifier.verify_and_decode_signed_transaction(signed))
                if signed else None
            )
        except VerificationException as exc:
            raise InvalidStoreTransaction() from exc
        return StoreNotification(type=note.rawNotificationType or "", transaction=tx)


def get_store_verifier() -> StoreVerifier:
    if settings.store_verifier == "app_store":
        return AppStoreVerifier()
    return MockStoreVerifier()
