from decimal import Decimal

from rest_framework import serializers

from apps.members.models import Member
from apps.savings.serializers import MemberBriefSerializer

from .models import InvestmentAccount, InvestmentProduct, InvestmentReturn

MONEY = {"max_digits": 15, "decimal_places": 2}
POSITIVE = {"min_value": Decimal("0.01"), **MONEY}


class InvestmentProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentProduct
        fields = ["id", "name", "code", "description", "min_amount", "lock_in_months",
                  "dividend_eligible", "allow_officer_liquidation", "is_active"]
        extra_kwargs = {"name": {"validators": []}, "code": {"validators": []}}


class InvestmentAccountSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    principal = serializers.DecimalField(source="balance", read_only=True, **MONEY)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = InvestmentAccount
        fields = ["id", "account_number", "member", "product", "product_name", "principal",
                  "status", "status_label", "opened_on", "closed_on"]


class InvestmentAccountCreateSerializer(serializers.Serializer):
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=InvestmentProduct.objects.all())


class InvestmentContributionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**POSITIVE)
    value_date = serializers.DateField(required=False)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    external_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class LiquidationSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**POSITIVE)
    reason = serializers.CharField(max_length=255)
    value_date = serializers.DateField(required=False)


class InvestmentReturnSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    recorded_by = serializers.CharField(source="recorded_by.full_name", read_only=True)

    class Meta:
        model = InvestmentReturn
        fields = ["id", "product", "product_name", "financial_year", "amount_earned", "description", "recorded_by", "created_at"]
        read_only_fields = ["id", "recorded_by", "created_at"]
