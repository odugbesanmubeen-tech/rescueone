import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import IncidentMedia
from .permissions import user_can_view_incident_files


@login_required
def media_download(request, pk):
    """Incident files are private: only ops, the reporting citizen, or an assigned responder."""
    media = get_object_or_404(IncidentMedia.objects.select_related("incident"), pk=pk)
    if not user_can_view_incident_files(request.user, media.incident):
        raise Http404
    content_type = mimetypes.guess_type(media.file.name)[0] or "application/octet-stream"
    return FileResponse(media.file.open("rb"), content_type=content_type)
