from django.urls import path

from . import views

urlpatterns = [
    path("meta/status", views.StatusView.as_view(), name="meta-status"),
    path("meta/connect", views.ConnectView.as_view(), name="meta-connect"),
    path("meta/pages", views.PagesView.as_view(), name="meta-pages"),
    path("meta/page", views.PageView.as_view(), name="meta-page"),
    path("meta/check-access", views.CheckAccessView.as_view(), name="meta-check-access"),
    path("meta/connection", views.ConnectionView.as_view(), name="meta-connection"),
    path("meta/settings", views.SettingsView.as_view(), name="meta-settings"),
    path("meta/sync", views.SyncNowView.as_view(), name="meta-sync"),
    path("meta/poll", views.PollView.as_view(), name="meta-poll"),
    path("meta/conversions", views.ConversionsView.as_view(), name="meta-conversions"),
    path("meta/conversions/test", views.ConversionTestView.as_view(), name="meta-conversions-test"),
    path("meta/forms", views.FormListView.as_view(), name="meta-forms"),
    path("meta/forms/refresh", views.FormRefreshView.as_view(), name="meta-forms-refresh"),
    path(
        "meta/forms/<int:form_pk>/connect",
        views.FormConnectView.as_view(connect=True),
        name="meta-form-connect",
    ),
    path(
        "meta/forms/<int:form_pk>/disconnect",
        views.FormConnectView.as_view(connect=False),
        name="meta-form-disconnect",
    ),
    path("meta/forms/<int:form_pk>/mapping", views.FormMappingView.as_view(), name="meta-mapping"),
    path("meta/sync-logs", views.SyncLogListView.as_view(), name="meta-sync-logs"),
    path("meta/failed-syncs", views.FailedSyncListView.as_view(), name="meta-failed-syncs"),
    path(
        "meta/failed-syncs/<int:failed_id>/retry",
        views.RetryView.as_view(),
        name="meta-failed-sync-retry",
    ),
]

# Public endpoints outside /api/v1 (no API token): Meta's webhook and the login popup return.
webhook_urlpatterns = [
    path("webhooks/meta", views.MetaWebhookView.as_view(), name="meta-webhook"),
    path("api/meta/callback/", views.OAuthReturnView.as_view(), name="meta-oauth-return"),
    path("api/meta/callback", views.OAuthReturnView.as_view()),
]
