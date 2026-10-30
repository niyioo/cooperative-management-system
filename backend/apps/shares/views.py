from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import FINANCE_STAFF, IsFinanceStaff

from . import services
from .models import ShareAccount, ShareTransaction
from .serializers import ShareAccountSerializer, ShareTransactionSerializer


class ShareAccountViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ShareAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ShareAccount.objects.select_related('member').order_by('member__last_name')
        if user.role in FINANCE_STAFF:
            return queryset
        return queryset.filter(member__user=user)


class ShareTransactionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                              viewsets.GenericViewSet):
    """Purchases at the price set in Settings; permanent once made."""

    serializer_class = ShareTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ShareTransaction.objects.select_related('account__member').order_by('-created_at')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())
        if user.role in FINANCE_STAFF:
            return queryset
        return queryset.filter(account__member__user=user)

    def perform_create(self, serializer):
        user = self.request.user
        data = serializer.validated_data
        if user.role in FINANCE_STAFF:
            member = data.get('member') or (data['account'].member if data.get('account') else None)
            if member is None:
                raise ValidationError({"member": "Choose the member buying the shares."})
        else:
            member = user.member_profile
        serializer.instance = services.purchase(member=member, number_of_shares=data['number_of_shares'], by=user)

    @action(detail=True, methods=['post'], permission_classes=[IsFinanceStaff])
    def approve(self, request, pk=None):
        return Response(ShareTransactionSerializer(services.approve(self.get_object(), by=request.user)).data)

    @action(detail=True, methods=['post'], permission_classes=[IsFinanceStaff])
    def reject(self, request, pk=None):
        return Response(ShareTransactionSerializer(services.reject(self.get_object(), by=request.user)).data)
