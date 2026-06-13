"""Phone normalization to E.164 and line-type validation."""
from __future__ import annotations

from dataclasses import dataclass

import phonenumbers

from app.core.config import settings
from app.core.errors import InvalidPhoneNumber, UnsupportedLineType

# Line types we refuse to use as a destination (cost/abuse/realism reasons).
_BLOCKED_LINE_TYPES = {"landline"}


@dataclass(frozen=True)
class NormalizedPhone:
    e164: str
    country_code: str | None
    line_type: str


def _map_line_type(parsed) -> str:
    ntype = phonenumbers.number_type(parsed)
    if ntype == phonenumbers.PhoneNumberType.MOBILE:
        return "mobile"
    if ntype == phonenumbers.PhoneNumberType.FIXED_LINE:
        return "landline"
    if ntype == phonenumbers.PhoneNumberType.VOIP:
        return "non_fixed_voip"
    if ntype == phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE:
        return "mobile"
    return "unknown"


def normalize_phone(raw: str, default_region: str | None = None) -> NormalizedPhone:
    """Normalize an input phone number to E.164.

    Raises InvalidPhoneNumber for unparseable / invalid / unsupported-country
    numbers.
    """
    if not raw or not raw.strip():
        raise InvalidPhoneNumber("Phone number is required.")
    candidate = raw.strip()
    # If no '+' and no default region, we cannot know the country.
    region = default_region
    if candidate.startswith("+"):
        region = None
    try:
        parsed = phonenumbers.parse(candidate, region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumber("The phone number could not be parsed.") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumber("The phone number is not valid.")

    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    country = phonenumbers.region_code_for_number(parsed)

    if settings.supported_countries and country not in settings.supported_countries:
        raise InvalidPhoneNumber(f"Phone numbers from region {country} are not supported.")

    return NormalizedPhone(e164=e164, country_code=country, line_type=_map_line_type(parsed))


def assert_supported_line_type(line_type: str) -> None:
    if line_type in _BLOCKED_LINE_TYPES:
        raise UnsupportedLineType(
            f"Line type '{line_type}' is not supported for delivery."
        )
