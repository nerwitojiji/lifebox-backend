from django.urls import path

from apps.course_collaborator.views import MyCoursesView

urlpatterns = [
    path("my-courses/", MyCoursesView.as_view(), name="my-courses"),
]
