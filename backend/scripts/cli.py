#!/usr/bin/env python
"""bc — a tiny CLI to exercise the BelievableCall backend API.

Run it from the `backend/` directory so the local helpers (`dispatch`,
`simulate`) can import the app for the all-mock flow.

Examples
--------
    python scripts/cli.py signup --phone +491701234567
    python scripts/cli.py templates
    python scripts/cli.py create --template boss_travel_assignment --channel call
    python scripts/cli.py dispatch              # run one worker tick locally
    python scripts/cli.py simulate <request_id> # drive provider webhooks -> completed
    python scripts/cli.py get <request_id>
    python scripts/cli.py history

    # the whole thing end-to-end, all-mock, no separate worker needed:
    python scripts/cli.py demo

The mock OTP code is always 123456.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Ensure `backend/` is importable when the script is run directly
# (so the local `dispatch` / `simulate` helpers can import `app`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_BASE_URL = os.environ.get("BC_BASE_URL", "http://localhost:8000")
SESSION_FILE = Path(__file__).resolve().parent.parent / ".bc_cli_session.json"
MOCK_OTP_CODE = "123456"

# --- tiny terminal helpers ---
_C = {"g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "b": "\033[34m", "d": "\033[2m", "x": "\033[0m"}


def _color(s: str, c: str) -> str:
    if not sys.stdout.isatty():
        return s
    return f"{_C[c]}{s}{_C['x']}"


def _header(text: str) -> None:
    print(_color(f"\n— {text} —", "b"))


def _dump(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _ok(text: str) -> None:
    print(_color("✓ " + text, "g"))


def _fail(text: str) -> None:
    print(_color("✗ " + text, "r"))


# --- session persistence ---
def load_session() -> dict:
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return {}


def save_session(data: dict) -> None:
    SESSION_FILE.write_text(json.dumps(data, indent=2))


def get_token(args) -> str | None:
    if getattr(args, "token", None):
        return args.token
    return load_session().get("token")


# --- HTTP ---
def api(method: str, path: str, base_url: str, *, token: str | None = None, json_body: dict | None = None) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = base_url.rstrip("/") + path
    try:
        resp = httpx.request(method, url, headers=headers, json=json_body, timeout=15.0)
    except httpx.ConnectError:
        _fail(f"Could not connect to {base_url}. Is the API running?  (make api)")
        sys.exit(2)

    if resp.headers.get("content-type", "").startswith("application/json"):
        body = resp.json()
    else:
        body = {"raw": resp.text}

    if resp.status_code >= 400:
        err = body.get("error", body)
        _fail(f"{resp.status_code} {err.get('code', '')}: {err.get('message', body)}")
        if os.environ.get("BC_DEBUG"):
            _dump(body)
        sys.exit(1)
    return body


def resolve_template_id(base_url: str, token: str, template: str) -> str:
    """Accept either a template code or a UUID."""
    if len(template) == 36 and template.count("-") == 4:
        return template
    catalog = api("GET", "/v1/templates", base_url, token=token)["templates"]
    for t in catalog:
        if t["code"] == template:
            return t["id"]
    _fail(f"template '{template}' not found. Available: {', '.join(t['code'] for t in catalog)}")
    sys.exit(1)


# --- commands ---
def cmd_signup(args) -> None:
    base = args.base_url
    _header(f"OTP start for {args.phone}")
    start = api("POST", "/v1/auth/phone/start", base, json_body={
        "phone_number": args.phone, "device_id": args.device, "locale": args.locale,
    })
    _dump(start)
    _header("OTP confirm")
    confirm = api("POST", "/v1/auth/phone/confirm", base, json_body={
        "verification_id": start["verification_id"], "code": args.code, "device_id": args.device,
    })
    save_session({"token": confirm["session_token"], "base_url": base, "user": confirm["user"]})
    _ok(f"signed in as {confirm['user']['id']}  ({confirm['user']['phone_number_masked']})")
    _ok(f"session saved to {SESSION_FILE.name}")


def cmd_me(args) -> None:
    _header("me")
    _dump(api("GET", "/v1/me", args.base_url, token=get_token(args)))


def cmd_templates(args) -> None:
    _header("templates")
    catalog = api("GET", "/v1/templates", args.base_url, token=get_token(args))["templates"]
    for t in catalog:
        chans = "/".join(t["supported_channels"])
        print(f"  {_color(t['code'], 'y')}  [{chans}]  — {t['display_name']}")


def cmd_create(args) -> None:
    base, token = args.base_url, get_token(args)
    tid = resolve_template_id(base, token, args.template)
    body = {"client_request_id": args.id, "template_id": tid, "channel": args.channel}
    if args.at:
        body["scheduled_at"] = args.at
    else:
        body["delay_seconds"] = args.delay
    _header(f"create {args.channel} request")
    result = api("POST", "/v1/requests", base, token=token, json_body=body)
    _dump(result)
    _ok(f"request_id = {result['request_id']}")


def cmd_get(args) -> None:
    _header(f"request {args.request_id}")
    _dump(api("GET", f"/v1/requests/{args.request_id}", args.base_url, token=get_token(args)))


def cmd_cancel(args) -> None:
    _header(f"cancel {args.request_id}")
    _dump(api("POST", f"/v1/requests/{args.request_id}/cancel", args.base_url, token=get_token(args)))


def cmd_history(args) -> None:
    _header("history")
    _dump(api("GET", "/v1/history", args.base_url, token=get_token(args)))


def cmd_entitlements(args) -> None:
    _header("entitlements")
    _dump(api("GET", "/v1/entitlements", args.base_url, token=get_token(args)))


def cmd_dispatch(args) -> None:
    """Run one local worker tick (claims + dispatches due requests)."""
    from datetime import timedelta

    from app.core.clock import utcnow
    from app.db.session import SessionLocal
    from app.workers import dispatch

    _header("worker dispatch tick (local)")
    db = SessionLocal()
    try:
        outcomes = dispatch.run_once(db, now=utcnow() + timedelta(seconds=5))
    finally:
        db.close()
    if outcomes:
        _ok(f"dispatched batch: {outcomes}")
    else:
        print(_color("  nothing due", "d"))


def cmd_simulate(args) -> None:
    """Drive mock provider webhooks for a request until it reaches a terminal state."""
    import uuid

    from app.db.models.attempts import CallAttempt, MessageAttempt
    from app.db.models.request import Request
    from app.db.session import SessionLocal
    from app.providers.messaging.mock import MockMessageProvider
    from app.providers.voice.mock import MockVoiceCallProvider

    base = args.base_url
    db = SessionLocal()
    try:
        req = db.get(Request, uuid.UUID(args.request_id))
        if req is None:
            _fail("request not found in local DB")
            sys.exit(1)
        if req.channel == "call":
            attempt = (
                db.query(CallAttempt).filter(CallAttempt.request_id == req.id)
                .order_by(CallAttempt.attempt_no.desc()).first()
            )
            if not attempt or not attempt.provider_call_id:
                _fail("no dispatched call attempt yet — run `dispatch` first")
                sys.exit(1)
            events = MockVoiceCallProvider.simulate_lifecycle(attempt.provider_call_id, outcome=args.outcome)
            endpoint = "/v1/webhooks/voice"
        else:
            attempt = (
                db.query(MessageAttempt).filter(MessageAttempt.request_id == req.id)
                .order_by(MessageAttempt.attempt_no.desc()).first()
            )
            if not attempt or not attempt.provider_message_id:
                _fail("no dispatched message attempt yet — run `dispatch` first")
                sys.exit(1)
            outcome = "delivered" if args.outcome == "completed" else args.outcome
            events = MockMessageProvider.simulate_lifecycle(attempt.provider_message_id, outcome=outcome)
            endpoint = "/v1/webhooks/sms"
    finally:
        db.close()

    _header(f"simulate {req.channel} lifecycle -> {endpoint}")
    for ev in events:
        result = api("POST", endpoint, base, json_body=ev)
        print(f"  {ev['type']:18} -> {result['status']}")
    _ok("done — check `get` to see the final status")


def cmd_demo(args) -> None:
    """Full all-mock flow end to end (no separate worker required)."""
    base = args.base_url
    print(_color("BelievableCall API demo (all-mock)", "b"))

    _header(f"1. signup {args.phone}")
    start = api("POST", "/v1/auth/phone/start", base, json_body={"phone_number": args.phone, "locale": "en"})
    confirm = api("POST", "/v1/auth/phone/confirm", base,
                  json_body={"verification_id": start["verification_id"], "code": MOCK_OTP_CODE})
    token = confirm["session_token"]
    save_session({"token": token, "base_url": base, "user": confirm["user"]})
    _ok(f"user {confirm['user']['id']}  ({confirm['user']['phone_number_masked']})")

    me = api("GET", "/v1/me", base, token=token)
    _ok(f"credits available: {me['credits_available']}")

    _header("2. pick a template")
    catalog = api("GET", "/v1/templates", base, token=token)["templates"]
    tmpl = next(t for t in catalog if t["code"] == "boss_travel_assignment")
    _ok(f"{tmpl['code']} [{'/'.join(tmpl['supported_channels'])}]")

    _header("3. create immediate call request")
    created = api("POST", "/v1/requests", base, token=token, json_body={
        "client_request_id": "demo-1", "template_id": tmpl["id"], "channel": "call", "delay_seconds": 0,
    })
    rid = created["request_id"]
    _ok(f"request {rid}  status={created['status']}")

    # local worker tick + webhook simulation
    args.request_id = rid
    args.outcome = "completed"
    cmd_dispatch(args)
    cmd_simulate(args)

    _header("4. final request state")
    final = api("GET", f"/v1/requests/{rid}", base, token=token)
    _dump(final)
    status = final["status"]
    (_ok if status == "completed" else _fail)(f"final status: {status}")

    _header("5. history")
    _dump(api("GET", "/v1/history", base, token=token))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bc", description="BelievableCall API test CLI")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"API base URL (default {DEFAULT_BASE_URL})")
    p.add_argument("--token", default=None, help="override the saved session token")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("signup", help="OTP start+confirm, save session")
    sp.add_argument("--phone", default="+491701234567")
    sp.add_argument("--locale", default="en", choices=["en", "de"])
    sp.add_argument("--device", default="cli-device")
    sp.add_argument("--code", default=MOCK_OTP_CODE)
    sp.set_defaults(func=cmd_signup)

    sub.add_parser("me", help="show profile").set_defaults(func=cmd_me)
    sub.add_parser("templates", help="list templates").set_defaults(func=cmd_templates)
    sub.add_parser("entitlements", help="show credits/entitlements").set_defaults(func=cmd_entitlements)
    sub.add_parser("history", help="list request history").set_defaults(func=cmd_history)

    sp = sub.add_parser("create", help="create a request")
    sp.add_argument("--template", required=True, help="template code or id")
    sp.add_argument("--channel", required=True, choices=["call", "sms"])
    sp.add_argument("--delay", type=int, default=0, choices=[0, 30, 300])
    sp.add_argument("--at", default=None, help="exact ISO time within 24h (overrides --delay)")
    sp.add_argument("--id", default="cli-1", help="client_request_id (idempotency key)")
    sp.set_defaults(func=cmd_create)

    sp = sub.add_parser("get", help="get a request")
    sp.add_argument("request_id")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("cancel", help="cancel a request")
    sp.add_argument("request_id")
    sp.set_defaults(func=cmd_cancel)

    sub.add_parser("dispatch", help="run one local worker dispatch tick").set_defaults(func=cmd_dispatch)

    sp = sub.add_parser("simulate", help="drive mock provider webhooks for a request")
    sp.add_argument("request_id")
    sp.add_argument("--outcome", default="completed", help="completed | no_answer | failed")
    sp.set_defaults(func=cmd_simulate)

    sp = sub.add_parser("demo", help="run the full all-mock flow end to end")
    sp.add_argument("--phone", default="+491701234567")
    sp.set_defaults(func=cmd_demo)

    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
