"""Stable sender-identity allocation.

The one load-bearing idea: a sender identity is allocated by the backend once,
per (user, sender persona, channel), and reused for every later message from the
same persona — independent of whether the user ever saves a contact.

Source-of-truth split:
  - the provider (Twilio) owns which sender numbers the company can send from
    (the ``service_identities`` pool — our "sender lines");
  - this backend owns how those lines are assigned to users and personas
    (``user_sender_bindings``).

Calls and texts from one persona share a line wherever it can do both, so the
contact the user saved ("Mom") shows up for either. Bindings stay one row per
channel; a new channel's binding reuses the line of the persona's other binding.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.db.models.enums import Channel, SenderBindingStatus, ServiceIdentityStatus
from app.db.models.service_identity import ServiceIdentity
from app.db.models.user_sender_binding import UserSenderBinding


def _line_supports(line: ServiceIdentity, channel: str) -> bool:
    if channel == Channel.call.value:
        return line.capability_outbound_voice
    return line.capability_outbound_sms


def select_sender_line(
    db: Session,
    channel: str,
    *,
    user_id: uuid.UUID | None = None,
    sender_persona_key: str | None = None,
) -> ServiceIdentity | None:
    """Pick an active sender line capable of the channel.

    Preference, in order: a line no other persona of this user is bound to (so
    "Mom" and "Boss" don't show up as the same contact), a line that can both
    call and text, then the oldest line. With a one-number pool every persona
    shares that number, which is an accepted outcome, not a bug.
    """
    stmt = select(ServiceIdentity).where(
        ServiceIdentity.status == ServiceIdentityStatus.active.value
    )
    if channel == Channel.call.value:
        stmt = stmt.where(ServiceIdentity.capability_outbound_voice.is_(True))
    else:
        stmt = stmt.where(ServiceIdentity.capability_outbound_sms.is_(True))
    lines = db.execute(stmt.order_by(ServiceIdentity.created_at)).scalars().all()
    if not lines:
        return None

    taken: set[uuid.UUID] = set()
    if user_id is not None:
        taken = set(
            db.execute(
                select(UserSenderBinding.sender_line_id).where(
                    UserSenderBinding.user_id == user_id,
                    UserSenderBinding.sender_persona_key != sender_persona_key,
                )
            ).scalars().all()
        )

    def rank(indexed):
        i, line = indexed
        both = line.capability_outbound_voice and line.capability_outbound_sms
        return (line.id in taken, not both, i)

    return min(enumerate(lines), key=rank)[1]


def _persona_line(
    db: Session, user_id: uuid.UUID, sender_persona_key: str, channel: str
) -> ServiceIdentity | None:
    """The line this persona already uses on another channel, if it can serve
    this channel too."""
    others = db.execute(
        select(UserSenderBinding).where(
            UserSenderBinding.user_id == user_id,
            UserSenderBinding.sender_persona_key == sender_persona_key,
            UserSenderBinding.channel != channel,
        )
    ).scalars().all()
    for other in others:
        line = db.get(ServiceIdentity, other.sender_line_id)
        if (
            line is not None
            and line.status == ServiceIdentityStatus.active.value
            and _line_supports(line, channel)
        ):
            return line
    return None


def _allocate_line(
    db: Session, user_id: uuid.UUID, sender_persona_key: str, channel: str
) -> ServiceIdentity | None:
    return _persona_line(db, user_id, sender_persona_key, channel) or select_sender_line(
        db, channel, user_id=user_id, sender_persona_key=sender_persona_key
    )


def resolve_or_allocate_binding(
    db: Session,
    user_id: uuid.UUID,
    *,
    sender_persona_key: str,
    channel: str,
    template_id: uuid.UUID | None,
) -> tuple[UserSenderBinding, ServiceIdentity] | None:
    """Return the stable (binding, line) for this user+persona+channel.

    A first binding on a channel takes the line the persona already uses on the
    other channel when that line can serve it.

    Reuses an existing active binding when its line is still usable. If the line
    was disabled/removed, the binding is marked orphaned and re-pointed at a
    freshly allocated line (keeping the same binding id so continuity holds).
    Returns ``None`` when the pool has no capable line — callers fall back to
    dispatch-time selection rather than failing the request.
    """
    now = utcnow()
    binding = db.execute(
        select(UserSenderBinding).where(
            UserSenderBinding.user_id == user_id,
            UserSenderBinding.sender_persona_key == sender_persona_key,
            UserSenderBinding.channel == channel,
        )
    ).scalars().first()

    if binding is not None:
        line = db.get(ServiceIdentity, binding.sender_line_id)
        if (
            line is not None
            and line.status == ServiceIdentityStatus.active.value
            and _line_supports(line, channel)
        ):
            binding.status = SenderBindingStatus.active.value
            binding.last_used_at = now
            return binding, line
        # Bound line vanished/disabled: reallocate without mutating past history.
        replacement = _allocate_line(db, user_id, sender_persona_key, channel)
        if replacement is None:
            binding.status = SenderBindingStatus.orphaned.value
            return None
        binding.sender_line_id = replacement.id
        binding.status = SenderBindingStatus.active.value
        binding.last_used_at = now
        return binding, replacement

    line = _allocate_line(db, user_id, sender_persona_key, channel)
    if line is None:
        return None
    binding = UserSenderBinding(
        user_id=user_id,
        sender_persona_key=sender_persona_key,
        channel=channel,
        sender_line_id=line.id,
        status=SenderBindingStatus.active.value,
        first_bound_at=now,
        last_used_at=now,
        created_from_template_id=template_id,
    )
    db.add(binding)
    db.flush()
    return binding, line
