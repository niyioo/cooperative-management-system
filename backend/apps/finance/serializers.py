from rest_framework import serializers
from .models import LedgerEntry
from apps.members.models import Member

class NestedMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        # Note: If first_name and last_name are only on the User model now, 
        # you may need to adjust these fields depending on where else you use this.
        fields = ['id', 'membership_id'] 

class LedgerEntrySerializer(serializers.ModelSerializer):
    # ✅ Added these two fields so the React frontend table populates correctly
    member_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.CharField(source='recorded_by.email', read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'reference_id', 'type', 'category', 'amount', 
            'date', 'description', 'member', 'member_name', 
            'recorded_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'reference_id', 'recorded_by', 'created_at']

    def get_member_name(self, obj):
        if obj.member:
            # Safely grab the first and last name from the connected CustomUser model
            user = getattr(obj.member, 'user', None)
            if user:
                full_name = f"{user.first_name} {user.last_name}".strip()
                return full_name if full_name else user.email
            return f"Member ID: {obj.member.id}"
            
        # Fallback for transactions not tied to a specific person (e.g., Office Expenses)
        return "Cooperative (Global)"