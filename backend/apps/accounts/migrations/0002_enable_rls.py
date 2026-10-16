from django.db import migrations

from common.tenancy.rls import EnableRLS


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    # `users` is global (one login, many workspaces) and has no tenant_id.
    operations = [EnableRLS("memberships"), EnableRLS("invitations")]
