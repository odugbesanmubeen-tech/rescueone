from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.analytics.services import dashboard_stats
from apps.incidents.models import Incident
from apps.incidents.services import create_incident
from apps.responders.models import Availability, ResponderProfile

User = get_user_model()


def make_user(email, role, **kw):
    return User.objects.create_user(email=email, password="pw-12345-x", role=role, first_name=email.split("@")[0], **kw)


class AccessControlTests(TestCase):
    def setUp(self):
        self.citizen = make_user("cit@example.com", Role.CITIZEN)
        self.responder = make_user("res@example.com", Role.RESPONDER)
        self.dispatcher = make_user("dis@example.com", Role.DISPATCHER)
        self.admin = make_user("adm@example.com", Role.ADMIN)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_citizen_and_responder_are_forbidden(self):
        for user in (self.citizen, self.responder):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("dashboard:overview")).status_code, 403)
            self.assertEqual(self.client.get(reverse("dashboard:incident_list")).status_code, 403)

    def test_dispatcher_can_view_but_not_admin_pages(self):
        self.client.force_login(self.dispatcher)
        self.assertEqual(self.client.get(reverse("dashboard:overview")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:audit_log")).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:responder_create")).status_code, 403)

    def test_admin_can_view_admin_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:audit_log")).status_code, 200)
        self.assertEqual(self.client.get(reverse("dashboard:responder_create")).status_code, 200)

    def test_citizen_cannot_sign_in_to_dashboard(self):
        r = self.client.post(reverse("accounts:login"), {"username": "cit@example.com", "password": "pw-12345-x"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class DashboardDataTests(TestCase):
    def setUp(self):
        self.dispatcher = make_user("dis@example.com", Role.DISPATCHER)
        self.client.force_login(self.dispatcher)

    def test_empty_database_shows_zeros(self):
        stats = dashboard_stats()
        self.assertEqual(stats["total_incidents"], 0)
        self.assertEqual(stats["available_responders"], 0)

    def test_stats_reflect_database_records(self):
        create_incident(category="FIRE", address_text="1 Test Street", created_by=self.dispatcher)
        create_incident(category="MEDICAL", lat=1.5, lng=2.5, created_by=self.dispatcher)
        rp = ResponderProfile.objects.create(user=make_user("r@example.com", Role.RESPONDER), availability=Availability.ONLINE)
        stats = dashboard_stats()
        self.assertEqual(stats["total_incidents"], 2)
        self.assertEqual(stats["pending_incidents"], 2)
        self.assertEqual(stats["available_responders"], 1)
        data = self.client.get(reverse("dashboard:stats_api")).json()
        self.assertEqual(data["total_incidents"], 2)
        self.assertTrue(rp.pk)

    def test_log_incident_form_saves_to_database(self):
        r = self.client.post(
            reverse("dashboard:incident_create"),
            {"category": "FIRE", "description": "Smoke", "address_text": "Market Road", "reporter_name": "Caller"},
        )
        self.assertEqual(r.status_code, 302)
        incident = Incident.objects.get()
        self.assertEqual(incident.address_text, "Market Road")
        self.assertEqual(incident.history.count(), 1)

    def test_log_incident_requires_location_or_address(self):
        r = self.client.post(reverse("dashboard:incident_create"), {"category": "FIRE"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Incident.objects.count(), 0)
