from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models.functions import Upper
from django.utils.translation import gettext_lazy as _

from common.tenancy.models import TenantScopedModel


class FieldType(models.TextChoices):
    TEXT = "text", _("Text")
    NUMBER = "number", _("Number")
    CURRENCY = "currency", _("Currency")
    DATE = "date", _("Date")
    DROPDOWN = "dropdown", _("Dropdown")
    MULTI_SELECT = "multi_select", _("Multi-select")
    CHECKBOX = "checkbox", _("Checkbox")


# Which value column each type uses.
VALUE_COLUMN = {
    FieldType.TEXT: "value_text",
    FieldType.DROPDOWN: "value_text",
    FieldType.NUMBER: "value_number",
    FieldType.CURRENCY: "value_number",
    FieldType.DATE: "value_date",
    FieldType.CHECKBOX: "value_bool",
    FieldType.MULTI_SELECT: "value_list",
}


class CustomField(TenantScopedModel):
    """A workspace-defined field on enquiries (spec: custom fields are enquiries only)."""

    key = models.SlugField(max_length=64)
    label = models.CharField(max_length=100)
    type = models.CharField(max_length=16, choices=FieldType.choices)
    options = models.JSONField(default=list, blank=True)  # for dropdown / multi_select
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "custom_fields"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uniq_custom_field_key")
        ]

    def __str__(self) -> str:
        return self.label

    @property
    def value_column(self) -> str:
        return VALUE_COLUMN[self.type]


class EnquiryCustomValue(TenantScopedModel):
    """One typed value per (enquiry, field). Typed columns keep filters fast and correct."""

    enquiry = models.ForeignKey(
        "enquiries.Enquiry", on_delete=models.CASCADE, related_name="custom_values"
    )
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name="values")
    value_text = models.CharField(max_length=1000, null=True, blank=True)
    value_number = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    value_list = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "enquiry_custom_values"
        constraints = [
            models.UniqueConstraint(fields=["enquiry", "field"], name="uniq_enquiry_field_value")
        ]
        indexes = [
            models.Index(fields=["field", "value_text"], name="ecv_text_idx"),
            models.Index(fields=["field", "value_number"], name="ecv_number_idx"),
            models.Index(fields=["field", "value_date"], name="ecv_date_idx"),
            models.Index(fields=["field", "value_bool"], name="ecv_bool_idx"),
            GinIndex(fields=["value_list"], name="ecv_list_gin"),
            GinIndex(OpClass(Upper("value_text"), name="gin_trgm_ops"), name="ecv_text_trgm"),
        ]

    def get_value(self):
        return getattr(self, VALUE_COLUMN[self.field.type])
