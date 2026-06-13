import pytest

from app.core.errors import InvalidPhoneNumber, UnsupportedLineType
from app.domain.phone import assert_supported_line_type, normalize_phone


def test_normalize_valid_de_mobile():
    n = normalize_phone("+49 170 1234567")
    assert n.e164 == "+491701234567"
    assert n.country_code == "DE"
    assert n.line_type == "mobile"


def test_normalize_strips_formatting():
    assert normalize_phone("+1 (415) 555-2671").e164 == "+14155552671"


def test_normalize_rejects_garbage():
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone("not-a-number")


def test_normalize_rejects_empty():
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone("   ")


def test_normalize_rejects_unsupported_country():
    # France (+33) is not in the default SUPPORTED_COUNTRIES.
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone("+33612345678")


def test_landline_line_type_is_blocked():
    with pytest.raises(UnsupportedLineType):
        assert_supported_line_type("landline")


def test_mobile_line_type_allowed():
    assert_supported_line_type("mobile")  # no raise
