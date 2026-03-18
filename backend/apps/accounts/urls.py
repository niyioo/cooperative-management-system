from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView, 
    RegisterView, 
    UserProfileView,
    MemberSummaryView  # Added the Dashboard Engine view
)

urlpatterns = [
    # --- Authentication Endpoints ---
    # React uses: axiosInstance.post('/accounts/login/', ...)
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    
    # SimpleJWT refresh endpoint
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # React uses: axiosInstance.post('/accounts/register/', ...)
    path('register/', RegisterView.as_view(), name='auth_register'),

    # --- User & Dashboard Data ---
    # Returns base CustomUser data (email, role)
    path('me/', UserProfileView.as_view(), name='auth_me'),
    
    # The Member Dashboard endpoint
    # React uses: axiosInstance.get('/accounts/my-summary/')
    path('my-summary/', MemberSummaryView.as_view(), name='my-summary'),
]