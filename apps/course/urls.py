from django.urls import path

from apps.course.views import (
    CourseAssignView,
    CourseEnrollmentsView,
    CourseListCreateView,
)

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="course-list"),
    # Va antes de cualquier ruta con parámetro: el conversor `int` ya evita la
    # colisión, pero el orden deja explícito que «enrollments» es una ruta fija.
    path("enrollments/", CourseEnrollmentsView.as_view(), name="course-enrollments"),
    path("<int:pk>/assign/", CourseAssignView.as_view(), name="course-assign"),
]
