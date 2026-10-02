"""
/api/v1/auth/ — sign-in, session refresh, sign-out and password management.

The access token is returned in the response body (keep it in memory only).
The refresh token is set as an httpOnly cookie scoped to /api/v1/auth/, so
page scripts can never read it. Refresh and logout also require the header
`X-Requested-With: XMLHttpRequest`: browsers only send custom headers
cross-origin after a CORS preflight, which only allowed origins pass. That
blocks cross-site request forgery against the cookie.
"""
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from apps.common.exceptions import envelope

from .. import services
from ..serializers import (
    CurrentUserSerializer,
    LoginSerializer,
    MessageSerializer,
    TokenResponseSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    TokenPasswordSerializer,
    user_payload,
)
from ..throttles import LoginIPRateThrottle, LoginRateThrottle, PasswordResetRateThrottle
from ..tokens import clear_refresh_cookie, issue_tokens, set_refresh_cookie


def token_response(user, status_code=status.HTTP_200_OK):
    access, refresh, lifetime = issue_tokens(user)
    response = Response(
        {"access": access, "access_expires_in": lifetime, "user": user_payload(user)},
        status=status_code,
    )
    set_refresh_cookie(response, refresh)
    response["Cache-Control"] = "no-store"
    return response


def require_xhr_header(request):
    if request.META.get("HTTP_X_REQUESTED_WITH") != "XMLHttpRequest":
        raise PermissionDenied("The X-Requested-With header is required.", code="csrf_header_missing")


class PublicAPIView(APIView):
    """No authentication attempted, so a stale Authorization header can't block these endpoints."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get_authenticate_header(self, request):
        # Without an authenticator DRF would downgrade 401 responses to 403.
        return 'Bearer realm="api"'


class LoginView(PublicAPIView):
    throttle_classes = (LoginRateThrottle, LoginIPRateThrottle)

    @extend_schema(request=LoginSerializer, responses={200: TokenResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.authenticate_for_portal(request, **serializer.validated_data)
        return token_response(user)


class TokenRefreshView(PublicAPIView):
    @extend_schema(request=None, responses={200: TokenResponseSerializer})
    def post(self, request):
        require_xhr_header(request)
        raw = request.COOKIES.get(settings.REFRESH_COOKIE["NAME"])
        try:
            if not raw:
                raise AuthenticationFailed(code="session_expired")
            user = services.consume_refresh_token(raw)
        except (TokenError, AuthenticationFailed):
            response = Response(
                envelope("session_expired", "Your session has ended. Please sign in again."),
                status=status.HTTP_401_UNAUTHORIZED,
            )
            clear_refresh_cookie(response)
            return response
        return token_response(user)


class LogoutView(PublicAPIView):
    @extend_schema(request=None, responses={204: OpenApiResponse(description="Signed out")})
    def post(self, request):
        require_xhr_header(request)
        services.end_session(request.COOKIES.get(settings.REFRESH_COOKIE["NAME"]))
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response


class MeView(APIView):
    """Available even while a password change is pending, so the SPA can route the user."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: CurrentUserSerializer})
    def get(self, request):
        return Response(user_payload(request.user))


class PasswordChangeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(request=PasswordChangeSerializer, responses={200: TokenResponseSerializer})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.change_password(request.user, **serializer.validated_data)
        # Changing the password revoked every existing token; hand back a fresh session.
        return token_response(request.user)


class PasswordResetRequestView(PublicAPIView):
    throttle_classes = (PasswordResetRateThrottle,)

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: MessageSerializer})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["email"])
        return Response(
            {"message": "If an account exists for that email address, we have sent instructions to it."},
            status=status.HTTP_202_ACCEPTED,
        )


class PasswordResetConfirmView(PublicAPIView):
    throttle_classes = (PasswordResetRateThrottle,)

    @extend_schema(request=TokenPasswordSerializer, responses={200: MessageSerializer})
    def post(self, request):
        serializer = TokenPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reset_password(**serializer.validated_data)
        return Response({"message": "Your password has been reset. You can now sign in."})


class ActivateAccountView(PublicAPIView):
    throttle_classes = (PasswordResetRateThrottle,)

    @extend_schema(request=TokenPasswordSerializer, responses={200: MessageSerializer})
    def post(self, request):
        serializer = TokenPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.activate_account(**serializer.validated_data)
        return Response({"message": "Your account is active. You can now sign in."})
