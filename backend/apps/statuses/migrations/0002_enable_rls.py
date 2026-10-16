from django.db import migrations

from common.tenancy.rls import EnableRLS


def create_defaults(apps, schema_editor):
    """Give every existing workspace the default statuses."""
    schema_editor.execute("SELECT set_config('app.rls_bypass', 'on', true)")
    Tenant = apps.get_model("tenants", "Tenant")
    Status = apps.get_model("statuses", "Status")
    from apps.statuses.models import DEFAULT_STATUSES

    for tenant_id in Tenant.objects.values_list("id", flat=True):
        if Status.objects.filter(tenant_id=tenant_id).exists():
            continue
        Status.objects.bulk_create(
            Status(tenant_id=tenant_id, order=i, **values)
            for i, values in enumerate(DEFAULT_STATUSES)
        )
    schema_editor.execute("SELECT set_config('app.rls_bypass', 'off', true)")


class Migration(migrations.Migration):
    dependencies = [("statuses", "0001_initial"), ("tenants", "0002_enable_rls")]

    operations = [
        EnableRLS("statuses"),
        migrations.RunPython(create_defaults, migrations.RunPython.noop),
    ]
