from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import Member, NextOfKin, MemberDocument
from .serializers import MemberSerializer, NextOfKinSerializer, MemberDocumentSerializer
from apps.accounts.permissions import STAFF, IsManagerOrAdmin, IsOwnerOrManager, IsStaff

User = get_user_model()

class MemberViewSet(viewsets.ModelViewSet):
    """
    Members are never deleted (their savings, loans and history must remain);
    they are suspended or made inactive with update_status instead.
    Public sign-up is /auth/register/; this endpoint is for managers registering members.
    """
    serializer_class = MemberSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ['create', 'update_status', 'approve']:
            return [IsManagerOrAdmin()]
        if self.action == 'list':
            return [IsStaff()]
        return [permissions.IsAuthenticated(), IsOwnerOrManager()]

    def get_queryset(self):
        user = self.request.user
        queryset = Member.objects.select_related('user', 'approved_by')\
                                 .prefetch_related('next_of_kin', 'documents').order_by('last_name', 'first_name')
        if user.is_authenticated and user.role in STAFF:
            return queryset
        return queryset.filter(user=user)

    def create(self, request, *args, **kwargs):
        """A manager registers a member: user account and profile together, approved by them."""
        email = (request.data.get('email') or '').strip()
        password = request.data.get('password') or ''
        if not email:
            return Response({"email": ["Enter an email address."]}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=email).exists():
            return Response({"email": ["A user with this email already exists."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password, user=User(email=email))
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User.objects.create_user(
                email=email, password=password, role=User.Role.MEMBER,
                first_name=request.data.get('first_name', ''), last_name=request.data.get('last_name', ''),
            )
            # The profile is created automatically with the user; fill it in.
            member = Member.objects.get(user=user)
            serializer = self.get_serializer(member, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(user=user, status=Member.Status.ACTIVE, approved_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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