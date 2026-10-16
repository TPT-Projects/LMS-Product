"""Typed validation for custom field values (Phase 2: "custom fields with typed validation").

API values:
    text / dropdown   -> string
    number / currency -> number or numeric string
    date              -> "DD/MM/YYYY" (or ISO "YYYY-MM-DD")
    checkbox          -> true / false
    multi_select      -> list of option strings
`None` or "" clears the value.
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils.translation import gettext as _

from common.dates import parse_display_date

from .models import CustomField, FieldType


class CustomValueError(ValueError):
    pass


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return parse_display_date(text)
    except ValueError:
        pass
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise CustomValueError(_("Enter a date as DD/MM/YYYY.")) from None


def coerce(field: CustomField, value: Any) -> Any:
    """Return the value to store, or raise CustomValueError with a readable message."""
    if is_empty(value):
        if field.is_required:
            raise CustomValueError(_("This field is required."))
        return None

    match field.type:
        case FieldType.TEXT:
            text = str(value).strip()
            if len(text) > 1000:
                raise CustomValueError(_("Use at most 1000 characters."))
            return text
        case FieldType.NUMBER | FieldType.CURRENCY:
            if isinstance(value, bool):
                raise CustomValueError(_("Enter a number."))
            try:
                number = Decimal(str(value).replace(",", "").strip())
            except InvalidOperation:
                raise CustomValueError(_("Enter a number.")) from None
            if not number.is_finite() or abs(number) >= Decimal("1e16"):
                raise CustomValueError(_("Enter a smaller number."))
            return number.quantize(Decimal("0.01"))
        case FieldType.DATE:
            return parse_date(value)
        case FieldType.CHECKBOX:
            if isinstance(value, bool):
                return value
            if str(value).lower() in ("true", "1", "yes"):
                return True
            if str(value).lower() in ("false", "0", "no"):
                return False
            raise CustomValueError(_("Choose yes or no."))
        case FieldType.DROPDOWN:
            text = str(value).strip()
            if text not in field.options:
                raise CustomValueError(_("Choose one of the options."))
            return text
        case FieldType.MULTI_SELECT:
            items = value if isinstance(value, list) else [value]
            items = [str(item).strip() for item in items if not is_empty(item)]
            if any(item not in field.options for item in items):
                raise CustomValueError(_("Choose from the options."))
            return list(dict.fromkeys(items)) or None  # unique, keep order
    raise CustomValueError(_("Unknown field type."))


def to_api(field: CustomField, stored: Any) -> Any:
    """Stored value -> JSON value (dates as DD/MM/YYYY, decimals as numbers)."""
    if stored is None:
        return None
    if field.type == FieldType.DATE:
        return stored.strftime("%d/%m/%Y")
    if field.type in (FieldType.NUMBER, FieldType.CURRENCY):
        return float(stored) if stored % 1 else int(stored)
    return stored
