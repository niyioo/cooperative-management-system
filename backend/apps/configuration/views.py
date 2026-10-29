"""/api/v1/admin/departments/ and /api/v1/admin/settings/"""
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.ledger.choices import TransactionType

from . import services
from .models import CooperativeSettings, Department


class DepartmentSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Department
        fields = ["id", "name", "code", "is_active"]
        extra_kwargs = {"name": {"validators": []}}  # uniqueness checked case-insensitively in the service


class DepartmentViewSet(
    OfficerAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    search_fields = ["name", "code"]
    filterset_fields = ["is_active"]
    permission_map = {
        "list": (),  # any officer (needed for member forms and filters)
        "retrieve": (),
        "create": (P.MANAGE_SETTINGS,),
        "partial_update": (P.MANAGE_SETTINGS,),
    }

    @extend_schema(request=DepartmentSerializer, responses={201: DepartmentSerializer})
    def create(self, request):
        serializer = DepartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department = services.create_department(request.user, **serializer.validated_data)
        return Response(DepartmentSerializer(department).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=DepartmentSerializer, responses={200: DepartmentSerializer})
    def partial_update(self, request, pk=None):
        department = self.get_object()
        serializer = DepartmentSerializer(department, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        department = services.update_department(request.user, department, **serializer.validated_data)
        return Response(DepartmentSerializer(department).data)


class CooperativeSettingsSerializer(serializers.ModelSerializer):
    maker_checker_types = serializers.MultipleChoiceField(choices=TransactionType.choices, required=False)

    class Meta:
        model = CooperativeSettings
        fields = services.SETTINGS_FIELDS + ["updated_at"]
        read_only_fields = ["updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["maker_checker_types"] = sorted(instance.maker_checker_types)
        return data


class CooperativeSettingsView(OfficerAPIMixin, APIView):
    """Cooperative-wide settings. Any officer can read them; changing them needs manage_settings."""

    permission_map = {"get": (), "patch": (P.MANAGE_SETTINGS,)}

    @extend_schema(responses={200: CooperativeSettingsSerializer})
    def get(self, request):
        return Response(CooperativeSettingsSerializer(CooperativeSettings.load()).data)

    @extend_schema(request=CooperativeSettingsSerializer, responses={200: CooperativeSettingsSerializer})
    def patch(self, request):
        serializer = CooperativeSettingsSerializer(CooperativeSettings.load(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if "maker_checker_types" in data:
            data["maker_checker_types"] = sorted(data["maker_checker_types"])
        return Response(CooperativeSettingsSerializer(services.update_settings(request.user, **data)).data)
