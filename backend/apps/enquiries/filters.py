"""Filter engine: a JSON tree of AND / OR groups -> a safe Django Q object.

    {"op": "and", "rules": [
        {"field": "status", "operator": "in", "value": [1, 2]},
        {"op": "or", "rules": [
            {"field": "campaign", "operator": "contains", "value": "Dubai"},
            {"field": "cf:investment_budget", "operator": "eq", "value": "₹5_cr+"}
        ]}
    ]}

Only whitelisted fields and operators are accepted, and values only ever reach
the database as ORM parameters (never string concatenation).
Dates use DD/MM/YYYY and are read in the workspace timezone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db.models import Exists, OuterRef, Q

from apps.customfields.models import CustomField, EnquiryCustomValue, FieldType
from apps.customfields.values import CustomValueError, parse_date

from .models import EnquiryOwner, Source
from .selectors import day_bounds, today_in

MAX_DEPTH = 4
MAX_RULES = 60


class FilterError(ValueError):
    pass


@dataclass(frozen=True)
class Ctx:
    tenant_id: int
    user_id: int
    tz: str


# Operators per kind of field.
TEXT_OPS = {
    "eq",
    "neq",
    "contains",
    "not_contains",
    "starts_with",
    "in",
    "is_empty",
    "is_not_empty",
}
CHOICE_OPS = {"eq", "neq", "in", "not_in", "is_empty", "is_not_empty"}
BOOL_OPS = {"is_true", "is_false"}
NUMBER_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "between", "is_empty", "is_not_empty"}
DATE_OPS = {"on", "before", "after", "between", "today", "last_days", "is_empty", "is_not_empty"}
MULTI_OPS = {"contains", "contains_any", "is_empty", "is_not_empty"}

# Standard fields: name -> (column, kind)
STANDARD_FIELDS: dict[str, tuple[str, str]] = {
    "name": ("name", "text"),
    "phone": ("phone_e164", "text"),
    "email": ("email", "text"),
    "campaign": ("campaign_name", "text"),
    "adset": ("adset_name", "text"),
    "ad": ("ad_name", "text"),
    "form": ("form_id", "text"),
    "status": ("status_id", "choice"),
    "owner": ("primary_owner_id", "choice"),
    "source": ("source", "choice"),
    "is_repeat": ("is_repeat", "bool"),
    "created_at": ("created_at", "datetime"),
    "updated_at": ("updated_at", "datetime"),
}
KIND_OPS = {
    "text": TEXT_OPS,
    "choice": CHOICE_OPS,
    "bool": BOOL_OPS,
    "datetime": DATE_OPS,
}


# --- value helpers -------------------------------------------------------------
def _list(value: Any) -> list:
    if isinstance(value, list):
        if not value:
            raise FilterError("Choose at least one value.")
        if len(value) > 200:
            raise FilterError("Too many values.")
        return value
    return [value]


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise FilterError("Expected a number.") from None


def _text(value: Any) -> str:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise FilterError("Expected text.")
    text = str(value).strip()
    if not text or len(text) > 255:
        raise FilterError("Enter between 1 and 255 characters.")
    return text


def _date(value: Any) -> date:
    try:
        return parse_date(value)
    except CustomValueError:
        raise FilterError("Enter a date as DD/MM/YYYY.") from None


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        raise FilterError("Expected a number.") from None


def _pair(value: Any) -> tuple[Any, Any]:
    if not isinstance(value, list) or len(value) != 2:
        raise FilterError("Expected [from, to].")
    return value[0], value[1]


# --- standard fields -----------------------------------------------------------
def _choice_value(field: str, value: Any, ctx: Ctx):
    if field == "owner":
        return ctx.user_id if value == "me" else _int(value)
    if field == "status":
        return _int(value)
    if field == "source":
        if value not in Source.values:
            raise FilterError("Unknown source.")
        return value
    raise FilterError("Unknown field.")


def _owner_q(op: str, values: list[int]) -> Q:
    """Owner matches primary OR secondary owners."""
    secondary = Exists(EnquiryOwner.objects.filter(enquiry=OuterRef("pk"), user_id__in=values))
    q = Q(primary_owner_id__in=values) | Q(secondary)
    return ~q if op in ("neq", "not_in") else q


def _text_q(column: str, op: str, value: Any) -> Q:
    if op == "is_empty":
        return Q(**{column: ""}) | Q(**{f"{column}__isnull": True})
    if op == "is_not_empty":
        return ~(Q(**{column: ""}) | Q(**{f"{column}__isnull": True}))
    if op == "in":
        return Q(**{f"{column}__in": [_text(v) for v in _list(value)]})
    text = _text(value)
    if column == "phone_e164":  # "98765" or "+91 98765" both match
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            raise FilterError("Enter digits.")
        text = digits
    lookups = {
        "eq": ("iexact", False),
        "neq": ("iexact", True),
        "contains": ("icontains", False),
        "not_contains": ("icontains", True),
        "starts_with": ("istartswith", False),
    }
    lookup, negate = lookups[op]
    if column == "phone_e164" and op in ("eq", "neq"):
        lookup = "endswith"
    q = Q(**{f"{column}__{lookup}": text})
    return ~q if negate else q


def _datetime_q(column: str, op: str, value: Any, ctx: Ctx) -> Q:
    if op == "is_empty":
        return Q(**{f"{column}__isnull": True})
    if op == "is_not_empty":
        return Q(**{f"{column}__isnull": False})
    if op == "today":
        start, end = day_bounds(today_in(ctx.tz), ctx.tz)
        return Q(**{f"{column}__gte": start, f"{column}__lt": end})
    if op == "last_days":
        days = _int(value)
        if not 1 <= days <= 3650:
            raise FilterError("Use 1 to 3650 days.")
        start, _ = day_bounds(today_in(ctx.tz) - timedelta(days=days - 1), ctx.tz)
        return Q(**{f"{column}__gte": start})
    if op == "between":
        low, high = _pair(value)
        start, _ = day_bounds(_date(low), ctx.tz)
        _, end = day_bounds(_date(high), ctx.tz)
        return Q(**{f"{column}__gte": start, f"{column}__lt": end})
    start, end = day_bounds(_date(value), ctx.tz)
    if op == "on":
        return Q(**{f"{column}__gte": start, f"{column}__lt": end})
    if op == "before":
        return Q(**{f"{column}__lt": start})
    return Q(**{f"{column}__gte": end})  # after


def _standard_q(field: str, op: str, value: Any, ctx: Ctx) -> Q:
    column, kind = STANDARD_FIELDS[field]
    if op not in KIND_OPS[kind]:
        raise FilterError(f"Operator '{op}' does not work with '{field}'.")
    if kind == "text":
        return _text_q(column, op, value)
    if kind == "bool":
        return Q(**{column: op == "is_true"})
    if kind == "datetime":
        return _datetime_q(column, op, value, ctx)
    # choice
    if op in ("is_empty", "is_not_empty"):
        if field != "owner":
            raise FilterError(f"Operator '{op}' does not work with '{field}'.")
        return Q(primary_owner__isnull=(op == "is_empty"))
    values = [_choice_value(field, v, ctx) for v in _list(value)]
    if field == "owner":
        return _owner_q(op, values)
    q = Q(**{f"{column}__in": values})
    return ~q if op in ("neq", "not_in") else q


# --- custom fields -------------------------------------------------------------
def _custom_q(field: CustomField, op: str, value: Any, ctx: Ctx) -> Q:
    col = field.value_column
    base = EnquiryCustomValue.objects.filter(enquiry=OuterRef("pk"), field_id=field.pk)
    has_value = Exists(base.filter(**{f"{col}__isnull": False}))
    if op == "is_empty":
        return ~Q(has_value)
    if op == "is_not_empty":
        return Q(has_value)

    unsupported = FilterError(f"Operator '{op}' does not work with '{field.label}'.")

    def where(**lookups) -> Q:
        return Q(Exists(base.filter(**lookups)))

    match field.type:
        case FieldType.TEXT:
            if op not in TEXT_OPS:
                raise unsupported
            if op == "in":
                return where(value_text__in=[_text(v) for v in _list(value)])
            text = _text(value)
            lookup = {
                "eq": "iexact",
                "neq": "iexact",
                "contains": "icontains",
                "not_contains": "icontains",
                "starts_with": "istartswith",
            }[op]
            q = where(**{f"value_text__{lookup}": text})
            return ~q if op in ("neq", "not_contains") else q
        case FieldType.DROPDOWN:
            if op not in CHOICE_OPS:
                raise unsupported
            values = [_text(v) for v in _list(value)]
            q = where(value_text__in=values)
            return ~q if op in ("neq", "not_in") else q
        case FieldType.NUMBER | FieldType.CURRENCY:
            if op not in NUMBER_OPS:
                raise unsupported
            if op == "between":
                low, high = _pair(value)
                return where(value_number__gte=_decimal(low), value_number__lte=_decimal(high))
            number = _decimal(value)
            if op == "neq":
                return ~where(value_number=number)
            lookup = {"eq": "exact", "gt": "gt", "gte": "gte", "lt": "lt", "lte": "lte"}[op]
            return where(**{f"value_number__{lookup}": number})
        case FieldType.DATE:
            if op not in DATE_OPS:
                raise unsupported
            if op == "today":
                return where(value_date=today_in(ctx.tz))
            if op == "last_days":
                days = _int(value)
                return where(value_date__gte=today_in(ctx.tz) - timedelta(days=days - 1))
            if op == "between":
                low, high = _pair(value)
                return where(value_date__gte=_date(low), value_date__lte=_date(high))
            lookup = {"on": "exact", "before": "lt", "after": "gt"}[op]
            return where(**{f"value_date__{lookup}": _date(value)})
        case FieldType.CHECKBOX:
            if op not in BOOL_OPS:
                raise unsupported
            if op == "is_true":
                return where(value_bool=True)
            return ~where(value_bool=True)
        case FieldType.MULTI_SELECT:
            if op not in MULTI_OPS:
                raise unsupported
            values = [_text(v) for v in _list(value)]
            if op == "contains":  # has all of them
                return where(value_list__contains=values)
            q = Q()
            for v in values:
                q |= where(value_list__contains=[v])
            return q
    raise unsupported


# --- tree --------------------------------------------------------------------------
class FilterBuilder:
    def __init__(self, ctx: Ctx):
        self.ctx = ctx
        self.rule_count = 0
        self._fields: dict[str, CustomField] | None = None

    def custom_field(self, key: str) -> CustomField:
        if self._fields is None:
            self._fields = {
                f.key: f for f in CustomField.objects.filter(tenant_id=self.ctx.tenant_id)
            }
        field = self._fields.get(key)
        if field is None:
            raise FilterError(f"Unknown field '{key}'.")
        return field

    def build(self, node: Any, depth: int = 0) -> Q:
        if not isinstance(node, dict):
            raise FilterError("Each filter must be an object.")
        if depth > MAX_DEPTH:
            raise FilterError("Filters are nested too deeply.")
        if "rules" in node:
            op = node.get("op", "and")
            if op not in ("and", "or"):
                raise FilterError("Group operator must be 'and' or 'or'.")
            rules = node["rules"]
            if not isinstance(rules, list):
                raise FilterError("'rules' must be a list.")
            q = Q()
            for child in rules:
                child_q = self.build(child, depth + 1)
                q = (q | child_q) if op == "or" and q else (q & child_q)
            return q
        return self.rule(node)

    def rule(self, node: dict) -> Q:
        self.rule_count += 1
        if self.rule_count > MAX_RULES:
            raise FilterError("Too many filter rules.")
        field, op, value = node.get("field"), node.get("operator"), node.get("value")
        if not isinstance(field, str) or not isinstance(op, str):
            raise FilterError("Each rule needs a field and an operator.")
        if field.startswith("cf:"):
            return _custom_q(self.custom_field(field[3:]), op, value, self.ctx)
        if field not in STANDARD_FIELDS:
            raise FilterError(f"Unknown field '{field}'.")
        return _standard_q(field, op, value, self.ctx)


def build_filter(tree: Any, ctx: Ctx) -> Q:
    if tree in (None, {}, ""):
        return Q()
    return FilterBuilder(ctx).build(tree)


# --- free-text search (list `q` param and global search) ---------------------------
def search_q(text: str, tenant_id: int) -> Q:
    text = text.strip()[:100]
    if not text:
        return Q()
    q = (
        Q(name__icontains=text)
        | Q(email__icontains=text)
        | Q(campaign_name__icontains=text)
        | Q(form_id=text)
    )
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 4:
        q |= Q(phone_e164__contains=digits)
    custom = EnquiryCustomValue.objects.filter(
        enquiry=OuterRef("pk"), tenant_id=tenant_id, value_text__icontains=text
    )
    return q | Q(Exists(custom))


# --- sorting -------------------------------------------------------------------------
SORTS = {
    "created_at": "created_at",
    "updated_at": "updated_at",
    "name": "name",
    "status": "status__order",
    "owner": "primary_owner__full_name",
    "campaign": "campaign_name",
}


def order_by(sort: str | None) -> list[str]:
    sort = (sort or "-created_at").strip()
    desc = sort.startswith("-")
    column = SORTS.get(sort.lstrip("-"))
    if column is None:
        column, desc = "created_at", True
    return [f"-{column}" if desc else column, "-id"]
