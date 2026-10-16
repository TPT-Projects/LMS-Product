from django.db import models
from django.utils.translation import gettext_lazy as _


class DedupeKey(models.TextChoices):
    PHONE = "phone", _("Phone")
    EMAIL = "email", _("Email")


class Tenant(models.Model):
    """A workspace (one business account). All other data belongs to a tenant."""

    name = models.CharField(max_length=120)
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")
    dedupe_key = models.CharField(max_length=10, choices=DedupeKey.choices, default=DedupeKey.PHONE)
    default_country = models.CharField(max_length=2, default="IN")  # ISO 3166-1 alpha-2
    plan = models.CharField(max_length=32, default="free")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants"

    def __str__(self) -> str:
        return self.name
