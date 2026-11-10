from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("auth/register/", views.register, name="register"),
    path("auth/login/", views.login, name="login"),
    path("auth/logout/", views.logout, name="logout"),
    path("me/", views.me, name="me"),
    path("incidents/", views.incidents, name="incidents"),
    path("incidents/<int:pk>/", views.incident_view, name="incident"),
    path("incidents/<int:pk>/cancel/", views.incident_cancel, name="incident_cancel"),
    path("media/<int:pk>/", views.media, name="media"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
]
