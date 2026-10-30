from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import FINANCE_STAFF, IsFinanceStaff

from . import services
from .models import Contribution
from .serializers import ContributionSerializer


class ContributionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                          viewsets.GenericViewSet):
    """Dues, levies and fines. Assessed by finance staff; permanent once made."""

    serializer_class = ContributionSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsFinanceStaff()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        queryset = Contribution.objects.select_related('member').order_by('-created_at')
        if user.role in FINANCE_STAFF:
            return queryset
        return queryset.filter(member__user=user)

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.assess(
            member=data['member'], type=data['type'], amount=data['amount'], due_date=data.get('due_date'),
            by=self.request.user,
        )

    @action(detail=True, methods=['post'], permission_classes=[IsFinanceStaff])
    def mark_paid(self, request, pk=None):
        contribution = services.mark_paid(self.get_object(), by=request.user)
        return Response(ContributionSerializer(contribution).data)
