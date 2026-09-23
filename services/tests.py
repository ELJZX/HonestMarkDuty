from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from services.models import Service


class ServiceModelTests(TestCase):
    def test_str(self):
        service = Service.objects.create(name="МДЛП", url="https://mdlp.example")
        self.assertEqual(str(service), "МДЛП")

    def test_ordering(self):
        Service.objects.create(name="Б", url="https://b.example", sort_order=1)
        Service.objects.create(name="А", url="https://a.example", sort_order=0)
        self.assertEqual(list(Service.objects.values_list("name", flat=True)), ["А", "Б"])


class ServiceViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="svc-admin", password="x", role=User.Role.ADMIN, is_superuser=True, is_staff=True
        )
        self.specialist = User.objects.create_user(
            username="svc-spec", password="x", role=User.Role.SPECIALIST
        )
        self.viewer = User.objects.create_user(
            username="svc-viewer", password="x", role=User.Role.VIEWER
        )
        self.service = Service.objects.create(name="МДЛП", url="https://mdlp.example")

    def test_list_requires_login(self):
        self.assertEqual(self.client.get(reverse("services:service_list")).status_code, 302)

    def test_list_renders_links_and_button(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("services:service_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сервисы Молвест.Маркировка")
        self.assertContains(response, "https://mdlp.example")
        self.assertContains(response, "Добавить сервис")

    def test_viewer_has_no_add_button(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("services:service_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("services:service_create"))

    def test_create_service(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("services:service_create"),
            {"name": "Честный знак", "url": "https://marking.example"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Service.objects.filter(name="Честный знак").exists())

    def test_viewer_cannot_create(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("services:service_create")).status_code, 403)

    def test_invalid_url_rejected(self):
        self.client.force_login(self.specialist)
        response = self.client.post(
            reverse("services:service_create"), {"name": "X", "url": "не ссылка"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Service.objects.filter(name="X").exists())

    def test_delete_admin_only(self):
        self.client.force_login(self.specialist)
        self.assertEqual(
            self.client.post(
                reverse("services:service_delete", args=[self.service.pk])
            ).status_code,
            403,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("services:service_delete", args=[self.service.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Service.objects.filter(pk=self.service.pk).exists())
