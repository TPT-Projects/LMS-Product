"""Celery Beat: the heartbeat for every workspace with Meta or connected apps."""

from celery import shared_task
from django.db import transaction

from apps.meta_integration.models import ConnectionStatus, MetaConnection
from common.tenancy.context import rls_bypass, tenant_context

from . import heartbeat
from .models import Integration


@shared_task(ignore_result=True)
def heartbeat_all() -> None:
    with transaction.atomic(), rls_bypass():
        tenant_ids = set(
            MetaConnection.objects.filter(status=ConnectionStatus.CONNECTED).values_list(
                "tenant_id", flat=True
            )
        ) | set(Integration.objects.values_list("tenant_id", flat=True))
    for tenant_id in tenant_ids:
        heartbeat_tenant.delay(tenant_id)


@shared_task(ignore_result=True)
def heartbeat_tenant(tenant_id: int) -> dict:
    with tenant_context(tenant_id):
        return heartbeat.run(tenant_id)
