from django.urls import path

from ..views.member import DashboardView, PhotoView, ProfileView

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/photo/", PhotoView.as_view(), name="profile-photo"),
]
