from django.urls import path

from apps.course.views import (
    CourseAssignView,
    CourseCollaboratorsView,
    CourseDetailView,
    CourseEnrollmentsView,
    CourseListCreateView,
    CourseNewVersionView,
    CourseUnenrollView,
)

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="course-list"),
    # Va antes de cualquier ruta con parámetro: el conversor `int` ya evita la
    # colisión, pero el orden deja explícito que «enrollments» es una ruta fija.
    path("enrollments/", CourseEnrollmentsView.as_view(), name="course-enrollments"),
    path("<int:pk>/", CourseDetailView.as_view(), name="course-detail"),
    path("<int:pk>/assign/", CourseAssignView.as_view(), name="course-assign"),
    path(
        "<int:pk>/new-version/",
        CourseNewVersionView.as_view(),
        name="course-new-version",
    ),
    path(
        "<int:pk>/collaborators/",
        CourseCollaboratorsView.as_view(),
        name="course-collaborators",
    ),
    path(
        "<int:pk>/collaborators/<int:enrollment_id>/",
        CourseUnenrollView.as_view(),
        name="course-unenroll",
    ),
]
