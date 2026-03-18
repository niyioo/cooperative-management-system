from rest_framework import serializers
from .models import SavingsAccount, SavingsTransaction
from apps.members.models import Member

class NestedMemberSerializer(serializers.ModelSerializer):
    """Provides the nested member data React expects: account.member.first_name"""
    class Meta:
        model = Member
        fields = ['id', 'first_name', 'last_name', 'membership_id']

class SavingsTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsTransaction
        fields = '__all__'
        # Removed 'account' from read_only so Admins can submit transactions for members
        read_only_fields = ['id', 'status', 'approved_by', 'reference', 'created_at', 'updated_at']

class SavingsAccountSerializer(serializers.ModelSerializer):
    # Use the nested serializer instead of just the ID
    member = NestedMemberSerializer(read_only=True)
    recent_transactions = serializers.SerializerMethodField()

    class Meta:
        model = SavingsAccount
        fields = ['id', 'member', 'account_number', 'balance', 'last_updated', 'recent_transactions']
        read_only_fields = ['id', 'member', 'account_number', 'balance', 'last_updated']

    def get_recent_transactions(self, obj):
        transactions = obj.transactions.all().order_by('-created_at')[:5]
        return SavingsTransactionSerializer(transactions, many=True).data