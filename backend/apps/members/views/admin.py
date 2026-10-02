"""/api/v1/admin/members/ — member register, profiles, documents and imports."""
from pathlib import Path

import django_filters
from django.db.models import Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.accounts.permissions import OfficerAPIMixin
from apps.accounts.perms import P
from apps.accounts.serializers import TemporaryPasswordSerializer
from apps.audit.services import record
from apps.common.serializers import money_to_str
from apps.ledger.selectors import member_transactions
from apps.ledger.serializers import TransactionSerializer
from apps.common.parsers import UPLOAD_PARSERS

from .. import importer, services
from ..models import Member, MemberDocument, MemberImport, NextOfKin
from ..selectors import financial_summary
from ..serializers import (
    ImportCommitSerializer,
    ImportUploadSerializer,
    MemberCreateSerializer,
    MemberDetailSerializer,
    MemberDocumentSerializer,
    MemberImportSerializer,
    MemberListSerializer,
    MemberProfileSerializer,
    NextOfKinSerializer,
    PhotoSerializer,
    StatusActionSerializer,
)

UUID_RE = r"[0-9a-fA-F-]{36}"


class MemberFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=Member.Status.choices)
    department = django_filters.UUIDFilter(field_name="department_id")
    employment_status = django_filters.ChoiceFilter(choices=Member.EmploymentStatus.choices)
    gender = django_filters.ChoiceFilter(choices=Member.Gender.choices)
    joined_from = django_filters.DateFilter(field_name="date_joined", lookup_expr="gte")
    joined_to = django_filters.DateFilter(field_name="date_joined", lookup_expr="lte")

    class Meta:
        model = Member
        fields = ["status", "department", "employment_status", "gender"]


class TransactionFilter(django_filters.FilterSet):
    txn_type = django_filters.CharFilter()
    status = django_filters.CharFilter()
    date_from = django_filters.DateFilter(field_name="value_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="value_date", lookup_expr="lte")


def _status_action(name, description):
    """Build one POST /members/{id}/<name>/ status action (activate, suspend, …)."""

    def handler(self, request, pk=None):
        serializer = StatusActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.change_member_status(request.user, self.get_object(), name, **serializer.validated_data)
        return Response(MemberDetailSerializer(member).data)

    # DRF maps HTTP methods to the function's name when @action is applied, so rename first.
    handler.__name__ = name
    handler = action(detail=True, methods=["post"], url_path=name, url_name=name)(handler)
    return extend_schema(request=StatusActionSerializer, responses={200: MemberDetailSerializer}, summary=description)(handler)


class MemberViewSet(OfficerAPIMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    lookup_value_regex = UUID_RE
    filterset_class = MemberFilter
    search_fields = [
        "membership_number",
        "first_name",
        "middle_name",
        "last_name",
        "phone",
        "staff_number",
        "ippis_number",
        "user__email",
    ]
    ordering_fields = ["last_name", "membership_number", "date_joined", "created_at"]
    ordering = ["last_name", "first_name"]
    permission_map = {
        "list": (P.VIEW_MEMBER,),
        "retrieve": (P.VIEW_MEMBER,),
        "create": (P.ADD_MEMBER,),
        "partial_update": (P.CHANGE_MEMBER,),
        "activate": (P.CHANGE_MEMBER_STATUS,),
        "suspend": (P.CHANGE_MEMBER_STATUS,),
        "reinstate": (P.CHANGE_MEMBER_STATUS,),
        "deactivate": (P.CHANGE_MEMBER_STATUS,),
        "reactivate": (P.CHANGE_MEMBER_STATUS,),
        "financial_summary": (P.VIEW_MEMBER,),
        "transactions": (P.VIEW_MEMBER, P.VIEW_ALL_TRANSACTIONS),
        "documents:get": (P.VIEW_MEMBER,),
        "documents:post": (P.MANAGE_MEMBER_DOCUMENTS,),
        "document_download": (P.VIEW_MEMBER,),
        "document_verify": (P.MANAGE_MEMBER_DOCUMENTS,),
        "document_remove": (P.MANAGE_MEMBER_DOCUMENTS,),
        "photo:get": (P.VIEW_MEMBER,),
        "photo:put": (P.CHANGE_MEMBER,),
        "next_of_kin:get": (P.VIEW_MEMBER,),
        "next_of_kin:post": (P.CHANGE_MEMBER,),
        "next_of_kin_detail": (P.CHANGE_MEMBER,),
        "send_activation": (P.CHANGE_MEMBER,),
        "temporary_password": (P.CHANGE_MEMBER,),
    }

    def get_queryset(self):
        return Member.objects.select_related("user", "department", "created_by")

    def get_serializer_class(self):
        return MemberListSerializer if self.action == "list" else MemberDetailSerializer

    @extend_schema(request=MemberCreateSerializer, responses={201: MemberDetailSerializer})
    def create(self, request):
        serializer = MemberCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        member = services.register_member(
            request.user,
            email=data.pop("email", ""),
            membership_number=data.pop("membership_number", ""),
            status=data.pop("status"),
            send_activation=data.pop("send_activation"),
            next_of_kin=data.pop("next_of_kin", None),
            profile=data,
        )
        return Response(MemberDetailSerializer(member).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=MemberProfileSerializer, responses={200: MemberDetailSerializer})
    def partial_update(self, request, pk=None):
        member = self.get_object()
        serializer = MemberProfileSerializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        member = services.update_member(request.user, member, **serializer.validated_data)
        return Response(MemberDetailSerializer(member).data)

    activate = _status_action("activate", "Activate a pending member")
    suspend = _status_action("suspend", "Suspend an active member (reason required)")
    reinstate = _status_action("reinstate", "Reinstate a suspended member")
    deactivate = _status_action("deactivate", "Deactivate a member (reason required)")
    reactivate = _status_action("reactivate", "Reactivate an inactive member")

    # -- financial views ----------------------------------------------------

    @extend_schema(responses={200: OpenApiResponse(description="Savings, loans, investments and dividends the viewer may see")})
    @action(detail=True, methods=["get"], url_path="financial-summary")
    def financial_summary(self, request, pk=None):
        return Response(money_to_str(financial_summary(self.get_object(), request.user)))

    @extend_schema(responses={200: TransactionSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):
        queryset = TransactionFilter(request.query_params, queryset=member_transactions(self.get_object())).qs
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(reference__icontains=search) | Q(description__icontains=search))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(TransactionSerializer(page, many=True).data)

    # -- documents ----------------------------------------------------------

    def _document(self, member, document_id):
        return get_object_or_404(MemberDocument, pk=document_id, member=member)

    @extend_schema(methods=["get"], responses={200: MemberDocumentSerializer(many=True)})
    @extend_schema(methods=["post"], request=MemberDocumentSerializer, responses={201: MemberDocumentSerializer})
    @action(detail=True, methods=["get", "post"], pagination_class=None, filter_backends=[], parser_classes=UPLOAD_PARSERS)
    def documents(self, request, pk=None):
        member = self.get_object()
        if request.method == "GET":
            docs = member.documents.select_related("uploaded_by", "verified_by")
            return Response(MemberDocumentSerializer(docs, many=True).data)
        serializer = MemberDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = services.upload_document(request.user, member, **serializer.validated_data)
        return Response(MemberDocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiResponse(description="The file")})
    @action(detail=True, methods=["get"], url_path=rf"documents/(?P<document_id>{UUID_RE})/download")
    def document_download(self, request, pk=None, document_id=None):
        member = self.get_object()
        document = self._document(member, document_id)
        record(
            "member.document_downloaded",
            actor=request.user,
            obj=member,
            metadata={"document_id": str(document.pk), "document_type": document.document_type},
        )
        ext = Path(document.file.name).suffix
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=f"{member.membership_number.replace('/', '-')}-{document.document_type.lower()}{ext}",
        )

    @extend_schema(request=None, responses={200: MemberDocumentSerializer})
    @action(detail=True, methods=["post"], url_path=rf"documents/(?P<document_id>{UUID_RE})/verify")
    def document_verify(self, request, pk=None, document_id=None):
        document = services.verify_document(request.user, self._document(self.get_object(), document_id))
        return Response(MemberDocumentSerializer(document).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=rf"documents/(?P<document_id>{UUID_RE})")
    def document_remove(self, request, pk=None, document_id=None):
        services.remove_document(request.user, self._document(self.get_object(), document_id))
        return Response(status=status.HTTP_204_NO_CONTENT)

    # -- photo --------------------------------------------------------------

    @extend_schema(methods=["put"], request=PhotoSerializer, responses={200: MemberDetailSerializer})
    @extend_schema(methods=["get"], responses={(200, "image/*"): OpenApiResponse(description="The photo")})
    @action(detail=True, methods=["get", "put"], parser_classes=UPLOAD_PARSERS)
    def photo(self, request, pk=None):
        member = self.get_object()
        if request.method == "GET":
            if not member.photo:
                raise NotFound("This member has no photo.")
            response = FileResponse(member.photo.open("rb"))
            response["Cache-Control"] = "private, max-age=300"
            return response
        serializer = PhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.set_member_photo(request.user, member, serializer.validated_data["photo"])
        return Response(MemberDetailSerializer(member).data)

    # -- next of kin --------------------------------------------------------

    @extend_schema(methods=["get"], responses={200: NextOfKinSerializer(many=True)})
    @extend_schema(methods=["post"], request=NextOfKinSerializer, responses={201: NextOfKinSerializer})
    @action(detail=True, methods=["get", "post"], url_path="next-of-kin", pagination_class=None, filter_backends=[])
    def next_of_kin(self, request, pk=None):
        member = self.get_object()
        if request.method == "GET":
            return Response(NextOfKinSerializer(member.next_of_kin.all(), many=True).data)
        serializer = NextOfKinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kin = services.add_next_of_kin(request.user, member, **serializer.validated_data)
        return Response(NextOfKinSerializer(kin).data, status=status.HTTP_201_CREATED)

    @extend_schema(methods=["patch"], request=NextOfKinSerializer, responses={200: NextOfKinSerializer})
    @extend_schema(methods=["delete"], responses={204: None})
    @action(detail=True, methods=["patch", "delete"], url_path=rf"next-of-kin/(?P<kin_id>{UUID_RE})")
    def next_of_kin_detail(self, request, pk=None, kin_id=None):
        kin = get_object_or_404(NextOfKin, pk=kin_id, member=self.get_object())
        if request.method == "DELETE":
            services.remove_next_of_kin(request.user, kin)
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = NextOfKinSerializer(kin, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        kin = services.update_next_of_kin(request.user, kin, **serializer.validated_data)
        return Response(NextOfKinSerializer(kin).data)

    # -- portal account -----------------------------------------------------

    @extend_schema(request=None, responses={202: OpenApiResponse(description="Activation email sent")})
    @action(detail=True, methods=["post"], url_path="send-activation")
    def send_activation(self, request, pk=None):
        services.send_member_activation(request.user, self.get_object())
        return Response({"message": "Activation email sent."}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(request=None, responses={200: TemporaryPasswordSerializer})
    @action(detail=True, methods=["post"], url_path="temporary-password")
    def temporary_password(self, request, pk=None):
        password = services.issue_member_temporary_password(request.user, self.get_object())
        response = Response(
            {
                "temporary_password": password,
                "message": "Give this password to the member privately. They must change it when they sign in. It will not be shown again.",
            }
        )
        response["Cache-Control"] = "no-store"
        return response


class MemberImportViewSet(
    OfficerAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    parser_classes = UPLOAD_PARSERS  # create receives a file
    serializer_class = MemberImportSerializer
    lookup_value_regex = UUID_RE
    permission_map = {"*": (P.IMPORT_MEMBERS,)}

    def get_queryset(self):
        return MemberImport.objects.select_related("created_by", "committed_by")

    @extend_schema(request={"multipart/form-data": ImportUploadSerializer}, responses={201: MemberImportSerializer})
    def create(self, request):
        serializer = ImportUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member_import = services.create_import(request.user, serializer.validated_data["file"])
        return Response(MemberImportSerializer(member_import).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ImportCommitSerializer, responses={200: MemberImportSerializer})
    @action(detail=True, methods=["post"])
    def commit(self, request, pk=None):
        serializer = ImportCommitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member_import = services.commit_import(request.user, self.get_object(), **serializer.validated_data)
        return Response(MemberImportSerializer(member_import).data)

    @extend_schema(
        responses={
            (200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiResponse(
                description="Excel template"
            )
        }
    )
    @action(detail=False, methods=["get"])
    def template(self, request):
        response = HttpResponse(
            importer.build_template(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="emdi-member-import-template.xlsx"'
        return response
