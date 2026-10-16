import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Membership
from apps.customfields.models import CustomField, FieldType
from apps.statuses.models import Status, create_default_statuses
from apps.tenants.models import Tenant
from common.tenancy.context import rls_bypass, tenant_context

from ...ingestion import EnquiryData, ingest_enquiry
from ...models import FollowUp, Source

# Shaped like the reference Meta leads in docs/reference (spec section 4).
CAMPAIGNS = [
    ("Leads_Dubai Properties_09/06/26", "Ahmedabad + G'nagar", "Ad 1", "2869657293379182"),
    (
        "Leads_Event4th5thJuly_10/06/26",
        "Ahmedabad+Gnagar",
        "New Leads ad – Copy 2",
        "1623165265438269",
    ),
    ("Leads_Event5th-6thSep_23/08/26", "Gujarat", "Event ad", "1623165265438270"),
    ("Leads_UddhavbhaiPersonal_29/08/26", "Surat", "Personal brand", "1623165265438271"),
]
FIRST = [
    "Karan",
    "Riya",
    "Arjun",
    "Priya",
    "Rahul",
    "Neha",
    "Vikram",
    "Anjali",
    "Rohan",
    "Kavya",
    "Amit",
    "Pooja",
    "Siddharth",
    "Meera",
    "Harsh",
    "Isha",
]
LAST = ["Shah", "Patel", "Mehta", "Desai", "Joshi", "Sachdev", "Trivedi", "Iyer", "Kapoor", "Rao"]
FIELDS = [
    (
        "investment_budget",
        "Investment budget",
        FieldType.DROPDOWN,
        ["₹5_cr+", "₹1.9_cr_–_₹3_cr", "₹1_cr_–_₹1.9_cr", "under_₹1_cr"],
    ),
    ("purpose", "Purpose", FieldType.DROPDOWN, ["investment", "end_use_/_future_relocation"]),
    (
        "event_attendance",
        "Event attendance",
        FieldType.DROPDOWN,
        ["yes,_5th_july", "yes,_6th_july", "no"],
    ),
    ("city", "City", FieldType.TEXT, []),
]
CITIES = ["Ahmedabad", "Gandhinagar", "Surat", "Vadodara", "Mumbai", "Dubai"]


class Command(BaseCommand):
    help = "Add realistic sample enquiries to a workspace (local development only)."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", default="Demo Workspace", help="Workspace name or id")
        parser.add_argument("--count", type=int, default=60)
        parser.add_argument("--seed", type=int, default=7)

    def handle(self, *args, workspace, count, seed, **options):
        rng = random.Random(seed)
        lookup = {"pk": int(workspace)} if workspace.isdigit() else {"name": workspace}
        with transaction.atomic(), rls_bypass():
            tenant = Tenant.objects.filter(**lookup).first()
        if tenant is None:
            raise CommandError(f"Workspace '{workspace}' not found. Run seed_demo first?")

        with tenant_context(tenant.pk):
            create_default_statuses(tenant.pk)
            fields = {}
            for order, (key, label, ftype, options) in enumerate(FIELDS):
                fields[key], _ = CustomField.objects.get_or_create(
                    tenant=tenant,
                    key=key,
                    defaults={"label": label, "type": ftype, "options": options, "order": order},
                )
            statuses = list(Status.objects.filter(tenant=tenant))
            owners = list(
                Membership.objects.filter(
                    tenant=tenant, is_active=True, role__in=["agent", "manager"]
                ).values_list("user_id", flat=True)
            )
            now = timezone.now()
            for _ in range(count):
                campaign, adset, ad, form = rng.choice(CAMPAIGNS)
                # ~15% repeat people, like real lead data
                person = rng.randrange(int(count * 0.85) or 1)
                name = f"{FIRST[person % len(FIRST)]} {LAST[person % len(LAST)]}"
                values = {
                    fields["investment_budget"]: rng.choice(FIELDS[0][3]),
                    fields["purpose"]: rng.choice(FIELDS[1][3]),
                    fields["city"]: rng.choice(CITIES),
                }
                if "Event" in campaign:
                    values[fields["event_attendance"]] = rng.choice(FIELDS[2][3])
                result = ingest_enquiry(
                    tenant=tenant,
                    data=EnquiryData(
                        name=name,
                        phone=f"+9198{person:08d}",
                        email=f"{name.split()[0].lower()}{person}@example.com",
                        source=rng.choice([Source.META, Source.META, Source.MANUAL]),
                        campaign_name=campaign,
                        adset_name=adset,
                        ad_name=ad,
                        form_id=form,
                        status=rng.choice(statuses),
                        primary_owner_id=rng.choice([None, *owners]) if owners else None,
                        custom_values=values,
                        created_at=now - timedelta(hours=rng.randrange(24 * 45)),
                    ),
                )
                if rng.random() < 0.3:
                    FollowUp.objects.create(
                        tenant=tenant,
                        enquiry=result.enquiry,
                        title="Call back",
                        due_at=now + timedelta(hours=rng.randrange(-48, 96)),
                        assignee_id=result.enquiry.primary_owner_id,
                    )
        self.stdout.write(self.style.SUCCESS(f"Added {count} enquiries to '{tenant.name}'."))
