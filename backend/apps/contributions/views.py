import uuid
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ContributionType, ContributionRecord, Fine
from .serializers import ContributionTypeSerializer, ContributionRecordSerializer, FineSerializer
from apps.accounts.permissions import IsManagerOrAdmin

class ContributionTypeViewSet(viewsets.ModelViewSet):
    queryset = ContributionType.objects.all()
    serializer_class = ContributionTypeSerializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsManagerOrAdmin()]
        return [permissions.IsAuthenticated()]

class ContributionRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ContributionRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return ContributionRecord.objects.all()
        return ContributionRecord.objects.filter(member__user=user)

    def perform_create(self, serializer):
        serializer.save(
            receipt_reference=f"CNTB-{uuid.uuid4().hex[:8].upper()}",
            received_by=self.request.user
        )

class FineViewSet(viewsets.ModelViewSet):
    serializer_class = FineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return Fine.objects.all()
        return Fine.objects.filter(member__user=user)

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def mark_paid(self, request, pk=None):
        fine = self.get_object()
        if fine.is_paid:
            return Response({"detail": "Fine is already paid."}, status=status.HTTP_400_BAD_REQUEST)
        
        fine.is_paid = True
        fine.date_paid = timezone.now().date()
        fine.save()
        return Response({"status": "Fine marked as paid."})