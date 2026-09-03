from django.urls import path

from apps.user.collaborator_views import (
    CollaboratorListView,
    CollaboratorResetPasswordView,
)

urlpatterns = [
    path("", CollaboratorListView.as_view(), name="collaborator-list"),
    path(
        "<int:pk>/reset-password/",
        CollaboratorResetPasswordView.as_view(),
        name="collaborator-reset-password",
    ),
]
