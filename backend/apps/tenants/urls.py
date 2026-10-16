from django.urls import path

from .views import WorkspaceView

urlpatterns = [
    path("workspace", WorkspaceView.as_view(), name="workspace"),
]
