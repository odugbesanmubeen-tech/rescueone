from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("api/stats/", views.stats_api, name="stats_api"),
    path("incidents/", views.incident_list, name="incident_list"),
    path("incidents/new/", views.incident_create, name="incident_create"),
    path("incidents/<int:pk>/", views.incident_detail, name="incident_detail"),
    path("incidents/<int:pk>/assign/", views.incident_assign, name="incident_assign"),
    path("incidents/<int:pk>/status/", views.incident_status, name="incident_status"),
    path("assignments/<int:pk>/cancel/", views.assignment_cancel, name="assignment_cancel"),
    path("responders/", views.responder_list, name="responder_list"),
    path("responders/new/", views.responder_create, name="responder_create"),
    path("dispatchers/", views.dispatcher_list, name="dispatcher_list"),
    path("dispatchers/new/", views.dispatcher_create, name="dispatcher_create"),
    path("citizens/", views.citizen_list, name="citizen_list"),
    path("users/<int:pk>/toggle-active/", views.user_toggle_active, name="user_toggle_active"),
    path("stations/", views.station_list, name="station_list"),
    path("stations/new/", views.station_create, name="station_create"),
    path("vehicles/", views.vehicle_list, name="vehicle_list"),
    path("vehicles/new/", views.vehicle_create, name="vehicle_create"),
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("analytics/", views.analytics_view, name="analytics"),
    path("audit/", views.audit_log_view, name="audit_log"),
]
