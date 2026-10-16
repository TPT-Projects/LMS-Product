from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("importexport", "0001_initial")]

    operations = [EnableRLS("import_jobs"), EnableRLS("import_rows_failed")]
