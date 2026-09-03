from django.urls import path

from apps.course.views import CourseListCreateView

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="course-list"),
]
