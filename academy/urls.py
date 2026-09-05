from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("user/", include("apps.user.urls")),
    path("course/", include("apps.course.urls")),
    path("collaborator/", include("apps.user.collaborator_urls")),
    path("course-collaborator/", include("apps.course_collaborator.urls")),
]

# SPEC-011: MEDIA_ROOT es privado; los PDFs se sirven con autenticación.
