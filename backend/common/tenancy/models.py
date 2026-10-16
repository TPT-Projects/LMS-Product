from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_tenant(self, tenant_or_id) -> "TenantQuerySet":
        tenant_id = getattr(tenant_or_id, "pk", tenant_or_id)
        return self.filter(tenant_id=tenant_id)


class TenantScopedModel(models.Model):
    """Base for every tenant-owned table.

    Adds `tenant_id`. Remember to add `EnableRLS("<table>")` to the app's
    migrations for each concrete subclass.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True
    )

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True
