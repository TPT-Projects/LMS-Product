from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0003_integration_settings_integration_synced_at_autocall_and_more")
    ]

    operations = [EnableRLS(t) for t in ("exotel_numbers", "auto_calls", "sheet_links")]
