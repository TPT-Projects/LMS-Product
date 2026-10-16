from typing import Any

from rest_framework.exceptions import ValidationError

from .models import VALUE_COLUMN, CustomField, EnquiryCustomValue
from .values import CustomValueError, coerce, to_api

ALL_VALUE_COLUMNS = sorted(set(VALUE_COLUMN.values()))


def active_fields(tenant_id: int) -> dict[str, CustomField]:
    return {f.key: f for f in CustomField.objects.filter(tenant_id=tenant_id, is_active=True)}


def validate_values(tenant_id: int, raw: dict[str, Any] | None) -> dict[CustomField, Any]:
    """Check a {key: value} payload. Raises a DRF ValidationError keyed by field key."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValidationError({"custom_fields": ["Send an object of {field_key: value}."]})
    fields = active_fields(tenant_id)
    errors: dict[str, list[str]] = {}
    clean: dict[CustomField, Any] = {}
    for key, value in raw.items():
        field = fields.get(key)
        if field is None:
            errors[key] = ["Unknown field."]
            continue
        try:
            clean[field] = coerce(field, value)
        except CustomValueError as exc:
            errors[key] = [str(exc)]
    if errors:
        raise ValidationError({"custom_fields": errors})
    return clean


def check_required(tenant_id: int, provided: dict[CustomField, Any]) -> None:
    """On create: every required field must have a value."""
    missing = {
        f.key: ["This field is required."]
        for f in active_fields(tenant_id).values()
        if f.is_required and provided.get(f) is None
    }
    if missing:
        raise ValidationError({"custom_fields": missing})


def current_values(enquiry) -> dict[str, Any]:
    """{key: api_value} for one enquiry (uses prefetched custom_values when present)."""
    return {
        v.field.key: to_api(v.field, v.get_value())
        for v in enquiry.custom_values.all()
        if v.field.is_active
    }


def save_values(enquiry, values: dict[CustomField, Any]) -> list[dict]:
    """Upsert values. Returns the changes [{field, label, from, to}] for the timeline."""
    if not values:
        return []
    existing = {
        v.field_id: v
        for v in EnquiryCustomValue.objects.filter(enquiry=enquiry, field__in=values.keys())
    }
    changes = []
    for field, new in values.items():
        row = existing.get(field.pk)
        old = row.get_value() if row else None
        if old == new:
            continue
        changes.append(
            {
                "field": field.key,
                "label": field.label,
                "from": to_api(field, old),
                "to": to_api(field, new),
            }
        )
        if new is None:
            if row:
                row.delete()
            continue
        if row is None:
            row = EnquiryCustomValue(tenant_id=enquiry.tenant_id, enquiry=enquiry, field=field)
        for column in ALL_VALUE_COLUMNS:
            setattr(row, column, None)
        setattr(row, field.value_column, new)
        row.save()
    return changes
