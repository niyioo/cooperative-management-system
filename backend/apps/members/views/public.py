"""/api/v1/public/ — the online membership form (BR-39), open to anyone, rate-limited per IP."""
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.configuration.models import CooperativeSettings, Department

from .. import services
from ..serializers import MembershipApplicationSerializer


class PublicDepartmentsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: inline_serializer("PublicDepartments", {
        "society": serializers.CharField(), "departments": serializers.ListField(child=serializers.DictField())})})
    def get(self, request):
        departments = Department.objects.filter(is_active=True).order_by("name").values("id", "name")
        return Response({"society": CooperativeSettings.load().name,
                         "departments": [{"id": str(d["id"]), "name": d["name"]} for d in departments]})


class MembershipApplicationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "membership_application"

    @extend_schema(request=MembershipApplicationSerializer, responses={201: inline_serializer("ApplicationReceived", {
        "reference": serializers.CharField(), "full_name": serializers.CharField()})})
    def post(self, request):
        serializer = MembershipApplicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        if data.pop("website", ""):  # a hidden field people never see; bots fill it in
            return Response({"reference": "", "full_name": ""}, status=status.HTTP_201_CREATED)
        data.pop("certify")
        email = data.pop("email", "")
        next_of_kin = data.pop("next_of_kin")
        member = services.apply_for_membership(profile=data, email=email, next_of_kin=next_of_kin)
        return Response({"reference": member.membership_number, "full_name": member.full_name}, status=status.HTTP_201_CREATED)
