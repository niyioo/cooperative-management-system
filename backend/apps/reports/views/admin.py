"""/api/v1/admin/dashboard/ and /api/v1/admin/reports/"""
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.audit.services import record
from apps.common.serializers import money_to_str
from apps.configuration.models import Department
from apps.investments.models import InvestmentProduct
from apps.loans.models import LoanProduct
from apps.members.models import Member
from apps.savings.models import SavingsProduct

from .. import definitions  # noqa: F401  (registers the reports)
from ..dashboard import officer_dashboard
from ..engine import available_reports, get_report
from ..renderers import to_json, to_pdf, to_xlsx


class DashboardView(OfficerAPIMixin, APIView):
    permission_map = {"get": ()}  # any officer; sections follow the officer's permissions

    @extend_schema(responses={200: OpenApiResponse(description="KPIs, trends, pending approvals and recent activity")})
    def get(self, request):
        return Response(money_to_str(officer_dashboard(request.user)))


def _name(model, value, attr="name"):
    obj = model.objects.filter(pk=value).first()
    return getattr(obj, attr) if obj else str(value)


def _product_name(value):
    for model in (SavingsProduct, LoanProduct, InvestmentProduct):
        obj = model.objects.filter(pk=value).first()
        if obj:
            return obj.name
    return str(value)


LOOKUPS = {
    "member": lambda v: (lambda m: f"{m.full_name} ({m.membership_number})" if m else str(v))(Member.objects.filter(pk=v).first()),
    "department": lambda v: _name(Department, v),
    "product": _product_name,
}

FORMATS = {
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", to_xlsx),
    "pdf": ("application/pdf", to_pdf),
}


class ReportCatalogueView(OfficerAPIMixin, APIView):
    permission_map = {"get": (P.VIEW_REPORTS,)}

    @extend_schema(operation_id="admin_reports_list", responses={200: OpenApiResponse(description="The reports this officer may run, with their filters")})
    def get(self, request):
        return Response([r.describe(request.user) for r in available_reports(request.user)])


class ReportView(OfficerAPIMixin, APIView):
    """
    Run one report. ?format=json (default) returns the on-screen table;
    xlsx and pdf return a file and need export_reports. Exports are audited.
    """

    permission_map = {"get": (P.VIEW_REPORTS,)}

    @extend_schema(
        operation_id="admin_reports_run",
        parameters=[
            OpenApiParameter("format", str, enum=["json", "xlsx", "pdf"]),
            *[OpenApiParameter(name, OpenApiTypes.STR) for name in
              ("date_from", "date_to", "as_at", "member", "department", "product", "status", "txn_type", "year")],
        ],
        responses={200: OpenApiResponse(description="Report table (JSON) or file (xlsx/pdf)")},
    )
    def get(self, request, key):
        report = get_report(request.user, key)
        fmt = request.query_params.get("format", "json")
        if fmt != "json" and fmt not in FORMATS:
            raise ValidationError({"format": ["Use json, xlsx or pdf."]})
        if fmt != "json" and not request.user.has_perm(P.EXPORT_REPORTS):
            raise PermissionDenied("Your role can view reports but not export them.")
        result = report.run(request.query_params)
        applied = {k: str(v) for k, v in result.params.items()}

        if fmt == "json":
            if key == "member-statement":
                record("report.viewed", actor=request.user, metadata={"report": key, "filters": applied})
            return Response(to_json(result, LOOKUPS, request.user))

        content_type, render = FORMATS[fmt]
        response = HttpResponse(render(result, LOOKUPS, request.user), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{key}-{timezone.localdate():%Y%m%d}.{fmt}"'
        response["Cache-Control"] = "no-store"
        record("report.exported", actor=request.user,
               metadata={"report": key, "format": fmt, "filters": applied, "rows": len(result.rows)})
        return response
