"""Server -> browser push over WebSockets (Django Channels).

Groups:
    tenant.<tenant_id>            everyone in a workspace (new leads)
    user.<tenant_id>.<user_id>    one person (notifications)

Sending never raises: a missing Redis or a closed socket must not break the
action that triggered the message. The browser also refetches on its own.
"""

from __future__ import annotations

import logging
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def tenant_group(tenant_id: int) -> str:
    return f"tenant.{tenant_id}"


def user_group(tenant_id: int, user_id: int) -> str:
    return f"user.{tenant_id}.{user_id}"


def _send(group: str, event: str, payload: dict[str, Any]) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, {"type": "push", "event": event, "data": payload})
    except Exception:  # Redis down, etc.
        logger.warning("Could not push %s to %s", event, group, exc_info=True)


def send_to_tenant(tenant_id: int, event: str, payload: dict[str, Any]) -> None:
    _send(tenant_group(tenant_id), event, payload)


def send_to_user(tenant_id: int, user_id: int, event: str, payload: dict[str, Any]) -> None:
    _send(user_group(tenant_id, user_id), event, payload)
