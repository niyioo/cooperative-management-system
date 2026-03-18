from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from apps.core.models import TimeStampedUUIDModel

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        # FIX: Replaced CustomUser.Role.SUPER_ADMIN with the string 'SUPER_ADMIN'
        # to prevent Python NameError since CustomUser isn't defined yet.
        extra_fields.setdefault('role', 'SUPER_ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin, TimeStampedUUIDModel):
    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
        MANAGER = 'MANAGER', 'Cooperative Manager'
        ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
        LOAN_OFFICER = 'LOAN_OFFICER', 'Loan Officer'
        MEMBER = 'MEMBER', 'Member'

    email = models.EmailField(unique=True)
    
    # ✅ ADDED: First and Last Name fields
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] # You can add ['first_name', 'last_name'] here if you want the CLI to prompt for them during createsuperuser

    def __str__(self):
        # Updated to show the name if it exists, otherwise fallback to email
        full_name = f"{self.first_name} {self.last_name}".strip()
        display_name = full_name if full_name else self.email
        return f"{display_name} - {self.role}"