"""Tenant context for one request or one background job.

Two layers keep tenants apart:

1. Application layer: a context variable holding the current tenant id. The
   MongoDB data layer and tenant-scoped querysets read it.
2. Database layer: the PostgreSQL setting `app.tenant_id`, read by the Row
   Level Security policies (see `common.tenancy.rls`). It is always set with
   `is_local = true`, so it lives only until the current transaction ends.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from django.db import DatabaseError, connection, transaction

_current_tenant_id: ContextVar[int | None] = ContextVar("current_tenant_id", default=None)


class TenantContextError(RuntimeError):
    """Raised when tenant-scoped code runs without a tenant."""


def get_current_tenant_id() -> int | None:
    return _current_tenant_id.get()


def require_current_tenant_id() -> int:
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise TenantContextError("No tenant in context.")
    return tenant_id


def set_current_tenant_id(tenant_id: int | None) -> None:
    _current_tenant_id.set(tenant_id)


def _set_db_setting(name: str, value: str) -> None:
    if not connection.in_atomic_block:
        # Outside a transaction a local setting would vanish immediately,
        # which would silently turn RLS into "deny all". Fail loudly instead.
        raise TenantContextError(f"{name} must be set inside a transaction.atomic() block.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [name, value])


def _get_db_setting(name: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting(%s, true)", [name])
        row = cursor.fetchone()
    return (row[0] or "") if row else ""


def _restore_db_setting(name: str, value: str) -> None:
    # If the block failed, the savepoint rollback restores the setting anyway
    # and the aborted transaction refuses new SQL, so ignore that case.
    try:
        _set_db_setting(name, value)
    except DatabaseError:
        pass


def set_db_tenant(tenant_id: int | None) -> None:
    """Set (or clear) the tenant used by PostgreSQL RLS for this transaction."""
    _set_db_setting("app.tenant_id", "" if tenant_id is None else str(int(tenant_id)))


def activate_tenant(tenant_id: int | None) -> None:
    """Set the tenant in both layers. Call inside a transaction."""
    set_db_tenant(tenant_id)
    set_current_tenant_id(tenant_id)


@contextmanager
def tenant_context(tenant_id: int) -> Iterator[None]:
    """Run code as one tenant. Use in Celery tasks, commands and tests."""
    with transaction.atomic():
        previous_db = _get_db_setting("app.tenant_id")
        token = _current_tenant_id.set(int(tenant_id))
        set_db_tenant(tenant_id)
        try:
            yield
        finally:
            _current_tenant_id.reset(token)
            _restore_db_setting("app.tenant_id", previous_db)


@contextmanager
def rls_bypass() -> Iterator[None]:
    """Run system code that must cross tenants (sign up, log in, accept invite).

    Keep the block as small as possible and always filter explicitly by user
    or token inside it. Never call this from code that handles tenant data
    on behalf of a user.
    """
    with transaction.atomic():
        previous = _get_db_setting("app.rls_bypass")
        _set_db_setting("app.rls_bypass", "on")
        try:
            yield
        finally:
            _restore_db_setting("app.rls_bypass", previous or "off")
