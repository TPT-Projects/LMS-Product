from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_tablepreference")]

    operations = [EnableRLS("table_preferences")]
