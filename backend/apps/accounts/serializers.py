from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.members.models import Member

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['email'] = user.email
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Include user info in the login response
        data.update({
            'user': {
                'id': str(self.user.id),
                'email': self.user.email,
                'role': self.user.role
            }
        })
        return data

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'role', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

class RegisterUserSerializer(serializers.ModelSerializer):
    """
    Public sign-up. Always creates an ordinary MEMBER whose profile waits for a
    manager's approval; any `role` in the request is ignored. Staff accounts are
    created by an administrator.
    """
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True, max_length=100)
    last_name = serializers.CharField(write_only=True, max_length=100)
    phone_number = serializers.CharField(write_only=True, max_length=20)

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 'phone_number']

    def validate_phone_number(self, value):
        if Member.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return value

    def validate(self, attrs):
        candidate = User(email=attrs['email'], first_name=attrs['first_name'], last_name=attrs['last_name'])
        try:
            validate_password(attrs['password'], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'], password=validated_data['password'], role=User.Role.MEMBER,
            first_name=validated_data['first_name'], last_name=validated_data['last_name'],
        )
        # A member profile (and savings account) is created automatically for
        # every new user; fill it in rather than creating a second one.
        Member.objects.filter(user=user).update(
            first_name=validated_data['first_name'], last_name=validated_data['last_name'],
            phone_number=validated_data['phone_number'], status=Member.Status.INACTIVE,
        )
        return user