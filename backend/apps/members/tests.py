from apps.core.testing import PASSWORD, APITestBase
from apps.members.models import Member


class MemberTests(APITestBase):
    url = "/api/v1/members/profiles/"

    def register(self, by=None, password=PASSWORD):
        if by:
            self.as_user(by)
        return self.client.post(self.url, {
            "email": "walkin@example.com", "password": password, "first_name": "Bisi", "last_name": "Ade",
            "phone_number": "08030000099", "residential_address": "12 Allen Avenue, Ikeja",
        }, format="json")

    def test_only_managers_register_members_here(self):
        self.assertIn(self.register().status_code, (401, 403))
        self.assertEqual(self.register(by=self.member).status_code, 403)
        response = self.register(by=self.manager)
        self.assertEqual(response.status_code, 201, response.data)
        member = Member.objects.get(user__email="walkin@example.com")
        self.assertEqual((member.status, member.approved_by), (Member.Status.ACTIVE, self.manager))

    def test_weak_passwords_are_refused(self):
        self.assertEqual(self.register(by=self.manager, password="12345678").status_code, 400)

    def test_staff_screens_can_list_members(self):
        for user in (self.accountant, self.officer, self.manager):
            self.as_user(user)
            self.assertEqual(self.client.get(self.url).status_code, 200, user.role)
        self.as_user(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_members_are_never_deleted(self):
        self.as_user(self.admin)
        response = self.client.delete(f"{self.url}{self.member.member_profile.pk}/")
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Member.objects.filter(pk=self.member.member_profile.pk).exists())
