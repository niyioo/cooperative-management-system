from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.common.serializers import PeriodField, money_to_str
from apps.members.models import Member
from apps.savings.serializers import MemberBriefSerializer

from .calculators import schedule_for_product
from .models import Loan, LoanApplication, LoanApplicationDocument, LoanGuarantor, LoanProduct, LoanRepayment

MONEY = {"max_digits": 15, "decimal_places": 2}
POSITIVE = {"min_value": Decimal("0.01"), **MONEY}


class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = [
            "id",
            "name",
            "code",
            "description",
            "interest_rate",
            "interest_rate_basis",
            "interest_method",
            "interest_collection",
            "min_amount",
            "max_amount",
            "max_savings_multiple",
            "min_term_months",
            "max_term_months",
            "allowed_terms",
            "min_membership_months",
            "max_active_loans",
            "guarantors_required",
            "required_documents",
            "allow_topup",
            "is_active",
        ]
        extra_kwargs = {"name": {"validators": []}, "code": {"validators": []}}


def schedule_preview(product, amount, term_months, disbursed_on=None):
    """A quote: what the loan would cost and the monthly repayment."""
    schedule = schedule_for_product(product, amount, term_months, disbursed_on or timezone.localdate())
    return money_to_str(
        {
            "principal": Decimal(amount).quantize(Decimal("0.01")),
            "total_interest": schedule.total_interest,
            "total_payable": schedule.total_payable,
            "monthly_payment": schedule.monthly_payment,
            "interest_deducted_upfront": product.interest_collection == "UPFRONT",
            "first_due_date": schedule.first_due_date,
            "maturity_date": schedule.maturity_date,
            "instalments": [
                {"number": i.number, "due_date": i.due_date, "principal": i.principal, "interest": i.interest, "total": i.total}
                for i in schedule.instalments
            ],
        }
    )


class QuoteQuerySerializer(serializers.Serializer):
    amount = serializers.DecimalField(**POSITIVE)
    term_months = serializers.IntegerField(min_value=1, max_value=600)


class EligibilityQuerySerializer(serializers.Serializer):
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=LoanProduct.objects.all())
    amount = serializers.DecimalField(required=False, **POSITIVE)
    term_months = serializers.IntegerField(required=False, min_value=1)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

class ApplicationDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source="uploaded_by.full_name", default=None, read_only=True)

    class Meta:
        model = LoanApplicationDocument
        fields = ["id", "title", "uploaded_by", "created_at"]


class GuarantorSerializer(serializers.ModelSerializer):
    guarantor = MemberBriefSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = LoanGuarantor
        fields = ["id", "guarantor", "amount_guaranteed", "status", "status_label", "requested_at", "responded_at", "decline_reason"]


class LoanApplicationListSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = LoanApplication
        fields = [
            "id",
            "reference",
            "member",
            "product",
            "product_name",
            "amount_requested",
            "term_months",
            "approved_amount",
            "approved_term_months",
            "status",
            "status_label",
            "submitted_at",
            "created_at",
        ]


class LoanApplicationDetailSerializer(LoanApplicationListSerializer):
    reviewed_by = serializers.CharField(source="reviewed_by.full_name", default=None, read_only=True)
    decided_by = serializers.CharField(source="decided_by.full_name", default=None, read_only=True)
    documents = ApplicationDocumentSerializer(many=True, read_only=True)
    guarantors = GuarantorSerializer(many=True, read_only=True)
    loan = serializers.SerializerMethodField()
    quote = serializers.SerializerMethodField()

    class Meta(LoanApplicationListSerializer.Meta):
        fields = LoanApplicationListSerializer.Meta.fields + [
            "purpose",
            "eligibility_snapshot",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "info_request_message",
            "decided_by",
            "decided_at",
            "decision_reason",
            "cancelled_at",
            "documents",
            "guarantors",
            "loan",
            "quote",
        ]

    def get_loan(self, obj) -> dict | None:
        loan = obj.loans.exclude(status=Loan.Status.CANCELLED).first()
        return {"id": str(loan.pk), "reference": loan.reference, "status": loan.status} if loan else None

    def get_quote(self, obj) -> dict:
        amount = obj.approved_amount or obj.amount_requested
        term = obj.approved_term_months or obj.term_months
        return schedule_preview(obj.product, amount, term)


class ApplicationOnBehalfSerializer(serializers.Serializer):
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    product = serializers.PrimaryKeyRelatedField(queryset=LoanProduct.objects.all())
    amount_requested = serializers.DecimalField(**POSITIVE)
    term_months = serializers.IntegerField(min_value=1)
    purpose = serializers.CharField(max_length=2000)
    guarantors = serializers.ListField(
        child=serializers.CharField(max_length=30), allow_empty=False,
        help_text="Guarantors' membership numbers. They are notified, in the portal and by e-mail, to accept or decline.",
    )


class ReviewSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ReturnSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)


class ApproveSerializer(serializers.Serializer):
    approved_amount = serializers.DecimalField(required=False, **POSITIVE)
    approved_term_months = serializers.IntegerField(required=False, min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)


class DisburseSerializer(serializers.Serializer):
    disbursed_on = serializers.DateField(required=False)
    external_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------

class LoanSerializer(serializers.ModelSerializer):
    member = MemberBriefSerializer(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    outstanding = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            "id",
            "reference",
            "member",
            "product",
            "product_name",
            "principal",
            "total_interest",
            "outstanding",
            "interest_rate",
            "interest_rate_basis",
            "interest_method",
            "interest_collection",
            "term_months",
            "disbursed_on",
            "first_due_date",
            "maturity_date",
            "status",
            "status_label",
            "completed_on",
            "defaulted_on",
        ]

    def get_outstanding(self, obj) -> str:
        # `balance` is annotated by with_balance(): credits - debits, so owed = -balance.
        return f"{-obj.balance:.2f}"


class LoanRepaymentOutSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(source="transaction.reference", read_only=True)
    amount = serializers.DecimalField(source="transaction.amount", read_only=True, **MONEY)
    value_date = serializers.DateField(source="transaction.value_date", read_only=True)
    status = serializers.CharField(source="transaction.status", read_only=True)
    description = serializers.CharField(source="transaction.description", read_only=True)

    class Meta:
        model = LoanRepayment
        fields = ["id", "reference", "amount", "value_date", "status", "description",
                  "principal_component", "interest_component", "penalty_component"]


class RepaymentInSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**POSITIVE)
    value_date = serializers.DateField(required=False)
    period = PeriodField(required=False, allow_null=True)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    external_reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class MarkDefaultSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000)
