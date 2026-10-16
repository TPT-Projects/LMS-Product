"""Live updates: sockets need a valid token and only receive their own workspace's events."""

import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator

from common.realtime import send_to_tenant, send_to_user

# Sockets read the database from another thread, so data must really be committed.
pytestmark = pytest.mark.django_db(transaction=True)


def communicator(token: str) -> WebsocketCommunicator:
    from config.asgi import application

    return WebsocketCommunicator(
        application, f"/ws/tenant/?token={token}", headers=[(b"origin", b"http://localhost:5173")]
    )


async def _scenario(a, b):
    sock_a, sock_b = communicator(a.access), communicator(b.access)
    assert (await sock_a.connect())[0] and (await sock_b.connect())[0]

    await send_to_tenant_async(a.tenant_id, "enquiry.created", {"id": 1})
    assert (await sock_a.receive_json_from())["event"] == "enquiry.created"
    assert await sock_b.receive_nothing(timeout=0.2)  # workspace B hears nothing

    await send_to_user_async(b.tenant_id, b.user_id, "notification", {"id": 7})
    assert (await sock_b.receive_json_from())["data"] == {"id": 7}
    assert await sock_a.receive_nothing(timeout=0.2)

    bad = communicator("not-a-token")
    connected, code = await bad.connect()
    assert not connected

    for sock in (sock_a, sock_b):
        await sock.disconnect()


async def send_to_tenant_async(*args):
    from asgiref.sync import sync_to_async

    await sync_to_async(send_to_tenant)(*args)


async def send_to_user_async(*args):
    from asgiref.sync import sync_to_async

    await sync_to_async(send_to_user)(*args)


def test_websocket_events_are_tenant_isolated(signup):
    a, b = signup(), signup()
    async_to_sync(_scenario)(a, b)
