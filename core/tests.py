from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from config.version import get_version
from core.audit import get_current_user, serialize, set_current_user, snapshot
from core.context_processors import project_context
from core.models import AuditLog, ProductionSite, Workshop
from core.views import server_error


class VersionTests(TestCase):
    def test_version_matches_file(self):
        version_file = Path(settings.BASE_DIR) / "VERSION"
        self.assertEqual(get_version(), version_file.read_text(encoding="utf-8").strip())

    def test_version_format(self):
        self.assertRegex(get_version(), r"^\d+\.\d+\.\d+$")

    def test_context_processor_has_version_and_tagline(self):
        request = RequestFactory().get("/")
        context = project_context(request)
        self.assertEqual(context["APP_VERSION"], get_version())
        self.assertEqual(context["PROJECT_TAGLINE"], "Честное выполнение обязанностей")
        self.assertEqual(context["PROJECT_NAME"], "HonestMarkDuty")


class AuditHelpersTests(TestCase):
    def test_serialize_types(self):
        self.assertEqual(serialize(None), None)
        self.assertEqual(serialize(5), 5)
        self.assertEqual(serialize("x"), "x")
        self.assertEqual(serialize(1.5), 1.5)

    def test_current_user_roundtrip(self):
        self.assertIsNone(get_current_user())
        user = User.objects.create_user(username="u", password="x")
        set_current_user(user)
        self.assertEqual(get_current_user(), user)
        set_current_user(None)

    def test_snapshot_excludes_timestamps(self):
        workshop = Workshop.objects.create(name="Цех", code="Ц")
        data = snapshot(workshop)
        self.assertNotIn("created_at", data)
        self.assertNotIn("updated_at", data)
        self.assertIn("name", data)


class AuditLogModelTests(TestCase):
    def test_create_logged(self):
        Workshop.objects.create(name="Цех 1", code="C1")
        self.assertTrue(
            AuditLog.objects.filter(model_name="workshop", action=AuditLog.Action.CREATE).exists()
        )

    def test_update_logged_with_diff(self):
        workshop = Workshop.objects.create(name="Цех 1", code="C1")
        workshop.chief = "Иванов"
        workshop.save()
        log = AuditLog.objects.filter(action=AuditLog.Action.UPDATE).first()
        self.assertIn("chief", log.changes)
        self.assertEqual(log.changes["chief"]["to"], "Иванов")

    def test_delete_logged(self):
        workshop = Workshop.objects.create(name="Цех 1", code="C1")
        workshop.delete()
        self.assertTrue(
            AuditLog.objects.filter(model_name="workshop", action=AuditLog.Action.DELETE).exists()
        )

    def test_str(self):
        log = AuditLog.objects.create(model_name="workshop", action=AuditLog.Action.CREATE, object_id="1")
        self.assertIn("Создание", str(log))


class HomeAndAuditViewsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )

    def test_home_redirects_to_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("core:home"))
        self.assertRedirects(response, reverse("analytics:dashboard"))

    def test_audit_list_renders(self):
        Workshop.objects.create(name="Цех", code="Ц")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("core:audit_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Аудит")

    def test_audit_list_filter_by_action(self):
        Workshop.objects.create(name="Цех", code="Ц")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("core:audit_list"), {"action": "create"})
        self.assertEqual(response.status_code, 200)


class WorkshopAndSiteViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )
        self.site = ProductionSite.objects.create(name="Площадка")

    def test_workshop_list(self):
        self.client.force_login(self.specialist)
        self.assertEqual(self.client.get(reverse("core:workshop_list")).status_code, 200)

    def test_workshop_create_admin(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("core:workshop_create"), {"name": "Новый цех", "code": "НЦ", "is_active": "on"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Workshop.objects.filter(code="НЦ").exists())

    def test_workshop_create_forbidden_for_specialist(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("core:workshop_create"))
        self.assertEqual(response.status_code, 403)

    def test_workshop_update(self):
        workshop = Workshop.objects.create(name="Цех", code="Ц")
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("core:workshop_update", args=[workshop.pk]),
            {"name": "Цех обновлён", "code": "Ц", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        workshop.refresh_from_db()
        self.assertEqual(workshop.name, "Цех обновлён")

    def test_workshop_delete(self):
        workshop = Workshop.objects.create(name="Цех", code="Ц")
        self.client.force_login(self.admin)
        response = self.client.post(reverse("core:workshop_delete", args=[workshop.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Workshop.objects.filter(pk=workshop.pk).exists())

    def test_site_list_and_create(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("core:site_list")).status_code, 200)
        response = self.client.post(
            reverse("core:site_create"), {"name": "Новая площадка", "is_active": "on"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProductionSite.objects.filter(name="Новая площадка").exists())

    def test_site_update_and_delete(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("core:site_update", args=[self.site.pk]),
            {"name": "Обновлена", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.site.refresh_from_db()
        self.assertEqual(self.site.name, "Обновлена")
        response = self.client.post(reverse("core:site_delete", args=[self.site.pk]))
        self.assertEqual(response.status_code, 302)


class ErrorViewTests(TestCase):
    def test_404_page(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)

    def test_500_view(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
