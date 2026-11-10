from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "citizens"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.CitizenLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="/app/login/"), name="logout"),
    path("register/", views.register, name="register"),
    path("report/", views.report, name="report"),
    path("incidents/", views.incident_list, name="incident_list"),
    path("incidents/<int:pk>/", views.incident_detail, name="incident_detail"),
    path("incidents/<int:pk>/cancel/", views.incident_cancel, name="incident_cancel"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("profile/", views.profile, name="profile"),
    path("api/sos/", views.sos_api, name="sos_api"),
    path("api/incidents/<int:pk>/", views.incident_status_api, name="incident_status_api"),
    path("offline/", views.offline, name="offline"),
    path("manifest.json", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="sw"),
]
