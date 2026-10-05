from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


def find_user_by_identifier(identifier):
    """Resolve an email address or a membership number to a user, or None."""
    User = get_user_model()
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    if "@" in identifier:
        return User.objects.filter(email__iexact=identifier).first()

    from apps.members.models import Member

    member = Member.objects.select_related("user").filter(membership_number__iexact=identifier).first()
    return member.user if member else None


class EmailOrMembershipNumberBackend(ModelBackend):
    """Authenticate with an email address or membership number plus password."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get("identifier")
        if not identifier or password is None:
            return None
        user = find_user_by_identifier(identifier)
        if user is None:
            # Run the hasher anyway so response time doesn't reveal whether the account exists.
            get_user_model()().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
