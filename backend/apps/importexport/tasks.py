from celery import shared_task

from . import services


@shared_task(acks_late=True, ignore_result=True)
def run_import(job_id: int, tenant_id: int) -> None:
    """Background import (more than 100 rows). Safe to deliver twice: a finished job is skipped."""
    services.run(job_id, tenant_id)
