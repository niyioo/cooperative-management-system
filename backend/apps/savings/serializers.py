from decimal import Decimal

from rest_framework import serializers
from .models import SavingsAccount, SavingsTransaction
from apps.members.models import Member

class NestedMemberSerializer(serializers.ModelSerializer):
    """Provides the nested member data React expects: account.member.first_name"""
    class Meta:
        model = Member
        fields = ['id', 'first_name', 'last_name', 'membership_id']

class SavingsTransactionSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    # Staff choose the account; for members the view always uses their own.
    account = serializers.PrimaryKeyRelatedField(queryset=SavingsAccount.objects.all(), required=False)
    member_name = serializers.SerializerMethodField()

    def get_member_name(self, obj):
        member = obj.account.member
        return f"{member.first_name} {member.last_name} ({member.membership_id})"

    class Meta:
        model = SavingsTransaction
        fields = '__all__'
        read_only_fields = ['id', 'status', 'approved_by', 'reference', 'rejection_reason', 'created_at', 'updated_at']

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