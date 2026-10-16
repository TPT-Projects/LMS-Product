from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("savedviews", "0001_initial")]

    operations = [EnableRLS("saved_views"), EnableRLS("saved_view_pins")]
