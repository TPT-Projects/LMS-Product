from django.core.management.base import BaseCommand

from common.mongo import ensure_indexes


class Command(BaseCommand):
    help = "Create the MongoDB indexes for lead_form_responses and activity_logs."

    def handle(self, *args, **options):
        ensure_indexes()
        self.stdout.write(self.style.SUCCESS("MongoDB indexes are ready."))
