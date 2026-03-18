from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Contribution
from .serializers import ContributionSerializer
from apps.accounts.permissions import IsManagerOrAdmin # Adjust path as needed

class ContributionViewSet(viewsets.ModelViewSet):
    serializer_class = ContributionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Optimize queries
        queryset = Contribution.objects.select_related('member').all().order_by('-created_at')
        
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return queryset
        return queryset.filter(member__user=user)

    def perform_create(self, serializer):
        # The React modal sends status='PENDING' by default
        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def mark_paid(self, request, pk=None):
        """Allows Admins to mark a due/fine as paid."""
        contribution = self.get_object()
        
        if contribution.status == Contribution.StatusChoices.PAID:
            return Response({"detail": "This assessment is already marked as paid."}, status=status.HTTP_400_BAD_REQUEST)

        contribution.status = Contribution.StatusChoices.PAID
        contribution.received_by = request.user
        contribution.date_paid = timezone.now().date()
        contribution.save()

        # NOTE: Once you build your `finance` global ledger app, 
        # you would inject a ledger entry here as Income!

        return Response({"status": "Assessment marked as paid successfully."})