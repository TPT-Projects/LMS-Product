from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("tenants", "0001_initial")]

    operations = [EnableRLS("tenants", column="id")]
