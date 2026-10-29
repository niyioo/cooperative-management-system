import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, Group, PermissionsMixin
from django.db import models
from django.utils import timezone


# Members without an email address get a unique placeholder on this reserved
# domain (RFC 2606: .invalid can never receive mail). They sign in with their
# membership number and an officer-issued temporary password.
PLACEHOLDER_EMAIL_DOMAIN = "no-email.invalid"


def placeholder_email(membership_number):
    local = "".join(c if c.isalnum() else "-" for c in membership_number.lower()).strip("-")
    return f"{local}@{PLACEHOLDER_EMAIL_DOMAIN}"


def is_placeholder_email(email):
    return (email or "").lower().endswith("@" + PLACEHOLDER_EMAIL_DOMAIN)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_staff_officer", True)
        if extra_fields["is_staff"] is not True or extra_fields["is_superuser"] is not True:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)


class User(AbstractBaseUser, PermissionsMixin):
    """
    A login. Officer powers come from roles (groups); the member profile, if
    any, is `user.member`. One person can be both an officer and a member.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(
        default=True, help_text="Inactive users cannot log in (e.g. after account closure)."
    )
    is_staff_officer = models.BooleanField(
        default=False, help_text="May use the officer portal. Requires at least one role."
    )
    is_staff = models.BooleanField(
        default=False, help_text="May open the Django support console (Super Administrator only)."
    )
    must_change_password = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(null=True, blank=True)

    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        default_permissions = ()
        permissions = [
            ("manage_officers", "Manage officer accounts"),
            ("manage_roles", "Manage roles and their permissions"),
        ]
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>" if self.full_name else self.email

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.last_password_change = timezone.now()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name

    @property
    def has_member_profile(self):
        return hasattr(self, "member")

    @property
    def has_real_email(self):
        return not is_placeholder_email(self.email)


class RoleProfile(models.Model):
    """Officer-facing metadata for a role (a Django auth Group)."""

    group = models.OneToOneField(
        Group, on_delete=models.CASCADE, primary_key=True, related_name="profile"
    )
    description = models.TextField(blank=True)
    is_system = models.BooleanField(
        default=False, help_text="Seeded role. Its permissions may be edited, but it cannot be deleted."
    )

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"Profile of {self.group.name}"


class Role(Group):
    """Officer role. Stored as an auth Group so Django's permission checks apply."""

    class Meta:
        proxy = True
        default_permissions = ()
        verbose_name = "role"
        verbose_name_plural = "roles"
