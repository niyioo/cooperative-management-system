from rest_framework import serializers
from .models import ShareAccount, ShareTransaction
from apps.members.models import Member

class NestedMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'first_name', 'last_name', 'membership_id']

class ShareTransactionSerializer(serializers.ModelSerializer):
    # Staff choose the account; members always buy for themselves.
    account = serializers.PrimaryKeyRelatedField(queryset=ShareAccount.objects.all(), required=False)
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all(), required=False, write_only=True)
    number_of_shares = serializers.IntegerField(min_value=1)
    member_name = serializers.SerializerMethodField()

    def get_member_name(self, obj):
        member = obj.account.member
        return f"{member.first_name} {member.last_name} ({member.membership_id})"

    class Meta:
        model = ShareTransaction
        fields = '__all__'
        # The price always comes from Settings, never from the request.
        read_only_fields = ['id', 'price_per_share', 'total_amount', 'reference', 'status', 'approved_by',
                            'created_at', 'updated_at']

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