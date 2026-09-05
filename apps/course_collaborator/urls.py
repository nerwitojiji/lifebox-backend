from django.urls import path

from apps.course_collaborator.views import MyCourseDetailView, MyCoursesView, MyCourseMaterialFileView

urlpatterns = [
    path(
        "my-courses/<int:pk>/materials/<int:material_id>/file/",
        MyCourseMaterialFileView.as_view(), name="my-course-material-file",
    ),
    path("my-courses/", MyCoursesView.as_view(), name="my-courses"),
    path(
        "my-courses/<int:pk>/",
        MyCourseDetailView.as_view(),
        name="my-course-detail",
    ),
]
