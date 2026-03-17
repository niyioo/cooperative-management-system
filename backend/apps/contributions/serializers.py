from rest_framework import serializers
from .models import ContributionType, ContributionRecord, Fine

class ContributionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributionType
        fields = '__all__'

class ContributionRecordSerializer(serializers.ModelSerializer):
    type_name = serializers.CharField(source='contribution_type.name', read_only=True)

    class Meta:
        model = ContributionRecord
        fields = '__all__'
        read_only_fields = ['id', 'payment_date', 'received_by', 'created_at']

class FineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fine
        fields = '__all__'
        read_only_fields = ['id', 'date_issued', 'date_paid', 'created_at']