from rest_framework import serializers
from .models import Contribution
from apps.members.models import Member

class NestedMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'first_name', 'last_name', 'membership_id']

class ContributionSerializer(serializers.ModelSerializer):
    # For reading (GET requests)
    member = NestedMemberSerializer(read_only=True)
    
    # For writing (POST requests from the React Modal)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=Member.objects.all(), source='member', write_only=True
    )

    class Meta:
        model = Contribution
        fields = [
            'id', 'member', 'member_id', 'type', 'amount', 
            'due_date', 'reference_id', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'reference_id', 'created_at']