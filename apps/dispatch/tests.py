from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.incidents.models import Status
from apps.incidents.services import change_status, create_incident
from apps.responders.models import Availability, ResponderProfile

from .models import AssignmentStatus, IncidentAssignment
from .services import AssignmentError, assign_responder, cancel_offer, respond_to_assignment

User = get_user_model()


def responder(email, availability=Availability.ONLINE):
    user = User.objects.create_user(email=email, password="x-12345-pw", role=Role.RESPONDER, first_name=email.split("@")[0])
    return ResponderProfile.objects.create(user=user, availability=availability)


class DispatchTests(TestCase):
    def setUp(self):
        self.dispatcher = User.objects.create_user(email="d@example.com", password="x-12345-pw", role=Role.DISPATCHER)
        self.incident = create_incident(category="MEDICAL", lat=6.0, lng=3.0, created_by=self.dispatcher)
        self.r1 = responder("r1@example.com")
        self.r2 = responder("r2@example.com")

    def test_offer_moves_incident_to_dispatch_pending(self):
        assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Status.DISPATCH_PENDING)

    def test_offline_responder_cannot_be_assigned(self):
        off = responder("off@example.com", Availability.OFFLINE)
        with self.assertRaises(AssignmentError):
            assign_responder(self.incident.pk, off.pk, self.dispatcher)

    def test_duplicate_offer_rejected(self):
        assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        with self.assertRaises(AssignmentError):
            assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        self.assertEqual(IncidentAssignment.objects.count(), 1)

    def test_responder_with_live_offer_cannot_take_another(self):
        other = create_incident(category="FIRE", address_text="Elsewhere", created_by=self.dispatcher)
        assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        with self.assertRaises(AssignmentError):
            assign_responder(other.pk, self.r1.pk, self.dispatcher)

    def test_accept_assigns_incident_and_marks_responder_busy(self):
        a = assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        respond_to_assignment(a.pk, self.r1.user, accept=True)
        self.incident.refresh_from_db()
        self.r1.refresh_from_db()
        self.assertEqual(self.incident.status, Status.ASSIGNED)
        self.assertEqual(self.r1.availability, Availability.BUSY)

    def test_other_responder_cannot_answer_an_offer(self):
        a = assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        with self.assertRaises(AssignmentError):
            respond_to_assignment(a.pk, self.r2.user, accept=True)

    def test_decline_reverts_incident_to_reported(self):
        a = assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        respond_to_assignment(a.pk, self.r1.user, accept=False)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Status.REPORTED)
        self.assertEqual(IncidentAssignment.objects.get().status, AssignmentStatus.DECLINED)

    def test_withdraw_offer_reverts_incident(self):
        a = assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        cancel_offer(a.pk, self.dispatcher)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Status.REPORTED)

    def test_resolving_releases_responder(self):
        a = assign_responder(self.incident.pk, self.r1.pk, self.dispatcher)
        respond_to_assignment(a.pk, self.r1.user, accept=True)
        change_status(self.incident.pk, Status.EN_ROUTE, user=self.dispatcher)
        change_status(self.incident.pk, Status.ON_SCENE, user=self.dispatcher)
        change_status(self.incident.pk, Status.RESOLVED, user=self.dispatcher)
        self.r1.refresh_from_db()
        a.refresh_from_db()
        self.assertEqual(self.r1.availability, Availability.ONLINE)
        self.assertEqual(a.status, AssignmentStatus.COMPLETED)
