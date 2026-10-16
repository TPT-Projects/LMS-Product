from django.urls import path

from . import views

urlpatterns = [
    path("imports", views.ImportListView.as_view(), name="imports"),
    path("imports/template", views.ImportTemplateView.as_view(), name="import-template"),
    path("imports/<int:job_id>", views.ImportDetailView.as_view(), name="import-detail"),
    path("imports/<int:job_id>/map", views.ImportMapView.as_view(), name="import-map"),
    path("imports/<int:job_id>/preview", views.ImportPreviewView.as_view(), name="import-preview"),
    path("imports/<int:job_id>/run", views.ImportRunView.as_view(), name="import-run"),
    path(
        "imports/<int:job_id>/failed-report",
        views.ImportFailedReportView.as_view(),
        name="import-failed-report",
    ),
    path("exports", views.ExportView.as_view(), name="exports"),
]
