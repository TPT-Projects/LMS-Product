from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("integrations", "0001_initial")]

    operations = [EnableRLS("integrations")]
