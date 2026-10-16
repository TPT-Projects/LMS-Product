from django.urls import path

from ..views import users as views
from ..views.preferences import TablePreferenceView

urlpatterns = [
    path("users", views.UserListView.as_view(), name="users"),
    path("users/<int:user_id>/role", views.UserRoleView.as_view(), name="user-role"),
    path("users/<int:user_id>/profile", views.UserProfileView.as_view(), name="user-profile"),
    path("invitations", views.InvitationListView.as_view(), name="invitations"),
    path(
        "invitations/<int:invitation_id>",
        views.InvitationDetailView.as_view(),
        name="invitation-detail",
    ),
    path("preferences/tables/<slug:table>", TablePreferenceView.as_view(), name="table-preference"),
]
