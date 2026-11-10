import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Role
from apps.incidents.models import Incident, IncidentMedia, Status
from apps.notifications.models import Notification

from .models import CitizenProfile

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp()


def png_bytes():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, "PNG")
    return buf.getvalue()


@override_settings(RATELIMIT_ENABLE=False, MEDIA_ROOT=TMP_MEDIA)
class CitizenFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.citizen = User.objects.create_user(
            email="c1@example.com", password="pw-12345-x", role=Role.CITIZEN, first_name="Ada", phone="0800"
        )
        self.other = User.objects.create_user(email="c2@example.com", password="pw-12345-x", role=Role.CITIZEN)
        self.dispatcher = User.objects.create_user(email="d@example.com", password="pw-12345-x", role=Role.DISPATCHER)
        self.sos = reverse("citizens:sos_api")

    # ---- registration / auth ----
    def test_register_creates_citizen_and_profile(self):
        r = self.client.post(
            reverse("citizens:register"),
            {
                "first_name": "New", "last_name": "User", "email": "NEW@example.com", "phone": "0801",
                "password1": "a-Strong-pass-77", "password2": "a-Strong-pass-77",
            },
        )
        self.assertEqual(r.status_code, 302)
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.role, Role.CITIZEN)
        self.assertTrue(CitizenProfile.objects.filter(user=user).exists())

    def test_register_rejects_mismatched_passwords(self):
        r = self.client.post(
            reverse("citizens:register"),
            {"first_name": "A", "last_name": "B", "email": "x@example.com", "phone": "1",
             "password1": "a-Strong-pass-77", "password2": "different"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(email="x@example.com").exists())

    def test_dispatcher_cannot_use_citizen_login(self):
        self.client.post(reverse("citizens:login"), {"username": "d@example.com", "password": "pw-12345-x"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_home_requires_login(self):
        r = self.client.get(reverse("citizens:home"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/app/login/", r["Location"])

    # ---- SOS API ----
    def test_sos_requires_login(self):
        r = self.client.post(self.sos, {"category": "FIRE", "address_text": "x"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(Incident.objects.count(), 0)

    def test_dispatcher_cannot_send_sos(self):
        self.client.force_login(self.dispatcher)
        r = self.client.post(self.sos, {"category": "FIRE", "address_text": "x"})
        self.assertEqual(r.status_code, 403)

    def test_sos_with_gps_is_saved_and_ops_notified(self):
        self.client.force_login(self.citizen)
        r = self.client.post(
            self.sos, {"category": "MEDICAL", "latitude": "6.5", "longitude": "3.4", "accuracy": "12.5", "description": "Collapse"}
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertTrue(body["ok"])
        incident = Incident.objects.get(pk=body["id"])
        self.assertEqual(incident.citizen, self.citizen)
        self.assertEqual((incident.latitude, incident.longitude), (6.5, 3.4))
        self.assertEqual(incident.location_accuracy_m, 12.5)
        self.assertEqual(incident.status, Status.REPORTED)
        self.assertEqual(incident.history.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.dispatcher, incident=incident).exists())

    def test_sos_with_address_only(self):
        self.client.force_login(self.citizen)
        r = self.client.post(self.sos, {"category": "FIRE", "address_text": "12 Market Road"})
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(Incident.objects.get().latitude)

    def test_sos_without_location_or_address_is_rejected_and_not_saved(self):
        self.client.force_login(self.citizen)
        r = self.client.post(self.sos, {"category": "FIRE"})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
        self.assertEqual(Incident.objects.count(), 0)

    def test_sos_rejects_bad_coordinates(self):
        self.client.force_login(self.citizen)
        r = self.client.post(self.sos, {"category": "FIRE", "latitude": "999", "longitude": "3"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Incident.objects.count(), 0)

    # ---- attachments ----
    def test_valid_photo_is_attached(self):
        self.client.force_login(self.citizen)
        photo = SimpleUploadedFile("evidence.png", png_bytes(), content_type="image/png")
        r = self.client.post(self.sos, {"category": "ACCIDENT", "address_text": "Ring Road", "media": [photo]})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["media_errors"], [])
        media = IncidentMedia.objects.get()
        self.assertEqual(media.media_type, "PHOTO")
        self.assertNotIn("evidence", media.file.name)  # stored under a random name

    def test_bad_attachment_is_reported_but_incident_still_saved(self):
        self.client.force_login(self.citizen)
        bad = SimpleUploadedFile("run.exe", b"MZ....", content_type="application/octet-stream")
        fake = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
        r = self.client.post(self.sos, {"category": "FIRE", "address_text": "x", "media": [bad, fake]})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(r.json()["media_errors"]), 2)
        self.assertEqual(Incident.objects.count(), 1)
        self.assertEqual(IncidentMedia.objects.count(), 0)

    def test_media_download_permissions(self):
        self.client.force_login(self.citizen)
        photo = SimpleUploadedFile("p.png", png_bytes(), content_type="image/png")
        self.client.post(self.sos, {"category": "FIRE", "address_text": "x", "media": [photo]})
        url = reverse("incidents:media", args=[IncidentMedia.objects.get().pk])
        self.assertEqual(self.client.get(url).status_code, 200)  # owner
        self.client.force_login(self.dispatcher)
        self.assertEqual(self.client.get(url).status_code, 200)  # ops
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)  # another citizen
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)  # anonymous -> login

    # ---- tracking / privacy / cancel ----
    def _make(self, citizen):
        self.client.force_login(citizen)
        return self.client.post(self.sos, {"category": "FIRE", "address_text": "x"}).json()["id"]

    def test_citizen_only_sees_own_incidents(self):
        pk = self._make(self.citizen)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("citizens:incident_detail", args=[pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("citizens:incident_status_api", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("citizens:incident_cancel", args=[pk])).status_code, 404)

    def test_status_api_reports_real_status(self):
        pk = self._make(self.citizen)
        data = self.client.get(reverse("citizens:incident_status_api", args=[pk])).json()
        self.assertEqual(data["status"], "REPORTED")
        self.assertIsNone(data["responder"])

    def test_citizen_can_cancel_pending_request(self):
        pk = self._make(self.citizen)
        self.client.post(reverse("citizens:incident_cancel", args=[pk]))
        self.assertEqual(Incident.objects.get(pk=pk).status, Status.CANCELLED)

    def test_dashboard_alert_api_returns_new_incident(self):
        pk = self._make(self.citizen)
        self.client.force_login(self.dispatcher)
        data = self.client.get(reverse("dashboard:new_incidents_api") + "?after=0").json()
        self.assertEqual([i["id"] for i in data["new"]], [pk])
        again = self.client.get(reverse("dashboard:new_incidents_api") + f"?after={pk}").json()
        self.assertEqual(again["new"], [])

    def test_citizen_cannot_open_dashboard_alert_api(self):
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse("dashboard:new_incidents_api")).status_code, 403)
