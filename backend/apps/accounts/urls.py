from django.urls import path

from .views import (
    CookieTokenRefreshView,
    CustomTokenObtainPairView,
    LogoutView,
    MemberSummaryView,
    RegisterView,
    UserProfileView,
)

urlpatterns = [
    # Login returns {access}; the refresh token is an httpOnly cookie.
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('me/', UserProfileView.as_view(), name='auth_me'),
    path('my-summary/', MemberSummaryView.as_view(), name='my-summary'),
]
