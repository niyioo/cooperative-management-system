from rest_framework import serializers
from .models import ShareAccount, ShareTransaction

class ShareTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShareTransaction
        fields = '__all__'
        read_only_fields = ['id', 'total_amount', 'status', 'approved_by', 'created_at']

class ShareAccountSerializer(serializers.ModelSerializer):
    recent_transactions = serializers.SerializerMethodField()

    class Meta:
        model = ShareAccount
        fields = ['id', 'member', 'total_shares', 'total_value', 'recent_transactions']
        read_only_fields = ['id', 'member', 'total_shares', 'total_value']

    def get_recent_transactions(self, obj):
        txns = obj.transactions.all().order_by('-created_at')[:5]
        return ShareTransactionSerializer(txns, many=True).data