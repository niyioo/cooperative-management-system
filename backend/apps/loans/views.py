from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import LOAN_STAFF, PAYMENT_STAFF, IsLoanOfficer, IsManagerOrAdmin, IsPaymentStaff

from . import services
from .models import Loan, LoanProduct, LoanRepayment
from .serializers import LoanProductSerializer, LoanRepaymentSerializer, LoanSerializer


class LoanProductViewSet(viewsets.ModelViewSet):
    queryset = LoanProduct.objects.order_by('name')
    serializer_class = LoanProductSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']  # retire with is_active, never delete

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update']:
            return [IsManagerOrAdmin()]
        return [permissions.IsAuthenticated()]


class LoanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  viewsets.GenericViewSet):
    """Applications are permanent once made; they move only through approve / reject / disburse."""

    serializer_class = LoanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = (Loan.objects.select_related('member', 'loan_product')
                    .prefetch_related('guarantors__guarantor_member', 'repayments').order_by('-created_at'))
        if user.role in PAYMENT_STAFF:
            return queryset
        return queryset.filter(member__user=user)

    def perform_create(self, serializer):
        user = self.request.user
        data = serializer.validated_data
        # Loan staff may apply on a member's behalf; everyone else applies for themselves.
        member = data.get('member') if user.role in LOAN_STAFF and data.get('member') else user.member_profile
        serializer.instance = services.apply(
            member=member, product=data['loan_product'], principal=data['principal_amount'],
            months=data['duration_months'], purpose=data.get('purpose') or "", by=user,
        )

    def _respond(self, loan):
        return Response(LoanSerializer(self.get_queryset().get(pk=loan.pk)).data)

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def approve(self, request, pk=None):
        return self._respond(services.approve(self.get_object(), by=request.user))

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def reject(self, request, pk=None):
        reason = (request.data.get('reason') or '').strip()
        return self._respond(services.reject(self.get_object(), by=request.user, reason=reason))

    @action(detail=True, methods=['post'], permission_classes=[IsLoanOfficer])
    def disburse(self, request, pk=None):
        return self._respond(services.disburse(self.get_object(), by=request.user))


class LoanRepaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                           viewsets.GenericViewSet):
    """Repayments are recorded by staff when money is received, and are never edited or deleted."""

    serializer_class = LoanRepaymentSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsPaymentStaff()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        queryset = LoanRepayment.objects.select_related('loan__member').order_by('-created_at')
        if user.role in PAYMENT_STAFF:
            return queryset
        return queryset.filter(loan__member__user=user)

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.repay(data['loan'], amount=data['amount_paid'], by=self.request.user)
