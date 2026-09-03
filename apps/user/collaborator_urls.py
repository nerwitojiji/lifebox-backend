from django.urls import path

from apps.user.collaborator_views import CollaboratorListCreateView

urlpatterns = [
    path("", CollaboratorListCreateView.as_view(), name="collaborator-list"),
]
