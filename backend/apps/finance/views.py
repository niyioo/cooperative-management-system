from rest_framework import viewsets
from .models import Income, Expense
from .serializers import IncomeSerializer, ExpenseSerializer
from apps.accounts.permissions import IsManagerOrAdmin

class IncomeViewSet(viewsets.ModelViewSet):
    queryset = Income.objects.all().order_by('-date_received')
    serializer_class = IncomeSerializer
    permission_classes = [IsManagerOrAdmin]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)

class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().order_by('-date_incurred')
    serializer_class = ExpenseSerializer
    permission_classes = [IsManagerOrAdmin]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)