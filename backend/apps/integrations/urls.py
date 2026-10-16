from django.urls import path

from . import views

# Specific paths first: "integrations/<app>" would otherwise catch them.
urlpatterns = [
    path("integrations", views.IntegrationListView.as_view(), name="integrations"),
    path("integrations/heartbeat", views.HeartbeatView.as_view(), name="integrations-heartbeat"),
    path("integrations/calling", views.CallingView.as_view(), name="integrations-calling"),
    # Exotel
    path("integrations/exotel/manage", views.ExotelView.as_view(), name="exotel"),
    path("integrations/exotel/refresh", views.ExotelRefreshView.as_view(), name="exotel-refresh"),
    path("integrations/exotel/numbers", views.ExotelNumbersView.as_view(), name="exotel-numbers"),
    path(
        "integrations/exotel/numbers/<int:number_id>",
        views.ExotelNumberView.as_view(),
        name="exotel-number",
    ),
    path("integrations/exotel/forms", views.ExotelFormsView.as_view(), name="exotel-forms"),
    path(
        "integrations/exotel/forms/<int:form_id>",
        views.ExotelFormView.as_view(),
        name="exotel-form",
    ),
    path("integrations/exotel/calls", views.AutoCallListView.as_view(), name="exotel-calls"),
    # WhatsApp (Facebook login)
    path(
        "integrations/whatsapp/connect",
        views.WhatsAppConnectView.as_view(),
        name="whatsapp-connect",
    ),
    path("integrations/whatsapp/manage", views.WhatsAppView.as_view(), name="whatsapp"),
    path(
        "integrations/whatsapp/signup-config",
        views.WhatsAppSignupConfigView.as_view(),
        name="whatsapp-signup-config",
    ),
    path(
        "integrations/whatsapp/embedded",
        views.WhatsAppEmbeddedView.as_view(),
        name="whatsapp-embedded",
    ),
    path(
        "integrations/whatsapp/numbers/<str:phone_number_id>/register",
        views.WhatsAppRegisterView.as_view(),
        name="whatsapp-register",
    ),
    path(
        "integrations/whatsapp/refresh",
        views.WhatsAppRefreshView.as_view(),
        name="whatsapp-refresh",
    ),
    # Google Sheets
    path(
        "integrations/google_sheets/connect",
        views.GoogleConnectView.as_view(),
        name="google-connect",
    ),
    path(
        "integrations/google_sheets/spreadsheets",
        views.SpreadsheetsView.as_view(),
        name="google-spreadsheets",
    ),
    path(
        "integrations/google_sheets/spreadsheets/<str:spreadsheet_id>/tabs",
        views.SpreadsheetTabsView.as_view(),
        name="google-tabs",
    ),
    path("integrations/google_sheets/links", views.SheetLinksView.as_view(), name="sheet-links"),
    path(
        "integrations/google_sheets/exports",
        views.SheetExportsView.as_view(),
        name="sheet-exports",
    ),
    path(
        "integrations/google_sheets/links/<int:link_id>",
        views.SheetLinkView.as_view(),
        name="sheet-link",
    ),
    path(
        "integrations/google_sheets/links/<int:link_id>/sync",
        views.SheetLinkSyncView.as_view(),
        name="sheet-link-sync",
    ),
    # Generic
    path("integrations/<slug:app>", views.IntegrationView.as_view(), name="integration"),
    path(
        "integrations/<slug:app>/check",
        views.IntegrationCheckView.as_view(),
        name="integration-check",
    ),
]

# Public (no API token): Google's login return and Exotel's call results.
public_urlpatterns = [
    path(
        "api/integrations/google/callback/",
        views.GoogleCallbackView.as_view(),
        name="google-oauth-return",
    ),
    path("api/integrations/google/callback", views.GoogleCallbackView.as_view()),
    path(
        "webhooks/exotel/<str:token>",
        views.ExotelStatusWebhookView.as_view(),
        name="exotel-webhook",
    ),
]
