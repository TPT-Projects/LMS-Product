from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("meta_integration", "0010_conversions_api")]

    operations = [EnableRLS("meta_conversion_events")]
