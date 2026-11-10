from django.urls import path

from . import views

app_name = "incidents"

urlpatterns = [
    path("media-files/<int:pk>/", views.media_download, name="media"),
]
