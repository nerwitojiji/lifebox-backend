from django.urls import path

from apps.user.views import (
    ChangePasswordView,
    LoginView,
    MeView,
    VerifyTokenView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="user-login"),
    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="user-change-password",
    ),
    path("verify-token/", VerifyTokenView.as_view(), name="user-verify-token"),
    path("me/", MeView.as_view(), name="user-me"),
]
