from django.test import TestCase

from accounts.models import User
from core.models import AuditLog


class AuditTests(TestCase):
    def test_update_is_recorded_with_diff(self):
        workshop = AuditLog.objects.count()
        from core.models import Workshop

        obj = Workshop.objects.create(name="Цех 1", code="C1")
        self.assertEqual(AuditLog.objects.count(), workshop + 1)
        obj.chief = "Иванов"
        obj.save()
        log = AuditLog.objects.filter(model_name="workshop", action=AuditLog.Action.UPDATE).first()
        self.assertIsNotNone(log)
        self.assertIn("chief", log.changes)
        self.assertEqual(log.changes["chief"]["to"], "Иванов")


class RoleTests(TestCase):
    def test_admin_flag(self):
        admin = User.objects.create_user(username="a", password="x", role=User.Role.ADMIN)
        viewer = User.objects.create_user(username="v", password="x", role=User.Role.VIEWER)
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin.can_edit)
        self.assertFalse(viewer.can_edit)
