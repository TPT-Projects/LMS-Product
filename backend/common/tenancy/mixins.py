class TenantScopedViewMixin:
    """Scope a DRF view's queryset to the request's workspace.

    This is the ORM half of the isolation rule. PostgreSQL RLS is the second
    half, so a missed filter still cannot leak another tenant's rows.
    """

    def get_queryset(self):
        return super().get_queryset().filter(tenant_id=self.request.tenant.pk)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
