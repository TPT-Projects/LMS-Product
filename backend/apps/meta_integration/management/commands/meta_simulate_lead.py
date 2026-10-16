"""Feed a Meta lead JSON file through the real ingestion pipeline (no Meta app needed).

    cd backend
    python manage.py meta_simulate_lead ../docs/reference/sample_2_Leads_Event4th5thJuly_10_06_26.json
    python manage.py meta_simulate_lead lead.json --workspace "Demo Workspace" --new-id

The form is created and connected if needed. Use --new-id to get a fresh lead id
each run (otherwise a second run is a duplicate and creates nothing, as in production).
"""

import json
import secrets
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.meta_integration.leads import ingest_lead
from apps.meta_integration.models import MetaForm, SyncSource
from apps.tenants.models import Tenant
from common.tenancy.context import rls_bypass, tenant_context


class Command(BaseCommand):
    help = "Simulate an incoming Meta lead from a JSON file (development and demos)."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Lead JSON (same shape as docs/reference samples)")
        parser.add_argument("--workspace", default="Demo Workspace", help="Workspace name or id")
        parser.add_argument("--new-id", action="store_true", help="Use a random lead id")
        parser.add_argument("--no-connect", action="store_true", help="Leave the form unconnected")

    def handle(self, *args, file, workspace, new_id, no_connect, **options):
        path = Path(file)
        if not path.exists():
            raise CommandError(f"{path} not found")
        lead = json.loads(path.read_text("utf-8"))
        if new_id:
            lead["id"] = str(10**15 + secrets.randbelow(9 * 10**15))
        lookup = {"pk": int(workspace)} if workspace.isdigit() else {"name": workspace}
        with transaction.atomic(), rls_bypass():
            tenant = Tenant.objects.filter(**lookup).first()
        if tenant is None:
            raise CommandError(f"Workspace '{workspace}' not found")

        with tenant_context(tenant.pk):
            form, _ = MetaForm.objects.get_or_create(
                tenant=tenant,
                form_id=str(lead.get("form_id", "")),
                defaults={"name": lead.get("campaign_name", "Simulated form")},
            )
            if not no_connect and not form.is_connected:
                from apps.meta_integration.services import set_form_connected

                set_form_connected(form, connected=True, user=None)
        result = ingest_lead(tenant.pk, lead, page_id="simulated", source=SyncSource.TEST)
        self.stdout.write(
            self.style.SUCCESS(f"Lead {lead['id']}: {result.status}")
            + (f" -> enquiry {result.enquiry_id}" if result.enquiry_id else "")
        )
