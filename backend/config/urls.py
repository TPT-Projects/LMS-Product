from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.integrations.urls import public_urlpatterns as integration_public_urls
from apps.meta_integration.urls import webhook_urlpatterns as meta_webhook_urls


def health(_request):
    return JsonResponse({"status": "ok"})


api_v1 = [
    path("auth/", include("apps.accounts.urls.auth")),
    path("", include("apps.accounts.urls.users")),
    path("", include("apps.tenants.urls")),
    path("", include("apps.teams.urls")),
    path("", include("apps.statuses.urls")),
    path("", include("apps.customfields.urls")),
    path("", include("apps.contacts.urls")),
    path("", include("apps.enquiries.urls")),
    path("", include("apps.views.urls")),
    path("", include("apps.search.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.importexport.urls")),
    path("", include("apps.meta_integration.urls")),
    path("", include("apps.integrations.urls")),
]

urlpatterns = [
    *meta_webhook_urls,  # /webhooks/meta (public, signature-checked)
    *integration_public_urls,  # Google login return, Exotel call results (signed token)
    path("admin/", admin.site.urls),
    path("health/", health),
    path("api/v1/", include(api_v1)),
]
