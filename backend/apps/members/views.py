from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import Member, NextOfKin, MemberDocument
from .serializers import MemberSerializer, NextOfKinSerializer, MemberDocumentSerializer
from apps.accounts.permissions import IsManagerOrAdmin, IsOwnerOrManager

User = get_user_model()

class MemberViewSet(viewsets.ModelViewSet):
    serializer_class = MemberSerializer
    
    def get_permissions(self):
        # Allow anyone (even unauthenticated) to POST to the create/register endpoint
        if self.action == 'create':
            return [permissions.AllowAny()]
        if self.action in ['list', 'update_status', 'approve']:
            return [IsManagerOrAdmin()]
        return [permissions.IsAuthenticated(), IsOwnerOrManager()]

    def get_queryset(self):
        user = self.request.user
        queryset = Member.objects.select_related('user', 'approved_by')\
                                 .prefetch_related('next_of_kin', 'documents')
        
        if user.is_authenticated and user.role in ['SUPER_ADMIN', 'MANAGER', 'ACCOUNTANT']:
            return queryset.all()
        
        return queryset.filter(user=user)

    def create(self, request, *args, **kwargs):
        """
        Custom create logic to handle both User and Member profile creation.
        Matches the RegisterModal.jsx payload.
        """
        email = request.data.get('email')
        password = request.data.get('password')
        
        # 1. Check if user already exists (Safety check)
        if User.objects.filter(email=email).exists():
            return Response(
                {"detail": "A user with this email already exists."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                # 2. Create the User
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=request.data.get('first_name', ''),
                    last_name=request.data.get('last_name', ''),
                    role='MEMBER'
                )

                # 3. Handle Member Profile (Prevent duplicate key error from Django signals)
                member, created = Member.objects.get_or_create(user=user)
                
                serializer = self.get_serializer(member, data=request.data)
                serializer.is_valid(raise_exception=True)
                serializer.save(user=user)
                
                return Response(serializer.data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def approve(self, request, pk=None):
        member = self.get_object()
        member.status = Member.Status.ACTIVE
        member.approved_by = request.user
        member.save()
        return Response({'status': 'Member approved successfully'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsManagerOrAdmin])
    def update_status(self, request, pk=None):
        member = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in Member.Status.values:
            return Response(
                {"detail": f"Invalid status. Choose from {Member.Status.values}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        member.status = new_status
        if new_status == Member.Status.ACTIVE:
            member.approved_by = request.user
            
        member.save()
        return Response({'status': 'success', 'message': f'Member status updated to {new_status}'})

# --- Keep NextOfKin and Document ViewSets as they were ---
class NextOfKinViewSet(viewsets.ModelViewSet):
    serializer_class = NextOfKinSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUPER_ADMIN', 'MANAGER']:
            return NextOfKin.objects.all()
        return NextOfKin.objects.filter(member__user=user)

    def perform_create(self, serializer):
        member = get_object_or_404(Member, user=self.request.user)
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
        member = get_object_or_404(Member, user=self.request.user)
        serializer.save(member=member)