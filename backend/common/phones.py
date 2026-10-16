"""Phone and email normalisation used for contact matching (spec section 6)."""

import re

import phonenumbers


def normalize_phone(raw: str | None, default_country: str = "IN") -> str | None:
    """Return the number in E.164 (`+919800011111`) or None if it is not a valid number."""
    if not raw or not raw.strip():
        return None
    text = raw.strip()
    candidates = [text]
    digits = digits_only(text)
    if not text.startswith("+") and 11 <= len(digits) <= 15:
        # Spreadsheets drop the "+": "919876543210" is +91 98765 43210.
        candidates.append("+" + digits.lstrip("0"))
    for candidate in candidates:
        try:
            number = phonenumbers.parse(candidate, default_country.upper())
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(number):
            return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    return None


def normalize_email(raw: str | None) -> str | None:
    value = (raw or "").strip().lower()
    return value or None


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)
