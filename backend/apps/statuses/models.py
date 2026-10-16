from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from common.tenancy.models import TenantScopedModel


class StatusColor(models.TextChoices):
    GRAY = "gray", _("Gray")
    BLUE = "blue", _("Blue")
    AMBER = "amber", _("Amber")
    VIOLET = "violet", _("Violet")
    GREEN = "green", _("Green")
    RED = "red", _("Red")


class Status(TenantScopedModel):
    """A stage an enquiry moves through. Admins can rename, reorder and add."""

    name = models.CharField(max_length=60)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=12, choices=StatusColor.choices, default=StatusColor.GRAY)
    is_default = models.BooleanField(default=False)  # given to new enquiries
    is_closed = models.BooleanField(default=False)  # no more work expected (Closed, Lost)
    is_won = models.BooleanField(default=False)  # counts as a conversion in reports
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "statuses"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="uniq_status_tenant_name"),
            models.UniqueConstraint(
                fields=["tenant"], condition=Q(is_default=True), name="uniq_status_default"
            ),
        ]

    def __str__(self) -> str:
        return self.name


# Spec section 6: New, Contacted, Qualified, Closed, Lost.
DEFAULT_STATUSES = [
    {"name": "New", "color": StatusColor.BLUE, "is_default": True},
    {"name": "Contacted", "color": StatusColor.AMBER},
    {"name": "Qualified", "color": StatusColor.VIOLET},
    {"name": "Closed", "color": StatusColor.GREEN, "is_closed": True, "is_won": True},
    {"name": "Lost", "color": StatusColor.RED, "is_closed": True},
]


def create_default_statuses(tenant_id: int) -> None:
    if Status.objects.filter(tenant_id=tenant_id).exists():
        return
    Status.objects.bulk_create(
        Status(tenant_id=tenant_id, order=index, **values)
        for index, values in enumerate(DEFAULT_STATUSES)
    )


def default_status(tenant_id: int) -> Status:
    status = Status.objects.filter(tenant_id=tenant_id, is_default=True).first()
    if status is None:
        create_default_statuses(tenant_id)
        status = Status.objects.filter(tenant_id=tenant_id).order_by("order", "id").first()
    return status
