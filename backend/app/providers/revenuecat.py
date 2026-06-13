"""Minimal RevenueCat webhook parsing helper (entitlement bridge, later).

In MVP we accept and persist the raw event; mapping to entitlements/credits is
intentionally conservative and feature-flagged.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RevenueCatEvent:
    event_id: str | None
    event_type: str | None
    app_user_id: str | None
    product_id: str | None
    entitlement_id: str | None


def parse_revenuecat_webhook(payload: dict) -> RevenueCatEvent:
    event = payload.get("event", payload) or {}
    return RevenueCatEvent(
        event_id=event.get("id"),
        event_type=event.get("type"),
        app_user_id=event.get("app_user_id"),
        product_id=event.get("product_id"),
        entitlement_id=event.get("entitlement_id"),
    )
