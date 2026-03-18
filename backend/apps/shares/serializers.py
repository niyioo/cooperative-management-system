from rest_framework import serializers
from .models import ShareAccount, ShareTransaction
from apps.members.models import Member

class NestedMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'first_name', 'last_name', 'membership_id']

class ShareTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareTransaction
        fields = '__all__'
        # Allow 'account' to be written during POST
        read_only_fields = ['id', 'total_amount', 'reference', 'status', 'approved_by', 'created_at']

class ShareAccountSerializer(serializers.ModelSerializer):
    member = NestedMemberSerializer(read_only=True)
    recent_transactions = serializers.SerializerMethodField()

    class Meta:
        model = ShareAccount
        fields = ['id', 'member', 'total_shares', 'current_value', 'recent_transactions']
        read_only_fields = ['id', 'member', 'total_shares', 'current_value']

    def get_recent_transactions(self, obj):
        txns = obj.transactions.all().order_by('-created_at')[:5]
        return ShareTransactionSerializer(txns, many=True).data