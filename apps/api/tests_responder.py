from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Role
from apps.dispatch.models import AssignmentStatus, IncidentAssignment
from apps.dispatch.services import assign_responder
from apps.incidents.models import Incident, Status
from apps.incidents.services import create_incident
from apps.locations.models import ResponderLocation
from apps.responders.models import Availability, ResponderProfile

User = get_user_model()
JSON = "application/json"


@override_settings(RATELIMIT_ENABLE=False)
class ResponderApiTests(TestCase):
    def setUp(self):
        self.pw = "pw-12345-Xy"
        self.dispatcher = User.objects.create_user(email="d@example.com", password=self.pw, role=Role.DISPATCHER)
        self.citizen = User.objects.create_user(email="c@example.com", password=self.pw, role=Role.CITIZEN, phone="0800111")
        self.r1_user = User.objects.create_user(email="r1@example.com", password=self.pw, role=Role.RESPONDER, first_name="Sam")
        self.r2_user = User.objects.create_user(email="r2@example.com", password=self.pw, role=Role.RESPONDER)
        self.r1 = ResponderProfile.objects.create(user=self.r1_user)
        self.r2 = ResponderProfile.objects.create(user=self.r2_user)
        self.incident = create_incident(category="FIRE", citizen=self.citizen, lat=6.5, lng=3.4, created_by=None)

    def token(self, email):
        r = self.client.post(reverse("api:login"), {"email": email, "password": self.pw}, content_type=JSON)
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["token"]

    def call(self, method, name, token, data=None, args=None):
        kwargs = {"HTTP_AUTHORIZATION": f"Token {token}"}
        url = reverse(name, args=args or [])
        if method == "get":
            return self.client.get(url, **kwargs)
        return self.client.post(url, data or {}, content_type=JSON, **kwargs)

    def go_online(self, token):
        return self.call("post", "api:responder_availability", token, {"availability": "ONLINE"})

    def offer(self, profile):
        profile.refresh_from_db()
        return assign_responder(self.incident.pk, profile.pk, self.dispatcher)

    # ---- sign-in ----
    def test_responder_can_sign_in_and_read_me(self):
        t = self.token("r1@example.com")
        r = self.client.get(reverse("api:me"), HTTP_AUTHORIZATION=f"Token {t}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["user"]["role"], "RESPONDER")

    def test_citizen_token_cannot_use_responder_endpoints(self):
        t = self.token("c@example.com")
        self.assertEqual(self.call("get", "api:responder_assignments", t).status_code, 403)
        self.assertEqual(self.call("post", "api:responder_availability", t, {"availability": "ONLINE"}).status_code, 403)

    def test_responder_without_profile_gets_clear_error(self):
        User.objects.create_user(email="np@example.com", password=self.pw, role=Role.RESPONDER)
        t = self.token("np@example.com")
        r = self.call("get", "api:responder_assignments", t)
        self.assertEqual(r.status_code, 403)

    # ---- availability ----
    def test_go_online_and_offline(self):
        t = self.token("r1@example.com")
        self.assertEqual(self.go_online(t).json()["profile"]["availability"], "ONLINE")
        r = self.call("post", "api:responder_availability", t, {"availability": "OFFLINE"})
        self.assertEqual(r.json()["profile"]["availability"], "OFFLINE")

    def test_bad_availability_rejected(self):
        t = self.token("r1@example.com")
        self.assertEqual(self.call("post", "api:responder_availability", t, {"availability": "BUSY"}).status_code, 400)

    def test_cannot_go_offline_with_active_assignment(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        self.offer(self.r1)
        r = self.call("post", "api:responder_availability", t, {"availability": "OFFLINE"})
        self.assertEqual(r.status_code, 409)

    # ---- location ----
    def test_location_saved_when_on_duty(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        r = self.call("post", "api:responder_location", t, {"latitude": 6.52, "longitude": 3.38, "accuracy": 8})
        self.assertEqual(r.status_code, 200, r.content)
        self.r1.refresh_from_db()
        self.assertEqual((self.r1.last_latitude, self.r1.last_longitude), (6.52, 3.38))
        self.assertIsNotNone(self.r1.last_location_at)
        self.assertEqual(ResponderLocation.objects.filter(responder=self.r1).count(), 1)

    def test_location_rejected_when_off_duty(self):
        t = self.token("r1@example.com")
        r = self.call("post", "api:responder_location", t, {"latitude": 6.5, "longitude": 3.4})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(ResponderLocation.objects.count(), 0)

    def test_location_validation(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        for bad in ({"latitude": 999, "longitude": 3}, {"latitude": "x", "longitude": 3}, {"longitude": 3}):
            self.assertEqual(self.call("post", "api:responder_location", t, bad).status_code, 400, bad)

    # ---- offers ----
    def test_offer_appears_without_caller_phone(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        self.offer(self.r1)
        data = self.call("get", "api:responder_assignments", t).json()
        self.assertEqual(len(data["current"]), 1)
        item = data["current"][0]
        self.assertEqual(item["status"], "OFFERED")
        self.assertEqual(item["incident"]["reporter_phone"], "")

    def test_offer_not_visible_to_other_responder(self):
        t1, t2 = self.token("r1@example.com"), self.token("r2@example.com")
        self.go_online(t1)
        a = self.offer(self.r1)
        self.assertEqual(self.call("get", "api:responder_assignments", t2).json()["current"], [])
        r = self.call("post", "api:responder_respond", t2, {"accept": True}, args=[a.pk])
        self.assertEqual(r.status_code, 404)

    def test_accept_assigns_incident_and_reveals_phone(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        a = self.offer(self.r1)
        r = self.call("post", "api:responder_respond", t, {"accept": True}, args=[a.pk])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["assignment"]["incident"]["reporter_phone"], "0800111")
        self.incident.refresh_from_db()
        self.r1.refresh_from_db()
        self.assertEqual(self.incident.status, Status.ASSIGNED)
        self.assertEqual(self.r1.availability, Availability.BUSY)

    def test_decline_returns_incident_to_reported(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        a = self.offer(self.r1)
        r = self.call("post", "api:responder_respond", t, {"accept": False}, args=[a.pk])
        self.assertEqual(r.status_code, 200)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Status.REPORTED)
        self.assertEqual(IncidentAssignment.objects.get().status, AssignmentStatus.DECLINED)

    def test_respond_requires_boolean(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        a = self.offer(self.r1)
        self.assertEqual(self.call("post", "api:responder_respond", t, {"accept": "yes"}, args=[a.pk]).status_code, 400)

    # ---- status progression ----
    def accepted(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        a = self.offer(self.r1)
        self.call("post", "api:responder_respond", t, {"accept": True}, args=[a.pk])
        return t, a

    def test_full_status_flow_releases_responder(self):
        t, a = self.accepted()
        for status in ("EN_ROUTE", "ON_SCENE", "RESOLVED"):
            r = self.call("post", "api:responder_status", t, {"status": status}, args=[a.pk])
            self.assertEqual(r.status_code, 200, (status, r.content))
        self.incident.refresh_from_db()
        self.r1.refresh_from_db()
        a.refresh_from_db()
        self.assertEqual(self.incident.status, Status.RESOLVED)
        self.assertEqual(self.r1.availability, Availability.ONLINE)
        self.assertEqual(a.status, AssignmentStatus.COMPLETED)
        history = self.call("get", "api:responder_assignments", t).json()["history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(self.incident.history.count(), 6)

    def test_skipping_a_step_is_rejected(self):
        t, a = self.accepted()
        r = self.call("post", "api:responder_status", t, {"status": "RESOLVED"}, args=[a.pk])
        self.assertEqual(r.status_code, 409)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Status.ASSIGNED)

    def test_cannot_update_status_before_accepting(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        a = self.offer(self.r1)
        r = self.call("post", "api:responder_status", t, {"status": "EN_ROUTE"}, args=[a.pk])
        self.assertEqual(r.status_code, 409)

    def test_other_responder_cannot_update_status(self):
        t, a = self.accepted()
        t2 = self.token("r2@example.com")
        self.assertEqual(self.call("post", "api:responder_status", t2, {"status": "EN_ROUTE"}, args=[a.pk]).status_code, 404)

    def test_distance_reported_when_both_have_locations(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        self.call("post", "api:responder_location", t, {"latitude": 6.5, "longitude": 3.5})
        self.offer(self.r1)
        item = self.call("get", "api:responder_assignments", t).json()["current"][0]
        self.assertIsNotNone(item["distance_km"])
        self.assertGreater(item["distance_km"], 5)

    def test_responder_notifications_endpoint(self):
        t = self.token("r1@example.com")
        self.go_online(t)
        self.offer(self.r1)
        data = self.call("get", "api:notifications", t).json()
        self.assertEqual(data["unread"], 1)
