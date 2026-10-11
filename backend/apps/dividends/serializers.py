from decimal import Decimal

from rest_framework import serializers

from apps.investments.models import InvestmentProduct
from apps.savings.models import SavingsProduct
from apps.savings.serializers import MemberBriefSerializer

from .models import DividendCalculationRun, DividendCycle, MemberDividend

MONEY = {"max_digits": 15, "decimal_places": 2}
RATE = {"max_digits": 7, "decimal_places": 4, "min_value": Decimal("0")}


class RunSerializer(serializers.ModelSerializer):
    run_by = serializers.CharField(source="run_by.full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DividendCalculationRun
        fields = ["id", "run_number", "status", "status_label", "run_by", "created_at", "parameters",
                  "member_count", "total_basis", "total_gross", "total_withholding", "total_net"]


class DividendCycleSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    basis_label = serializers.CharField(source="get_basis_display", read_only=True)
    eligible_investment_products = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    eligible_savings_products = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    latest_run = serializers.SerializerMethodField()
    approved_by = serializers.CharField(source="approved_by.full_name", default=None, read_only=True)

    class Meta:
        model = DividendCycle
        fields = [
            "id", "reference", "financial_year", "status", "status_label", "basis", "basis_label", "cutoff_date",
            "rate", "distributable_surplus", "withholding_rate", "payment_method", "credit_savings_product",
            "eligible_investment_products", "eligible_savings_products", "notes", "latest_run",
            "approved_by", "approved_at", "published_at", "paid_at", "created_at",
        ]

    def get_latest_run(self, obj) -> dict | None:
        run = obj.approved_run or obj.runs.order_by("-run_number").first()
        return RunSerializer(run).data if run else None


class DividendCycleWriteSerializer(serializers.Serializer):
    financial_year = serializers.IntegerField(min_value=2000, max_value=2100)
    rate = serializers.DecimalField(**RATE)
    basis = serializers.ChoiceField(choices=DividendCycle.Basis.choices, required=False)
    cutoff_date = serializers.DateField(required=False)
    eligible_investment_products = serializers.PrimaryKeyRelatedField(queryset=InvestmentProduct.objects.all(), many=True, required=False)
    eligible_savings_products = serializers.PrimaryKeyRelatedField(queryset=SavingsProduct.objects.all(), many=True, required=False)
    distributable_surplus = serializers.DecimalField(required=False, allow_null=True, min_value=Decimal("0"), **MONEY)
    withholding_rate = serializers.DecimalField(required=False, max_value=Decimal("100"), **RATE)
    payment_method = serializers.ChoiceField(choices=DividendCycle.PaymentMethod.choices, required=False)
    credit_savings_product = serializers.PrimaryKeyRelatedField(queryset=SavingsProduct.objects.all(), required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class MemberDividendSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    payment_reference = serializers.CharField(source="payment_transaction.reference", default=None, read_only=True)

    class Meta:
        model = MemberDividend
        fields = ["id", "member", "basis_amount", "rate", "gross_amount", "withholding_amount", "net_amount",
                  "status", "status_label", "calculation_detail", "payment_reference", "paid_at"]


class PaySerializer(serializers.Serializer):
    value_date = serializers.DateField(required=False)
