from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.incidents.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("app/", include("apps.citizens.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("", RedirectView.as_view(pattern_name="dashboard:overview", permanent=False)),
]
