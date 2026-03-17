from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedUUIDModel

class Member(TimeStampedUUIDModel):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='member_profile')
    membership_id = models.CharField(max_length=50, unique=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    residential_address = models.TextField()
    passport_photo = models.ImageField(upload_to='passports/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INACTIVE)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_members')

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.membership_id})"

    def save(self, *args, **kwargs):
        if not self.membership_id:
            # Generate a simple unique membership ID (In production, use a robust sequence generator)
            last_member = Member.objects.order_by('-created_at').first()
            if last_member and last_member.membership_id:
                last_id = int(last_member.membership_id.split('-')[-1])
                self.membership_id = f"COOP-{self.created_at.year if self.created_at else '0000'}-{last_id + 1:04d}"
            else:
                self.membership_id = "COOP-2024-0001"
        super().save(*args, **kwargs)

class NextOfKin(TimeStampedUUIDModel):
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name='next_of_kin')
    full_name = models.CharField(max_length=200)
    relationship = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField()

    def __str__(self):
        return f"{self.full_name} - NOK to {self.member.first_name}"

class MemberDocument(TimeStampedUUIDModel):
    class DocumentType(models.TextChoices):
        ID_CARD = 'ID_CARD', 'National ID / Passport'
        UTILITY_BILL = 'UTILITY_BILL', 'Utility Bill'
        SIGNATURE = 'SIGNATURE', 'Signature Specimen'

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    file = models.FileField(upload_to='member_documents/')
    is_verified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.member.membership_id}"