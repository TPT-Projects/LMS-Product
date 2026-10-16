"""WebSocket endpoint /ws/tenant/?token=<access JWT>.

Browsers cannot set headers on a WebSocket, so the short-lived access token is
sent as a query parameter. The token's workspace and the user's membership are
checked exactly like an API request; the socket only joins that workspace's
groups, so one tenant can never receive another tenant's events.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from common.realtime import tenant_group, user_group
from common.tenancy.authentication import TENANT_CLAIM
from common.tenancy.context import activate_tenant


@database_sync_to_async
def authenticate(raw_token: str) -> tuple[int, int] | None:
    from apps.accounts.models import Membership

    try:
        token = AccessToken(raw_token)
    except TokenError:
        return None
    user_id, tenant_id = token.get("user_id"), token.get(TENANT_CLAIM)
    if not user_id or not tenant_id:
        return None
    with transaction.atomic():
        activate_tenant(int(tenant_id))
        ok = Membership.objects.filter(
            tenant_id=tenant_id, user_id=user_id, is_active=True, user__is_active=True
        ).exists()
        activate_tenant(None)
    return (int(tenant_id), int(user_id)) if ok else None


class TenantConsumer(AsyncJsonWebsocketConsumer):
    groups_joined: list[str]

    async def connect(self):
        query = parse_qs(self.scope.get("query_string", b"").decode())
        identity = await authenticate((query.get("token") or [""])[0])
        if identity is None:
            await self.close(code=4401)
            return
        tenant_id, user_id = identity
        self.groups_joined = [tenant_group(tenant_id), user_group(tenant_id, user_id)]
        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        for group in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"event": "pong"})

    async def push(self, message):
        await self.send_json({"event": message["event"], "data": message.get("data", {})})
