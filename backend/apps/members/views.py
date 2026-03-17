from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Member, NextOfKin, MemberDocument
from .serializers import MemberSerializer, NextOfKinSerializer, MemberDocumentSerializer
from apps.accounts.permissions import IsManagerOrAdmin

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Members only see their own profile, Admins see all
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return Member.objects.all()
        return Member.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        member = self.get_object()
        member.status = Member.Status.ACTIVE
        member.approved_by = request.user
        member.save()
        return Response({'status': 'Member approved successfully'})

class NextOfKinViewSet(viewsets.ModelViewSet):
    serializer_class = NextOfKinSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER']:
            return NextOfKin.objects.all()
        return NextOfKin.objects.filter(member__user=user)

    def perform_create(self, serializer):
        member = Member.objects.get(user=self.request.user)
        serializer.save(member=member)

class MemberDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = MemberDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER']:
            return MemberDocument.objects.all()
        return MemberDocument.objects.filter(member__user=user)

    def perform_create(self, serializer):
        member = Member.objects.get(user=self.request.user)
        serializer.save(member=member)