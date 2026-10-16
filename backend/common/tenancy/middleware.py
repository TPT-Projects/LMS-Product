from .context import set_current_tenant_id


class TenantContextMiddleware:
    """Tenant guard: every request starts and ends with no tenant in context.

    The tenant is set by `TenantJWTAuthentication` only after the token and
    the membership have been checked. Clearing it here means a worker thread
    can never carry the previous request's tenant into the next one.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_tenant_id(None)
        request.tenant = None
        request.membership = None
        try:
            return self.get_response(request)
        finally:
            set_current_tenant_id(None)
