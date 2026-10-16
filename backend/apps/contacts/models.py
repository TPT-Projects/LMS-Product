from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models import Q
from django.db.models.functions import Upper

from common.tenancy.models import TenantQuerySet, TenantScopedModel


class ContactQuerySet(TenantQuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)


class Contact(TenantScopedModel):
    """One unique person per workspace. Read-only for users: only the system writes it.

    Matched by phone (E.164) or email depending on the workspace's dedupe key.
    Each Enquiry keeps its own copy of what was submitted.
    """

    name = models.CharField(max_length=200, blank=True)
    phone_e164 = models.CharField(max_length=20, null=True, blank=True)
    phone_raw = models.CharField(max_length=50, blank=True)
    email_lower = models.CharField(max_length=254, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ContactQuerySet.as_manager()

    class Meta:
        db_table = "contacts"
        constraints = [
            # Concurrent webhooks for the same person cannot create two contacts.
            models.UniqueConstraint(
                fields=["tenant", "phone_e164"],
                condition=Q(phone_e164__isnull=False, deleted_at__isnull=True),
                name="uniq_contact_phone",
            ),
            models.UniqueConstraint(
                fields=["tenant", "email_lower"],
                condition=Q(email_lower__isnull=False, deleted_at__isnull=True),
                name="uniq_contact_email",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "deleted_at", "created_at"], name="contact_list_idx"),
            GinIndex(OpClass(Upper("name"), name="gin_trgm_ops"), name="contact_name_trgm"),
        ]

    def __str__(self) -> str:
        return self.name or self.phone_e164 or self.email_lower or f"Contact {self.pk}"
