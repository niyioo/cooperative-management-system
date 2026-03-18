from rest_framework import serializers
from .models import LoanProduct, Loan, LoanGuarantor, LoanRepayment
from apps.members.models import Member

class NestedMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'first_name', 'last_name', 'membership_id']

class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = '__all__'

class LoanGuarantorSerializer(serializers.ModelSerializer):
    # Added full name for better UI display
    guarantor_name = serializers.SerializerMethodField()

    class Meta:
        model = LoanGuarantor
        fields = ['id', 'guarantor_member', 'guarantor_name', 'amount_guaranteed', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']

    def get_guarantor_name(self, obj):
        return f"{obj.guarantor_member.first_name} {obj.guarantor_member.last_name}"

class LoanRepaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRepayment
        fields = '__all__'
        read_only_fields = ['id', 'payment_date', 'received_by', 'created_at']

class LoanSerializer(serializers.ModelSerializer):
    # For GET requests (React Table displays)
    member = NestedMemberSerializer(read_only=True)
    product = LoanProductSerializer(source='loan_product', read_only=True)
    
    # Matches the 'balance' key used in React state
    balance = serializers.DecimalField(source='balance_remaining', max_digits=15, decimal_places=2, read_only=True)
    
    # For POST requests (React Form Submission)
    member_id = serializers.PrimaryKeyRelatedField(
        queryset=Member.objects.all(), source='member', write_only=True
    )
    loan_product_id = serializers.PrimaryKeyRelatedField(
        queryset=LoanProduct.objects.all(), source='loan_product', write_only=True
    )

    guarantors = LoanGuarantorSerializer(many=True, read_only=True)
    repayments = LoanRepaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Loan
        fields = [
            'id', 'loan_id', 'member', 'member_id', 'product', 'loan_product_id', 
            'principal_amount', 'duration_months', 'purpose', 'interest_amount', 
            'total_payable', 'balance', 'status', 'application_date', 
            'disbursed_at', 'guarantors', 'repayments'
        ]
        read_only_fields = [
            'id', 'loan_id', 'interest_amount', 'total_payable', 
            'status', 'application_date', 'disbursed_at'
        ]