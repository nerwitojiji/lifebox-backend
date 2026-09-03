from django.urls import path

from apps.course.views import CourseAssignView, CourseListCreateView

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="course-list"),
    path("<int:pk>/assign/", CourseAssignView.as_view(), name="course-assign"),
]
