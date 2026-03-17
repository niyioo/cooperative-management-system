from rest_framework import serializers
from .models import LoanProduct, Loan, LoanGuarantor, LoanRepayment

class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = '__all__'

class LoanGuarantorSerializer(serializers.ModelSerializer):
    guarantor_name = serializers.CharField(source='guarantor_member.first_name', read_only=True)

    class Meta:
        model = LoanGuarantor
        fields = '__all__'
        read_only_fields = ['id', 'status', 'created_at']

class LoanRepaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanRepayment
        fields = '__all__'
        read_only_fields = ['id', 'payment_date', 'received_by', 'created_at']

class LoanSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='loan_product.name', read_only=True)
    guarantors = LoanGuarantorSerializer(many=True, read_only=True)
    repayments = LoanRepaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Loan
        fields = [
            'id', 'member', 'loan_product', 'product_name', 'principal_amount', 'duration_months',
            'interest_amount', 'total_payable', 'balance_remaining', 'status', 
            'application_date', 'disbursed_at', 'guarantors', 'repayments'
        ]
        read_only_fields = [
            'id', 'interest_amount', 'total_payable', 'balance_remaining', 
            'status', 'application_date', 'disbursed_at'
        ]