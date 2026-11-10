import os
import uuid

from .models import IncidentMedia

MAX_FILES = 5
MB = 1024 * 1024
LIMITS = {
    IncidentMedia.MediaType.PHOTO: 10 * MB,
    IncidentMedia.MediaType.VIDEO: 50 * MB,
    IncidentMedia.MediaType.AUDIO: 15 * MB,
}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v"}
AUDIO_EXT = {".mp3", ".m4a", ".ogg", ".wav", ".weba"}
AMBIGUOUS_EXT = {".webm"}  # may hold audio (voice note) or video
IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def _classify(name, content_type):
    ext = os.path.splitext(name)[1].lower()
    ctype = (content_type or "").lower()
    if ext in IMAGE_EXT and ctype.startswith("image/"):
        return ext, IncidentMedia.MediaType.PHOTO
    if ext in VIDEO_EXT and ctype.startswith("video/"):
        return ext, IncidentMedia.MediaType.VIDEO
    if ext in AUDIO_EXT and (ctype.startswith("audio/") or ctype == "application/ogg"):
        return ext, IncidentMedia.MediaType.AUDIO
    if ext in AMBIGUOUS_EXT and ctype.startswith("audio/"):
        return ext, IncidentMedia.MediaType.AUDIO
    if ext in AMBIGUOUS_EXT and ctype.startswith("video/"):
        return ext, IncidentMedia.MediaType.VIDEO
    return ext, None


def _is_real_image(upload):
    try:
        from PIL import Image

        upload.seek(0)
        with Image.open(upload) as img:
            ok = img.format in IMAGE_FORMATS
            img.verify()
        return ok
    except Exception:
        return False
    finally:
        upload.seek(0)


def attach_media(incident, files, user=None):
    """Validate and store uploads. Returns (saved_count, error_messages).

    A bad attachment never blocks the emergency itself, so errors are reported, not raised.
    """
    saved, errors = 0, []
    if len(files) > MAX_FILES:
        errors.append(f"Only the first {MAX_FILES} attachments were considered.")
        files = files[:MAX_FILES]
    for f in files:
        ext, media_type = _classify(f.name, f.content_type)
        if media_type is None:
            errors.append(f"{f.name}: file type is not allowed (use photo, video or audio).")
            continue
        if f.size > LIMITS[media_type]:
            errors.append(f"{f.name}: larger than {LIMITS[media_type] // MB} MB.")
            continue
        if media_type == IncidentMedia.MediaType.PHOTO and not _is_real_image(f):
            errors.append(f"{f.name}: not a valid image.")
            continue
        f.name = f"{uuid.uuid4().hex}{ext}"  # never trust the client's file name
        IncidentMedia.objects.create(incident=incident, file=f, media_type=media_type, uploaded_by=user)
        saved += 1
    return saved, errors
