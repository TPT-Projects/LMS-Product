import os
import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Membership, User
from apps.permissions.roles import Role
from apps.statuses.models import create_default_statuses
from apps.teams.models import Team, TeamMember
from apps.tenants.models import Tenant
from common.tenancy.context import rls_bypass

DEMO_WORKSPACE = "Demo Workspace"
DEMO_DOMAIN = "demo.test"


class Command(BaseCommand):
    help = "Create a demo workspace with one user per role (local development only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.environ.get("DEMO_PASSWORD"),
            help="Password for all demo users. Default: $DEMO_PASSWORD, else a random one.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"] or secrets.token_urlsafe(9)

        with rls_bypass():
            tenant, _ = Tenant.objects.get_or_create(name=DEMO_WORKSPACE)
            team, _ = Team.objects.get_or_create(tenant=tenant, name="Sales")
            create_default_statuses(tenant.pk)

            for role in Role:
                email = f"{role.value}@{DEMO_DOMAIN}"
                user = User.objects.filter(email=email).first()
                if user is None:
                    user = User.objects.create_user(
                        email=email, password=password, full_name=f"Demo {role.label}"
                    )
                else:
                    user.set_password(password)
                    user.save(update_fields=["password"])
                Membership.objects.update_or_create(
                    tenant=tenant, user=user, defaults={"role": role.value, "is_active": True}
                )
                if role in (Role.MANAGER, Role.AGENT):
                    TeamMember.objects.get_or_create(tenant=tenant, team=team, user=user)

        self.stdout.write(self.style.SUCCESS(f"Workspace '{DEMO_WORKSPACE}' is ready."))
        self.stdout.write("Log in with any of these (same password for all):")
        for role in Role:
            self.stdout.write(f"  {role.label:<8} {role.value}@{DEMO_DOMAIN}")
        self.stdout.write(f"  Password: {password}")
