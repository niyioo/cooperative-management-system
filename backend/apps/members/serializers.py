from rest_framework import serializers
from .models import Member, NextOfKin, MemberDocument

class NextOfKinSerializer(serializers.ModelSerializer):
    class Meta:
        model = NextOfKin
        fields = '__all__'
        read_only_fields = ['id', 'member', 'created_at', 'updated_at']

class MemberDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberDocument
        fields = '__all__'
        read_only_fields = ['id', 'member', 'is_verified', 'uploaded_at', 'created_at', 'updated_at']

class MemberSerializer(serializers.ModelSerializer):
    next_of_kin = NextOfKinSerializer(read_only=True)
    documents = MemberDocumentSerializer(many=True, read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Member
        fields = [
            'id', 'user', 'email', 'membership_id', 'first_name', 'last_name', 
            'phone_number', 'date_of_birth', 'residential_address', 'passport_photo', 
            'status', 'next_of_kin', 'documents', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'membership_id', 'status', 'approved_by', 'created_at']