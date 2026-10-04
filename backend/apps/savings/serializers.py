from decimal import Decimal

from rest_framework import serializers

from apps.common.serializers import PeriodField
from apps.members.models import Member

from .models import SavingsAccount, SavingsCycle, SavingsProduct

MONEY = {"max_digits": 15, "decimal_places": 2}


class SavingsProductSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = SavingsProduct
        fields = [
            "id",
            "name",
            "code",
            "description",
            "kind",
            "kind_label",
            "cycle_start_month",
            "cycle_end_month",
            "payout_month",
            "expected_monthly_contribution",
            "min_contribution",
            "max_monthly_contribution",
            "allow_contribution_outside_window",
            "allow_multiple_contributions_per_period",
            "min_membership_months",
            "is_mandatory",
            "allow_officer_withdrawal",
            "allow_member_withdrawal_request",
            "counts_toward_loan_eligibility",
            "is_active",
            "display_order",
        ]
        # Uniqueness is checked case-insensitively in the service layer.
        extra_kwargs = {"name": {"validators": []}, "code": {"validators": []}}


class SavingsCycleSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="__str__", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    account_count = serializers.IntegerField(read_only=True)
    total_saved = serializers.DecimalField(read_only=True, **MONEY)

    class Meta:
        model = SavingsCycle
        fields = [
            "id",
            "name",
            "product",
            "product_name",
            "year",
            "start_date",
            "end_date",
            "expected_monthly_contribution",
            "status",
            "status_label",
            "account_count",
            "total_saved",
            "opened_at",
            "closed_at",
        ]


class SavingsCycleCreateSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=SavingsProduct.objects.all())
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    expected_monthly_contribution = serializers.DecimalField(required=False, min_value=0, **MONEY)


class SavingsCycleUpdateSerializer(serializers.Serializer):
    expected_monthly_contribution = serializers.DecimalField(min_value=0, **MONEY)


class PayoutSerializer(serializers.Serializer):
    value_date = serializers.DateField(required=False)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class MemberBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Member
        fields = ["id", "membership_number", "full_name", "status"]


class SavingsAccountSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_kind = serializers.CharField(source="product.kind", read_only=True)
    cycle_name = serializers.SerializerMethodField()
    balance = serializers.DecimalField(read_only=True, **MONEY)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SavingsAccount
        fields = [
            "id",
            "account_number",
            "member",
            "product",
            "product_name",
            "product_kind",
            "cycle",
            "cycle_name",
            "elected_monthly_amount",
            "balance",
            "status",
            "status_label",
            "opened_on",
            "closed_on",
        ]

    def get_cycle_name(self, obj) -> str | None:
        return str(obj.cycle) if obj.cycle_id else None


class SavingsAccountCreateSerializer(serializers.Serializer):
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=SavingsProduct.objects.all())
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100, help_text="Cycle year, for cycle products.")
    elected_monthly_amount = serializers.DecimalField(required=False, allow_null=True, min_value=0, **MONEY)


class SavingsAccountUpdateSerializer(serializers.Serializer):
    elected_monthly_amount = serializers.DecimalField(required=False, allow_null=True, min_value=0, **MONEY)
    status = serializers.ChoiceField(choices=[SavingsAccount.Status.ACTIVE, SavingsAccount.Status.FROZEN], required=False)


class ContributionSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=SavingsAccount.objects.select_related("member", "product", "cycle"))
    amount = serializers.DecimalField(min_value=Decimal("0.01"), **MONEY)
    period = PeriodField(required=False, allow_null=True, help_text='Month the contribution counts for, e.g. "2026-03".')
    value_date = serializers.DateField(required=False)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    external_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class WithdrawalSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=SavingsAccount.objects.select_related("member", "product"))
    amount = serializers.DecimalField(min_value=Decimal("0.01"), **MONEY)
    reason = serializers.CharField(max_length=255)
    value_date = serializers.DateField(required=False)


class MonthlyContributionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(min_value=Decimal("0.01"), **MONEY)
    effective_from = PeriodField(
        required=False, allow_null=True, help_text='First month the amount applies to, e.g. "2026-11". Defaults to this month.'
    )
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class MyMonthlyContributionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(min_value=Decimal("0.01"), help_text="Applies from next month.", **MONEY)


class DeductionScheduleQuerySerializer(serializers.Serializer):
    period = PeriodField(required=False, allow_null=True, help_text='Payroll month, e.g. "2026-10". Defaults to this month.')
    include_arrears = serializers.BooleanField(required=False, default=True)
