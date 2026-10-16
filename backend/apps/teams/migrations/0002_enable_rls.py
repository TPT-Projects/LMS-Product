from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("teams", "0001_initial")]

    operations = [EnableRLS("teams"), EnableRLS("team_members")]
