from django.db import migrations

from common.tenancy.rls import EnableRLS

TABLES = ["meta_connections", "meta_forms", "form_field_mappings", "sync_logs", "failed_sync_logs"]


class Migration(migrations.Migration):
    dependencies = [("meta_integration", "0001_initial")]

    # The webhook finds the workspace that owns a Page with rls_bypass() (ids only).
    operations = [EnableRLS(table) for table in TABLES]
