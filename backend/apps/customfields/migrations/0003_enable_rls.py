from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("customfields", "0002_initial")]

    operations = [EnableRLS("custom_fields"), EnableRLS("enquiry_custom_values")]
