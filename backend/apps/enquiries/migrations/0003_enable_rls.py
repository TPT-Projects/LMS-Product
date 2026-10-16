from django.db import migrations

from common.tenancy.rls import EnableRLS

TABLES = [
    "enquiries",
    "enquiry_owners",
    "status_history",
    "notes",
    "followups",
    "call_logs",
    "attachments",
]


class Migration(migrations.Migration):
    dependencies = [("enquiries", "0002_initial")]

    operations = [EnableRLS(table) for table in TABLES]
