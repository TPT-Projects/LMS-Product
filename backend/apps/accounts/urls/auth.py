from django.urls import path

from ..views import auth as views

urlpatterns = [
    path("signup", views.SignupView.as_view(), name="auth-signup"),
    path("login", views.LoginView.as_view(), name="auth-login"),
    path("refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("logout", views.LogoutView.as_view(), name="auth-logout"),
    path("forgot-password", views.ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("reset-password", views.ResetPasswordView.as_view(), name="auth-reset-password"),
    path("accept-invite", views.AcceptInviteView.as_view(), name="auth-accept-invite"),
    path("me", views.MeView.as_view(), name="auth-me"),
    path("switch-workspace", views.SwitchWorkspaceView.as_view(), name="auth-switch-workspace"),
]
