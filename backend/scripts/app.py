#!/usr/bin/env python
"""BelievableCall — an interactive terminal "app" that mimics the iOS frontend.

Navigate with the arrow keys. Sign in with your phone number, schedule a
believable call or text, then watch it ring/arrive on screen.

It talks to the backend over HTTP like the real app would, and embeds the
dispatch + provider-webhook simulation so a scheduled call actually fires
without a separate worker process.

Run:
    python scripts/app.py            # needs the API running (make api)
or, in its own window:
    make app

The mock OTP code is always 123456.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import questionary
from questionary import Choice, Style
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

# Make `backend/` importable so the embedded dispatch/webhook helpers work.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = os.environ.get("BC_BASE_URL", "http://localhost:8000")
SESSION_FILE = Path(__file__).resolve().parent.parent / ".bc_app_session.json"
MOCK_OTP_CODE = "123456"

console = Console()
QSTYLE = Style(
    [
        ("qmark", "fg:#5fafff bold"),
        ("question", "bold"),
        ("pointer", "fg:#5fafff bold"),
        ("highlighted", "fg:#5fafff bold"),
        ("selected", "fg:#87d787"),
    ]
)


# --------------------------------------------------------------------------- #
# HTTP layer (the "frontend → API" calls)
# --------------------------------------------------------------------------- #
class ApiError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def api(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        resp = httpx.request(method, BASE_URL.rstrip("/") + path, headers=headers, json=body, timeout=15.0)
    except httpx.ConnectError:
        console.print(
            Panel(
                f"Could not reach the API at [bold]{BASE_URL}[/].\n\n"
                "Start it first in another terminal:\n  [bold cyan]make api[/]",
                title="Backend not running",
                border_style="red",
            )
        )
        sys.exit(2)
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code >= 400:
        err = data.get("error", {"code": "error", "message": resp.text})
        raise ApiError(err.get("code", "error"), err.get("message", "Request failed"))
    return data


# --------------------------------------------------------------------------- #
# Session persistence
# --------------------------------------------------------------------------- #
def load_session() -> dict:
    if SESSION_FILE.exists():
        import json

        return json.loads(SESSION_FILE.read_text())
    return {}


def save_session(data: dict) -> None:
    import json

    SESSION_FILE.write_text(json.dumps(data, indent=2))


def clear_session() -> None:
    SESSION_FILE.unlink(missing_ok=True)


# --------------------------------------------------------------------------- #
# Embedded mechanics (dispatch + read snapshot + drive provider webhooks)
# These mirror what the real worker + provider would do, so the call "arrives".
# --------------------------------------------------------------------------- #
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_dispatch_tick() -> list[str]:
    from app.db.session import SessionLocal
    from app.workers import dispatch

    db = SessionLocal()
    try:
        return dispatch.run_once(db, now=_utcnow() + timedelta(seconds=5))
    finally:
        db.close()


def get_call_content(request_id: str) -> dict:
    from app.db.models.request import Request
    from app.db.session import SessionLocal
    from app.domain.templates import rendering

    db = SessionLocal()
    try:
        req = db.get(Request, uuid.UUID(request_id))
        snap = req.request_plan_snapshot_json or {}
        ctx = rendering.build_context(
            locale=snap.get("locale", "en"),
            caller_persona=snap.get("caller_persona", "caller"),
            reason_code=snap.get("reason_code", ""),
        )
        return {
            "persona_label": ctx["caller_persona_label"],
            "opening_line": snap.get("rendered_opening_line") or "…",
            "followups": snap.get("allowed_followup_facts") or [],
            "max_duration": snap.get("max_duration_seconds") or 60,
        }
    finally:
        db.close()


def get_sms_content(request_id: str) -> dict:
    from app.db.models.request import Request
    from app.db.session import SessionLocal
    from app.domain.templates import rendering

    db = SessionLocal()
    try:
        req = db.get(Request, uuid.UUID(request_id))
        snap = req.request_plan_snapshot_json or {}
        ctx = rendering.build_context(
            locale=snap.get("locale", "en"),
            caller_persona=snap.get("caller_persona", "caller"),
            reason_code=snap.get("reason_code", ""),
        )
        return {
            "persona_label": ctx["caller_persona_label"],
            "body": snap.get("rendered_sms_body") or "…",
        }
    finally:
        db.close()


def _provider_id(request_id: str, channel: str) -> str | None:
    from app.db.models.attempts import CallAttempt, MessageAttempt
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        if channel == "call":
            a = (
                db.query(CallAttempt).filter(CallAttempt.request_id == uuid.UUID(request_id))
                .order_by(CallAttempt.attempt_no.desc()).first()
            )
            return a.provider_call_id if a else None
        a = (
            db.query(MessageAttempt).filter(MessageAttempt.request_id == uuid.UUID(request_id))
            .order_by(MessageAttempt.attempt_no.desc()).first()
        )
        return a.provider_message_id if a else None
    finally:
        db.close()


_evt_counter = {"n": 0}


def _evt_id(kind: str) -> str:
    _evt_counter["n"] += 1
    return f"app-evt-{kind}-{_evt_counter['n']}"


def voice_event(provider_call_id: str, etype: str, **fields) -> None:
    payload = {"event_id": _evt_id(etype), "type": etype, "provider_call_id": provider_call_id, **fields}
    api("POST", "/v1/webhooks/voice", body=payload)


def sms_event(provider_message_id: str, etype: str, **fields) -> None:
    payload = {"event_id": _evt_id(etype), "type": etype, "provider_message_id": provider_message_id, **fields}
    api("POST", "/v1/webhooks/sms", body=payload)


# --------------------------------------------------------------------------- #
# Screens
# --------------------------------------------------------------------------- #
def banner() -> None:
    console.clear()
    title = Text("☎  BelievableCall", style="bold #5fafff")
    sub = Text("your believable interruption, on demand", style="dim italic")
    console.print(Panel(Align.center(Group(title, sub)), border_style="#5fafff", padding=(1, 4)))


def flow_login() -> dict:
    banner()
    console.print("[dim]Passwordless sign-in. We text you a one-time code.[/]\n")
    phone = questionary.text(
        "Your phone number (E.164):", default="+491701234567", style=QSTYLE
    ).ask()
    if not phone:
        sys.exit(0)
    try:
        start = api("POST", "/v1/auth/phone/start", body={"phone_number": phone, "locale": "en"})
    except ApiError as e:
        console.print(f"[red]✗ {e.message}[/]")
        time.sleep(1.5)
        return flow_login()

    console.print(f"\n[green]✓ Code sent[/] (channel: {start['channel']}).  "
                  f"[dim]Mock code is[/] [bold]{MOCK_OTP_CODE}[/]\n")
    code = questionary.text("Enter the 6-digit code:", default=MOCK_OTP_CODE, style=QSTYLE).ask()
    if not code:
        sys.exit(0)
    try:
        confirm = api(
            "POST", "/v1/auth/phone/confirm",
            body={"verification_id": start["verification_id"], "code": code},
        )
    except ApiError as e:
        console.print(f"[red]✗ {e.message}[/]")
        time.sleep(1.5)
        return flow_login()

    session = {"token": confirm["session_token"], "user": confirm["user"]}
    save_session(session)
    console.print(f"\n[green]✓ Welcome![/] Signed in as {confirm['user']['phone_number_masked']}")
    time.sleep(1.0)
    return session


def home(session: dict) -> str:
    token = session["token"]
    me = api("GET", "/v1/me", token=token)
    banner()
    info = Text()
    info.append("  📱  ", style="")
    info.append(f"{me['phone_number_masked']}", style="bold")
    info.append("      💳  ", style="")
    info.append(f"{me['credits_available']} credits", style="bold #87d787")
    console.print(Align.center(info))
    if me.get("active_request"):
        ar = me["active_request"]
        console.print(Align.center(Text(f"  ⏳ active {ar['channel']} request: {ar['status']}", style="yellow")))
    console.print()

    choice = questionary.select(
        "What would you like to do?",
        choices=[
            Choice("📞  Schedule a believable call / text", "new"),
            Choice("🕓  History", "history"),
            Choice("👤  Profile", "profile"),
            Choice("🚪  Sign out", "logout"),
            Choice("✕  Quit", "quit"),
        ],
        style=QSTYLE,
    ).ask()
    return choice or "quit"


def flow_new_request(session: dict) -> None:
    token = session["token"]

    # If a request is already live, offer to resume or cancel it.
    me = api("GET", "/v1/me", token=token)
    if me.get("active_request"):
        ar = me["active_request"]
        action = questionary.select(
            f"You already have a {ar['channel']} request ({ar['status']}). What now?",
            choices=[Choice("▶  Resume / receive it", "resume"), Choice("🗑  Cancel it", "cancel"),
                     Choice("← Back", "back")],
            style=QSTYLE,
        ).ask()
        if action == "resume":
            return receive(session, ar["request_id"], ar["channel"], ar["execute_at"])
        if action == "cancel":
            try:
                api("POST", f"/v1/requests/{ar['request_id']}/cancel", token=token)
                console.print("[green]✓ canceled[/]"); time.sleep(0.8)
            except ApiError as e:
                console.print(f"[yellow]{e.message}[/]"); time.sleep(1.2)
        return

    catalog = api("GET", "/v1/templates", token=token)["templates"]
    banner()
    tmpl_id = questionary.select(
        "Choose a scenario:",
        choices=[Choice(f"{t['display_name']}  [{'/'.join(t['supported_channels'])}]", t) for t in catalog],
        style=QSTYLE,
    ).ask()
    if not tmpl_id:
        return
    tmpl = tmpl_id  # value is the full template dict

    channel = questionary.select(
        "Call or text?",
        choices=[Choice("📞  Call" if c == "call" else "💬  Text", c) for c in tmpl["supported_channels"]],
        style=QSTYLE,
    ).ask()
    if not channel:
        return

    timing = questionary.select(
        "When?",
        choices=[
            Choice("⚡  Right now", 0),
            Choice("⏱  In 30 seconds", 30),
            Choice("🕔  In 5 minutes", 300),
            Choice("🗓  Custom (minutes from now)", "custom"),
        ],
        style=QSTYLE,
    ).ask()
    if timing is None:
        return

    body = {"client_request_id": str(uuid.uuid4()), "template_id": tmpl["id"], "channel": channel}
    if timing == "custom":
        mins = questionary.text("Minutes from now (1–1440):", default="1", style=QSTYLE).ask()
        try:
            mins_i = max(1, min(1440, int(mins)))
        except (TypeError, ValueError):
            console.print("[red]invalid number[/]"); time.sleep(1); return
        body["scheduled_at"] = (_utcnow() + timedelta(minutes=mins_i)).isoformat()
    else:
        body["delay_seconds"] = timing

    try:
        created = api("POST", "/v1/requests", token=token, body=body)
    except ApiError as e:
        console.print(Panel(e.message, title=f"Couldn't schedule ({e.code})", border_style="red"))
        questionary.press_any_key_to_continue(style=QSTYLE).ask()
        return

    receive(session, created["request_id"], channel, created["execute_at"])


def _parse_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _countdown(execute_at: str) -> bool:
    """Show a live countdown until the scheduled time. Returns False if user aborts."""
    target = _parse_dt(execute_at)
    console.clear()
    try:
        while True:
            remaining = (target - _utcnow()).total_seconds()
            if remaining <= 0:
                break
            mm, ss = divmod(int(remaining) + 1, 60)
            face = Text()
            face.append("\n  Waiting for your believable interruption…\n\n", style="dim")
            face.append(f"   ⏳  {mm:02d}:{ss:02d}\n", style="bold #5fafff")
            face.append("\n  [Ctrl-C to cancel]\n", style="dim")
            console.clear()
            console.print(Panel(Align.center(face), border_style="#5fafff", padding=(1, 6)))
            time.sleep(1)
    except KeyboardInterrupt:
        return False
    return True


def receive(session: dict, request_id: str, channel: str, execute_at: str) -> None:
    token = session["token"]

    if not _countdown(execute_at):
        try:
            api("POST", f"/v1/requests/{request_id}/cancel", token=token)
            console.print("\n[yellow]Canceled.[/]")
        except ApiError:
            console.print("\n[yellow]Could not cancel (already dispatching).[/]")
        time.sleep(1.0)
        return

    # Fire it: dispatch locally (no-op if a real worker already did it).
    local_dispatch_tick()
    provider_id = _provider_id(request_id, channel)
    if provider_id is None:
        console.print(Panel("The request did not dispatch (no credits or no sender identity).",
                            border_style="red", title="Dispatch failed"))
        questionary.press_any_key_to_continue(style=QSTYLE).ask()
        return

    if channel == "call":
        _incoming_call(request_id, provider_id)
    else:
        _incoming_sms(request_id, provider_id)


def _ring_panel(persona: str, ringing: bool) -> Panel:
    body = Text()
    body.append("\n   📞  Incoming call\n\n", style="bold")
    body.append(f"   {persona}\n", style="bold #ffffff")
    body.append("   mobile\n\n", style="dim")
    body.append("   " + ("◉ ◉ ◉  ringing…" if ringing else "       "), style="#87d787" if ringing else "dim")
    body.append("\n")
    return Panel(Align.center(body), border_style="#87d787", padding=(1, 6), title="BelievableCall")


def _incoming_call(request_id: str, provider_call_id: str) -> None:
    voice_event(provider_call_id, "call.queued")
    voice_event(provider_call_id, "call.ringing")

    content = get_call_content(request_id)
    persona = content["persona_label"]

    # Ring animation, then prompt to answer.
    for i in range(3):
        console.clear()
        console.print(_ring_panel(persona, ringing=(i % 2 == 0)))
        time.sleep(0.6)

    action = questionary.select(
        " ",
        choices=[Choice("✅  Answer", "answer"), Choice("🔴  Decline", "decline")],
        style=QSTYLE,
        qmark="📞",
    ).ask()

    if action != "answer":
        voice_event(provider_call_id, "call.failed", ended_reason="declined")
        console.print("\n[dim]Call declined.[/]")
        time.sleep(0.8)
        return

    voice_event(provider_call_id, "call.answered")
    started = time.time()

    # Reveal the caller's script line by line.
    lines = [content["opening_line"], *content["followups"]]
    transcript: list[Text] = []
    for idx, line in enumerate(lines):
        t = Text()
        t.append(f"{persona}: ", style="bold #5fafff")
        t.append(line, style="white")
        transcript.append(t)
        console.clear()
        console.print(Panel(Group(*transcript), title="📞  On the call", border_style="#87d787", padding=(1, 3)))
        if idx < len(lines) - 1:
            cont = questionary.select(
                " ", choices=[Choice("▶  Continue", "go"), Choice("📵  Hang up", "end")], style=QSTYLE
            ).ask()
            if cont == "end":
                break
        else:
            questionary.press_any_key_to_continue("Press a key to hang up…", style=QSTYLE).ask()

    duration = max(1, int(time.time() - started))
    voice_event(provider_call_id, "call.completed", duration_seconds=duration, ended_reason="completed")
    console.print(f"\n[green]✓ Call ended[/] ({duration}s). You have your exit. 🙌")
    time.sleep(1.2)


def _incoming_sms(request_id: str, provider_message_id: str) -> None:
    sms_event(provider_message_id, "message.queued")
    sms_event(provider_message_id, "message.sent")
    content = get_sms_content(request_id)

    console.clear()
    bubble = Text()
    bubble.append(f"{content['persona_label']}\n", style="bold #5fafff")
    bubble.append(content["body"], style="white")
    console.print(Panel(bubble, title="💬  New message", border_style="#87d787", padding=(1, 3), width=60))
    sms_event(provider_message_id, "message.delivered", estimated_cost_minor=1)
    console.print("\n[green]✓ Delivered.[/]")
    questionary.press_any_key_to_continue("Press a key to continue…", style=QSTYLE).ask()


def screen_history(session: dict) -> None:
    items = api("GET", "/v1/history", token=session["token"])["items"]
    banner()
    if not items:
        console.print("[dim]No history yet.[/]")
    else:
        for it in items:
            icon = "📞" if it["channel"] == "call" else "💬"
            status = it["final_status"]
            color = {"completed": "green", "failed": "red", "canceled": "yellow"}.get(status, "white")
            line = Text(f"  {icon}  {it['template_label']}  —  ")
            line.append(status, style=color)
            if it.get("duration_seconds"):
                line.append(f"  ({it['duration_seconds']}s)", style="dim")
            console.print(line)
            if it.get("delivered_preview"):
                console.print(Text(f"        “{it['delivered_preview']}”", style="dim italic"))
    console.print()
    questionary.press_any_key_to_continue(style=QSTYLE).ask()


def screen_profile(session: dict) -> None:
    me = api("GET", "/v1/me", token=session["token"])
    ent = api("GET", "/v1/entitlements", token=session["token"])
    banner()
    t = Text()
    t.append(f"  Phone:    {me['phone_number_masked']}\n")
    t.append(f"  Locale:   {me['locale']}\n")
    t.append(f"  Timezone: {me['timezone']}\n")
    t.append(f"  Credits:  {ent['credits_available']}\n")
    plans = ", ".join(e["plan_code"] or "?" for e in ent["active_entitlements"]) or "none"
    t.append(f"  Plans:    {plans}\n")
    console.print(Panel(t, title="👤  Profile", border_style="#5fafff"))
    questionary.press_any_key_to_continue(style=QSTYLE).ask()


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def run() -> None:
    # Verify the API is up before doing anything.
    api("GET", "/health/live")

    session = load_session()
    if session.get("token"):
        try:
            api("GET", "/v1/me", token=session["token"])  # validate
        except ApiError:
            clear_session()
            session = {}

    if not session.get("token"):
        session = flow_login()

    while True:
        try:
            choice = home(session)
        except ApiError as e:
            if e.code in ("unauthorized", "session_expired"):
                clear_session()
                session = flow_login()
                continue
            console.print(f"[red]✗ {e.message}[/]")
            time.sleep(1.5)
            continue

        if choice == "new":
            flow_new_request(session)
        elif choice == "history":
            screen_history(session)
        elif choice == "profile":
            screen_profile(session)
        elif choice == "logout":
            try:
                api("POST", "/v1/auth/logout", token=session["token"])
            except ApiError:
                pass
            clear_session()
            session = flow_login()
        else:
            console.clear()
            console.print("👋  Bye!")
            return


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        console.print("\n👋  Bye!")
