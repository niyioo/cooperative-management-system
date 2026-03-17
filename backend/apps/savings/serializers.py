from rest_framework import serializers
from .models import SavingsAccount, SavingsTransaction

class SavingsTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsTransaction
        fields = '__all__'
        read_only_fields = ['id', 'account', 'status', 'approved_by', 'reference', 'created_at', 'updated_at']

class SavingsAccountSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()

    class Meta:
        model = SavingsAccount
        fields = ['id', 'member', 'member_name', 'balance', 'last_updated', 'recent_transactions']
        read_only_fields = ['id', 'member', 'balance', 'last_updated']

    def get_member_name(self, obj):
        return f"{obj.member.first_name} {obj.member.last_name}"

    def get_recent_transactions(self, obj):
        transactions = obj.transactions.all().order_by('-created_at')[:5]
        return SavingsTransactionSerializer(transactions, many=True).data