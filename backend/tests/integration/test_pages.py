"""The privacy policy and support pages on the API domain."""
from __future__ import annotations

import pytest

from app.api.routes import pages


@pytest.fixture(autouse=True)
def fresh_render():
    pages._render.cache_clear()
    yield
    pages._render.cache_clear()


def test_privacy_page_renders_the_policy_with_its_table(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<h1>AlibiMe privacy policy" in resp.text
    assert "<table>" in resp.text and "Vapi Inc." in resp.text


def test_support_page_links_the_configured_email(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "support_email", "help@alibime.test")
    resp = client.get("/support")
    assert resp.status_code == 200
    assert '<a href="mailto:help@alibime.test">help@alibime.test</a>' in resp.text
    assert "{support_email}" not in resp.text
    assert 'href="/privacy"' in resp.text


def test_without_an_email_the_gap_stays_visible(client):
    assert "[support email]" in client.get("/support").text


def test_pages_stay_out_of_the_api_schema(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/privacy" not in paths and "/support" not in paths
