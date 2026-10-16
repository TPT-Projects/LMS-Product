from typing import Any

from django.db import transaction

from common.realtime import send_to_user

from .models import Notification

IMPORT_FINISHED = "import.finished"


def notify(
    *,
    tenant_id: int,
    user_id: int,
    kind: str,
    title: str,
    body: str = "",
    link: str = "",
    data: dict[str, Any] | None = None,
) -> Notification:
    notification = Notification.objects.create(
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        title=title[:200],
        body=body[:500],
        link=link,
        data=data or {},
    )
    # Push to the user's open tabs (WebSocket) once the row is committed.
    transaction.on_commit(
        lambda: send_to_user(
            tenant_id, user_id, "notification", {"id": notification.pk, "title": notification.title}
        )
    )
    return notification
