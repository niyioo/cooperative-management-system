from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import CustomUser
from apps.core.testing import PASSWORD, APITestBase
from apps.members.models import Member


class UserManagersTests(TestCase):
    def test_create_user(self):
        User = get_user_model()
        user = User.objects.create_user(email='test@coop.com', password='foo')
        self.assertEqual(user.email, 'test@coop.com')
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        User = get_user_model()
        admin_user = User.objects.create_superuser(email='super@coop.com', password='foo')
        self.assertEqual(admin_user.email, 'super@coop.com')
        self.assertTrue(admin_user.is_active)
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.role, 'SUPER_ADMIN')


class RegistrationTests(APITestBase):
    def register(self, **extra):
        return self.client.post("/api/v1/auth/register/", {
            "email": "newcomer@example.com", "password": PASSWORD,
            "first_name": "Ada", "last_name": "Obi", "phone_number": "08030000001", **extra,
        }, format="json")

    def test_public_registration_creates_a_member(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        user = CustomUser.objects.get(email="newcomer@example.com")
        self.assertEqual(user.role, CustomUser.Role.MEMBER)
        self.assertEqual(Member.objects.get(user=user).first_name, "Ada")

    def test_nobody_can_register_themselves_as_staff(self):
        self.register(role="SUPER_ADMIN")
        self.assertEqual(CustomUser.objects.get(email="newcomer@example.com").role, CustomUser.Role.MEMBER)

    def test_new_members_wait_for_approval(self):
        self.register()
        self.assertEqual(Member.objects.get(user__email="newcomer@example.com").status, Member.Status.INACTIVE)


class SessionTests(APITestBase):
    def login(self, user, password=PASSWORD):
        return self.client.post("/api/v1/auth/login/", {"email": user.email, "password": password}, format="json")

    def test_login_sets_an_httponly_refresh_cookie_and_returns_access(self):
        response = self.login(self.member)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        self.assertTrue(response.cookies["coop_refresh"]["httponly"])

    def test_refresh_uses_the_cookie_and_logout_revokes_it(self):
        self.login(self.member)
        self.assertEqual(self.client.post("/api/v1/auth/login/refresh/", {}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout/", {}, format="json").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/login/refresh/", {}, format="json").status_code, 401)

    def test_wrong_password_is_refused(self):
        self.assertEqual(self.login(self.member, "wrong-password").status_code, 401)


class RoutingTests(APITestBase):
    def test_settings_and_notifications_are_routed(self):
        self.as_user(self.member)
        self.assertEqual(self.client.get("/api/v1/core/settings/").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/core/notifications/unread_count/").status_code, 200)

    def test_only_managers_change_settings(self):
        self.as_user(self.member)
        self.assertEqual(self.client.post("/api/v1/core/settings/", {"cooperative_name": "Mine"}, format="json").status_code, 403)
