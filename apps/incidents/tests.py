from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Role
from apps.audit.models import AuditLog

from .models import Status
from .services import InvalidTransition, change_status, create_incident

User = get_user_model()


class StatusTransitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="d@example.com", password="x-12345-pw", role=Role.DISPATCHER)
        self.incident = create_incident(category="FIRE", address_text="Main St", created_by=self.user)

    def test_new_incident_has_history_and_audit(self):
        self.assertEqual(self.incident.status, Status.REPORTED)
        self.assertEqual(self.incident.history.count(), 1)
        self.assertTrue(AuditLog.objects.filter(action="incident.create").exists())

    def test_every_change_is_stored(self):
        change_status(self.incident.pk, Status.DISPATCH_PENDING, user=self.user)
        change_status(self.incident.pk, Status.ASSIGNED, user=self.user)
        self.assertEqual(self.incident.history.count(), 3)
        self.assertEqual(self.incident.history.last().to_status, Status.ASSIGNED)

    def test_invalid_transition_rejected_and_not_saved(self):
        with self.assertRaises(InvalidTransition):
            change_status(self.incident.pk, Status.RESOLVED, user=self.user)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.status, Status.REPORTED)
        self.assertEqual(self.incident.history.count(), 1)

    def test_terminal_status_sets_closed_at_and_blocks_further_changes(self):
        change_status(self.incident.pk, Status.CANCELLED, user=self.user)
        self.incident.refresh_from_db()
        self.assertIsNotNone(self.incident.closed_at)
        with self.assertRaises(InvalidTransition):
            change_status(self.incident.pk, Status.REPORTED, user=self.user)

    def test_incident_requires_location_or_address(self):
        with self.assertRaises(ValueError):
            create_incident(category="FIRE", created_by=self.user)
