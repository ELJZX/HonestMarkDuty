from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from accounts.models import User


class UserModelTests(TestCase):
    def test_full_name_falls_back_to_username(self):
        user = User.objects.create_user(username="admin", password="x")
        self.assertEqual(user.full_name, "admin")

    def test_full_name_with_parts(self):
        user = User.objects.create_user(
            username="ivanov",
            password="x",
            last_name="Иванов",
            first_name="Иван",
            patronymic="Иванович",
        )
        self.assertEqual(user.full_name, "Иванов Иван Иванович")

    def test_role_flags(self):
        admin = User.objects.create_user(username="a", password="x", role=User.Role.ADMIN)
        specialist = User.objects.create_user(username="s", password="x", role=User.Role.SPECIALIST)
        viewer = User.objects.create_user(username="v", password="x", role=User.Role.VIEWER)
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin.can_edit)
        self.assertFalse(admin.is_specialist)
        self.assertTrue(specialist.is_specialist)
        self.assertTrue(specialist.can_edit)
        self.assertFalse(viewer.is_admin)
        self.assertFalse(viewer.can_edit)

    def test_str_and_ordering(self):
        User.objects.create_user(username="zzz", password="x")
        User.objects.create_user(username="aaa", password="x")
        self.assertEqual(str(User.objects.first()), "aaa")


class AuthViewTests(TestCase):
    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)

    def test_login_success_redirects(self):
        User.objects.create_user(username="u", password="pass12345")
        response = self.client.post(
            reverse("accounts:login"), {"username": "u", "password": "pass12345"}
        )
        self.assertEqual(response.status_code, 302)

    def test_login_failure_shows_errors(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "nope", "password": "bad"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")

    def test_logout(self):
        user = User.objects.create_user(username="u", password="pass12345")
        self.client.force_login(user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)

    def test_profile_route_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("accounts:profile")


class UserAdminViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="x",
            role=User.Role.ADMIN,
            is_superuser=True,
            is_staff=True,
        )
        self.specialist = User.objects.create_user(
            username="spec", password="x", role=User.Role.SPECIALIST
        )

    def test_list_requires_login(self):
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 302)

    def test_list_renders_for_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin")

    def test_list_forbidden_for_specialist(self):
        self.client.force_login(self.specialist)
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 403)

    def test_create_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "newuser",
                "password1": "ComplexPass123",
                "password2": "ComplexPass123",
                "role": User.Role.SPECIALIST,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_update_user(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("accounts:user_update", args=[self.specialist.pk]),
            {
                "username": "spec",
                "role": User.Role.SPECIALIST,
                "position": "Ведущий специалист",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.specialist.refresh_from_db()
        self.assertEqual(self.specialist.position, "Ведущий специалист")
