import factory
from django.contrib.auth.models import Group
from factory.django import DjangoModelFactory

from apps.accounts.models import User
from apps.members.models import Member

DEFAULT_PASSWORD = "Correct-Horse-7"


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = "Test"
    last_name = factory.Sequence(lambda n: f"User{n}")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", DEFAULT_PASSWORD)
        return model_class.objects.create_user(*args, password=password, **kwargs)


class MemberFactory(DjangoModelFactory):
    class Meta:
        model = Member

    user = factory.SubFactory(UserFactory)
    first_name = factory.SelfAttribute("user.first_name")
    last_name = factory.SelfAttribute("user.last_name")
    phone = factory.Sequence(lambda n: f"0803{n:07d}")
    status = Member.Status.ACTIVE


def make_officer(*role_names, **user_kwargs):
    user = UserFactory(is_staff_officer=True, **user_kwargs)
    user.groups.set(Group.objects.filter(name__in=role_names))
    assert user.groups.count() == len(role_names), f"Unknown role in {role_names}"
    return user


def add_guarantors(actor, application, count=1):
    """Add `count` fresh active members as guarantors (before submission). Returns the members."""
    from apps.loans import services as loans

    members = [MemberFactory() for _ in range(count)]
    for member in members:
        loans.add_guarantor(actor, application, member.membership_number)
    return members


def accept_guarantees(application):
    """Every guarantor who has been asked accepts (after submission)."""
    from apps.loans import services as loans

    for guarantee in application.guarantors.filter(status="PENDING", requested_at__isnull=False).select_related("guarantor__user"):
        loans.respond_to_guarantee(guarantee.guarantor.user, guarantee, accept=True)
