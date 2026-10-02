from decimal import Decimal

from rest_framework import serializers

from apps.common.serializers import PeriodField, validate_model_field
from apps.common.spreadsheets import parse_period

from .batches import uploadable_types
from .choices import BatchType, EntrySide, TransactionType
from .models import Transaction, TransactionBatch


class TransactionSerializer(serializers.ModelSerializer):
    """Read-only ledger entry, as shown in member statements and officer views."""

    type_label = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    signed_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    account = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "reference",
            "value_date",
            "period",
            "txn_type",
            "type_label",
            "entry_side",
            "amount",
            "signed_amount",
            "description",
            "external_reference",
            "account",
            "status",
            "status_label",
            "created_at",
        ]
        read_only_fields = fields

    def get_type_label(self, obj) -> str:
        # Contributions to a cycle product read as e.g. "Christmas Savings contribution".
        if obj.txn_type == TransactionType.SAVINGS_CONTRIBUTION and obj.savings_account_id:
            return f"{obj.savings_account.product.name} contribution"
        return obj.get_txn_type_display()

    def get_account(self, obj) -> dict | None:
        if obj.savings_account_id:
            acct = obj.savings_account
            label = f"{acct.product.name} {acct.cycle.year}" if acct.cycle_id else acct.product.name
            return {"kind": "SAVINGS", "id": str(acct.pk), "number": acct.account_number, "label": label}
        if obj.loan_id:
            return {"kind": "LOAN", "id": str(obj.loan.pk), "number": obj.loan.reference, "label": "Loan"}
        if obj.investment_account_id:
            acct = obj.investment_account
            return {"kind": "INVESTMENT", "id": str(acct.pk), "number": acct.account_number, "label": acct.product.name}
        return None



class LedgerEntrySerializer(TransactionSerializer):
    """Officer view of an entry: adds the member and who created and approved it."""

    member = serializers.SerializerMethodField()
    created_by = serializers.CharField(source="created_by.full_name", default=None, read_only=True)
    approved_by = serializers.CharField(source="approved_by.full_name", default=None, read_only=True)
    batch_reference = serializers.CharField(source="batch.reference", default=None, read_only=True)

    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + [
            "member",
            "created_by",
            "approved_by",
            "approved_at",
            "posted_at",
            "batch_reference",
        ]
        read_only_fields = fields

    def get_member(self, obj) -> dict:
        return {"id": str(obj.member_id), "membership_number": obj.member.membership_number, "full_name": obj.member.full_name}


class BatchSerializer(serializers.ModelSerializer):
    batch_type_label = serializers.CharField(source="get_batch_type_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    created_by = serializers.CharField(source="created_by.full_name", read_only=True)
    approved_by = serializers.CharField(source="approved_by.full_name", default=None, read_only=True)
    period = serializers.SerializerMethodField()

    class Meta:
        model = TransactionBatch
        fields = [
            "id",
            "reference",
            "batch_type",
            "batch_type_label",
            "period",
            "description",
            "line_count",
            "total_amount",
            "status",
            "status_label",
            "validation_report",
            "rejection_reason",
            "created_by",
            "created_at",
            "submitted_at",
            "approved_by",
            "approved_at",
            "posted_at",
        ]

    def get_period(self, obj) -> str | None:
        return obj.period.strftime("%Y-%m") if obj.period else None


class BatchUploadSerializer(serializers.Serializer):
    batch_type = serializers.ChoiceField(choices=[])
    file = serializers.FileField()
    product = serializers.CharField(required=False, allow_blank=True, default="", help_text="Default savings product code, e.g. CHRISTMAS.")
    period = serializers.CharField(required=False, allow_blank=True, default="", help_text='Default month, e.g. "2026-03".')
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Batch types are registered by their modules at start-up.
        self.fields["batch_type"].choices = [(t, BatchType(t).label) for t in uploadable_types()]

    def validate_file(self, value):
        return validate_model_field(TransactionBatch, "source_file", value)

    def validate_period(self, value):
        try:
            return parse_period(value) if value else None
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class AdjustmentSerializer(serializers.Serializer):
    account_type = serializers.ChoiceField(choices=[("SAVINGS", "Savings"), ("INVESTMENT", "Investment")])
    account = serializers.UUIDField()
    entry_side = serializers.ChoiceField(choices=EntrySide.choices, help_text="CREDIT increases the balance; DEBIT reduces it.")
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal("0.01"))
    reason = serializers.CharField(max_length=255)
    value_date = serializers.DateField(required=False)
    period = PeriodField(required=False, allow_null=True)

    def validate(self, attrs):
        from apps.investments.models import InvestmentAccount
        from apps.savings.models import SavingsAccount

        model = SavingsAccount if attrs["account_type"] == "SAVINGS" else InvestmentAccount
        account = model.objects.select_related("member").filter(pk=attrs.pop("account")).first()
        if account is None:
            raise serializers.ValidationError({"account": ["Account not found."]})
        attrs.pop("account_type")
        attrs["account"] = account
        return attrs
