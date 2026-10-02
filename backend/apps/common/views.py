from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Liveness/readiness probe for load balancers. Reveals nothing sensitive."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses=inline_serializer("HealthCheck", {"status": serializers.CharField()}))
    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok"})
