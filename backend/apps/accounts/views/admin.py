"""/api/v1/admin/ — officer accounts, roles and the permission catalogue."""
import django_filters
from django.contrib.auth.models import Permission
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import services
from ..models import Role, User
from ..permissions import AnyPerm, OfficerAPIMixin
from ..perms import PERMISSION_APPS, P
from ..serializers import (
    OfficerCreateSerializer,
    OfficerRolesSerializer,
    OfficerSerializer,
    OfficerUpdateSerializer,
    PermissionModuleSerializer,
    RevokeSerializer,
    RoleSerializer,
    RoleWriteSerializer,
    TemporaryPasswordSerializer,
    permission_catalogue,
)


class OfficerFilter(django_filters.FilterSet):
    role = django_filters.NumberFilter(field_name="groups__id")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = User
        fields = ["role", "is_active"]


class OfficerViewSet(
    OfficerAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OfficerSerializer
    filterset_class = OfficerFilter
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["last_name", "email", "last_login", "date_joined"]
    permission_map = {"*": (P.MANAGE_OFFICERS,)}

    def get_queryset(self):
        return (
            User.objects.filter(Q(is_staff_officer=True) | Q(is_superuser=True))
            .select_related("member")
            .prefetch_related("groups")
            .order_by("last_name", "first_name")
            .distinct()
        )

    @extend_schema(request=OfficerCreateSerializer, responses={201: OfficerSerializer})
    def create(self, request):
        serializer = OfficerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, created = services.grant_officer_access(request.user, **serializer.validated_data)
        data = OfficerSerializer(user).data
        data["account_created"] = created
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(request=OfficerUpdateSerializer, responses={200: OfficerSerializer})
    def partial_update(self, request, pk=None):
        officer = self.get_object()
        serializer = OfficerUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_officer_profile(request.user, officer, **serializer.validated_data)
        return Response(OfficerSerializer(officer).data)

    @extend_schema(request=OfficerRolesSerializer, responses={200: OfficerSerializer})
    @action(detail=True, methods=["put"])
    def roles(self, request, pk=None):
        officer = self.get_object()
        serializer = OfficerRolesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_officer_roles(request.user, officer, serializer.validated_data["roles"])
        return Response(OfficerSerializer(officer).data)

    @extend_schema(request=RevokeSerializer, responses={204: OpenApiResponse(description="Officer access revoked")})
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        officer = self.get_object()
        serializer = RevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.revoke_officer_access(request.user, officer, **serializer.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={202: OpenApiResponse(description="Activation email sent")})
    @action(detail=True, methods=["post"], url_path="send-activation")
    def send_activation(self, request, pk=None):
        services.resend_activation(request.user, self.get_object(), permission=P.MANAGE_OFFICERS)
        return Response({"message": "Activation email sent."}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(request=None, responses={200: TemporaryPasswordSerializer})
    @action(detail=True, methods=["post"], url_path="temporary-password")
    def temporary_password(self, request, pk=None):
        password = services.issue_temporary_password(request.user, self.get_object(), permission=P.MANAGE_OFFICERS)
        response = Response(
            {
                "temporary_password": password,
                "message": "Give this password to the officer privately. They must change it when they sign in. It will not be shown again.",
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class RoleViewSet(OfficerAPIMixin, viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    search_fields = ["name"]
    permission_map = {
        # Officer managers need to see roles in order to assign them.
        "list": AnyPerm(P.MANAGE_ROLES, P.MANAGE_OFFICERS),
        "retrieve": AnyPerm(P.MANAGE_ROLES, P.MANAGE_OFFICERS),
        "create": (P.MANAGE_ROLES,),
        "partial_update": (P.MANAGE_ROLES,),
        "destroy": (P.MANAGE_ROLES,),
    }

    def get_queryset(self):
        return (
            Role.objects.select_related("profile")
            .prefetch_related("permissions__content_type")
            .annotate(officer_count=Count("user", filter=Q(user__is_staff_officer=True, user__is_active=True)))
            .order_by("name")
        )

    def _read(self, role):
        return RoleSerializer(self.get_queryset().get(pk=role.pk)).data

    @extend_schema(request=RoleWriteSerializer, responses={201: RoleSerializer})
    def create(self, request):
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.create_role(request.user, **serializer.validated_data)
        return Response(self._read(role), status=status.HTTP_201_CREATED)

    @extend_schema(request=RoleWriteSerializer, responses={200: RoleSerializer})
    def partial_update(self, request, pk=None):
        role = self.get_object()
        serializer = RoleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_role(request.user, role, **serializer.validated_data)
        return Response(self._read(role))

    def destroy(self, request, pk=None):
        services.delete_role(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class PermissionCatalogueView(OfficerAPIMixin, APIView):
    permission_map = {"get": AnyPerm(P.MANAGE_ROLES, P.MANAGE_OFFICERS)}

    @extend_schema(responses={200: PermissionModuleSerializer(many=True)})
    def get(self, request):
        permissions = sorted(
            Permission.objects.filter(content_type__app_label__in=PERMISSION_APPS).select_related("content_type"),
            key=lambda p: (PERMISSION_APPS.index(p.content_type.app_label), p.name),
        )
        return Response(permission_catalogue(permissions))
