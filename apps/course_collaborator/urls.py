from django.urls import path

from apps.course_collaborator.views import MyCourseDetailView, MyCoursesView

urlpatterns = [
    path("my-courses/", MyCoursesView.as_view(), name="my-courses"),
    path(
        "my-courses/<int:pk>/",
        MyCourseDetailView.as_view(),
        name="my-course-detail",
    ),
]
