import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import AuthToken, Role
from apps.incidents.models import Incident, IncidentMedia

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp()


def png_bytes():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, "PNG")
    return buf.getvalue()


@override_settings(RATELIMIT_ENABLE=False, MEDIA_ROOT=TMP_MEDIA)
class ApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.pw = "pw-12345-Xy"
        self.citizen = User.objects.create_user(email="a@example.com", password=self.pw, role=Role.CITIZEN, phone="1")
        self.other = User.objects.create_user(email="b@example.com", password=self.pw, role=Role.CITIZEN)
        self.dispatcher = User.objects.create_user(email="d@example.com", password=self.pw, role=Role.DISPATCHER)

    def login(self, email="a@example.com"):
        r = self.client.post(reverse("api:login"), {"email": email, "password": self.pw}, content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["token"]

    def auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Token {token}"}

    def test_register_returns_token_and_creates_citizen(self):
        r = self.client.post(
            reverse("api:register"),
            {"first_name": "N", "last_name": "U", "email": "new@example.com", "phone": "2", "password": "a-Strong-pass-77"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["user"]["role"], "CITIZEN")
        self.assertTrue(AuthToken.objects.filter(user__email="new@example.com").exists())

    def test_register_validation_errors(self):
        r = self.client.post(reverse("api:register"), {"email": "bad"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])

    def test_wrong_password_rejected(self):
        r = self.client.post(reverse("api:login"), {"email": "a@example.com", "password": "nope"}, content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_dispatcher_cannot_use_mobile_login(self):
        r = self.client.post(reverse("api:login"), {"email": "d@example.com", "password": self.pw}, content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_endpoints_require_token(self):
        for name in ("api:me", "api:incidents", "api:notifications"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 401, name)
        self.assertEqual(self.client.get(reverse("api:me"), HTTP_AUTHORIZATION="Token bogus").status_code, 401)

    def test_logout_revokes_token(self):
        t = self.login()
        self.assertEqual(self.client.post(reverse("api:logout"), **self.auth(t)).status_code, 200)
        self.assertEqual(self.client.get(reverse("api:me"), **self.auth(t)).status_code, 401)

    def test_update_profile(self):
        t = self.login()
        r = self.client.put(
            reverse("api:me"), {"first_name": "Ada", "address": "5 Road"}, content_type="application/json", **self.auth(t)
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["user"]["first_name"], "Ada")
        self.assertEqual(r.json()["user"]["address"], "5 Road")

    def test_create_incident_saves_to_database(self):
        t = self.login()
        r = self.client.post(
            reverse("api:incidents"),
            {"category": "FIRE", "latitude": "6.5", "longitude": "3.4", "accuracy": "9", "description": "Smoke"},
            **self.auth(t),
        )
        self.assertEqual(r.status_code, 201, r.content)
        incident = Incident.objects.get(pk=r.json()["incident"]["id"])
        self.assertEqual(incident.citizen, self.citizen)
        self.assertEqual(incident.latitude, 6.5)

    def test_create_incident_needs_location_or_address(self):
        t = self.login()
        r = self.client.post(reverse("api:incidents"), {"category": "FIRE"}, **self.auth(t))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Incident.objects.count(), 0)

    def test_incident_privacy(self):
        ta, tb = self.login(), self.login("b@example.com")
        pk = self.client.post(reverse("api:incidents"), {"category": "FIRE", "address_text": "x"}, **self.auth(ta)).json()["incident"]["id"]
        self.assertEqual(self.client.get(reverse("api:incident", args=[pk]), **self.auth(tb)).status_code, 404)
        self.assertEqual(self.client.post(reverse("api:incident_cancel", args=[pk]), **self.auth(tb)).status_code, 404)
        self.assertEqual(self.client.get(reverse("api:incidents"), **self.auth(tb)).json()["results"], [])
        self.assertEqual(len(self.client.get(reverse("api:incidents"), **self.auth(ta)).json()["results"]), 1)

    def test_cancel_incident(self):
        t = self.login()
        pk = self.client.post(reverse("api:incidents"), {"category": "FIRE", "address_text": "x"}, **self.auth(t)).json()["incident"]["id"]
        r = self.client.post(reverse("api:incident_cancel", args=[pk]), **self.auth(t))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["incident"]["status"], "CANCELLED")
        again = self.client.post(reverse("api:incident_cancel", args=[pk]), **self.auth(t))
        self.assertEqual(again.status_code, 409)

    def test_photo_upload_and_protected_media_url(self):
        ta, tb = self.login(), self.login("b@example.com")
        photo = SimpleUploadedFile("p.png", png_bytes(), content_type="image/png")
        r = self.client.post(reverse("api:incidents"), {"category": "FIRE", "address_text": "x", "media": [photo]}, **self.auth(ta))
        self.assertEqual(r.status_code, 201, r.content)
        url = r.json()["incident"]["media"][0]["url"]
        self.assertEqual(self.client.get(url, **self.auth(ta)).status_code, 200)
        self.assertEqual(self.client.get(url, **self.auth(tb)).status_code, 404)
        self.assertEqual(IncidentMedia.objects.count(), 1)

    def test_notifications_listed_and_marked_read(self):
        t = self.login()
        self.client.post(reverse("api:incidents"), {"category": "FIRE", "address_text": "x"}, **self.auth(t))
        from apps.incidents.services import change_status

        inc = Incident.objects.get()
        change_status(inc.pk, "CANCELLED", user=self.dispatcher)
        data = self.client.get(reverse("api:notifications"), **self.auth(t)).json()
        self.assertEqual(data["unread"], 1)
        self.client.post(reverse("api:notifications_read"), **self.auth(t))
        self.assertEqual(self.client.get(reverse("api:notifications"), **self.auth(t)).json()["unread"], 0)
